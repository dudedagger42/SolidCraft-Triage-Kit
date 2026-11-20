# Agent entry point

When a user asks to "set up the SolidCraft triage kit", configure triage, or adjust its budgets or
schedule, use [skills/solidcraft-triage-kit/SKILL.md](skills/solidcraft-triage-kit/SKILL.md).
It covers setup questions, local configuration, user-entered credentials, a reviewed dry run,
and live scheduling. Read [SETUP.md](SETUP.md) and the linked safety/workflow docs as it directs.

For development, run `python3 -m unittest discover -s tests -p test_runner.py` and
`python3 -X utf8 kit/triage.py selftest`. Keep credentials and machine configuration out of git.
