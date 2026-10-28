"""SolidCraft Triage Kit v2: one CLI for triaging github.com/tangency-labs/solidcraft. Start with SOLO.md or MULTI.md.

    python -X utf8 kit/triage.py inbox [--limit 10]          MULTI: issues you may claim, oldest first
    python -X utf8 kit/triage.py claim N                     MULTI: react with the claim emoji; keep it only if yours is the earliest valid one
    python -X utf8 kit/triage.py unclaim N                   MULTI: remove your claim (gave up, or stuck)
    python -X utf8 kit/triage.py note N --reproducing 0.25.1 MULTI: the short 'Reproducing on <version>' note (keeps a claim past 30 min)
    python -X utf8 kit/triage.py next [--limit 10]           SOLO: untouched reports, newest first
    python -X utf8 kit/triage.py case N                      build the case file (thread, attachments, duplicate candidates, environment)
    python -X utf8 kit/triage.py prompt N                    the checklist prompt for the case -> state/cases/N.prompt.md
    python -X utf8 kit/triage.py decide N                    answers -> verdict and what the comment must do (state/cases/N.answers.json)
    python -X utf8 kit/triage.py submit N [--comment F] [--translation F] [--by first|repro] [--result R]   lint + route + queue
    python -X utf8 kit/triage.py post N [--approve]          post the queued comment (live checks, duplicate guard, 6 s gap)
    python -X utf8 kit/triage.py fix N --file F --why "..."  a correction: edit your existing comment in place (never a new one)
    python -X utf8 kit/triage.py followups                   threads you own where someone replied after you
    python -X utf8 kit/triage.py reply N --file F --why "..." / handled N --why "..."
    python -X utf8 kit/triage.py corrections [--reply K --file F]   open correction issues about your account on the kit repo
    python -X utf8 kit/triage.py appcheck "keyword" | cluster | rootcause "error text" [--cmd id]
    python -X utf8 kit/triage.py audit [--hours 6] [--per 3] [--mine]  sample recent kit comments per account (--mine: self-assessment), re-lint, flag signatures
    python -X utf8 kit/triage.py lint-text F [--by first|repro]   lint any text file as a comment (no case needed)
    python -X utf8 kit/triage.py corrective ... | retrolint | maintainers [--refresh] | release | bump "changelog line" | selftest

State (cases, queue, logs, claims) lives in state/ next to kit/ and is per machine; it is never committed.
"""
import argparse, datetime as dt, json, os, random, re, shutil, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATE = os.environ.get("TRIAGE_STATE") or os.path.join(ROOT, "state")
CASES, QUEUE, LOGS = (os.path.join(STATE, d) for d in ("cases", "queue", "logs"))
for _d in (CASES, QUEUE, LOGS):
    os.makedirs(_d, exist_ok=True)
POSTED, FIXES, LASTPOST = os.path.join(LOGS, "posted.jsonl"), os.path.join(LOGS, "fixes.jsonl"), os.path.join(LOGS, "last_post.txt")
RULES, CHECKLIST, LESSONS = os.path.join(HERE, "rules.json"), os.path.join(HERE, "checklist.json"), os.path.join(ROOT, "docs", "lessons.md")
VERSION = open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip()
MARKER_RE = re.compile(r"<!-- solidcraft-triage-kit v(\d+\.\d+)(?: https://\S+)?(?: status=(\w+))? -->")
HEADER_RE = re.compile(r"\*\*(?:Triage|Verified|Triaged) by @?([A-Za-z0-9-]+):?\*\*:?")


def _cfg():
    c = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
    local = os.path.join(STATE, "config.local.json")
    if os.path.exists(local):
        c.update(json.load(open(local, encoding="utf-8")))
    return c


CFG = _cfg()
REPO, KIT_REPO, BOTS = CFG["upstream_repo"], CFG["kit_repo"], set(CFG["bots"])
MARKER = f"<!-- solidcraft-triage-kit v{VERSION} https://github.com/{KIT_REPO} -->"  # hidden; lets any agent reading a thread find the kit
GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
SRC_REPO = os.environ.get("SOLIDCRAFT_SRC") or os.path.join(ROOT, "..", "solidcraft")  # a checkout with an `upstream` remote; read via `git grep` only
ATT = re.compile(r"https://github\.com/user-attachments/files/[^\s)\"\]>]+")   # zips, designs, json, step: things to run
IMG = re.compile(r"https://github\.com/user-attachments/assets/[^\s)\"\]>]+")  # screenshots and recordings
PROFILES = {"first": "first", "repro": "repro", "deepseek": "first", "haiku": "first", "sonnet": "repro"}
VERDICTS = ["duplicate", "needs_info", "feature_note", "support_answer", "kernel_describe", "needs_repro", "no_action",
            "reproduced", "not_reproduced", "could_not_test"]
POSTABLE = {"duplicate", "needs_info", "feature_note", "support_answer", "kernel_describe", "reproduced", "not_reproduced", "could_not_test"}
REPRO_ONLY = {"reproduced", "not_reproduced", "could_not_test"}
BANDS = [(1, 2, "one person"), (3, 4, "few"), (5, 6, "some"), (7, 8, "many"), (9, 10, "everyone")]
CANT_RUN = "I can only triage here; this still needs to be reproduced."


# ---------------------------------------------------------------- plumbing
GH_WRITES = {("issue", "comment"), ("issue", "create"), ("issue", "edit"), ("issue", "close"), ("issue", "reopen"),
             ("pr", "create"), ("pr", "comment"), ("pr", "edit"), ("pr", "merge"), ("label", "create")}


def dry_run():
    """TRIAGE_DRY_RUN=1, or "dry_run": true in state/config.local.json: no GitHub write happens."""
    return os.environ.get("TRIAGE_DRY_RUN") == "1" or bool(CFG.get("dry_run"))


def gh_is_write(args):
    if args and args[0] == "api":
        if "-X" in args:
            return args[args.index("-X") + 1].upper() != "GET"
        return any(x in args for x in ("-f", "-F", "--field", "--raw-field", "--input"))  # gh api defaults to POST with fields
    return tuple(args[:2]) in GH_WRITES


def gh(*args, inp=None):
    if dry_run() and gh_is_write(args):
        print(f"DRY RUN: skipped gh {' '.join(args[:4])}")  # every GitHub write stops here in a dry run
        return ""
    r = subprocess.run([GH, *args], input=inp, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"gh {' '.join(args[:3])}: {r.stderr.strip()[:300]}")
    return r.stdout


def ghj(*args, inp=None):
    return json.loads(gh(*args, inp=inp) or "null")


