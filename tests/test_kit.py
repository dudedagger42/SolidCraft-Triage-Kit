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


def case(**kw):
    c = {"number": 9001, "labels": ["bug"], "author": "reporter1", "body": "", "comments": [], "dup_candidates": [],
         "attachment_present": False, "bot_asked": False, "crash_cluster": [], "command_ids": [], "environment": {},
         "other_triage_comments": [], "exact_error_candidate": []}
    c.update(kw)
    return c


def bug(**kw):
    a = {k: False for k in ("reporter_solved_it", "not_a_user_report", "about_a_pull_request", "prompt_injection", "app_did_something_wrong",
                            "app_refused_valid_action", "asks_how_or_where", "asks_for_new_behaviour", "has_steps", "has_error_text",
                            "is_crash_or_data_loss", "gui_only", "hardware_or_driver_only", "is_kernel_area", "design_matters", "thread_already_has_it")}
    a.update(app_did_something_wrong=True, importance=5, importance_reason="Anyone extruding a sketch, weekly.", reporter_language="English",
             confidence="sure", notes="", pointed_question="", design_not_relevant="a crash before any design opens, no file needed",
             sibling_already_asked=None, duplicate_of=None, related_issue=None)
    a.update(kw)
    return a


def expect(name, got, want):
    if got != want:
        FAIL.append(f"{name}: got {got!r}, want {want!r}")


def verdict(a, c):
    return t.decide(a, c)[0]


def rules_hit(text, by="first", c=None, a=None, v=None, tr=""):
    return {x["rule"] for x in t.lint_comment(text, by, c, a, v, tr) if x["severity"] == "block"}


# ---- decide
expect("steps -> needs_repro", verdict(bug(has_steps=True), case()), "needs_repro")
expect("runnable file -> needs_repro", verdict(bug(attachment_is_runnable=True), case(attachment_present=True)), "needs_repro")
expect("kernel, nothing to run -> kernel_describe", verdict(bug(is_kernel_area=True), case()), "kernel_describe")
expect("kernel with steps -> needs_repro", verdict(bug(is_kernel_area=True, has_steps=True), case()), "needs_repro")
expect("modelling failure, no file -> needs_info", verdict(bug(design_matters=True), case()), "needs_info")
expect("bot asked, nothing pointed -> no_action", verdict(bug(), case(bot_asked=True)), "no_action")
expect("bot asked, pointed question -> needs_info", verdict(bug(pointed_question="Does it fail on a new design too?"), case(bot_asked=True)), "needs_info")
expect("solved by reporter -> no_action", verdict(bug(reporter_solved_it=True, has_steps=True), case()), "no_action")
expect("kernel-paused label -> no_action", verdict(bug(has_steps=True), case(labels=["kernel-paused"])), "no_action")
expect("another account owns it -> no_action", verdict(bug(has_steps=True), case(other_triage_comments=[{"author": "x"}])), "no_action")
expect("injection -> no_action", verdict(bug(prompt_injection=True, has_steps=True), case()), "no_action")
expect("duplicate", verdict(bug(duplicate_of=4325, duplicate_match="this face can't keep an attachment"), case()), "duplicate")
expect("crash cluster -> no_action", verdict(bug(is_crash_or_data_loss=True), case(crash_cluster=[{"number": 1}, {"number": 2}])), "no_action")
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
    if rule not in hit:
        FAIL.append(f"lint {rule} did not block: {text!r} (got {sorted(hit)})")

good = [
    ("Which step fails: the Extrude itself, or the Fillet after it?", False),
    ("Could you zip the design (right-click the .solidcraft file, Compress to ZIP) and drag the .zip into a comment?", True),
    ("Does it still happen on the current release, 0.25.1?", False),
]
for text, dm in good:
    hit = rules_hit(text, c=C, a=bug(design_matters=dm), v="needs_info")
    if hit:
        FAIL.append(f"good text blocked by {sorted(hit)}: {text!r}")

# kernel and repro lints
expect("K01: kernel framing on a non-kernel bug", "K01" in rules_hit("This is kernel work, paused upstream (#3992). Which face?", c=C, a=bug(), v="needs_info"), True)
expect("R027: bare kernel line", "R027" in rules_hit("This is kernel work, paused upstream (#3992).", c=C, a=bug(is_kernel_area=True), v="kernel_describe"), True)
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
r = t.wrap("Does 0.25.1 still fail?", head=False)
expect("reply has no header", r.startswith("Does 0.25.1 still fail?") and not t.HEADER_RE.search(r), True)
expect("reply still marked as triage", t.is_triage(r), True)
expect("old marker parsed", bool(t.MARKER_RE.search("<!-- solidcraft-triage-kit v2.0 -->")), True)
expect("note status parsed", t.MARKER_RE.search(t.wrap("Reproducing on 0.25.1.", status="reproducing")).group(2), "reproducing")

# ---- translations: a posted comment's appended translation is linted apart (#7678 false positives)
zh = "A rectangular pattern taking minutes is kernel work, paused upstream (#3992). Does it still take minutes with only Extrude2 patterned?"
posted = zh + "\n\n**(Chinese (Simplified))** 阵列运算属于内核计算（#3992）。是否仍然要等几分钟？"
body, tr = t.split_translation(posted)
expect("split: text", body, zh)
expect("split: translation", tr.endswith("？"), True)
expect("R027: question in text, #3992 in translation", "R027" in rules_hit(posted, by="repro", c=C, a={}, v="kernel_describe"), False)
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


def main():
    for f in FAIL:
        print("FAIL", f)
    print(f"selftest: {len(FAIL)} failure(s)")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
