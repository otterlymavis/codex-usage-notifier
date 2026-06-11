# Usage Refresh Notifier

Small Windows-friendly notifier for AI usage refreshes across Codex, Claude, Cursor, ChatGPT, Gemini, Poe, and similar tools.

Codex has an automatic local-log provider. Other tools can use manual reminders from whatever reset time they show, such as "try again at 6:30 PM" or "resets in 5 hours."

## Quick Start

Create the optional config:

```powershell
python .\codex_usage_notifier.py init
```

Send a test desktop notification:

```powershell
python .\codex_usage_notifier.py test
```

List available providers:

```powershell
python .\codex_usage_notifier.py providers
```

Schedule a Claude reminder from a visible reset time:

```powershell
python .\codex_usage_notifier.py schedule-manual --provider claude --label "Claude Pro" --in "5h"
```

Or:

```powershell
python .\codex_usage_notifier.py schedule-manual --provider claude --label "Claude Pro" --at "18:30"
```

Read the latest Codex app usage cached in local Codex logs:

```powershell
python .\codex_usage_notifier.py usage
```

Read every account found in local Codex logs:

```powershell
python .\codex_usage_notifier.py usage --all-accounts
```

Install the background monitor. This is the recommended setup:

```powershell
python .\codex_usage_notifier.py install-monitor
```

The monitor checks the Codex app logs every 15 minutes and keeps a separate refresh reminder scheduled for each account with a future reset time.

Check the monitor:

```powershell
python .\codex_usage_notifier.py monitor-status
```

Schedule a one-off reminder from the reset time reported by the Codex app:

```powershell
python .\codex_usage_notifier.py schedule-from-app
```

If you want to enter the reset manually, run:

```powershell
python .\codex_usage_notifier.py schedule --in "5h"
```

Or use a specific time:

```powershell
python .\codex_usage_notifier.py schedule --at "2026-05-30 18:30"
```

The `schedule` command creates a one-time Windows scheduled task, so the terminal does not need to stay open.

Check the registered reminder:

```powershell
python .\codex_usage_notifier.py status
```

For a simple foreground timer, you can still use:

```powershell
python .\codex_usage_notifier.py watch --in "5h"
```

## Email

Run `init`, then edit:

```text
%LOCALAPPDATA%\CodexUsageNotifier\config.json
```

Set `email.enabled` to `true` and fill in SMTP settings. For Gmail, use an app password rather than your normal account password.

Example email block:

```json
{
  "email": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "you@gmail.com",
    "smtp_password": "your-app-password",
    "from_address": "you@gmail.com",
    "to_address": "you@gmail.com",
    "use_tls": true
  }
}
```

## Notes

- Codex reset times come from Codex's local app logs.
- Claude and other services currently use manual reset times unless a stable local usage source is added.
- `usage` and `schedule-from-app` read Codex's local app logs, not your OpenAI auth file.
- This version does not scrape your OpenAI account or browser session.
- Multi-account monitoring can only use accounts that appear in Codex's local app logs. If an account is stale, switch to that account in Codex and use Codex once so the app writes a fresh usage event.
- `install-monitor` is needed if you want the tool to keep working automatically in the background.
- `schedule` is more reliable than `watch` because Windows owns the reminder.
- Scheduled reminders are allowed to run on battery power.
- Notification attempts and task state are logged in `%LOCALAPPDATA%\CodexUsageNotifier\notifier.log`.

## Codex Plugin

This repo includes a local Codex plugin at:

```text
plugins/codex-usage-notifier
```

The plugin bundles a skill that tells Codex how to set usage refresh reminders with this notifier.

## Claude Skill

This repo also includes a Claude-compatible skill at:

```text
.claude/skills/codex-usage-notifier
```

Copy that folder into your Claude skills directory, or keep it in a project that Claude Code can read.