def jload(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def jsave(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


def jl_read(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()] if os.path.exists(path) else []


def jl_append(path, row):
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts(s):
    return dt.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)


def age_s(s):
    return (dt.datetime.now(dt.timezone.utc) - ts(s)).total_seconds()


def say(*a):
    print(*a, flush=True)


_ME = []


def me():
    """The posting account is whatever `gh` is logged in as. The header is built from it, so it cannot name anyone else."""
    if not _ME:
        _ME.append(gh("api", "user", "--jq", ".login").strip())
    return _ME[0]


def header():
    return f"**Triage by {me()}:**"


def wrap(text, status=None):
    """Header + text + hidden marker. The marker carries the kit version (and `status=reproducing` on a claim note)."""
    t = HEADER_RE.sub("", text.strip(), count=1).strip() if text.lstrip().startswith("**") else text.strip()
    mark = MARKER if not status else MARKER.replace(" -->", f" status={status} -->")
    return f"{header()} {t}\n\n{mark}"


def signer(body):
    m = HEADER_RE.search(body or "")
    return m.group(1) if m else None


def is_triage(body):
    return bool(MARKER_RE.search(body or "") or HEADER_RE.search(body or ""))


def profile(by):
    p = PROFILES.get(by)
    if not p:
        sys.exit(f"--by must be first or repro (got {by})")
    return p


def mode():
    return os.environ.get("TRIAGE_MODE") or CFG.get("mode") or "multi"


# ---------------------------------------------------------------- maintainers and latest release
def maintainers():
    m = set(CFG.get("maintainers") or []) | set(jload(os.path.join(STATE, "maintainers.json"), []))
    return m


def cmd_maintainers(a):
    if a.refresh:
        found = set()
        for page in (1, 2, 3):
            for c in ghj("api", f"repos/{REPO}/issues/comments?sort=created&direction=desc&per_page=100&page={page}"):
                if c.get("author_association") in CFG["maintainer_associations"]:
                    found.add(c["user"]["login"])
        jsave(os.path.join(STATE, "maintainers.json"), sorted(found))
    say("maintainers (claims and replies from these are not triage claims):", ", ".join(sorted(maintainers())) or "none known: run `maintainers --refresh`")


def latest_release():
    p = os.path.join(STATE, "release.json")
    c = jload(p, {})
    if c.get("at") and age_s(c["at"]) < 3600:
        return c["tag"]
    try:
        tag = ghj("release", "list", "-R", REPO, "-L", "1", "--json", "tagName")[0]["tagName"].lstrip("v")
    except (RuntimeError, IndexError, ValueError):
        return c.get("tag")
    jsave(p, {"tag": tag, "at": now()})
    return tag


def cmd_release(a):
    say(f"current release: {latest_release()} (cached up to 1 h in state/release.json)")


# ---------------------------------------------------------------- claims (MULTI.md)
def issue_live(n):
    return ghj("issue", "view", str(n), "-R", REPO, "--json", "number,title,state,labels,author,createdAt,comments,url,body")


def linked_prs(n):
    out = []
    try:
        for e in ghj("api", f"repos/{REPO}/issues/{n}/timeline?per_page=100", "-H", "Accept: application/vnd.github+json"):
            src = (e.get("source") or {}).get("issue") or {}
            if e.get("event") == "cross-referenced" and src.get("pull_request") and src.get("state") == "open":
                out.append(src["number"])
            elif e.get("event") == "connected":
                out.append("connected")
    except RuntimeError:
        pass
    return out


def eyes(n):
    return ghj("api", f"repos/{REPO}/issues/{n}/reactions?content={CFG['claim_reaction']}&per_page=100")


def claim_state(n, d=None):
    """Who holds issue N, by MULTI.md's rules. Returns {ok, reason, holder, mine, takeover}."""
    d = d or issue_live(n)
    author, mt = d["author"]["login"], maintainers()
    cs = d["comments"]
    res = {"number": n, "ok": False, "holder": None, "mine": None, "takeover": False}
    if d["state"] != "OPEN":
        return {**res, "reason": "closed"}
    if {l["name"] for l in d["labels"]} & set(CFG["skip_labels"]):
        return {**res, "reason": "label: " + ", ".join(sorted({l["name"] for l in d["labels"]} & set(CFG["skip_labels"])))}
    if age_s(d["createdAt"]) < CFG["author_window_s"]:
        return {**res, "reason": f"younger than {CFG['author_window_s']} s: the author may still /claim it"}
    if any(c["author"]["login"] == author and (c["body"] or "").strip().lower().startswith("/claim") for c in cs):
        return {**res, "reason": "the author claimed it (/claim): they plan their own PR"}
    if any(c["author"]["login"] in mt or c.get("authorAssociation") in CFG["maintainer_associations"] for c in cs
           if c["author"]["login"] != author):
        return {**res, "reason": "a maintainer replied"}
    prs = linked_prs(n)
    if prs:
        return {**res, "reason": f"linked PR: {prs}"}
    tri = [c for c in cs if is_triage(c["body"])]
    since = None
    if tri:
        owner = tri[0]["author"]["login"]
        own_last = max(c["createdAt"] for c in cs if c["author"]["login"] == owner)
        later = [c for c in cs if c["createdAt"] > own_last and c["author"]["login"] not in BOTS | {owner}]
        if owner == me():
            return {**res, "ok": True, "holder": owner, "mine": True, "reason": "you own the thread"}
        if not (later and age_s(later[-1]["createdAt"]) >= CFG["takeover_after_h"] * 3600):
            return {**res, "holder": owner, "reason": f"owned by {owner} (triage comment); takeover only after {CFG['takeover_after_h']} h of their silence"}
        since, res["takeover"] = own_last, True
    commented = lambda u, t: any(c["author"]["login"] == u and c["createdAt"] >= t for c in cs)
    valid = []
    for r in eyes(n):
        u, t = r["user"]["login"], r["created_at"]
        if u == author or u in mt or u in BOTS or (since and t <= since):
            continue
        if age_s(t) <= CFG["claim_expiry_min"] * 60 or commented(u, t):
            valid.append((t, u, r["id"]))
    valid.sort()
    if valid:
        res["holder"] = valid[0][1]
        res["mine"] = valid[0][1] == me()
        res["mine_id"] = next((i for t, u, i in valid if u == me()), None)
    res["ok"] = not valid or res["mine"]
    res["reason"] = (f"claimed by {res['holder']}" if valid and not res["mine"] else "yours" if valid else
                     "free (takeover)" if res["takeover"] else "free")
    return res


def cmd_inbox(a):
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=a.hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    items = ghj("issue", "list", "-R", REPO, "--state", "open", "--limit", "1000", "--search", f"created:>={since}",
                "--json", "number,title,labels,comments,author,createdAt")
    shown = 0
    for i in sorted(items, key=lambda x: x["number"]):  # oldest unclaimed first
        if {l["name"] for l in i["labels"]} & set(CFG["skip_labels"]) or any(is_triage(c["body"]) for c in i["comments"]):
            continue
        if any(c["author"]["login"] not in BOTS | {i["author"]["login"]} for c in i["comments"]):
            continue
        st = claim_state(i["number"])
        if st["ok"] and not st["mine"]:
            say(f"#{i['number']} {i['title'][:80]}  ({st['reason']})")
            shown += 1
            if shown >= a.limit:
                break
        time.sleep(0.5)
    say(f"{shown} claimable shown. Claim one (`claim N`) BEFORE any model work.")


def cmd_claim(a):
    st = claim_state(a.n)
    if st.get("mine"):
        return say(f"#{a.n}: already yours ({st['reason']})")
    if not st["ok"]:
        sys.exit(f"#{a.n}: not claimable: {st['reason']}")
    if dry_run():
        return say(f"DRY RUN #{a.n}: claimable; no reaction added")
    gh("api", f"repos/{REPO}/issues/{a.n}/reactions", "-X", "POST", "-f", f"content={CFG['claim_reaction']}")
    time.sleep(3)
    st = claim_state(a.n)
    if not st.get("mine"):
        mine = [r for r in eyes(a.n) if r["user"]["login"] == me()]
        for r in mine:
            gh("api", f"repos/{REPO}/issues/{a.n}/reactions/{r['id']}", "-X", "DELETE")
        sys.exit(f"#{a.n}: lost the claim to {st['holder']} (earlier valid claim); your reaction was removed")
    jl_append(os.path.join(LOGS, "claims.jsonl"), {"ts": now(), "issue": a.n, "event": "claim", "takeover": st["takeover"]})
    say(f"#{a.n}: claimed. Comment within {CFG['claim_expiry_min']} min (the triage comment, or `note {a.n} --reproducing <version>`), or unclaim.")


def cmd_unclaim(a):
    for r in eyes(a.n):
        if r["user"]["login"] == me():
            gh("api", f"repos/{REPO}/issues/{a.n}/reactions/{r['id']}", "-X", "DELETE")
    jl_append(os.path.join(LOGS, "claims.jsonl"), {"ts": now(), "issue": a.n, "event": "unclaim", "why": a.why or ""})
    say(f"#{a.n}: claim removed")


def cmd_note(a):
    ver = a.reproducing
    if ver != latest_release() and not re.fullmatch(r"main|[0-9a-f]{7,40}", ver):
        sys.exit(f"reproduce on the current official build ({latest_release()}), or name main / a commit")
    d = issue_live(a.n)
    if any(is_triage(c["body"]) and c["author"]["login"] == me() for c in d["comments"]):
        sys.exit("you already have a comment on this issue: edit it (`fix`) instead of adding a note")
    post_comment(a.n, f"Reproducing on {ver}.", status="reproducing", d=d)


# ---------------------------------------------------------------- next (SOLO)
def cmd_next(a):
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=a.hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    items = ghj("issue", "list", "-R", REPO, "--state", "open", "--limit", "1500", "--search", f"created:>={since}",
                "--json", "number,title,labels,comments,author,createdAt")
    done = {int(f[:-5]) for f in os.listdir(QUEUE) if f.endswith(".json") and (jload(os.path.join(QUEUE, f)) or {}).get("status") != "REJECTED"}
    out = [i for i in sorted(items, key=lambda x: -x["number"])
           if i["number"] not in done and not {l["name"] for l in i["labels"]} & set(CFG["skip_labels"])
           and not any(c["author"]["login"] not in BOTS for c in i["comments"])]
    for i in out[: a.limit]:
        say(f"#{i['number']} [{','.join(sorted(l['name'] for l in i['labels']))}] {i['title'][:80]}")
    say(f"{len(out)} untouched in the last {a.hours:g} h (showing {min(a.limit, len(out))})")


# ---------------------------------------------------------------- case
def error_texts(body):
    outs = []
    for m in re.finditer(r'"([^"\n]{14,240})"', body or ""):
        t = m.group(1)
        if re.search(r"[a-z]{4}", t) and not t.startswith(("http", "type", "SolidCraft ")) and " " in t:
            outs.append(t.replace("\\n", " ").strip())
    outs.sort(key=lambda t: (0 if re.search(r"fail|refus|no result|not supported|cannot|can.t|must|unknown|invalid", t, re.I) else 1, len(t)))
    return list(dict.fromkeys(outs))[:4]


def search(kind, text, limit):
    cmd = ["search", kind, text, "-R", REPO, "--limit", str(limit), "--json",
           "number,title,state,labels" if kind == "issues" else "number,title,state,isDraft"]
    try:
        return ghj(*cmd)
    except (RuntimeError, ValueError) as e:
        return [{"error": str(e)[:120]}]


STOP = set("this that with from have when then than they them there these those what which would could should about after before "
           "while into onto also just only some does doesn't dont cant cannot error issue problem report modeling unexpected result "
           "operation failed wrong steps reproduce expected actual behavior because being using used uses like want need make made "
           "able more most very still even each other".split())


def keyword_queries(title, body):
    """Short keyword queries: GitHub search ANDs every word, so long titles find nothing."""
    m = re.search(r"## Actual behavior\s*(.{0,300})", body or "", re.S)
    text = re.sub(r"\[[^\]]*\]", " ", title) + " " + (m.group(1) if m else (body or "")[:200])
    text = re.sub(r"https?://\S+|<img[^>]*>", " ", text)
    toks = list(dict.fromkeys(w.lower().replace("-", "") for w in re.findall(r"[A-Za-z][A-Za-z-]{3,}", text)
                              if w.lower().replace("-", "") not in STOP))
    if len(toks) < 2:
        return []
    qs = [" ".join(toks[:3]), " ".join(toks[1:4]), " ".join(sorted(toks, key=len, reverse=True)[:2])]
    return list(dict.fromkeys(q for q in qs if q))[:3]


def download_images(n, texts):
    urls = list(dict.fromkeys(m.group(0) for t in texts for m in IMG.finditer(t or "")))
    out, imgdir = [], os.path.join(CASES, "img", str(n))
    for i, u in enumerate(urls[:4]):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "solidcraft-triage-kit"}), timeout=30) as r:
                data = r.read(6_000_001)
            kind = ("png" if data[:4] == b"\x89PNG" else "jpg" if data[:2] == b"\xff\xd8" else "gif" if data[:3] == b"GIF"
                    else "webp" if data[8:12] == b"WEBP" else None)
            if kind and len(data) <= 6_000_000:
                os.makedirs(imgdir, exist_ok=True)
                path = os.path.join(imgdir, f"{i + 1}.{kind}")
                open(path, "wb").write(data)
                out.append({"path": path, "bytes": len(data)})
            else:
                out.append({"url": u, "skipped": "video, too large, or not an image"})
        except Exception as e:
            out.append({"url": u, "error": str(e)[:80]})
    return out


