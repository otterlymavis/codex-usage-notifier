# Codex Usage Notifier

Small Windows-friendly notifier for Codex usage refreshes.

OpenAI's public Codex help page says Codex limits depend on your plan and that the current reset/options are shown in the Codex usage page or limit banner. It does not document a public API for personal Codex usage refreshes, so this first version works from the reset time Codex shows you.

## Quick Start

Create the optional config:

```powershell
python .\codex_usage_notifier.py init
```

Send a test desktop notification:

```powershell
python .\codex_usage_notifier.py test
```

When Codex says something like "resets in 5 hours", run:

```powershell
python .\codex_usage_notifier.py schedule --in "5h"
```

Or use a specific time:

```powershell
python .\codex_usage_notifier.py schedule --at "2026-05-30 18:30"
```

The `schedule` command creates a one-time Windows scheduled task, so the terminal does not need to stay open.

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

- The reset time comes from Codex's own usage page or limit banner.
- This version does not scrape your OpenAI account.
- `schedule` is more reliable than `watch` because Windows owns the reminder.

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
