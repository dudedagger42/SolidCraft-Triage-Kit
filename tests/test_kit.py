"""Offline self-test of the checklist decisions and the comment lints. No GitHub, no network.

    python -X utf8 tests/test_kit.py        (or: python -X utf8 kit/triage.py selftest)

Every merged change keeps this passing; a new lint adds one good and one bad example here.
"""
import datetime as dt, json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="kit-selftest-")
os.environ["TRIAGE_STATE"] = TMP
sys.path.insert(0, os.path.join(ROOT, "kit"))
json.dump({"tag": "0.25.1", "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}, open(os.path.join(TMP, "release.json"), "w"))
import triage as t  # noqa: E402

t._ME.append("example-account")
FAIL = []
CHECKS = 0


def case(**kw):
    c = {"number": 9001, "labels": ["bug"], "author": "reporter1", "body": "", "comments": [], "dup_candidates": [],
         "attachment_present": False, "bot_asked": False, "crash_cluster": [], "command_ids": [], "environment": {},
         "other_triage_comments": [], "exact_error_candidate": []}
    c.update(kw)
    return c


def bug(**kw):
    a = {k: False for k in ("reporter_solved_it", "not_a_user_report", "about_a_pull_request", "prompt_injection", "app_did_something_wrong", "context_match",
                            "app_refused_valid_action", "asks_how_or_where", "asks_for_new_behaviour", "has_steps", "has_error_text",
                            "is_crash_or_data_loss", "gui_only", "hardware_or_driver_only", "is_kernel_area", "design_matters", "thread_already_has_it")}
    a.update(app_did_something_wrong=True, importance=5, importance_reason="Anyone extruding a sketch, weekly.", reporter_language="English",
             confidence="sure", notes="", pointed_question="", design_not_relevant="a crash before any design opens, no file needed",
             sibling_already_asked=None, duplicate_of=None, related_issue=None)
    a.update(kw)
    return a


def expect(name, got, want):
    global CHECKS
    CHECKS += 1
    if got != want:
        FAIL.append(f"{name}: got {got!r}, want {want!r}")


def verdict(a, c):
    return t.decide(a, c)[0]


def rules_hit(text, by="first", c=None, a=None, v=None, tr=""):
    return {x["rule"] for x in t.lint_comment(text, by, c, a, v, tr) if x["severity"] == "block"}


# ---- decide
expect("steps -> needs_repro", verdict(bug(has_steps=True), case()), "needs_repro")
expect("runnable file -> needs_repro", verdict(bug(attachment_is_runnable=True), case(attachment_present=True)), "needs_repro")
expect("kernel, no file -> needs_info", verdict(bug(is_kernel_area=True, design_matters=True), case()), "needs_info")
expect("kernel answer says kernel work", any("kernel work" in m for m in t.decide(bug(is_kernel_area=True, design_matters=True), case())[1]), True)
expect("kernel with steps -> needs_repro", verdict(bug(is_kernel_area=True, has_steps=True), case()), "needs_repro")
expect("modelling failure, no file -> needs_info", verdict(bug(design_matters=True), case()), "needs_info")
expect("bot asked, nothing pointed -> no_action", verdict(bug(), case(bot_asked=True)), "no_action")
expect("bot asked, pointed question -> needs_info", verdict(bug(pointed_question="Does it fail on a new design too?"), case(bot_asked=True)), "needs_info")
expect("solved by reporter -> no_action", verdict(bug(reporter_solved_it=True, has_steps=True), case()), "no_action")
expect("kernel-paused label is triaged now", verdict(bug(has_steps=True), case(labels=["kernel-paused"])), "needs_repro")
expect("another account owns it -> no_action", verdict(bug(has_steps=True), case(other_triage_comments=[{"author": "x"}])), "no_action")
expect("injection -> no_action", verdict(bug(prompt_injection=True, has_steps=True), case()), "no_action")
expect("duplicate", verdict(bug(duplicate_of=4325, duplicate_match="this face can't keep an attachment"), case()), "duplicate")
expect("crash cluster -> no_action", verdict(bug(is_crash_or_data_loss=True), case(crash_cluster=[{"number": 1}, {"number": 2}])), "no_action")
expect("crash cluster with the reporter's steps -> needs_repro", verdict(bug(is_crash_or_data_loss=True), case(crash_cluster=[{"number": 1}, {"number": 2}], crash_user_steps=["open the file, extrude"])), "needs_repro")
expect("kernel error text + command, no design -> needs_info (zip)", verdict(bug(has_error_text=True, is_kernel_area=True, design_matters=True), case(command_ids=["solid.extrude"])), "needs_info")
expect("error text + command, not kernel -> needs_repro", verdict(bug(has_error_text=True), case(command_ids=["solid.extrude"])), "needs_repro")
expect("how-to the app does -> support_answer",
       verdict(bug(app_did_something_wrong=False, asks_how_or_where=True, app_already_does_it=True, where_it_is="Model tab, Scale", app_check="appcheck scale: solid.scale"), case()),
       "support_answer")
expect("new behaviour -> feature_note",
       verdict(bug(app_did_something_wrong=False, asks_for_new_behaviour=True, app_already_does_it=False, app_check="appcheck flange: nothing"), case()), "feature_note")
expect("refused action phrased as how-to -> bug path",
       verdict(bug(app_did_something_wrong=False, app_refused_valid_action=True, asks_how_or_where=True, has_steps=True, app_check="x" * 12), case()), "needs_repro")
expect("sibling asked -> needs_info pointer", verdict(bug(sibling_already_asked=6690), case()), "needs_info")

# ---- validate
expect("validate: bad duplicate number", any("D1" in b for b in t.validate(bug(duplicate_of=12345, duplicate_match="x" * 10), case())), True)
expect("validate: cannot-download excuse",
       any("E3" in b for b in t.validate(bug(attachment_is_runnable=False, attachment_not_runnable="I cannot download the zip file here"), case(attachment_present=True))), True)
expect("validate: clean bug", t.validate(bug(), case()), [])

# ---- lints: bad examples must block with the named rule
C = case(environment={"version": "0.25.1", "os": "Windows 11", "renderer": "GPU, RTX 3060"})
bad = [
    ("S01", "**Triage by dudedagger42:** Which command failed?"),
    ("R034", "Verified by dudedagger42. Which command failed?"),
    ("R002", "Thanks for the report. Which command failed?"),
    ("R001", "We will look at it. Which command failed?"),
    ("R003", "I reproduced it on 0.25.1."),
    ("R005", "As a workaround, try a smaller radius."),
    ("R008", "I can't download the zip file. Could you paste the error?"),
    ("R009", "Could you attach the .solidcraft file?"),
    ("R026", "This is logged as a feature request."),
    ("R029", "Could you share more details?"),
    ("R030", "This looks like a P1 to me."),
    ("R033", "Could not reproduce here."),
    ("R022", "Which SolidCraft version are you on?"),
    ("Q01", "Which command failed? And which face?"),
    ("G01", "Which the the command failed?"),
    ("G03", "Which command failed and"),
    ("V01", "Does it still happen on 0.24.1?"),
    ("P01", r"Open C:\Users\someone\Desktop\part.zip and check it."),
    ("M01", "@somemaintainer, which command failed?"),
    ("R017", "The report says Extrude fails. Which profile?"),
]
for rule, text in bad:
    hit = rules_hit(text, c=C, a=bug(), v="needs_info")
    expect(f"lint {rule}: {text!r}", rule in hit, True)

good = [
    ("Which step fails: the Extrude itself, or the Fillet after it?", False),
    ("Could you zip the design (right-click the .solidcraft file, Compress to ZIP) and drag the .zip into a comment?", True),
    ("Does it still happen on the current release, 0.25.1?", False),
]
for text, dm in good:
    hit = rules_hit(text, c=C, a=bug(design_matters=dm), v="needs_info")
    expect(f"good text: {text!r}", hit, set())

# kernel and repro lints
expect("K01: kernel framing on a non-kernel bug", "K01" in rules_hit("This is kernel work in Solidcore. Which face?", c=C, a=bug(), v="needs_info"), True)
expect("R027: says kernel work is paused", "R027" in rules_hit("This is kernel work, paused upstream (#3992).", c=C, a=bug(is_kernel_area=True), v="kernel_describe"), True)
expect("Z01: modelling failure without zip", "Z01" in rules_hit("Which profile did you extrude?", c=C, a=bug(design_matters=True), v="needs_info"), True)
expect("Z01 yields to Z02 on a GUI report", "Z01" in rules_hit("Which element did you edit?", c=C, a=bug(design_matters=True, gui_only=True), v="needs_info"), False)
expect("Z02: zip on a crash", "Z02" in rules_hit("Could you zip the design and drag the .zip into a comment?", c=C, a=bug(is_crash_or_data_loss=True), v="needs_info"), True)
rep = "Reproduced on 0.25.1: solid.fillet radius 2 fails with 'no result'; radius 1 works. Root cause (likely): crates/kernel/src/blend.rs `fillet_edges`, the rolling ball leaves the face."
expect("repro clean", rules_hit(rep, by="repro", c=C, a={}, v="reproduced"), set())
expect("R039: needs-to-be-reproduced is not a claim", "R039" in rules_hit(t.CANT_RUN + " The report is from Linux.", by="repro", c=C, a={}, v="could_not_test"), False)
expect("R039: claim without build", "R039" in rules_hit("Reproduced it. Root cause (unknown): ruled out a.", by="repro", c=C, a={}, v="reproduced"), True)
expect("X01: no root cause", "X01" in rules_hit("Reproduced on 0.25.1: it fails.", by="repro", c=C, a={}, v="reproduced"), True)
expect("X03: could_not_test wording", "X03" in rules_hit("No display here.", by="repro", c=C, a={}, v="could_not_test"), True)
expect("L01: missing translation", "L01" in rules_hit("Which step fails?", c=C, a=bug(reporter_language="French"), v="needs_info"), True)

# ---- wrap: header from the account, marker carries the version
w = t.wrap("Which step fails?")
expect("wrap header", w.startswith("**Triage by example-account:** Which step fails?"), True)
expect("wrap marker", f"<!-- solidcraft-triage-kit v{t.VERSION} https://github.com/{t.KIT_REPO} -->" in w, True)
expect("marker parsed", bool(t.MARKER_RE.search(w)), True)
t.CFG["shard"] = [1, 2]
expect("shard keeps odd", [n for n in (6400, 6401, 6402, 6403) if t.in_shard(n)], [6401, 6403])
t.CFG.pop("shard")
expect("no shard keeps all", t.in_shard(6400), True)
for row in ({"issue": 6400, "event": "claim"}, {"issue": 6401, "event": "claim"}, {"issue": 6401, "event": "unclaim"}):
    t.jl_append(os.path.join(t.LOGS, "claims.jsonl"), row)
expect("claimed here", [n for n in (6400, 6401, 6402) if t.claimed_here(n)], [6400])
r = t.wrap("Does 0.25.1 still fail?", head=False)
expect("reply has no header", r.startswith("Does 0.25.1 still fail?") and not t.HEADER_RE.search(r), True)
expect("reply still marked as triage", t.is_triage(r), True)
expect("old marker parsed", bool(t.MARKER_RE.search("<!-- solidcraft-triage-kit v2.0 -->")), True)
expect("note status parsed", t.MARKER_RE.search(t.wrap("Reproducing on 0.25.1.", status="reproducing")).group(2), "reproducing")

# ---- translations: a posted comment's appended translation is linted apart (#7678 false positives)
zh = "A rectangular pattern taking minutes is kernel work. Does it still take minutes with only Extrude2 patterned?"
posted = zh + "\n\n**(Chinese (Simplified))** 阵列运算属于内核计算。是否仍然要等几分钟？"
body, tr = t.split_translation(posted)
expect("split: text", body, zh)
expect("split: translation", tr.endswith("？"), True)
expect("R027: plain kernel line with a translation passes", "R027" in rules_hit(posted, by="repro", c=C, a={}, v="needs_info"), False)
expect("R027: still fires with no question", "R027" in rules_hit("Kernel work is paused upstream (#3992).", by="repro", c=C, a={}, v="kernel_describe"), True)
expect("G03: full-width question mark ends a sentence", "G03" in rules_hit("是否仍然？", by="repro", c=C, a={}, v="needs_info"), False)

# ---- M02: never ask for a recording the thread already has (#6408 dry run); L03: replies in the reporter's language
vid = dict(C, body="Steps: edit a face. https://github.com/user-attachments/assets/e5f60e10-66cf-49c3-a0c5-f9b2fe5452f7", comments=[])
expect("M02: recording already attached", "M02" in rules_hit("Which element did you edit? A short recording of the bodies would show it.", c=vid, a=bug(), v="needs_info"), True)
expect("M02: no media in thread", "M02" in rules_hit("Which element did you edit? A short recording of the bodies would show it.", c=dict(C, body="x", comments=[]), a=bug(), v="needs_info"), False)
expect("non-Latin reply", t.non_latin_share("cache/thumbnail.png 已存缩略图，会在每次保存时自动更新吗") > 0.3, True)
expect("English reply", t.non_latin_share("Does it update on every save?") > 0.3, False)

# ---- dry run: every GitHub write is recognised
expect("write: reaction", t.gh_is_write(("api", "repos/x/issues/1/reactions", "-X", "POST", "-f", "content=eyes")), True)
expect("write: implicit POST", t.gh_is_write(("api", "repos/x/issues/1/comments", "-f", "body=x")), True)
expect("write: issue comment", t.gh_is_write(("issue", "comment", "5", "-R", "x")), True)
expect("read: api GET", t.gh_is_write(("api", "repos/x/issues/1/comments")), False)
expect("read: issue list", t.gh_is_write(("issue", "list", "-R", "x")), False)
expect("signer", t.signer(w), "example-account")
expect("note marker", "status=reproducing" in t.wrap("Reproducing on 0.25.1.", status="reproducing"), True)


# ---- MULTI.md 6a: could not run it -> reproducer wanted; a listed reproducer claims and posts the one other comment
def cmt(who, body, at):
    return {"author": {"login": who}, "body": body, "createdAt": at, "authorAssociation": "NONE"}


old_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
t1 = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
t2 = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
want = cmt("other-account", "**Triage by other-account:** Steps are clear. " + t.CANT_RUN + "\n\n" + t.MARKER.replace(" -->", " status=repro_wanted -->"), t1)
expect("repro wanted parsed", t.repro_wanted([want])[1], None)
expect("plain triage is not repro wanted", t.repro_wanted([cmt("other-account", t.wrap("Which file?"), t1)]), None)
repro = cmt("example-account", t.wrap("Reproduced on 0.25.1: it crashes."), t2)
expect("reproducer's comment found", t.repro_wanted([want, repro])[1]["author"]["login"], "example-account")
t.linked_prs, t.maintainers = (lambda n: []), (lambda: set())
issue = {"state": "OPEN", "labels": [], "author": {"login": "reporter1"}, "createdAt": old_ago, "comments": [want]}
t.reactions = lambda n, content: [{"user": {"login": "other-account"}, "created_at": t1, "id": 1}] if content == "rocket" else []
t.eyes = lambda n: []
st = t.claim_state(9001, issue)
expect("repro wanted: free for a reproducer", (st["ok"], st["reason"]), (True, "free (reproducer wanted)"))
t.eyes = lambda n: [{"user": {"login": "example-account"}, "created_at": t2, "id": 2}]
expect("repro wanted: reproducer's 👀 holds it", t.claim_state(9001, issue)["mine"], True)
t.eyes = lambda n: [{"user": {"login": "example-account"}, "created_at": old_ago, "id": 2}]
expect("repro wanted: a 👀 from before the ask does not count", t.claim_state(9001, issue)["mine"], None)
st = t.claim_state(9001, dict(issue, comments=[want, repro]))
expect("after the reproduction the reproducer owns it", (st["holder"], st["mine"]), ("example-account", True))
t.REPRODUCERS = os.path.join(TMP, "reproducers.json")
json.dump({"reproducers": [{"account": "a1", "platforms": ["windows"], "ping": True}, {"account": "a2", "platforms": ["linux"], "ping": True},
                           {"account": "a3", "platforms": ["windows", "linux"], "ping": False}, {"account": "example-account", "platforms": ["windows"], "ping": True}]},
          open(t.REPRODUCERS, "w"))
expect("pings: OS match, opted in, never yourself", t.pick_reproducers(4, "Windows 11", {"example-account"}), ["a1"])
expect("pings: linux", t.pick_reproducers(4, "Ubuntu 24.04", {"example-account"}), ["a2"])
expect("kit's own list parses", all("account" in r for r in json.load(open(os.path.join(ROOT, "reproducers.json"), encoding="utf-8"))["reproducers"]), True)


# ---- claims on one account: expired 👀 of this account are taken over; an issue the account opened can be claimed
import argparse  # noqa: E402

ago = lambda m: (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%SZ")
CALLS, POST_STATUS, EYES = [], ["HTTP/2.0 201 Created"], {}
saved = (t.gh, t.eyes, t.issue_live, t.time.sleep)


def fake_gh(*args, inp=None):
    if t.dry_run() and t.gh_is_write(args):
        return ""
    CALLS.append(args)
    if "DELETE" in args:
        n, rid = args[1].split("/")[-3], int(args[1].split("/")[-1])
        EYES[int(n)] = [r for r in EYES.get(int(n), []) if r["id"] != rid]
    elif "POST" in args:
        n = int(args[2].split("/")[-2])
        if POST_STATUS[0].endswith("201 Created"):
            EYES.setdefault(n, []).append({"user": {"login": "example-account"}, "created_at": ago(0), "id": 900 + len(CALLS)})
        return POST_STATUS[0] + "\n\n{}"
    return ""


ISSUES = {}
t.gh, t.eyes, t.time.sleep = fake_gh, (lambda n: list(EYES.get(n, []))), (lambda s: None)
t.issue_live = lambda n: ISSUES[n]


def eye(who, at, rid):
    return {"user": {"login": who}, "created_at": at, "id": rid}


def run_claim(n):
    CALLS.clear()
    try:
        t.cmd_claim(argparse.Namespace(n=n))
        return "ok"
    except SystemExit as e:
        return str(e)


def last_events(n):
    return [r["event"] for r in t.jl_read(os.path.join(t.LOGS, "claims.jsonl")) if r.get("issue") == n]


# 3: the issue author is this account (#11997): its own 👀 is a claim; another author's 👀 still is not
ISSUES[7101] = {"state": "OPEN", "labels": [], "author": {"login": "example-account"}, "createdAt": old_ago, "comments": []}
EYES[7101] = [eye("example-account", ago(2), 1)]
st = t.claim_state(7101, ISSUES[7101])
expect("own issue: own 👀 holds it", (st["holder"], st["mine"]), ("example-account", True))
EYES[7101] = []
expect("own issue: claim keeps its reaction", (run_claim(7101), len(EYES[7101]), last_events(7101)[-1]), ("ok", 1, "claim"))
ISSUES[7102] = {"state": "OPEN", "labels": [], "author": {"login": "reporter1"}, "createdAt": old_ago, "comments": []}
EYES[7102] = [eye("reporter1", ago(2), 1)]
expect("author's 👀 (another account) is not a claim", t.claim_state(7102, ISSUES[7102])["holder"], None)

# 2: a peer worker's 👀 (same account) older than the expiry, no comment after it: taken over, with a log line
EYES[7102] = [eye("example-account", ago(140), 5)]
st = t.claim_state(7102, ISSUES[7102])
expect("expired own 👀: free, stale", (st["ok"], st["mine"], len(st["own_stale"])), (True, None, 1))
expect("expired own 👀: claim takes it over", run_claim(7102), "ok")
expect("takeover: old 👀 deleted first, then a new one", [c[c.index("-X") + 1] for c in CALLS if "-X" in c], ["DELETE", "POST"])
expect("takeover logged before the claim", last_events(7102)[-2:], ["takeover", "claim"])
expect("takeover: now held here", run_claim(7102), "ok")
expect("takeover: no second reaction", [c for c in CALLS if "POST" in c or "DELETE" in c], [])
EYES[7103] = [eye("example-account", ago(140), 6)]
ISSUES[7103] = dict(ISSUES[7102], comments=[])
POST_STATUS[0] = "HTTP/2.0 200 OK"  # a peer re-added it between our delete and our post
expect("takeover race: a peer re-claimed first", "claimed it a moment ago" in run_claim(7103), True)
POST_STATUS[0] = "HTTP/2.0 201 Created"
EYES[7104] = [eye("example-account", ago(3), 7)]
ISSUES[7104] = dict(ISSUES[7102], comments=[])
expect("a live peer 👀 still refuses", "another worker on this account holds it" in run_claim(7104), True)
ISSUES[7105] = dict(ISSUES[7102], comments=[cmt("example-account", "/note", ago(100))])
EYES[7105] = [eye("example-account", ago(140), 8)]
expect("an old 👀 followed by our comment still holds", t.claim_state(7105, ISSUES[7105])["mine"], True)

# 1: a thread this account owns by comment: a 👀 from before its last comment, or expired after it, does not block
mine_c = cmt("example-account", t.wrap("Which file?"), ago(300))
ISSUES[7106] = dict(ISSUES[7102], comments=[mine_c, cmt("reporter1", "here", ago(60))])
EYES[7106] = [eye("example-account", ago(2900), 9), eye("example-account", ago(30), 10)]
t.jl_append(os.path.join(t.LOGS, "claims.jsonl"), {"ts": ago(400), "issue": 7106, "event": "unclaim"})
st = t.claim_state(7106, ISSUES[7106])
expect("own thread: old 👀 are stale", (st["mine"], st["own_live"], len(st["own_stale"])), (True, [], 2))
expect("own thread: re-claim after unclaim", (run_claim(7106), len(EYES[7106]), last_events(7106)[-2:]), ("ok", 1, ["takeover", "claim"]))
EYES[7107] = [eye("example-account", ago(5), 11)]
ISSUES[7107] = dict(ISSUES[7106])
t.jl_append(os.path.join(t.LOGS, "claims.jsonl"), {"ts": ago(400), "issue": 7107, "event": "claim"})
expect("own thread: a fresh 👀 after our old claim is a peer's", "another worker" in run_claim(7107), True)
EYES[7108] = []
ISSUES[7108] = dict(ISSUES[7106])
os.environ["TRIAGE_DRY_RUN"] = "1"
expect("dry run: no reaction, no log", (run_claim(7108), CALLS, last_events(7108)), ("ok", [], []))
del os.environ["TRIAGE_DRY_RUN"]

# round start: this checkout's own expired claims are released; used or replaced ones are not deleted
for n, m in ((7201, 40), (7202, 40), (7203, 40), (7204, 5)):
    t.jl_append(os.path.join(t.LOGS, "claims.jsonl"), {"ts": ago(m), "issue": n, "event": "claim"})
    ISSUES[n] = dict(ISSUES[7102], comments=[])
EYES[7201] = [eye("example-account", ago(40), 21)]
EYES[7202] = [eye("example-account", ago(40), 22)]
t.jl_append(t.POSTED, {"ts": ago(30), "issue": 7202})
EYES[7203] = [eye("example-account", ago(4), 23)]  # a peer took it over
EYES[7204] = [eye("example-account", ago(5), 24)]
CALLS.clear()
t.release_expired()
expect("round start: expired own claim removed", (EYES[7201], last_events(7201)[-1]), ([], "unclaim"))
expect("round start: a used claim is kept", (len(EYES[7202]), last_events(7202)[-1]), (1, "claim"))
expect("round start: a peer's newer 👀 is kept", (len(EYES[7203]), last_events(7203)[-1]), (1, "unclaim"))
expect("round start: a young claim is kept", (len(EYES[7204]), last_events(7204)[-1]), (1, "claim"))
expect("round start: only claim API calls", {c[0] for c in CALLS}, {"api"})
t.gh, t.eyes, t.issue_live, t.time.sleep = saved


# v2.26: developer work items (the solidcore issues moved in on 2026-11-08) are not inbox reports
WI = lambda who, body: {"author": {"login": who}, "body": body}
expect("work item: listed developer, no report sections", t.is_work_item(WI("bherbruck", "kernel_cases: a case runs past 180 s")), True)
expect("work item: listed developer filing an app report", t.is_work_item(WI("bherbruck", "## Actual behavior" + chr(10) + "Extrude fails")), False)
expect("work item: a user with no sections is still a report", t.is_work_item(WI("reporter1", "it crashes")), False)
expect("work item: no body", t.is_work_item(WI("ChrisNourse", None)), True)

# ---- wake on work: all GitHub reads are fake, including quota and context searches
import contextlib, io, threading, time  # noqa: E402

saved_wake = {k: getattr(t, k) for k in ("ghj", "issue_live", "claim_state", "cmd_claim", "dispatch_run", "open_issues_since")}
saved_cfg = dict(t.CFG)
work_path = os.path.join(TMP, "work.json")
t.maintenance_checked("corrections")
t.maintenance_checked("audit")
NEW, FOLLOW, REPRO, PRS = [], [], [], []
QUOTA = [100]

def wake_ghj(*args, inp=None):
    if args == ("api", "rate_limit"):
        return {"resources": {k: {"remaining": QUOTA[0]} for k in ("core", "search")}}
    if args[:2] == ("pr", "list"):
        return PRS
    if args[:2] == ("issue", "list"):
        if "--author" in args:
            return NEW
        query = args[args.index("--search") + 1]
        if query.startswith("involves:"):
            return FOLLOW + REPRO
        if query.startswith("commenter:"):
            return FOLLOW
        if "still needs to be reproduced" in query:
            return REPRO
        raise AssertionError(args)
    if args[:1] == ("api",) and "comments" in args[1] and "POST" in args:
        return {"id": 123, "html_url": "https://github.com/example/project/issues/1#issuecomment-123"}
    raise AssertionError(args)

def wake_issue(n, **kw):
    d = {"number": n, "title": "Fillet edge fails", "state": "OPEN", "author": {"login": "reporter1"},
         "body": "", "labels": [{"name": "area:kernel"}], "createdAt": ago(30), "comments": [],
         "url": f"https://github.com/{t.REPO}/issues/{n}"}
    d.update(kw)
    return d

t.ghj = wake_ghj
t.open_issues_since = lambda hours: NEW
t.claim_state = lambda n, d=None: {"ok": True, "mine": False, "reason": "free"}
t.issue_live = lambda n: wake_issue(n)
NEW[:] = [wake_issue(8101)]
first = t.waiting_work()
expect("work: new issue waiting", [(r["kind"], r.get("number")) for r in first], [("new", 8101)])
with contextlib.redirect_stdout(io.StringIO()) as printed:
    try:
        t.cmd_work(argparse.Namespace(json=True))
    except SystemExit as e:
        expect("work: exit 0 with work", e.code, 0)
expect("work: machine-readable list", json.loads(printed.getvalue()), first)
expect("work: new issue offered once", t.waiting_work(), [])
expect("dispatch: a prior work check preserves pending launch", t.waiting_work(include_offered=True), first)
NEW.clear()
with contextlib.redirect_stdout(io.StringIO()) as printed:
    try:
        t.cmd_work(argparse.Namespace(json=True))
    except SystemExit as e:
        expect("work: exit 1 with nothing new", e.code, 1)
expect("work: empty JSON list", json.loads(printed.getvalue()), [])
FOLLOW[:] = [wake_issue(8102, comments=[cmt("example-account", t.wrap("Which file?"), ago(20)), cmt(next(iter(t.BOTS)), "bot reply", ago(5))])]
expect("work: bot-only reply ignored", t.waiting_work(), [])
FOLLOW[0]["comments"].append(cmt("reporter1", "Here is the file", ago(1)))
expect("work: person's reply is a follow-up", [r["kind"] for r in t.waiting_work()], ["followup"])
FOLLOW.clear()
REPRO[:] = [wake_issue(8103, comments=[cmt("other-account", t.wrap(t.CANT_RUN + " @example-account", status="repro_wanted"), ago(5))])]
expect("work: reproducer ping", [r["kind"] for r in t.waiting_work()], ["repro"])
REPRO[0]["comments"][0]["body"] = t.wrap(t.CANT_RUN, status="repro_wanted")
expect("work: unaddressed repro request does not wake account", t.waiting_work(), [])
REPRO.clear()
st = t.jload(work_path)
st["audit"] = ago(400)
st["corrections"] = ago(300)
t.jsave(work_path, st)
expect("work: maintenance due", [r["kind"] for r in t.waiting_work()], ["corrections", "audit"])
t.maintenance_checked("audit")
t.maintenance_checked("corrections")

# Ledger: a real post path appends exactly one summary, with cause and links.
c = case(number=8201, title="Fillet edge fails", labels=["area:kernel"], built_at=t.now())
t.jsave(os.path.join(t.CASES, "8201.json"), c)
t.jsave(os.path.join(t.QUEUE, "8201.json"), {"status": "AUTO-POST", "by": "first", "verdict": "needs_info", "priority": "P2",
                                         "answers": {"related_issue": 8101}, "final_comment": "Root cause (likely): edge ordering. Which edge?"})
t.CFG["mode"] = "solo"
t.cmd_post(argparse.Namespace(n=8201, approve=False))
ledger = t.jl_read(os.path.join(TMP, "ledger.jsonl"))
expect("ledger: post appends one line", len(ledger), 1)
expect("ledger: verdict, area, reporter, cause, related", (ledger[0]["verdict"], ledger[0]["area_labels"], ledger[0]["reporter"], ledger[0]["cause"], ledger[0]["related"]),
       ("needs_info", ["area:kernel"], "reporter1", "edge ordering. Which edge?", 8101))
# A no_action decision is memory too, with no GitHub write.
c2 = case(number=8202, title="Already solved", labels=["area:kernel"])
t.jsave(os.path.join(t.CASES, "8202.json"), c2)
t.jsave(os.path.join(t.CASES, "8202.answers.json"), bug(reporter_solved_it=True))
t.cmd_submit(argparse.Namespace(n=8202, by="first", result=None, comment=None, translation=None, p0=None))
expect("ledger: no_action decision", t.jl_read(os.path.join(TMP, "ledger.jsonl"))[-1]["verdict"], "no_action")
FOLLOW[:] = [wake_issue(8203, comments=[cmt("example-account", t.wrap("Which file?"), ago(20)), cmt("reporter1", "Solved", ago(1))])]
rows = t.followup_items()
t.jsave(os.path.join(TMP, "followups.json"), rows)
t.cmd_handled(argparse.Namespace(n=8203, why="Reporter solved it"))
expect("ledger: handled decision", t.jl_read(os.path.join(TMP, "ledger.jsonl"))[-1]["verdict"], "handled")
FOLLOW.clear()

# Context: reporter history, 48-hour area/title matches, old/unrelated exclusions, PRs and UTF-8 byte cap.
t.ledger_append(8301, "duplicate", case(title="Earlier issue", created_at=ago(60)), {"duplicate_of": 8101}, "")
t.ledger_append(8302, "reproduced", case(author="another-reporter", title="Different title", labels=["area:kernel"]), {}, "")
t.ledger_append(8303, "needs_info", case(author="another-reporter", title="Fillet edge problem"), {}, "")
old = dict(t.jl_read(os.path.join(TMP, "ledger.jsonl"))[-1], issue=8304, ts=ago(3000), title="Old same area", area_labels=["area:kernel"])
t.jl_append(os.path.join(TMP, "ledger.jsonl"), old)
PRS[:] = [{"number": 70, "title": "Fix #8301", "body": "", "url": ""}]
pack = open(t.context_pack(8399), encoding="utf-8").read()
expect("context: reporter history with verdict", "/issues/8301 — duplicate" in pack, True)
expect("context: recent area issue with verdict", "/issues/8302 — reproduced" in pack, True)
expect("context: two title words", "/issues/8303 — needs_info" in pack, True)
expect("context: old area issue excluded", "/issues/8304" in pack, False)
expect("context: account's related open PR", "/pull/70" in pack, True)
NEW[:] = [wake_issue(8400 + i, title="界" * 150) for i in range(100)]
pack = open(t.context_pack(8399), encoding="utf-8").read()
expect("context: byte cap", len(pack.encode("utf-8")) <= 2048, True)
NEW.clear()
old_search, old_sleep = t.search, t.time.sleep
t.search, t.time.sleep = (lambda *args: []), (lambda seconds: None)
try:
    t.cmd_case(argparse.Namespace(n=8399, q=None, no_images=True))
finally:
    t.search, t.time.sleep = old_search, old_sleep
built = t.load_case(8399)
expect("case: includes shared context", "Context for #8399" in built["shared_context"], True)
expect("case: context candidates have live state", any(r["number"] == 8301 and r["state"] == "open" for r in built["dup_candidates"]), True)
expect("prompt: includes shared context", "Context for #8399" in t.build_prompt(built), True)
expect("context: yes without link blocked", any("D5" in b for b in t.validate(bug(context_match=True), case())), True)
expect("context: same bug uses existing duplicate verdict", verdict(bug(context_match=True, duplicate_of=8301, duplicate_match="fillet edge"), case()), "duplicate")
expect("context: ledger candidate accepted", t.validate(bug(context_match=True, duplicate_of=8301, duplicate_match="fillet edge"), case(dup_candidates=[{"number": 8301, "kind": "issue", "state": "open"}])), [])
expect("context: same reporter different bug stays related", any("#8301" in m for m in t.decide(bug(context_match=True, related_issue=8301), case())[1]), True)

# Regression: three reports about one command arrive within eleven minutes of a claimed fix.
def same_reporter_claimed_pr_context():
    saved_reports, saved_prs = list(NEW), list(PRS)
    start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    at = lambda seconds: (start + dt.timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
    reports = [wake_issue(n, author={"login": "reporter-a"}, labels=[], createdAt=at(seconds),
                          title=f"Extrude profile fails on design {n}")
               for n, seconds in ((1001, 0), (1002, 600), (1003, 606))]
    # The claim and its open PR predate both later reports; only the PR body names #1001.
    t.jl_append(os.path.join(TMP, "ledger.jsonl"), {
        "ts": at(300), "issue": 1001, "reporter": "reporter-a", "title": reports[0]["title"],
        "created_at": at(0), "area_labels": [], "verdict": "claimed", "claimed_pr": 2001})
    try:
        PRS[:] = [{"number": 2001, "title": "Correct Extrude profile handling", "body": "Fixes #1001",
                   "url": f"https://github.com/{t.REPO}/pull/2001", "state": "OPEN", "author": {"login": t.me()}}]
        for extra_count in (0, 20):
            NEW[:] = reports + [wake_issue(1100 + i, author={"login": "reporter-a"}, labels=[], createdAt=at(-60 * (i + 1)),
                                          title="Another Extrude report with enough detail to fill the context pack " + str(i))
                                for i in range(extra_count)]
            pack = open(t.context_pack(1002, reports[1]), encoding="utf-8").read()
            prefix = f"context: rapid reporter burst with {extra_count} other reports"
            expect(prefix + " keeps open PR", f"- Open PR: https://github.com/{t.REPO}/pull/2001 Correct Extrude profile handling" in pack, True)
            expect(prefix + " keeps claimed sibling", f"- same reporter: https://github.com/{t.REPO}/issues/1001 — claimed:" in pack, True)
            expect(prefix + " keeps later sibling", f"- same reporter: https://github.com/{t.REPO}/issues/1003 — not in ledger:" in pack, True)
            expect(prefix + " stays within byte cap", len(pack.encode("utf-8")) <= 2048, True)
        expect("context: crowded burst exercises truncation", sum(f"/issues/{1100 + i} " in pack for i in range(20)) < 20, True)
    finally:
        NEW[:], PRS[:] = saved_reports, saved_prs


same_reporter_claimed_pr_context()

# Dispatcher: real scheduler, fake agent launches; deterministic simultaneous worker measurement.
LAUNCHES, active, peak = [], [0], [0]
mutex = threading.Lock()
barrier = threading.Barrier(2)

def fake_run(argv, env, item):
    with mutex:
        active[0] += 1
        peak[0] = max(peak[0], active[0])
        LAUNCHES.append((argv, env, item))
    if item.get("number") in (8502, 8503):
        barrier.wait(timeout=5)
    time.sleep(0.01)
    with mutex:
        active[0] -= 1
    return {"issue": item.get("number"), "kind": item["kind"], "exit_code": 0, "duration_s": 0.01, "output_tail": "done"}

CLAIMS = []
def fake_claim(a):
    CLAIMS.append(a.n)
    if a.n == 8501:
        raise SystemExit("held by a peer")

t.cmd_claim, t.dispatch_run = fake_claim, fake_run
# Clear pending work previously offered by the CLI.
t.jsave(work_path, {"new": [], "audit": t.now(), "corrections": t.now(), "audit_posts": len(t.jl_read(t.POSTED))})
NEW[:] = [wake_issue(n) for n in (8501, 8502, 8503, 8504)]
da = argparse.Namespace(run='agent --issue {n} --context "{context}" --kit "{kit}" --work "{work}"', per_issue=True, max=2, dry_run=False)
t.cmd_dispatch(da)
expect("dispatch: refused claim skipped", {x[2]["number"] for x in LAUNCHES}, {8502, 8503, 8504})
expect("dispatch: maximum respected and reached", peak[0], 2)
expect("dispatch: claim before each launch", set(CLAIMS), {8501, 8502, 8503, 8504})
expect("dispatch: context environment", all(x[1]["TRIAGE_N"] == str(x[2]["number"]) and os.path.exists(x[1]["TRIAGE_CONTEXT"]) for x in LAUNCHES), True)
expect("dispatch: one log per launch", len(t.jl_read(os.path.join(t.LOGS, "dispatch.jsonl"))), 3)
NEW.clear()
LAUNCHES.clear()
t.cmd_dispatch(da)
expect("dispatch: nothing waiting means no run", LAUNCHES, [])
os.mkdir(os.path.join(TMP, "dispatch.lock"))
try:
    try:
        t.cmd_dispatch(da)
        FAIL.append("dispatch: second dispatcher bypassed lock")
    except SystemExit as e:
        expect("dispatch: lock blocks second dispatcher", "already running" in str(e), True)
finally:
    os.rmdir(os.path.join(TMP, "dispatch.lock"))
NEW[:] = [wake_issue(8505)]
da.dry_run = True
before = t.jload(work_path)
t.cmd_dispatch(da)
expect("dispatch: dry run launches nothing, consumes nothing", (LAUNCHES, t.jload(work_path)), ([], before))
da.dry_run = False
QUOTA[0] = 0
t.cmd_dispatch(da)
expect("dispatch: low quota launches nothing, consumes nothing", (LAUNCHES, t.jload(work_path)), ([], before))
QUOTA[0] = 100
da.per_issue = False
t.cmd_dispatch(da)
expect("dispatch: batch run gets work file", len(LAUNCHES), 1)
expect("dispatch: batch work file contains issue", t.jload(LAUNCHES[0][1]["TRIAGE_WORK"])[0]["number"], 8505)
# Exercise the actual process runner without network or an agent executable.
result = saved_wake["dispatch_run"]([sys.executable, "-c", "import os,sys; print(os.environ['TRIAGE_N']); sys.exit(7)"],
                                     dict(os.environ, TRIAGE_N="8505"), {"number": 8505, "kind": "new"})
expect("dispatch: exit code and output captured", (result["exit_code"], result["output_tail"].strip()), (7, "8505"))
expect("dispatch: duration recorded", result["duration_s"] >= 0, True)
# Every already-started run is logged even when preparing a later context fails.
old_context = t.context_pack
NEW[:] = [wake_issue(8601), wake_issue(8602)]
da.per_issue = True
log_before = len(t.jl_read(os.path.join(t.LOGS, "dispatch.jsonl")))
def broken_context(n, *args):
    if n == 8601:  # newest first: 8602 has already started
        raise RuntimeError("context read failed")
    return old_context(n, *args)
t.context_pack = broken_context
try:
    t.cmd_dispatch(da)
    FAIL.append("dispatch: expected context error")
except RuntimeError as e:
    expect("dispatch: context error reported", str(e), "context read failed")
finally:
    t.context_pack = old_context
expect("dispatch: prior run logged on preparation error", len(t.jl_read(os.path.join(t.LOGS, "dispatch.jsonl"))), log_before + 1)
expect("dispatch: error releases dispatcher lock", os.path.exists(os.path.join(TMP, "dispatch.lock")), False)
NEW[:] = [wake_issue(8603)]
def failed_run(*args):
    return dict(fake_run(*args), exit_code=7)
t.dispatch_run = failed_run
try:
    t.cmd_dispatch(da)
    FAIL.append("dispatch: failed run should exit 1")
except SystemExit as e:
    expect("dispatch: failed run propagates failure", e.code, 1)
expect("dispatch: failed run logged", t.jl_read(os.path.join(t.LOGS, "dispatch.jsonl"))[-1]["exit_code"], 7)
# The posting lock covers the call itself, including its gap check and GitHub write.
post_active, post_peak = [0], [0]
@t.serial_post
def fake_post():
    with mutex:
        post_active[0] += 1
        post_peak[0] = max(post_peak[0], post_active[0])
    time.sleep(0.02)
    with mutex:
        post_active[0] -= 1
with t.concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(lambda n: fake_post(), range(2)))
expect("post: concurrent calls serialized", post_peak[0], 1)
for k, v in saved_wake.items():
    setattr(t, k, v)
t.CFG.clear()
t.CFG.update(saved_cfg)


def main():
    for f in FAIL:
        print("FAIL", f)
    print(f"selftest: {CHECKS} checks, {len(FAIL)} failure(s)")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