def cmd_case(a):
    n = a.n
    d = issue_live(n)
    body = d.get("body") or ""
    atts = [{"url": m.group(0), "where": "body", "by": d["author"]["login"]} for m in ATT.finditer(body)]
    comments = []
    for c in d["comments"]:
        atts += [{"url": m.group(0), "where": f"comment {c['createdAt'][:16]}", "by": c["author"]["login"]} for m in ATT.finditer(c["body"] or "")]
        comments.append({"author": c["author"]["login"], "association": c.get("authorAssociation"), "at": c["createdAt"],
                         "triage_comment": is_triage(c["body"]), "signed_as": signer(c["body"]), "body": (c["body"] or "")[:1500]})
    errs = error_texts(body)
    gpu = re.search(r"Renderer: GPU, ([^(\n]{4,60}?) \(", body)
    gpu_q = [gpu.group(1).strip()] if gpu and re.search(r"grid|plane|visible|black|blank|dots|render|display|glitch|flicker|draw",
                                                      d["title"] + " " + body[:400], re.I) else []
    queries = errs[:2] + keyword_queries(d["title"], body) + gpu_q + list(a.q or [])
    dups = []
    for qi, t in enumerate(queries):
        for kind in (("issues", "prs") if qi < 2 else ("issues",)):
            for r in search(kind, t, 6 if kind == "issues" else 4):
                if r.get("number") == n or r.get("error") or any(x["number"] == r.get("number") for x in dups):
                    continue
                dups.append({**r, "kind": "issue" if kind == "issues" else "pr", "labels": [l["name"] for l in r.get("labels", [])], "matched_query": t})
            time.sleep(7)  # GitHub search secondary limit
    for k in list(dict.fromkeys(int(m.group(1)) for m in re.finditer(r"(?<![\w/])#(\d{2,5})\b", body)))[:5]:
        if k != n and not any(x["number"] == k for x in dups):
            try:
                r = ghj("api", f"repos/{REPO}/issues/{k}")
                dups.append({"number": k, "title": r["title"], "state": r["state"], "kind": "pr" if "pull_request" in r else "issue",
                             "labels": [l["name"] for l in r.get("labels", [])], "matched_query": "cited in the report"})
            except RuntimeError:
                pass
    bot_asked = any(c["author"]["login"] in BOTS and re.search(r"we need a little more|Steps to reproduce|arrived empty", c["body"] or "", re.I)
                    for c in d["comments"])
    crash_cluster = []
    if d["title"].startswith("Crash:"):
        since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            rows = ghj("issue", "list", "-R", REPO, "--state", "open", "--limit", "100", "--search", f"Crash: SolidCraft in:title created:>={since}", "--json", "number,title")
        except RuntimeError:
            rows = []
        ver = lambda t: (re.search(r"SolidCraft (\d+\.\d+)", t) or [None, None])[1]
        crash_cluster = [{"number": r["number"], "title": r["title"][:80]} for r in rows if r["number"] != n and ver(r["title"]) == ver(d["title"])]
    envm = lambda pat: (lambda m: m.group(1).split("\\n")[0].strip() if m else None)(re.search(pat, body))
    environment = {"version": envm(r"SolidCraft (\d+\.\d+\.\d+)"), "os": envm(r"OS: ([^\n]+)") or envm(r"SolidCraft \d+\.\d+\.\d+ \([^)]*\), ([^\n]+)"),
                   "renderer": envm(r"Renderer: ([^\n]+)"), "note": "from the report's Environment block; never ask for anything listed here"}
    case = {
        "built_at": now(), "kit_version": VERSION, "number": n, "url": d["url"], "title": d["title"], "state": d["state"],
        "labels": [l["name"] for l in d["labels"]], "author": d["author"]["login"], "created_at": d["createdAt"],
        "environment": environment, "current_release": latest_release(), "bot_asked": bot_asked, "crash_cluster": crash_cluster,
        "image_files": [] if a.no_images else download_images(n, [body] + [c["body"] for c in d["comments"]]),
        "body": body[:6000], "comments": comments, "attachments": atts, "attachment_present": bool(atts),
        "error_texts": errs, "command_ids": sorted(set(re.findall(r'"((?:solid|sketch|sheet|surface|timeline|component|joint|inspect|construct)\.[a-z_.]+)"', body))),
        "search_queries": queries, "dup_candidates": dups,
        "other_triage_comments": [{"author": c["author"], "signed_as": c["signed_as"]} for c in comments if c["triage_comment"] and c["author"] != me()],
    }
    case["exact_error_candidate"] = [x["number"] for x in dups if x.get("kind") == "issue" and x.get("state") == "open" and x.get("matched_query") in errs]
    jsave(os.path.join(CASES, f"{n}.json"), case)
    say(f"case #{n}: {d['title'][:70]} | files {len(atts)} | error texts {len(errs)} | dup candidates {len(dups)} | "
        f"release {case['current_release']} -> state/cases/{n}.json")
    if case["other_triage_comments"]:
        say(f"  WARNING: another triage comment is already on this thread: {case['other_triage_comments']}. MULTI.md: it is theirs.")


def load_case(n):
    c = jload(os.path.join(CASES, f"{n}.json"))
    if not c:
        sys.exit(f"no case file for #{n}: run `case {n}` first")
    return c


# ---------------------------------------------------------------- checklist: prompt, validate, decide
def questions():
    return jload(CHECKLIST)["questions"]


def applies(q, ans, case):
    if q.get("ask_if_case") and not case.get(q["ask_if_case"]):
        return False
    if q.get("ask_if") and not all(ans.get(k) for k in q["ask_if"]):
        return False
    if q.get("ask_if_any") and not any(ans.get(k) for k in q["ask_if_any"]):
        return False
    if q.get("ask_if_false") and any(ans.get(k) for k in q["ask_if_false"]):
        return False
    return True


def render_questions():
    out, group = [], None
    for q in questions():
        if q["group"] != group:
            group = q["group"]
            out.append(f"\n### {group}\n")
        cond = []
        if q.get("ask_if"):
            cond.append("only if " + " and ".join(f"`{k}` is yes" for k in q["ask_if"]))
        if q.get("ask_if_any"):
            cond.append("only if " + " or ".join(f"`{k}` is yes" for k in q["ask_if_any"]))
        if q.get("ask_if_false"):
            cond.append("only if " + " and ".join(f"`{k}` is no/null" for k in q["ask_if_false"]))
        if q.get("ask_if_case"):
            cond.append(f"only if the case's `{q['ask_if_case']}` is set")
        out.append(f"- **{q['id']} `{q['key']}`** ({q['kind']}{'; ' + '; '.join(cond) if cond else ''}): {q['q']}")
    return "\n".join(out)


