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
python .\codex_usage_notifier.py watch --in "5h"
```

Or use a specific time:

```powershell
python .\codex_usage_notifier.py watch --at "2026-05-29 18:30"
```

The tool keeps running until the reset time, then shows a Windows desktop notification.

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
- If your PC sleeps, the notification will fire after it wakes and the script resumes.

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
