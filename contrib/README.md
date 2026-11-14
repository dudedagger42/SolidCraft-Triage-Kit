# Contrib

Optional helpers that are not part of the kit's tested core.

## claude-code-wake.sh

Wakes a long-running Claude Code triage session only when there is work, instead of the session polling on a
timer (which spends model turns even when nothing is new). Schedule the cheap check, and wake the session with
the result. `work --json` comes with the dispatch change (#4):

```sh
# every 5 minutes (systemd timer, launchd, cron, Task Scheduler...)
python3 -X utf8 kit/triage.py work --json > /tmp/triage-work.json
if [ -s /tmp/triage-work.json ] && grep -q '"issue"' /tmp/triage-work.json; then
  contrib/claude-code-wake.sh <your-session-id> "New triage work: run python3 -X utf8 kit/triage.py next"
fi
```

`<your-session-id>` is the id the session was started or resumed with (`claude --resume <id>`); a pid also works.
The message lands in the running session as if another session had sent it, with no tmux and no extra model
call to deliver it.

This uses an undocumented local socket and message frame of Claude Code (Linux; the socket folder can be set with
`CC_SOCK_DIR`). It can break in any Claude Code release: run `contrib/claude-code-wake.sh --selftest` and one live
probe into your own session after updating, and add the version to `VERIFIED_AGAINST`. If you'd rather not depend on
it, `dispatch --per-issue --run` starts a fresh non-interactive run per issue instead, which needs nothing
undocumented.