def compact_case(c):
    k = dict(c)
    k["body"] = c["body"][:4000]
    k["comments"] = [{**x, "body": x["body"][:900]} for x in c["comments"][-8:]]
    return json.dumps(k, indent=1, ensure_ascii=False)


def build_prompt(c):
    t = open(os.path.join(ROOT, "docs", "prompt.md"), encoding="utf-8").read()
    clusters = open(os.path.join(ROOT, "docs", "duplicate-clusters.md"), encoding="utf-8").read()
    return (t.replace("{{QUESTIONS}}", render_questions()).replace("{{CLUSTERS}}", clusters)
             .replace("{{RELEASE}}", str(c.get("current_release"))).replace("{{CASE}}", compact_case(c)))


def cmd_prompt(a):
    p = build_prompt(load_case(a.n))
    path = os.path.join(CASES, f"{a.n}.prompt.md")
    open(path, "w", encoding="utf-8", newline="\n").write(p)
    say(f"prompt for #{a.n}: {len(p)} chars (~{len(p) // 4} tokens) -> {path}. Answers go in state/cases/{a.n}.answers.json")


def band(imp):
    return next((name for lo, hi, name in BANDS if lo <= imp <= hi), None)


def load_answers(n):
    p = os.path.join(CASES, f"{n}.answers.json")
    if not os.path.exists(p):
        sys.exit(f"no answers: write state/cases/{n}.answers.json (one key per checklist question)")
    txt = open(p, encoding="utf-8").read()
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        sys.exit("no JSON object in the answers file")
    return json.loads(m.group(0))


def validate(ans, case):
    bad = []
    for q in questions():
        k, v = q["key"], ans.get(q["key"])
        if not applies(q, ans, case):
            continue
        if q["kind"] == "bool" and not isinstance(v, bool):
            bad.append(f"{q['id']} `{k}` must be true or false")
        elif q["kind"] == "int" and (not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 10):
            bad.append(f"{q['id']} `{k}` must be an integer 1-10")
        elif q["kind"] == "issue" and v is not None and not isinstance(v, int):
            bad.append(f"{q['id']} `{k}` must be an issue number or null")
        elif q["kind"] in ("text", "language") and not isinstance(v, str):
            bad.append(f"{q['id']} `{k}` must be a string")
    if ans.get("confidence") not in ("sure", "unsure"):
        bad.append("C1 `confidence` must be sure or unsure")
    if isinstance(ans.get("importance_reason"), str) and len(ans["importance_reason"].strip()) < 12:
        bad.append("I2 `importance_reason` must name who is affected and how often")
    if case.get("attachment_present") and ans.get("attachment_is_runnable") is False and len((ans.get("attachment_not_runnable") or "").strip()) < 20:
        bad.append("E3 `attachment_not_runnable` needs a real reason (20+ characters)")
    if re.search(r"can.?t (download|open|extract)|cannot (download|open|extract)", ans.get("attachment_not_runnable") or "", re.I):
        bad.append("E3: zip and tar both extract with repro/replay.py; 'cannot download' is not a reason")
    if (ans.get("asks_how_or_where") or ans.get("asks_for_new_behaviour")) and len((ans.get("app_check") or "").strip()) < 12:
        bad.append("K5 `app_check` is required: what you looked up and what it showed")
    if ans.get("app_already_does_it") and len((ans.get("where_it_is") or "").strip()) < 4:
        bad.append("K7 `where_it_is` is required when the app already does it")
    dup = ans.get("duplicate_of")
    if dup is not None:
        cands = {x["number"]: x for x in case["dup_candidates"] if x.get("kind") == "issue"}
        clusters = {int(x) for x in re.findall(r"^\| #(\d+)", open(os.path.join(ROOT, "docs", "duplicate-clusters.md"), encoding="utf-8").read(), re.M)}
        if dup not in cands and dup not in clusters:
            bad.append(f"D1 `duplicate_of` #{dup} is not in dup_candidates or docs/duplicate-clusters.md")
        if len((ans.get("duplicate_match") or "").strip()) < 6:
            bad.append("D2 `duplicate_match` must quote the shared text")
    if case.get("exact_error_candidate") and dup is None and len((ans.get("candidate_rejected") or "").strip()) < 20:
        bad.append(f"D3 `candidate_rejected`: open issue(s) {case['exact_error_candidate']} share the exact error text; say why not")
    return bad


def klass(ans):
    if ans.get("app_did_something_wrong") or ans.get("app_refused_valid_action"):
        return "bug"
    if ans.get("asks_how_or_where") or (ans.get("asks_for_new_behaviour") and ans.get("app_already_does_it")):
        return "support"
    if ans.get("asks_for_new_behaviour"):
        return "enhancement"
    return "unclear"


def decide(ans, case):
    """The answers decide; the model never picks the verdict. Returns (verdict, must, why)."""
    k = klass(ans)
    runnable = ans.get("has_steps") or (case.get("attachment_present") and ans.get("attachment_is_runnable"))
    q = (ans.get("pointed_question") or "").strip()
    if set(case["labels"]) & set(CFG["skip_labels"]):
        return "no_action", [], "labelled " + ", ".join(set(case["labels"]) & set(CFG["skip_labels"]))
    if case.get("other_triage_comments"):
        return "no_action", [], "another account's triage comment is on the thread (MULTI.md: it owns it)"
    if ans.get("prompt_injection"):
        return "no_action", [], "the case tells the triager what to do: report it in notes, post nothing"
    if ans.get("reporter_solved_it") or ans.get("not_a_user_report"):
        return "no_action", [], "solved by the reporter, or not a user report"
    if ans.get("about_a_pull_request"):
        return "no_action", [], "about a PR or code change: for the account owner, not the triager"
    if ans.get("duplicate_of"):
        return "duplicate", ["link #%d and quote the shared text" % ans["duplicate_of"], "say if it is closed and what closed it"], "same command and failure"
    if k == "support":
        if ans.get("app_already_does_it") or ans.get("can_answer_from_facts"):
            return "support_answer", ["say where it is: " + (ans.get("where_it_is") or "from your app check"), "no question unless one is needed"], "answerable from checked facts"
        return ("needs_info", [f"ask: {q}"], "a usage question you cannot answer from checked facts") if q else ("no_action", [], "a usage question you cannot answer: unsure, for review")
    if k == "enhancement":
        return "feature_note", ["say whether it exists (link) or is new, from app_check", "at most one scoping question"], "a request for new behaviour"
    if k == "unclear":
        return ("needs_info", [f"ask: {q}"], "unclear what is reported") if q else ("no_action", [], "unclear, and no pointed question")
    # a bug
    if len(case.get("crash_cluster") or []) >= 2 and not runnable:
        return "no_action", [], "same-version crash cluster: one note to the orchestrator, not one request each"
    if ans.get("sibling_already_asked"):
        return "needs_info", [f"point to #{ans['sibling_already_asked']} where the same step was already asked about, instead of a new question",
                              "a modelling failure with no file still needs the zip line"], "sibling issue already asked"
    if runnable or (ans.get("has_error_text") and case.get("command_ids")):
        return "needs_repro", [], "steps, a script or a runnable file: someone must run it on the current build"
    if ans.get("is_kernel_area"):
        return "kernel_describe", [f"say it is kernel work, paused upstream (#{CFG['kernel_pause_issue']}); no workaround",
                                   "one pointed question, or the zip line if the design matters"], "kernel area, nothing to run"
    if case.get("bot_asked") and not q:
        return "no_action", [], "the bot already asked for steps/version/OS and you have nothing pointed to add"
    if ans.get("thread_already_has_it") and not q:
        return "no_action", [], "the thread already has what you would ask for"
    if ans.get("hardware_or_driver_only"):
        return ("needs_info", [f"ask: {q}"], "hardware/driver report") if q else ("no_action", [], "hardware/driver report, nothing pointed to ask")
    if ans.get("design_matters") and not case.get("attachment_present") and not ans.get("is_crash_or_data_loss") and not ans.get("gui_only"):
        return "needs_info", ["ask for the design zipped: right-click the .solidcraft file, Compress to ZIP, drag the .zip into a comment"], "modelling failure, no file"
    return ("needs_info", [f"ask: {q}"], "a bug with one thing missing") if q else ("no_action", [], "a bug with nothing pointed to ask")


