"""Replay what a report attached, with no model: download the attachments of issue N, find a design/script,
run it on the official CLI, and print a verdict line the agent can use.

    python -X utf8 repro/replay.py N [--cli PATH] [--keep]

Prints: REPLAY #N <result> | file | detail. Results:
  FAILED          the CLI reported the error the reporter saw (compare the text with the report's error text)
  RAN_CLEAN       the saved design evaluates with no feature error. This does NOT prove the bug does not reproduce: the action the reporter tried next is usually not in the file
  NO_FILE         nothing runnable attached (zip without a .solidcraft/.json/.step, or no attachment)
  CANNOT_RUN      the CLI refused the file type, timed out, or the download failed

This never proves a GUI or hardware bug: those stay `could_not_test`. A FAILED/RAN_CLEAN result is still only "on the official
CLI at version X": say so in any comment. Downloaded files are untrusted data: they go in a fresh folder, are never executed,
and are only passed as arguments to the CLI.
"""
import argparse, glob, json, os, re, subprocess, sys, tempfile, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
CASES = os.path.join(os.environ.get("TRIAGE_STATE") or os.path.join(KIT, "state"), "cases")
DEFAULT_CLI = os.environ.get("SOLIDCRAFT_CLI")  # the official build's solidcraft-cli (see SOLO.md, "Setup")
RUNNABLE = (".solidcraft", ".json", ".step", ".stp")


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "triage-replay"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(60_000_001)
    if len(data) > 60_000_000:
        raise RuntimeError("attachment over 60 MB")
    open(dest, "wb").write(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int)
    ap.add_argument("--cli", default=DEFAULT_CLI)
    ap.add_argument("--keep", action="store_true", help="keep the download folder and print it")
    a = ap.parse_args()
    if not a.cli:
        sys.exit("set SOLIDCRAFT_CLI to the official build's solidcraft-cli, or pass --cli")
    case_path = os.path.join(CASES, f"{a.n}.json")
    if not os.path.exists(case_path):
        sys.exit(f"build the case first: triage.py case {a.n}")
    case = json.load(open(case_path, encoding="utf-8"))
    urls = [x["url"] for x in case.get("attachments", [])]
    work = tempfile.mkdtemp(prefix=f"replay-{a.n}-")
    files = []
    try:
        for i, u in enumerate(urls[:6]):
            name = re.sub(r"[^\w.\-]", "_", u.rsplit("/", 1)[-1])[:80] or f"att{i}"
            dest = os.path.join(work, f"{i}-{name}")
            fetch(u, dest)
            if zipfile.is_zipfile(dest):
                out = dest + "_x"
                with zipfile.ZipFile(dest) as z:
                    for m in z.namelist()[:200]:  # zip-slip safe: only members that stay inside `out`
                        t = os.path.realpath(os.path.join(out, m))
                        if t.startswith(os.path.realpath(out) + os.sep) and not m.endswith("/") and z.getinfo(m).file_size < 200_000_000:
                            os.makedirs(os.path.dirname(t), exist_ok=True)
                            open(t, "wb").write(z.read(m))
                files += [p for p in glob.glob(os.path.join(out, "**", "*"), recursive=True) if p.lower().endswith(RUNNABLE)]
            elif dest.lower().endswith(RUNNABLE):
                files.append(dest)
    except Exception as e:
        print(f"REPLAY #{a.n} CANNOT_RUN | download | {str(e)[:120]}")
        return
    if not files:
        print(f"REPLAY #{a.n} NO_FILE | {len(urls)} attachment(s), none runnable")
        return
    for f in files[:3]:
        out_json = os.path.join(work, "result.json")
        is_script = f.lower().endswith(".json")
        if is_script:
            try:
                ok = isinstance(json.load(open(f, encoding="utf-8")), dict) and "commands" in json.load(open(f, encoding="utf-8"))
            except Exception:
                ok = False
            if not ok:  # container.json / document.json of an unpacked design, a crash report, etc.: not a command script
                print(f"REPLAY #{a.n} NO_FILE | {os.path.basename(f)} | a .json that is not a command script (no `commands` array)")
                continue
        # a script replays with `run`; a design or STEP file is measured with `eval` (its timeline lists each feature's error)
        cmd = [a.cli, "run", f, "--results", "--json-out", out_json] if is_script else [a.cli, "eval", f, "--json-out", out_json]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=300)
        except subprocess.TimeoutExpired:
            print(f"REPLAY #{a.n} CANNOT_RUN | {os.path.basename(f)} | timed out after 300 s (does the design hang?)")
            continue
        text = (r.stderr or r.stdout or "").strip().replace("\n", " ")[:300]
        name = os.path.basename(f)
        if r.returncode != 0:
            # a script that fails is the reproduction; a file the CLI cannot even read is not
            unreadable = re.search(r"invalid utf-8|unsupported|not a valid|cannot read|unknown format", text, re.I)
            print(f"REPLAY #{a.n} {'CANNOT_RUN' if unreadable or not is_script else 'FAILED'} | {name} | exit {r.returncode} | {text}")
            continue
        errs = []
        try:
            data = json.load(open(out_json, encoding="utf-8"))
            errs = [(t.get("name"), t.get("error")) for t in data.get("timeline", []) if t.get("error")] if isinstance(data, dict) else []
        except Exception:
            pass
        if errs:
            print(f"REPLAY #{a.n} FAILED | {name} | {len(errs)} feature(s) with an error: " + "; ".join(f"{n}: {str(e)[:120]}" for n, e in errs[:3]))
        else:
            print(f"REPLAY #{a.n} RAN_CLEAN | {name} | no feature reports an error")
    print(f"(official CLI: {subprocess.run([a.cli, '--version'], capture_output=True, text=True).stdout.strip()})")
    if a.keep:
        print("files kept in", work)


if __name__ == "__main__":
    main()
