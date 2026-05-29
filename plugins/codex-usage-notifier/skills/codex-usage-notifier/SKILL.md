---
name: codex-usage-notifier
description: Create and manage local reminders for Codex usage refreshes. Use when the user wants to be notified on their PC or by email when Codex usage, limits, quota, agentic usage, or a Codex reset time refreshes.
---

# Codex Usage Notifier

Use the bundled Python script to set reminders from the reset time shown in Codex's usage page or limit banner. Codex does not provide a documented public personal-usage refresh API, so ask for or infer the displayed reset time instead of promising automatic account polling.

## Workflow

1. Identify the reset time.
   - If the user gives a duration such as `5h`, `4 days`, or `1w 2d 3h`, use `watch --in`.
   - If the user gives a clock time or timestamp, use `watch --at`.
   - If the user only says "when refreshed", ask them for the reset time shown by Codex.
2. Run the script from this skill's plugin root:

```powershell
python .\scripts\codex_usage_notifier.py watch --in "5h"
```

or:

```powershell
python .\scripts\codex_usage_notifier.py watch --at "2026-05-29 18:30"
```

3. For a first-time setup or email configuration, create the config file:

```powershell
python .\scripts\codex_usage_notifier.py init
```

4. To verify desktop notification and optional email settings:

```powershell
python .\scripts\codex_usage_notifier.py test
```

## Email Setup

The config file lives at `%LOCALAPPDATA%\CodexUsageNotifier\config.json`.

Set `email.enabled` to `true` and fill SMTP settings. For Gmail, use an app password instead of the normal account password.

## Notes

- The script must keep running until the reset time unless the user installs it into Task Scheduler or another background runner.
- If the PC sleeps, the reminder fires after the machine wakes and the script resumes.
- Do not scrape private OpenAI account pages unless the user explicitly requests browser automation and accepts that login/session state may be required.