def route(ans, verdict, case, violations, force_p0=False):
    k = klass(ans)
    imp = ans.get("importance") if isinstance(ans.get("importance"), int) else 1
    crash = bool(ans.get("is_crash_or_data_loss"))
    pr = ("P0" if force_p0 or (crash and imp >= 8) else "P1" if k == "bug" and imp >= 8
          else "P2" if (k == "bug" and imp >= 5) or (k != "bug" and imp >= 7) else "P3")
    blocks = [x for x in violations if x["severity"] == "block"]
    status = ("REJECTED" if blocks else "NEEDS-REPRO" if verdict == "needs_repro" else "NO-ACTION" if verdict == "no_action"
              else "REVIEW" if ans.get("confidence") == "unsure" or (case.get("bot_asked") and verdict == "needs_info") else "AUTO-POST")
    item = (f"LINE ITEM: #{case['number']} | {k} | importance {imp} ({band(imp) if isinstance(imp, int) else '?'}) | {pr} | {status} | "
            f"verdict={verdict} | kernel={'yes' if ans.get('is_kernel_area') else 'no'} | gui={'yes' if ans.get('gui_only') else 'no'}")
    return {"priority": pr, "status": status, "line_item": item}


def cmd_decide(a):
    case, ans = load_case(a.n), load_answers(a.n)
    bad = validate(ans, case)
    for b in bad:
        say("  [block] " + b)
    if bad:
        sys.exit("fix the answers and run decide again")
    verdict, must, why = decide(ans, case)
    jsave(os.path.join(CASES, f"{a.n}.decision.json"), {"verdict": verdict, "must": must, "why": why, "at": now()})
    say(f"#{a.n}: verdict {verdict} ({why})")
    if verdict in POSTABLE:
        for m in must:
            say("  the comment must: " + m)
        lang = (ans.get("reporter_language") or "English").strip()
        say(f"  write it to state/cases/{a.n}.comment.md (no header: the kit adds it; at most one question)"
            + (f", and the same text in {lang} to state/cases/{a.n}.translation.md" if lang.lower() != "english" else ""))
    else:
        say("  nothing is posted. `submit` it to record the verdict." + (" Then claim/hand it to whoever reproduces." if verdict == "needs_repro" else ""))


# ---------------------------------------------------------------- comment lints
PRIVATE_FILE = os.path.join(STATE, "private-names.txt")  # one name or regex per line; never committed
LOCAL_PATH = re.compile(r"[A-Za-z]:\\(?:Users|Documents and Settings)\\(?!%USERNAME%|<you>|you\\)[^\\\s]+|/(?:Users|home)/(?!<you>|you/)[A-Za-z0-9._-]+/|\\Downloads\\|OneDrive\\")


def grammar_lints(text):
    out = []
    t = re.sub(r"`[^`]*`", "", text)
    m = re.search(r"\b(\w{2,})\s+\1\b", t, re.I)
    if m and m.group(1).lower() not in ("that", "had", "is"):
        out.append(("G01", "block", f"doubled word '{m.group(0)}': a mechanical edit garbled the sentence; re-read it"))
    if text.count("`") % 2 or text.count("**") % 2 or text.count("(") != text.count(")"):
        out.append(("G02", "block", "unbalanced backticks, bold markers or parentheses"))
    if not re.search(r"[.?!)`\]:。？！）]\s*$", text.strip()):  # full-width endings too (translations)
        out.append(("G03", "block", "the comment does not end with a full sentence"))
    if re.search(r"[.?!] [a-z]", t) and not re.search(r"[.?!] (e\.g|i\.e|vs)\b", t):
        out.append(("G04", "warn", "a sentence starts in lower case: a fragment may be left from an edit"))
    return out


def lint_comment(text, by, case=None, ans=None, verdict=None, translation=""):
    """Every lint on a comment's text. `case`/`ans` may be None (follow-ups, audit): then only text lints run."""
    v, p, ans, case = [], profile(by), ans or {}, case or {}

    def add(rule, sev, msg):
        v.append({"rule": rule, "severity": sev, "message": msg})

    limit = CFG["comment_limit"]["repro" if p == "repro" else "first"]
    if len(text) > limit:
        add("T03", "block", f"comment is {len(text)} chars (limit {limit})")
    if text.count("?") > 1 and verdict not in REPRO_ONLY:
        add("Q01", "block", f"comment asks {text.count('?')} questions: ask at most ONE specific question")
    names = HEADER_RE.findall(text + "\n" + translation)
    if names:
        add("S01", "block", f"the text carries a signature ('{names[0]}'): the kit adds the one header, as the posting account. "
            "Never copy another account's header (MULTI.md)")
    for kind, val in (("version", "env_version"), ("renderer", "env_renderer"), ("os", "env_os")):
        if (case.get("environment") or {}).get(kind):
            case[val] = True
    for x in grammar_lints(text):
        add(*x)
    thread = (case.get("body") or "") + " " + " ".join((c or {}).get("body", "") for c in case.get("comments") or [] if isinstance(c, dict))
    if IMG.search(thread) and re.search(r"\b(a|an|another|short|new)\s+(\w+\s+){0,2}(recording|video|screenshots?|screen ?shots?|screencast|gif|clip)\b", text, re.I):
        add("M02", "block", "asks for a screenshot or recording, but the thread already has one: open it (image_files), or ask for something else")
    full = text + "\n\n" + translation
    cur = latest_release()
    for s in re.split(r"(?<=[.?!])\s+", full):
        if "?" in s and re.search(r"\b(still|again|happen|persist)", s):
            for ver in re.findall(r"\b(\d+\.\d+\.\d+)\b", s):
                if cur and ver != cur:
                    add("V01", "block", f"asks about {ver}; the current release is {cur} (gh release list). Ask about 'the current release, {cur}'")
    if LOCAL_PATH.search(full):
        add("P01", "block", "a local path with a user or folder name: never post local paths")
    if os.path.exists(PRIVATE_FILE):
        for line in open(PRIVATE_FILE, encoding="utf-8"):
            pat = line.strip()
            if pat and not pat.startswith("#") and re.search(pat, full, re.I):
                add("P02", "block", "names a private or work file listed in state/private-names.txt")
                break
    if re.search(r"user-attachments/(files|assets)/", text):
        add("P03", "warn", "the comment links an upload: make sure it is a public test file you made, never a private or work file")
    for m in re.finditer(r"(?<![\w-])@([A-Za-z0-9-]{2,39})\b", text):
        if m.group(1) != case.get("author"):
            add("M01", "block", f"@-mentions {m.group(1)}: never ping maintainers or other accounts from a triage comment")
            break
    known = {case.get("number")} | {x["number"] for x in case.get("dup_candidates", [])} | {CFG["kernel_pause_issue"]}
    known |= {int(x) for x in re.findall(r"#(\d{2,5})", json.dumps(case.get("comments", [])) + case.get("body", ""))}
    if ans.get("sibling_already_asked"):
        known.add(ans["sibling_already_asked"])
    if ans.get("related_issue"):
        known.add(ans["related_issue"])
    if case:
        for x in re.findall(r"#(\d{2,5})\b", text):
            if int(x) not in known:
                add("N01", "warn", f"links #{x}, which is not in the case (candidates, thread, answers): check it is the issue you mean")
    if case and re.search(r"#%d|kernel work" % CFG["kernel_pause_issue"], text) and not ans.get("is_kernel_area") and verdict not in REPRO_ONLY:
        add("K01", "block", "kernel framing on a report whose failing step is not in the kernel (E9 is no)")
    if verdict == "needs_info" and ans.get("design_matters") and not case.get("attachment_present") and not re.search(r"\bzip", text, re.I):
        add("Z01", "block", "a modelling failure with no file must ask for the design zipped (right-click, Compress to ZIP, drag the .zip into a comment)")
    if (ans.get("is_crash_or_data_loss") or ans.get("gui_only") or verdict == "support_answer") and re.search(r"\bzip\b|Compress to", text, re.I):
        add("Z02", "block", "no zip request for a crash, a GUI/selection problem or a usage question")
    if verdict == "duplicate":
        dup = ans.get("duplicate_of")
        if f"#{dup}" not in text:
            add("D05", "block", f"a duplicate comment must link #{dup}")
        st = next((x.get("state") for x in case.get("dup_candidates", []) if x["number"] == dup), "open")
        if st and st.lower() != "open" and not re.search(r"\bclosed\b", text, re.I):
            add("D02", "block", f"#{dup} is {st}: say it is closed (and what closed it)")
    if verdict == "reproduced" and not re.search(r"Root cause \((confirmed|likely|unknown)\)", text):
        add("X01", "block", "a reproduction names the root cause: 'Root cause (confirmed|likely|unknown): file:function, mechanism'")
    if verdict in ("reproduced", "not_reproduced") and cur and cur not in text and not re.search(r"\bon (main|[0-9a-f]{7,40})\b", text):
        add("X02", "block", f"say which build it ran on (the current release is {cur})")
    if verdict == "could_not_test" and CANT_RUN not in text:
        add("X03", "block", f"could_not_test must say exactly: '{CANT_RUN}'")
    lang = str(ans.get("reporter_language") or "English").strip()
    if ans and lang.lower() != "english" and verdict in POSTABLE and not translation.strip():
        add("L01", "block", f"the report is in {lang}: add the same comment in {lang} (--translation)")
    for r in jload(RULES)["rules"]:
        if r["profile"] not in ("all", p):
            continue
        if r.get("when") and not case.get(r["when"]):
            continue
        if r.get("unless_field") and ans.get(r["unless_field"]):
            continue
        if not re.search(r["pattern"], full, re.I | re.M):
            continue
        if r.get("unless") and re.search(r["unless"], full, re.I):
            continue
        add(r["id"], r["severity"], r["message"])
    return v


