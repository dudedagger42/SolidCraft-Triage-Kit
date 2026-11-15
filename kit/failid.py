#!/usr/bin/env python3
"""Failure ID v1: builds the 11-digit code from TT, MM and the program's error text.

  python failid.py code 40 10 "SMLib fillet: operation: the blend failed (status 1001): ..."
  python failid.py collect raw_dir > haiku.jsonl
  python failid.py backfill haiku.jsonl issues_dir > coded.jsonl

Code = TT MM K SSSSSS (uppercase hex, no spaces).
  K 0  no error text                          SSSSSS = 000000  bucket only, never a duplicate claim
  K 1  refusal of the input or the state      SSSSSS = hash    same K+S = same bug
  K 2  limit or other refusal                 SSSSSS = hash    same K+S = same refusal; duplicate unless
                                                               one report shows the refusal itself is wrong
  K 3  failure inside the kernel              SSSSSS = hash    same K+S = same failure class only
  K F  unsure                                 SSSSSS = 000000  never matches
Only this script makes K and S. The model (or the triager) supplies TT, MM and the error text.

backfill: issues_dir holds <number>.json from
  gh issue view N -R tangency-labs/solidcraft --json number,title,body
and each line of haiku.jsonl is the model's JSON for one issue.
"""
import hashlib, json, os, re, sys

# Old wording -> today's key, so reports from before a message was reworded still match.
# Left side: the first part of the key as this script prints it.
ALIASES = {
    "mesh exceeds the conversion budget": "mesh over the triangle limit",
    "the mesh has # triangles more than the # conversion can take": "mesh over the triangle limit",
}
# Refusals known to be one bug each (duplicate-clusters.md). Matched inside the key. They get K 1.
STRONG = [
    "there is no body to cut or intersect",
    "the mirror line must be a straight curve of this sketch",
    "unknown sketch line",
    "there is no sheet metal body",
    "only bodies with planes cylinders cones spheres and tori",
    "this face can't keep an attachment",
    "the selected planar face no longer exists",
    "is where # edges meet",
    "mesh over the triangle limit",
    "this mesh is not a supported constant section prism",
    "a boolean needs a solid body",
]
# Messages that the same words produce on unrelated geometry. They get K 3.
GENERIC = [
    r"\bno result\b", r"\bblend\b", r"^(the )?operation failed$", r"could not open its window",
    r"could not be computed reliably", r"shell boundaries intersect or touch",
    r"is not a closed solid", r"coincident faces were left in place",
]
KERNEL = re.compile(r"^smlib\b|solidcore|::|\(status \d+\)|panicked at|smlib's (check|result)|smlib failed")
# Wrappers that say where the message came from, not what it is.
WRAP = re.compile(
    r"^(body .* the operation failed|the operation failed|invalid parameters for.*|invalid input|"
    r"not supported yet|error|failed)$")
NESTED = re.compile(r"\s*\(([^()]*(the operation failed|not supported yet|invalid input)[^()]*)\)?")
IDENT = re.compile(r"[a-z_][a-z0-9_.\[\]]*")


