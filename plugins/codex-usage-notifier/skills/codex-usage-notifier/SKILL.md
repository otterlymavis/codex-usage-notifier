---
name: codex-usage-notifier
description: Create and manage local reminders for Codex usage refreshes. Use when the user wants to be notified on their PC or by email when Codex usage, limits, quota, agentic usage, or a Codex reset time refreshes.
---

# Codex Usage Notifier

Use the bundled Python script to read Codex's locally cached app usage and set reminders from the 5-hour reset time. Codex does not provide a documented public personal-usage refresh API, so prefer local Codex app logs over scraping private account pages.

## Workflow

1. Read the latest Codex app usage:

```powershell
python .\scripts\codex_usage_notifier.py usage
```

2. Read every account found in Codex logs:

```powershell
python .\scripts\codex_usage_notifier.py usage --all-accounts
```

3. Install the background monitor when the user wants this to work automatically across accounts:

```powershell
python .\scripts\codex_usage_notifier.py install-monitor
```

4. Check the monitor:

```powershell
python .\scripts\codex_usage_notifier.py monitor-status
```

5. Schedule a one-off reminder from the reset time reported by the Codex app:

```powershell
python .\scripts\codex_usage_notifier.py schedule-from-app
```

6. If app usage is unavailable or stale, ask for the reset time shown by Codex and use `schedule` manually:

```powershell
python .\scripts\codex_usage_notifier.py schedule --in "5h"
```

or:

```powershell
python .\scripts\codex_usage_notifier.py schedule --at "2026-05-30 18:30"
```

7. For a first-time setup or email configuration, create the config file:

```powershell
python .\scripts\codex_usage_notifier.py init
```

8. To verify desktop notification and optional email settings:

```powershell
python .\scripts\codex_usage_notifier.py test
```

9. To check whether the scheduled reminder task exists or ran:

```powershell
python .\scripts\codex_usage_notifier.py status
```

## Email Setup

The config file lives at `%LOCALAPPDATA%\CodexUsageNotifier\config.json`.

Set `email.enabled` to `true` and fill SMTP settings. For Gmail, use an app password instead of the normal account password.

## Notes

- Use `watch` only when the user explicitly wants a foreground timer and can keep the process running.
- `usage` and `schedule-from-app` read Codex's local `logs_2.sqlite`; they do not read `auth.json`.
- Use `install-monitor` for automatic background behavior; a Codex plugin/skill does not run continuously by itself.
- Multi-account monitoring can only use accounts that appear in Codex's local app logs. If an account is stale, switch to that account in Codex and use Codex once so the app writes a fresh usage event.
- If the latest usage event is stale, use Codex once, then run `usage` again.
- If the PC sleeps, the reminder fires after the machine wakes and the script resumes.
- Scheduled reminders are allowed to run on battery power.
- Notification attempts and task state are logged in `%LOCALAPPDATA%\CodexUsageNotifier\notifier.log`.
- Do not scrape private OpenAI account pages unless the user explicitly requests browser automation and accepts that login/session state may be required.