def show(v):
    for x in v:
        say(f"  [{x['severity']}] {x['rule']}: {x['message']}")


def cmd_lint_text(a):
    v = lint_comment(open(a.file, encoding="utf-8").read().strip(), a.by)
    show(v)
    say(f"{sum(x['severity'] == 'block' for x in v)} block(s), {sum(x['severity'] == 'warn' for x in v)} warning(s)")
    sys.exit(1 if any(x["severity"] == "block" for x in v) else 0)


def cmd_submit(a):
    case, p = load_case(a.n), profile(a.by)
    ans = load_answers(a.n) if os.path.exists(os.path.join(CASES, f"{a.n}.answers.json")) else {}
    if p == "repro":
        if not a.result:
            sys.exit("the repro profile submits a result: --result reproduced|not_reproduced|could_not_test")
        verdict, must, why = a.result, [], "reproduction result"
    else:
        bad = validate(ans, case)
        if bad:
            for b in bad:
                say("  [block] " + b)
            sys.exit("fix the answers (run decide) first")
        verdict, must, why = decide(ans, case)
    cpath = a.comment or os.path.join(CASES, f"{a.n}.comment.md")
    tpath = a.translation or os.path.join(CASES, f"{a.n}.translation.md")
    text = open(cpath, encoding="utf-8").read().strip() if os.path.exists(cpath) else ""
    tr = open(tpath, encoding="utf-8").read().strip() if os.path.exists(tpath) else ""
    v = []
    if verdict in POSTABLE and not text:
        v.append({"rule": "T01", "severity": "block", "message": f"verdict {verdict} needs a comment ({cpath})"})
    if verdict not in POSTABLE and text:
        v.append({"rule": "T02", "severity": "block", "message": f"verdict {verdict} posts nothing: delete {cpath}"})
    if text:
        v += lint_comment(text, a.by, case, ans, verdict, tr)
    r = route(ans, verdict, case, v, force_p0=bool(a.p0))
    final = text + (f"\n\n**({ans.get('reporter_language')})** {tr}" if tr else "")
    jsave(os.path.join(QUEUE, f"{a.n}.json"), {"issue": a.n, "by": p, "submitted_at": now(), "kit_version": VERSION, "answers": ans,
                                                "verdict": verdict, "why": why, "must": must, "violations": v, "final_comment": final or None, **r})
    show(v)
    say(r["line_item"])


# ---------------------------------------------------------------- post / fix
def gap_wait():
    """At least post_gap_s between posts from this machine (one account: keep one machine posting at a time)."""
    if os.path.exists(LASTPOST):
        try:
            g = time.time() - float(open(LASTPOST).read() or 0)
        except ValueError:
            g = 999
        if g < CFG["post_gap_s"]:
            time.sleep(CFG["post_gap_s"] - g)


def mine_on(d):
    return [c for c in d["comments"] if c["author"]["login"] == me() and is_triage(c["body"])]


def post_comment(n, text, status=None, d=None, by="first", extra=None):
    d = d or issue_live(n)
    if dry_run():
        jl_append(os.path.join(LOGS, "dryrun.jsonl"), {"ts": now(), "issue": n, "text": wrap(text, status)})
        say(wrap(text, status))
        return say(f"DRY RUN #{n}: the comment above was not posted; logged to state/logs/dryrun.jsonl")
    gap_wait()
    out = ghj("api", f"repos/{REPO}/issues/{n}/comments", "-X", "POST", "-F", "body=@-", inp=wrap(text, status))
    open(LASTPOST, "w").write(str(time.time()))
    jl_append(POSTED, {"ts": now(), "issue": n, "comment_id": out["id"], "url": out["html_url"], "by": by, "status": status, "text": text, **(extra or {})})
    say(f"posted #{n}: {out['html_url']}")
    return out


def edit_comment(n, cid, text, why, status=None):
    if dry_run():
        return say(f"DRY RUN: would edit comment {cid} on #{n}")
    gap_wait()
    old = ghj("api", f"repos/{REPO}/issues/comments/{cid}")
    ghj("api", f"repos/{REPO}/issues/comments/{cid}", "-X", "PATCH", "-F", "body=@-", inp=wrap(text, status))
    open(LASTPOST, "w").write(str(time.time()))
    jl_append(FIXES, {"ts": now(), "issue": n, "comment_id": cid, "why": why, "old": old["body"], "new": text})
    say(f"edited comment {cid} on #{n} in place (no new comment): {old['html_url']}")


def cmd_post(a):
    q = jload(os.path.join(QUEUE, f"{a.n}.json"))
    if not q:
        sys.exit("not queued: submit first")
    if q["status"] not in ("AUTO-POST", "REVIEW") and not (q["by"] == "repro" and q["status"] != "REJECTED"):
        sys.exit(f"status is {q['status']}: nothing to post")
    if q["status"] == "REVIEW" and not a.approve:
        sys.exit("REVIEW: run the docs/verify.md checks in a fresh context, then post with --approve")
    text = q["final_comment"]
    if not text:
        sys.exit("no comment queued")
    case = load_case(a.n)
    d = issue_live(a.n)
    if d["state"] != "OPEN":
        sys.exit("issue is closed now")
    if {l["name"] for l in d["labels"]} & set(CFG["skip_labels"]):
        sys.exit("issue carries a skip label now (claimed, in progress or kernel-paused): nothing posted")
    others = [c for c in d["comments"] if is_triage(c["body"]) and c["author"]["login"] != me()]
    if others:
        sys.exit(f"duplicate guard: {others[0]['author']['login']} already posted a triage comment here; it owns the thread")
    newer = [c for c in d["comments"] if c["createdAt"] > case["built_at"] and c["author"]["login"] not in BOTS | {me()}]
    if newer:
        sys.exit("someone commented since the case was built: rebuild the case (`case N`) and re-answer")
    if mode() == "multi":
        st = claim_state(a.n, d)
        if not st.get("mine") and not (dry_run() and st.get("ok")):  # a dry run takes no claim; claimable is enough
            sys.exit(f"MULTI: you do not hold the claim ({st['reason']}). `claim {a.n}` first")
    if q["verdict"] == "duplicate":
        cs = ghj("issue", "view", str(q["answers"]["duplicate_of"]), "-R", REPO, "--json", "state")
        if cs["state"] != "OPEN" and not re.search(r"\bclosed\b", text, re.I):
            sys.exit(f"#{q['answers']['duplicate_of']} is {cs['state']} now: say it is closed, resubmit")
    mine = mine_on(d)
    note = next((c for c in mine if (MARKER_RE.search(c["body"]) or [None, None, None])[2] == "reproducing"), None) if mine else None
    if mine and not note:
        sys.exit(f"you already have a triage comment on #{a.n}: a correction edits it (`fix {a.n} --file F --why ...`), never a new one")
    if note:
        cid = next(c["id"] for c in ghj("api", f"repos/{REPO}/issues/{a.n}/comments?per_page=100")
                   if c["user"]["login"] == me() and (MARKER_RE.search(c["body"] or "") or [None, None, None])[2] == "reproducing")
        edit_comment(a.n, cid, text, "result replaces the 'Reproducing on' note")
    else:
        post_comment(a.n, text, d=d, by=q["by"], extra={"verdict": q["verdict"], "priority": q["priority"]})
    q["status"] = "POSTED"
    jsave(os.path.join(QUEUE, f"{a.n}.json"), q)


def cmd_fix(a):
    text = open(a.file, encoding="utf-8").read().strip()
    v = [x for x in lint_comment(text, a.by, jload(os.path.join(CASES, f"{a.n}.json"))) if x["severity"] == "block"]
    if v:
        show(v)
        sys.exit("REJECTED: fix the text")
    rows = [c for c in ghj("api", f"repos/{REPO}/issues/{a.n}/comments?per_page=100") if c["user"]["login"] == me() and is_triage(c["body"])]
    if not rows:
        sys.exit(f"no triage comment of yours on #{a.n}")
    if len(rows) > 1 and not a.comment_id:
        sys.exit(f"you have {len(rows)} triage comments on #{a.n}: pass --comment-id (ids {[r['id'] for r in rows]})")
    cid = a.comment_id or rows[0]["id"]
    edit_comment(a.n, cid, text, a.why)


# ---------------------------------------------------------------- follow-ups
FSTATE = os.path.join(STATE, "followup-state.json")


