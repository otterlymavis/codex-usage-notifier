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

2. Install the background monitor when the user wants this to work automatically:

```powershell
python .\scripts\codex_usage_notifier.py install-monitor
```

3. Check the monitor:

```powershell
python .\scripts\codex_usage_notifier.py monitor-status
```

4. Schedule a one-off reminder from the reset time reported by the Codex app:

```powershell
python .\scripts\codex_usage_notifier.py schedule-from-app
```

5. If app usage is unavailable or stale, ask for the reset time shown by Codex and use `schedule` manually:

```powershell
python .\scripts\codex_usage_notifier.py schedule --in "5h"
```

or:

```powershell
python .\scripts\codex_usage_notifier.py schedule --at "2026-05-30 18:30"
```

6. For a first-time setup or email configuration, create the config file:

```powershell
python .\scripts\codex_usage_notifier.py init
```

7. To verify desktop notification and optional email settings:

```powershell
python .\scripts\codex_usage_notifier.py test
```

8. To check whether the scheduled reminder task exists or ran:

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
- If the latest usage event is stale, use Codex once, then run `usage` again.
- If the PC sleeps, the reminder fires after the machine wakes and the script resumes.
- Scheduled reminders are allowed to run on battery power.
- Notification attempts and task state are logged in `%LOCALAPPDATA%\CodexUsageNotifier\notifier.log`.
- Do not scrape private OpenAI account pages unless the user explicitly requests browser automation and accepts that login/session state may be required.
