---
name: codex-usage-notifier
description: Create and manage local reminders for AI usage refreshes across Codex, Claude, Cursor, ChatGPT, Gemini, Poe, and similar tools. Use when the user wants to be notified on their PC or by email when usage, limits, quota, agentic usage, or a reset time refreshes.
---

# Usage Refresh Notifier

Use the bundled Python script to read Codex's locally cached app usage and to set manual reminders for other tools such as Claude. Prefer local provider data when available; otherwise schedule from the reset time visible in the app.

## Workflow

1. List supported providers:

```powershell
python .\scripts\codex_usage_notifier.py providers
```

2. For Claude or another manual provider, schedule from the reset time shown by the app:

```powershell
python .\scripts\codex_usage_notifier.py schedule-manual --provider claude --label "Claude Pro" --in "5h"
```

or:

```powershell
python .\scripts\codex_usage_notifier.py schedule-manual --provider cursor --label "Cursor" --at "18:30"
```

3. Read the latest Codex app usage:

```powershell
python .\scripts\codex_usage_notifier.py usage
```

4. Read every account found in Codex logs:

```powershell
python .\scripts\codex_usage_notifier.py usage --all-accounts
```

5. Install the Codex background monitor when the user wants Codex to work automatically across accounts:

```powershell
python .\scripts\codex_usage_notifier.py install-monitor
```

6. Check the monitor:

```powershell
python .\scripts\codex_usage_notifier.py monitor-status
```

7. Schedule a one-off reminder from the reset time reported by the Codex app:

```powershell
python .\scripts\codex_usage_notifier.py schedule-from-app
```

8. If app usage is unavailable or stale, ask for the reset time shown by Codex and use `schedule` manually:

```powershell
python .\scripts\codex_usage_notifier.py schedule --in "5h"
```

or:

```powershell
python .\scripts\codex_usage_notifier.py schedule --at "2026-05-30 18:30"
```

9. For a first-time setup or email configuration, create the config file:

```powershell
python .\scripts\codex_usage_notifier.py init
```

10. To verify desktop notification and optional email settings:

```powershell
python .\scripts\codex_usage_notifier.py test
```

11. To check whether the scheduled reminder task exists or ran:

```powershell
python .\scripts\codex_usage_notifier.py status
```

## Email Setup

The config file lives at `%LOCALAPPDATA%\CodexUsageNotifier\config.json`.

Set `email.enabled` to `true` and fill SMTP settings. For Gmail, use an app password instead of the normal account password.

## Notes

- Use `watch` only when the user explicitly wants a foreground timer and can keep the process running.
- Use `schedule-manual` for Claude, Cursor, ChatGPT, Gemini, Poe, and other services that show a reset time but do not expose a stable local usage event.
- `usage` and `schedule-from-app` read Codex's local `logs_2.sqlite`; they do not read `auth.json`.
- Use `install-monitor` for automatic background behavior; a Codex plugin/skill does not run continuously by itself.
- Multi-account monitoring can only use accounts that appear in Codex's local app logs. If an account is stale, switch to that account in Codex and use Codex once so the app writes a fresh usage event.
- If the latest usage event is stale, use Codex once, then run `usage` again.
- If the PC sleeps, the reminder fires after the machine wakes and the script resumes.
- Scheduled reminders are allowed to run on battery power.
- Notification attempts and task state are logged in `%LOCALAPPDATA%\CodexUsageNotifier\notifier.log`.
- Do not scrape private OpenAI account pages unless the user explicitly requests browser automation and accepts that login/session state may be required.
