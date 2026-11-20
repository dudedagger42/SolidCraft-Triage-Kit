# Unattended runner

Already use Claude Code with a subscription? Run `claude auth login`, then `kit/run --auth subscription --dry-run`
and `kit/run --auth subscription`. No API key is needed for subscription-only use.
`--auth auto` (the default) uses the subscription first, even when a saved API key exists. When the
subscription reports a usage limit, it retries the same model request using the saved key under the
API dollar caps. It stays on API until the reported reset time, then tries the subscription again.
The reset is saved in `~/.config/solidcraft-triage/subscription.json` across scheduled runs. Explicit
reset timestamps (ISO or epoch) and CLI messages such as `resets 7pm (America/New_York)` are supported.
If no usable reset is reported, auto tries the subscription before the next request rather than guessing
its reset time. Without a saved key, the limit stops the batch. If no subscription is logged in, auto
uses the saved API key directly. Other subscription errors stop without API fallback.
`--auth api` and `--auth subscription` force one tier; neither switches. API rate/credit limits stop
without retries on another model. API caps apply only to API calls: an exhausted API allowance or
unresolved API reservation does not prevent subscription work in auto mode.

The runner handles one bounded SOLO batch: follow-ups, corrections, an audit, and new reports, retaining the
kit's configured claim mode (`multi` by default). It is **first pass only**: it does not run attachments or
claim to reproduce a bug. Reports needing reproduction go through the existing `wantrepro` hand-off.
It uses the same checklist, decisions, lints, claims, posting limits and live thread checks as a manual run.
REVIEW comments get a separate, fresh Claude verification before `post --approve`.
Issue text is hostile data; Claude has no shell, file or MCP tools. The runner accepts only listed kit actions
and case-file writes. It never opens bugfix PRs or changes the kit's rules.

New reports run back to back in one process. The host claims before any model work (and skips failed claims).
Haiku screens each live thread for a downloadable file, a prior human answer, and duplicates; any failed check skips the report before Sonnet. For eligible threads,
the host builds a case without image downloads, then Haiku checks the duplicate candidates before
Sonnet drafts. Screenshots/videos alone do not count as attached files. The host finishes one screened issue
before choosing the next and refuses model requests to start an unscreened issue. Existing follow-ups,
corrections and audit fixes are maintenance, separate from new-report screening.
Reproduction hand-offs require an attached file; this runner itself never executes attachments.

The kit docs and prompt are loaded once as the first, unchanged system prefix for screening, drafting and
fresh verification; only the task/history/case data comes afterward. API mode requests a **1-hour cache TTL**
with `CLAUDE_CODE_PROMPT_CACHE_TTL=1h` (and `ENABLE_PROMPT_CACHING_1H=1` for older CLI versions),
overriding cache-disable/5-minute environment flags for the model child. Use current Claude Code (v2.1.242+
for the TTL variable). Cache hits depend on the provider and model; Haiku and Sonnet have separate caches,
and 1-hour cache writes cost more. See [Claude Code caching](https://code.claude.com/docs/en/prompt-caching).

Defaults are Sonnet for drafts/verification, Haiku for eligibility, and at most **10 full triages per batch**
(`--max-triages N`, including dry runs). Each Haiku-approved full triage counts when started, even if it
later fails or is deferred. Skipped screens and maintenance do not count. `--max-actions` still bounds
Sonnet actions across maintenance and all issues; dollar caps bound every API call, including screening.

API plan presets (allowances only, not a promise of credits):

| Preset | Daily cap (UTC) | Total cap |
| --- | --- | --- |
| `--plan max100` (default) | $5 | $100 |
| `--plan max200` | $10 | $200 |

Manual `--budget-usd` and `--total-budget-usd` values override the corresponding preset, in either argument order:

```bash
kit/run --plan max200 --max-triages 5 --budget-usd 3 --total-budget-usd 150
```

The shared local ledger is `~/.config/solidcraft-triage/usage.json`, across all this user's checkouts.
Daily spend resets at midnight **UTC**; the total never resets. Each Claude invocation reports `total_cost_usd`,
including reads and verification, and receives the lesser remaining daily/total allowance via `--max-budget-usd`.
No further model call starts once a reported cap is reached. Use a current Claude Code release supporting these
flags. [Claude's budget flag](https://code.claude.com/docs/en/cli-reference) uses client-side cost estimates:
a final request can exceed its allowance, and reported costs can differ from the bill. For a strict billing
ceiling also set an organization spend limit on **Anthropic Console → Settings → Spend limits**:
[platform.claude.com/settings/spend-limits](https://platform.claude.com/settings/spend-limits).
The local runner cannot guarantee a billing ceiling; the Console limit is monthly, not a lifetime credit budget.
Every live/dry batch summary (also on errors or Ctrl-C during a batch) prints settled ledger USD,
full triages started, and **$ per triage**: all reported batch costs divided by that count. This includes
Haiku screening, drafts, verification and maintenance, and includes unfinished triages; it is not a guessed
price or a count of posted comments. A lifetime ledger summary uses the same calculation. Zero triages gives
`n/a`, and unresolved reservations are shown as unknown cost, never counted as actual spend. Old ledger rows
without triage counts still enforce caps, but their lifetime average is `n/a`; new batch averages remain available.
Each issue summary lists the tiers used (including its eligibility screens) and its reported API cost;
a triage that switches can list both. Maintenance has its own tier/cost line. Subscription costs are not
charged to the API ledger. Subscription-only batches report `n/a` for the aggregate API average.
In auto mode, the API ledger is opened only on the first API call; triages started earlier in that batch
are then recorded too, so the API average includes subscription work in the same batch. CLI-reported costs are measured usage,
not a guarantee of the provider's final invoice.

Before each API call, the runner reserves its remaining allowance durably. Interrupted calls, invalid usage,
or a damaged ledger block further spending. To recover, check Anthropic's actual usage and reconcile that
ledger's pending row (`usd` and `pending: false`) with the charge; do not delete the ledger to retry.
The ledger counts this runner's usage, not other clients or machines using the same key. Keep caps unchanged
between scheduled runs unless you intend to raise/lower them.

One runner runs at a time per OS user, across checkouts. Do not run other posting workers on that account at
the same time. Each invocation exits after at most 80 Sonnet actions (`--max-actions` changes this); schedule
`kit/run` every 15 minutes if wanted. Stop with Ctrl-C or remove the schedule. The runner releases unfinished
claims on normal exits/errors; after a killed process, inspect state and use `python3 kit/triage.py unclaim N`.
No network integration test posts on your behalf; run the dry batch locally to check your credentials and CLI.
For reproducer/team setups, follow [SETUP.md](../SETUP.md).