def cmd_followups(a):
    st = jload(FSTATE, {})
    rows = ghj("issue", "list", "-R", REPO, "--state", "open", "--limit", "600", "--search", f"commenter:{me()}",
               "--json", "number,title,labels,comments,author")
    out = []
    for i in rows:
        cs = i["comments"]
        mine = [k for k, c in enumerate(cs) if c["author"]["login"] == me() and is_triage(c["body"])]
        if not mine:
            continue
        after = [c for c in cs[mine[-1] + 1:] if c["author"]["login"] not in BOTS | {me()}]
        if not after or st.get(str(i["number"])) == after[-1]["createdAt"]:
            continue
        out.append({"number": i["number"], "title": i["title"][:70], "last_reply_at": after[-1]["createdAt"],
                    "maintainer_replied": any(c.get("authorAssociation") in CFG["maintainer_associations"] for c in after),
                    "has_file": any(ATT.search(c["body"] or "") for c in after), "replies": [{"by": c["author"]["login"], "body": c["body"][:700]} for c in after]})
    out.sort(key=lambda x: -x["number"])
    jsave(os.path.join(STATE, "followups.json"), out)
    for o in out:
        say(f"#{o['number']} {o['title']} | {len(o['replies'])} repl{'y' if len(o['replies']) == 1 else 'ies'}" + (" | FILE" if o["has_file"] else "")
            + (" | maintainer replied: read it, follow their lead" if o["maintainer_replied"] else ""))
    say(f"{len(out)} follow-up(s) on threads you own -> state/followups.json")


def non_latin_share(s):
    """Share of letters outside Latin script (CJK, Cyrillic, Arabic, ...): a reply in another language."""
    letters = [ch for ch in re.sub(r"`[^`]*`|https?://\S+|> .*", "", s or "") if ch.isalpha()]
    return sum(1 for ch in letters if ord(ch) > 0x024F) / len(letters) if letters else 0.0


def followup_entry(n):
    e = next((r for r in jload(os.path.join(STATE, "followups.json"), []) if r["number"] == n), None)
    if not e:
        sys.exit(f"#{n} is not in state/followups.json: run `followups` first")
    return e


def cmd_reply(a):
    e = followup_entry(a.n)
    text = open(a.file, encoding="utf-8").read().strip()
    tr = open(a.translation, encoding="utf-8").read().strip() if a.translation else ""
    v = [x for x in lint_comment(text, a.by, jload(os.path.join(CASES, f"{a.n}.json")), translation=tr) if x["severity"] == "block"]
    if len(text) > CFG["comment_limit"]["reply"]:
        v.append({"rule": "T03", "severity": "block", "message": f"reply is {len(text)} chars (limit {CFG['comment_limit']['reply']})"})
    theirs = " ".join(r.get("body", "") for r in e.get("replies") or [])
    if non_latin_share(theirs) > 0.3 and not (tr and a.language):
        v.append({"rule": "L03", "severity": "block", "message": "they did not write in English: add --translation F --language \"<language>\" (the same reply in their language)"})
    if tr and a.language:
        text = f"{text}\n\n**({a.language})** {tr}"
    if v:
        show(v)
        sys.exit("REJECTED: fix the reply")
    d = issue_live(a.n)
    if d["state"] != "OPEN" or {l["name"] for l in d["labels"]} & set(CFG["skip_labels"]):
        sys.exit("issue is closed or carries a skip label now: no reply")
    if [c for c in d["comments"] if c["createdAt"] > e["last_reply_at"] and c["author"]["login"] not in BOTS]:
        sys.exit("newer comments than the follow-up list: run `followups` again and re-read the thread")
    post_comment(a.n, text, d=d, by=a.by, extra={"kind": "followup", "why": a.why})
    st = jload(FSTATE, {})
    st[str(a.n)] = e["last_reply_at"]
    jsave(FSTATE, st)


def cmd_handled(a):
    e = followup_entry(a.n)
    st = jload(FSTATE, {})
    st[str(a.n)] = e["last_reply_at"]
    jsave(FSTATE, st)
    jl_append(os.path.join(LOGS, "followups-handled.jsonl"), {"ts": now(), "issue": a.n, "why": a.why})
    say(f"#{a.n} follow-up marked handled: {a.why}")


# ---------------------------------------------------------------- corrections (kit repo issues about your account)
def cmd_corrections(a):
    if a.reply:
        body = open(a.file, encoding="utf-8").read().strip()
        gh("issue", "comment", str(a.reply), "-R", KIT_REPO, "--body-file", "-", inp=body)
        return say(f"replied on {KIT_REPO}#{a.reply}; the orchestrator verifies and closes it")
    rows = ghj("issue", "list", "-R", KIT_REPO, "--state", "open", "--label", "correction", "--search", f"{me()} in:body,title",
               "--json", "number,title,createdAt,url,comments")
    for r in rows:
        replied = any(c["author"]["login"] == me() for c in r["comments"])
        say(f"{KIT_REPO}#{r['number']} {r['title'][:80]}  {'(you replied; waiting for the orchestrator)' if replied else 'OPEN: fix the comment in place, then reply'}  {r['url']}")
    say(f"{len(rows)} open correction(s) naming {me()}. Check every {CFG['correction_check_h']} h.")


# ---------------------------------------------------------------- audit (orchestrator sampling)
def split_translation(body):
    """A posted comment is text + '\n\n**(<language>)** <translation>' (as `submit` builds it): lint the two apart."""
    m = re.search(r"\n\n\*\*\([^\n]+?\)\*\* ", body)
    return (body[:m.start()].strip(), body[m.end():].strip()) if m else (body, "")


def cmd_audit(a):
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=a.hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    found = []
    for page in range(1, 6):
        rows = ghj("api", f"repos/{REPO}/issues/comments?since={since}&per_page=100&page={page}")
        found += [c for c in rows if is_triage(c["body"]) and c["created_at"] >= since
                  and (not a.mine or c["user"]["login"] == me())]
        if len(rows) < 100:
            break
    by = {}
    for c in found:
        by.setdefault(c["user"]["login"], []).append(c)
    say(f"{len(found)} kit/triage comments since {since}, {len(by)} account(s)")
    for acct, cs in sorted(by.items()):
        bad_sig = [c for c in cs if signer(c["body"]) and signer(c["body"]) != acct]
        unmarked = [c for c in cs if not MARKER_RE.search(c["body"])]
        say(f"\n== {acct}: {len(cs)} comment(s) | signature mismatch {len(bad_sig)} | no kit marker {len(unmarked)}")
        for c in bad_sig:
            say(f"   SIGNATURE: posted by {acct}, signed '{signer(c['body'])}': {c['html_url']}")
        for c in random.sample(cs, min(a.per, len(cs))):
            body = MARKER_RE.sub("", HEADER_RE.sub("", c["body"], count=1)).strip()
            body, tr = split_translation(body)
            v = [x for x in lint_comment(body, "repro", translation=tr) if x["rule"] not in ("T03",)]
            say(f"   sample {c['html_url']}" + ("" if not v else "  lints: " + ", ".join(f"{x['rule']}[{x['severity']}]" for x in v)))
    if a.mine:
        say("\nSelf-assessment: read each sample against its thread (docs/verify.md) in a fresh context. A wrong comment: `fix N`. "
            "A mistake the kit should have caught: `corrective` here, then a `kit-gap` issue or a PR on the kit repo (SOLO.md).")
    else:
        say("\nRead each sample against its thread (docs/verify.md). A mistake: open a `correction` issue on the kit repo naming the account.")


# ---------------------------------------------------------------- corrective / retrolint / bump
def cmd_corrective(a):
    data = jload(RULES)
    if any(r["id"] == a.id for r in data["rules"]):
        sys.exit(f"rule {a.id} already exists")
    re.compile(a.pattern)
    data["rules"].append({"id": a.id, "profile": a.profile, "severity": a.severity, "pattern": a.pattern, "message": a.message})
    jsave(RULES, data)
    with open(LESSONS, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"\n## {now()[:10]} #{a.issue}: rule {a.id}\n{a.lesson}\n")
    say(f"added {a.id} and a lesson line. Re-linting what this machine posted:")
    cmd_retrolint(a)


def cmd_retrolint(a):
    hits = 0
    for r in jl_read(POSTED):
        for x in lint_comment(r["text"], r.get("by", "first")):
            if x["severity"] == "block":
                hits += 1
                say(f"  #{r['issue']} {x['rule']}: {x['message'][:100]}  {r['url']}")
    say(f"{hits} block(s) across {len(jl_read(POSTED))} posted comment(s)")