def clean(text):
    s = text.replace("\\n", "\n").replace("’", "'").replace("‘", "'")
    s = s.strip().strip('"“”')
    # names of bodies and features go; parameter and command ids stay
    s = re.sub(r"`([^`]*)`", lambda m: m.group(1) if IDENT.fullmatch(m.group(1)) else "`", s)
    s = s.lower()
    s = re.sub(r"0x[0-9a-fx]+", "#", s)
    keep = {}

    def hold(m):
        keep["<" + "abcdefghij"[len(keep) % 10] * (1 + len(keep) // 10) + ">"] = m.group(0)
        return list(keep)[-1]
    s = re.sub(r"status \d+|test #\d+", hold, s)       # numbers that name the failure
    s = re.sub(r"[-+]?\d+(\.\d+)?(e[-+]?\d+)?", "#", s)
    for k, v in keep.items():
        s = s.replace(k, v)
    s = re.sub(r"^(step # \([^)]*\):\s*)?body [^:]*: the operation failed:\s*", "", s)
    return s


def squash(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9#:' ]+", " ", s)).strip(" :")


def signature(error_text):
    """-> (K, key). key is what gets hashed; '' when there is nothing to hash."""
    if not error_text or not error_text.strip():
        return "0", ""
    s = clean(error_text)
    if "check refuses the result" in s:
        stage = re.search(r"smlib ([a-z ]+?):", s)
        test = re.search(r"(sm\w+)::(test #\d+) ([^:\n\[(]+)", s)
        if not test:
            return "F", ""
        return "3", squash(f"check {stage.group(1) if stage else '?'} {test.group(1)} {test.group(2)} {test.group(3)}")
    first = s.split("\n")[0]
    if KERNEL.search(first) or any(re.search(g, squash(first)) for g in GENERIC):
        key = squash(first.split(";")[0])
        return ("3", key) if len(key.split()) >= 3 else ("F", "")
    limit = "not supported yet" in first
    guard = re.search(r"invalid (input|parameters)", first) is not None
    t = NESTED.sub(lambda m: "; " + m.group(1) + "; ", first)   # a message inside brackets is a second cause
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"\([^)]*$", " ", t)                             # a bracket the reporter cut off
    parts = re.split(r":\s|;\s|\.\s", t + " ")
    parts = [squash(p) for p in parts if not re.search(r"[/\\]", p)]   # a file path is not the message
    parts = [p for p in parts if p and not WRAP.match(p)]
    while len(parts) > 1 and len(parts[0].split()) <= 2:        # the tool or feature name in front
        parts.pop(0)
    if not parts:
        return "F", ""
    key = ALIASES.get(parts[0], " | ".join(parts[:2]))
    if len(key.replace("|", " ").split()) < 3:                  # too short to mean one thing
        return "F", ""
    strong = (guard and not limit) or any(x in key for x in STRONG)
    return ("1" if strong else "2"), key


def make(tt, mm, error_text, error_state="quoted"):
    tt, mm = str(tt).upper(), str(mm).upper()
    if not re.fullmatch(r"[0-9A-F]{2}", tt):
        tt = "FF"
    if not re.fullmatch(r"[0-9A-F]{2}", mm):
        mm = "FF"
    if error_state == "quoted":
        k, key = signature(error_text)
    else:
        k, key = ("F" if error_state == "mentioned" else "0"), ""
    sig = hashlib.sha1(key.encode()).hexdigest()[:6].upper() if key else "000000"
    return tt + mm + k + sig, key


def flat(s):
    s = s.replace("\\n", "").replace("\\", "")
    return re.sub("[\\s\"'`‘’“”]+", "", s).lower()


def backfill(jsonl, issues_dir):
    for line in open(jsonl, encoding="utf-8"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        r = json.loads(line)
        state, err = r.get("error", "none"), r.get("error_text", "") or ""
        p = os.path.join(issues_dir, f"{r['number']}.json")
        if state == "quoted" and os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            # the error must be in the report word for word; a reworded one is not evidence
            if flat(err)[:200] not in flat((d.get("title") or "") + (d.get("body") or "")):
                state, r["note"] = "mentioned", "error_text not found in the report"
        r["fail_id"], r["sig_key"] = make(r.get("tt", "FF"), r.get("mm", "FF"), err, state)
        if "F" in r["fail_id"][:5]:
            r["confidence"] = "low"
        print(json.dumps(r, ensure_ascii=False))


def collect(raw_dir):
    """raw/<number>.json from `claude -p --output-format json` -> one model line per issue."""
    for name in sorted(os.listdir(raw_dir)):
        if not re.fullmatch(r"\d+\.json", name):
            continue
        try:
            text = json.load(open(os.path.join(raw_dir, name), encoding="utf-8"))["result"]
            line = next(l for l in text.splitlines() if l.strip().startswith("{"))
            r = json.loads(line)
            r["number"] = int(name[:-5])          # the file name wins over what the model wrote
            print(json.dumps(r, ensure_ascii=False))
        except Exception as e:                    # rerun these numbers
            print(f"{name}: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) == 3 and sys.argv[1] == "collect":
        collect(sys.argv[2])
    elif len(sys.argv) >= 5 and sys.argv[1] == "code":
        code, key = make(sys.argv[2], sys.argv[3], sys.argv[4])
        print(code, "|", key)
    elif len(sys.argv) == 4 and sys.argv[1] == "backfill":
        backfill(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
