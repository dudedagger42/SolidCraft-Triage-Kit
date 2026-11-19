#!/usr/bin/env bash
# claude-code-wake.sh: deliver one message into a RUNNING Claude Code session, without a model call, tmux
# or polling. Pair it with `dispatch --run` (or any scheduler) so a long-lived triage session wakes only when
# there is work.
#
#   contrib/claude-code-wake.sh <session-id|pid> "<message>"
#   contrib/claude-code-wake.sh --selftest            # frame round-trip against a throwaway socket
#
# How: a Claude Code session listens on a local socket for messages from other sessions (the cross-session
# messages that arrive as <cross-session-message ...>). This writes one such message straight into that
# socket. The socket is per process, owned by you, mode 600:
#   Linux: $XDG_RUNTIME_DIR/cc-socks/<claude pid>.sock      (override the folder with CC_SOCK_DIR)
#
# WARNING: this frame is NOT a documented Claude Code interface. It was captured from a working session and
# can change in any release. The script refuses nothing on a new version, but says so on stderr; run
# --selftest and one live probe (wake your own session with a test message) after each Claude Code update.
# Verified against: 2.1.325 (Linux, live probe into a running session). Messages arrive as from-name "$WAKE_FROM_NAME" (default: triage-kit).
set -euo pipefail
VERIFIED_AGAINST="${VERIFIED_AGAINST:-2.1.325}"
FROM_NAME="${WAKE_FROM_NAME:-triage-kit}"
SOCKDIR="${CC_SOCK_DIR:-${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/cc-socks}"

send() {  # send <socket> <body>: one JSON line, then close
  node --input-type=module - "$1" "$2" "$FROM_NAME" <<'JS'
import net from "node:net";
import { randomUUID } from "node:crypto";
const [sock, body, fromName] = process.argv.slice(2);
const from = "daemon";
const content = `<cross-session-message from="${from}" from-name="${fromName}" from-mode="prompting">\n${body}\n</cross-session-message>`;
const frame = JSON.stringify({ msgV: 1, msg_id: randomUUID(), type: "user", message: { role: "user", content }, priority: "next", from }) + "\n";
const c = net.createConnection(sock);
c.setTimeout(5000, () => { console.error("timeout"); c.destroy(); process.exit(1); });
c.on("error", (e) => { console.error(e.message); process.exit(1); });
c.on("connect", () => c.write(frame, (err) => { if (err) { console.error(err.message); process.exit(1); } c.end(); }));
JS
}

# pid_for <session id>: the claude process running that session (`--resume <id>` or `--session-id <id>`).
pid_for() {
  local p
  for p in $(pgrep -x claude 2>/dev/null); do
    case " $(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null) " in
      *" --resume $1 "*|*" --resume=$1 "*|*" --session-id $1 "*|*" --session-id=$1 "*) echo "$p"; return 0 ;;
    esac
  done
}

if [ "${1:-}" = "--selftest" ]; then
  dir=$(mktemp -d); sock="$dir/selftest.sock"; out="$dir/out"; token="SELFTEST-$RANDOM$RANDOM"
  node -e 'const n=require("net"),fs=require("fs");const s=n.createServer(c=>c.on("data",d=>fs.appendFileSync(process.argv[2],d)));s.listen(process.argv[1]);setTimeout(()=>s.close(),3000)' "$sock" "$out" &
  for _ in 1 2 3 4 5 6 7 8 9 10; do [ -S "$sock" ] && break; sleep 0.2; done
  send "$sock" "$token"; wait
  if python3 -c 'import json,sys; d=json.loads(open(sys.argv[1]).read().splitlines()[0]); assert d["msgV"]==1 and d["type"]=="user" and sys.argv[2] in d["message"]["content"]' "$out" "$token"; then
    echo "selftest: frame round-trips"; rm -rf "$dir"; exit 0
  fi
  echo "selftest: FAILED"; rm -rf "$dir"; exit 1
fi

target="${1:?usage: claude-code-wake.sh <session-id|pid> \"<message>\" | --selftest}"; body="${2:?message}"
case "$target" in
  ''|*[!0-9]*) pid=$(pid_for "$target") ;;
  *) pid="$target" ;;
esac
[ -n "${pid:-}" ] || { echo "no running claude session with id $target" >&2; exit 1; }
sock="$SOCKDIR/$pid.sock"
[ -S "$sock" ] || { echo "session $target (pid $pid) has no socket at $sock" >&2; exit 1; }
ver=$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
case " $VERIFIED_AGAINST " in *" ${ver:-?} "*) ;; *) echo "note: Claude Code ${ver:-unknown} is not in VERIFIED_AGAINST ($VERIFIED_AGAINST); sending anyway" >&2 ;; esac
send "$sock" "$body" && echo "delivered to $target (pid $pid)"