def cmd_bump(a):
    """Orchestrator, at merge: next minor version + one CHANGELOG line. Minor is a counter, two digits: 2.01 ... 2.99, then 2.100."""
    major, minor = VERSION.split(".")
    new = f"{major}.{int(minor) + 1:02d}"
    open(os.path.join(ROOT, "VERSION"), "w", encoding="utf-8", newline="\n").write(new + "\n")
    cl = os.path.join(ROOT, "CHANGELOG.md")
    lines = open(cl, encoding="utf-8").read().split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith("- v"))
    lines.insert(i, f"- v{new} ({now()[:10]}): {a.line}")
    open(cl, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    say(f"v{VERSION} -> v{new}; CHANGELOG line added")


# ---------------------------------------------------------------- appcheck / cluster / rootcause
def newest_cli():
    env = os.environ.get("SOLIDCRAFT_CLI")
    if env and os.path.exists(env):
        return env
    import glob
    found = glob.glob(os.path.join(ROOT, "builds", "upstream-*", "**", "solidcraft-cli*"), recursive=True)

    def ver(p):
        m = re.search(r"upstream-(\d+)\.(\d+)\.(\d+)", p)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    return max(found, key=ver) if found else None


def cmd_appcheck(a):
    cli = newest_cli()
    words = [w.lower() for w in a.keyword.split()]
    if cli:
        ver = subprocess.run([cli, "--version"], capture_output=True, text=True).stdout.strip()
        out = subprocess.run([cli, "commands"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        hits = []
        for b in re.split(r"\n\s*\{\s*\n", out):
            if all(w in b.lower() for w in words):
                cid, label = re.search(r'"id":\s*"([^"]+)"', b), re.search(r'"label":\s*"([^"]+)"', b)
                sc = re.search(r'"shortcut":\s*"([^"]*)"', b)
                if cid:
                    hits.append(f"{cid.group(1)} | {label.group(1) if label else ''}" + (f" | shortcut {sc.group(1)}" if sc and sc.group(1) else ""))
        say(f"{ver}: {len(hits)} command(s) mention {a.keyword!r}")
        for h in hits[:12]:
            say("  " + h)
    else:
        say("no solidcraft-cli found (put the official build in builds/upstream-<version>/ or set SOLIDCRAFT_CLI): command list not checked")
    ui = [l.strip() for l in open(os.path.join(ROOT, "docs", "ui-features.md"), encoding="utf-8") if l.startswith("- ") and all(w in l.lower() for w in words)]
    say(f"{len(ui)} line(s) in docs/ui-features.md (UI features that are not commands)")
    for l in ui[:6]:
        say("  " + l[:200])
    say("A command list cannot prove a UI option absent. Put what you checked and what it showed in `app_check`.")


def cmd_cluster(a):
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=a.hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = ghj("issue", "list", "-R", REPO, "--state", "open", "--limit", "200", "--search", f"Crash: SolidCraft in:title created:>={since}", "--json", "number,title")
    by = {}
    for r in rows:
        m = re.search(r"SolidCraft (\d+\.\d+\.\d+)", r["title"])
        by.setdefault(m.group(1) if m else "?", []).append(r["number"])
    for v, ns in sorted(by.items(), key=lambda kv: -len(kv[1])):
        say(f"{v}: {len(ns)} crash report(s) in {a.hours:g} h: " + ", ".join(f"#{x}" for x in sorted(ns)))
    say("3 or more on one version is a likely regression: one note to the orchestrator, no per-issue generic request.")


def sgrep(pattern, fixed=True):
    r = subprocess.run(["git", "-C", SRC_REPO, "grep", "-n", "-I"] + (["-F"] if fixed else ["-E"]) + [pattern, "upstream/main", "--", "crates", "apps"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [l for l in r.stdout.splitlines() if l.strip()][:40]


def enclosing_fn(path, line, cache={}):
    if path not in cache:
        cache[path] = subprocess.run(["git", "-C", SRC_REPO, "show", f"upstream/main:{path}"], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace").stdout.splitlines()
    for i in range(min(line, len(cache[path])) - 1, -1, -1):
        m = re.match(r"\s*(?:pub(?:\([a-z]+\))?\s+)?(?:async\s+)?fn\s+(\w+)", cache[path][i])
        if m:
            return m.group(1), i + 1
    return None, None


def cmd_rootcause(a):
    if a.fetch:
        subprocess.run(["git", "-C", SRC_REPO, "fetch", "upstream", "main", "--quiet"])
    head = subprocess.run(["git", "-C", SRC_REPO, "log", "-1", "--format=%h %cI", "upstream/main"], capture_output=True, text=True).stdout.strip()
    say(f"searching upstream/main ({head or 'no checkout: set SOLIDCRAFT_SRC'}); `--fetch` to update first")
    frags = sorted((f.strip() for f in re.split(r"[:;(),]|\s-\s", a.text) if len(f.strip()) >= 14), key=len, reverse=True)
    seen = set()
    for fr in frags[:3] + ([f'"{a.cmd}"'] if a.cmd else []):
        hits = sgrep(fr) or (sgrep(re.sub(r"\s*\d[\d.,]*\s*", " ", fr).strip()) if re.search(r"\d", fr) else [])
        say(f"\n-- '{fr[:70]}': {len(hits)} hit(s)")
        for h in hits[:6]:
            m = re.match(r"upstream/main:(.+?):(\d+):(.*)", h)
            if m and (m.group(1), m.group(2)) not in seen:
                seen.add((m.group(1), m.group(2)))
                fn, fl = enclosing_fn(m.group(1), int(m.group(2)))
                say(f"   {m.group(1)}:{m.group(2)}  in fn {fn} (line {fl}): {m.group(3).strip()[:110]}")
    say("\nRead the function before writing 'Root cause (confirmed|likely|unknown)' (docs/reproducing.md).")


# ---------------------------------------------------------------- status / selftest
def cmd_status(a):
    q = [jload(os.path.join(QUEUE, f)) for f in os.listdir(QUEUE) if f.endswith(".json")]
    from collections import Counter
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    for r in sorted(q, key=lambda r: (order.get(r["priority"], 9), -r["issue"]))[: a.limit]:
        say(f"{r['line_item']}  [{r['status']}]")
    say(f"kit v{VERSION} | account {me()} | mode {mode()} | queue: {dict(Counter(r['status'] for r in q))} | posted (this machine): {len(jl_read(POSTED))}")


def cmd_selftest(a):
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_kit
    sys.exit(test_kit.main())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *args):
        p = sp.add_parser(name)
        for flags, kw in args:
            p.add_argument(*flags, **kw)
        p.set_defaults(fn=fn)

    N = (["n"], dict(type=int))
    BY = (["--by"], dict(default="first", choices=sorted(PROFILES)))
    add("inbox", cmd_inbox, (["--limit"], dict(type=int, default=10)), (["--hours"], dict(type=float, default=96)))
    add("claim", cmd_claim, N)
    add("unclaim", cmd_unclaim, N, (["--why"], {}))
    add("note", cmd_note, N, (["--reproducing"], dict(required=True, metavar="VERSION")))
    add("next", cmd_next, (["--limit"], dict(type=int, default=10)), (["--hours"], dict(type=float, default=96)))
    add("case", cmd_case, N, (["--q"], dict(action="append")), (["--no-images"], dict(action="store_true", dest="no_images")))
    add("prompt", cmd_prompt, N)
    add("decide", cmd_decide, N)
    add("submit", cmd_submit, N, BY, (["--comment"], {}), (["--translation"], {}),
        (["--result"], dict(choices=sorted(REPRO_ONLY))), (["--p0"], dict(help="force P0, with the reason")))
    add("lint-text", cmd_lint_text, (["file"], {}), BY)
    add("post", cmd_post, N, (["--approve"], dict(action="store_true")))
    add("fix", cmd_fix, N, (["--file"], dict(required=True)), (["--why"], dict(required=True)), BY, (["--comment-id"], dict(type=int, dest="comment_id")))
    add("followups", cmd_followups)
    add("reply", cmd_reply, N, (["--file"], dict(required=True)), (["--why"], dict(required=True)), BY,
        (["--translation"], {}), (["--language"], {}))
    add("handled", cmd_handled, N, (["--why"], dict(required=True)))
    add("corrections", cmd_corrections, (["--reply"], dict(type=int)), (["--file"], {}))
    add("audit", cmd_audit, (["--hours"], dict(type=float, default=6)), (["--per"], dict(type=int, default=3)),
        (["--mine"], dict(action="store_true")))
    add("corrective", cmd_corrective, (["--issue"], dict(required=True)), (["--id"], dict(required=True)), (["--pattern"], dict(required=True)),
        (["--message"], dict(required=True)), (["--lesson"], dict(required=True)), (["--severity"], dict(default="block", choices=["block", "warn"])),
        (["--profile"], dict(default="all", choices=["first", "repro", "all"])))
    add("retrolint", cmd_retrolint)
    add("bump", cmd_bump, (["line"], {}))
    add("maintainers", cmd_maintainers, (["--refresh"], dict(action="store_true")))
    add("release", cmd_release)
    add("appcheck", cmd_appcheck, (["keyword"], {}))
    add("cluster", cmd_cluster, (["--hours"], dict(type=float, default=30)))
    add("rootcause", cmd_rootcause, (["text"], {}), (["--cmd"], {}), (["--fetch"], dict(action="store_true")))
    add("status", cmd_status, (["--limit"], dict(type=int, default=30)))
    add("selftest", cmd_selftest)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
