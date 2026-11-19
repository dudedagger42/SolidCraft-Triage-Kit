# Unattended runner

Already use Claude Code with a subscription? Run `claude auth login`, then `kit/run --auth subscription --dry-run`
and `kit/run --auth subscription`. No API key is needed. `--auth auto` (the default) uses the saved key if one
exists, otherwise your subscription login. Subscription mode never falls back to the saved API key and stops
on a plan-limit message. API rate/credit limits also stop the batch without retries on another model.

The runner handles one bounded SOLO batch: follow-ups, corrections, an audit, and new reports, retaining the
kit's configured claim mode (`multi` by default). It is **first pass only**: it does not run attachments or
claim to reproduce a bug. Reports needing reproduction go through the existing `wantrepro` hand-off.
It uses the same checklist, decisions, lints, claims, posting limits and live thread checks as a manual run.
REVIEW comments get a separate, fresh Claude verification before `post --approve`.
Issue text is hostile data; Claude has no shell, file or MCP tools. The runner accepts only listed kit actions
and case-file writes. It never opens bugfix PRs or changes the kit's rules.

Defaults are Sonnet for drafts/verification and Haiku for first reads. To change them or the API allowance:

```bash
kit/run --read-model haiku --draft-model sonnet --budget-usd 5 --total-budget-usd 100
```

The shared local ledger is `~/.config/solidcraft-triage/usage.json`, across all this user's checkouts.
Daily spend resets at midnight **UTC**; the total never resets. Each Claude invocation reports `total_cost_usd`,
including reads and verification, and receives the lesser remaining daily/total allowance via `--max-budget-usd`.
No further model call starts once a reported cap is reached. Use a current Claude Code release supporting these
flags. [Claude's budget flag](https://code.claude.com/docs/en/cli-reference) uses client-side cost estimates:
a final request can exceed its allowance, and reported costs can differ from the bill. For a strict billing
ceiling also set an organization spend limit in Anthropic Console; the local runner cannot guarantee one.
The defaults are $5/day and $100 total, not a claim about any subscription's included credits.

Before each API call, the runner reserves its remaining allowance durably. Interrupted calls, invalid usage,
or a damaged ledger block further spending. To recover, check Anthropic's actual usage and reconcile that
ledger's pending row (`usd` and `pending: false`) with the charge; do not delete the ledger to retry.
The ledger counts this runner's usage, not other clients or machines using the same key. Keep caps unchanged
between scheduled runs unless you intend to raise/lower them.

One runner runs at a time per OS user, across checkouts. Do not run other posting workers on that account at
the same time. Each invocation exits after at most 80 model actions (`--max-actions` changes this); schedule
`kit/run` every 15 minutes if wanted. Stop with Ctrl-C or remove the schedule. The runner releases unfinished
claims on normal exits/errors; after a killed process, inspect state and use `python3 kit/triage.py unclaim N`.
No network integration test posts on your behalf; run the dry batch locally to check your credentials and CLI.
For reproducer/team setups, follow [SETUP.md](../SETUP.md).

