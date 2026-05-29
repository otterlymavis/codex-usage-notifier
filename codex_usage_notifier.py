#!/usr/bin/env python3
"""Notify when Codex usage should be refreshed.

Codex does not currently provide a public usage-refresh API for personal plan
limits, so this tool works from the reset time shown in Codex's usage page or
limit banner.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import smtplib
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any


APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CodexUsageNotifier"
CONFIG_PATH = APP_DIR / "config.json"
STATE_PATH = APP_DIR / "state.json"


@dataclass
class EmailConfig:
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_address: str = ""
    to_address: str = ""
    use_tls: bool = True


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def default_config() -> dict[str, Any]:
    return {
        "email": {
            "enabled": False,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "",
            "smtp_password": "",
            "from_address": "",
            "to_address": "",
            "use_tls": True,
        }
    }


def parse_email_config(raw: dict[str, Any]) -> EmailConfig:
    email = raw.get("email", {})
    return EmailConfig(
        enabled=bool(email.get("enabled", False)),
        smtp_host=str(email.get("smtp_host", "")),
        smtp_port=int(email.get("smtp_port", 587)),
        smtp_user=str(email.get("smtp_user", "")),
        smtp_password=str(email.get("smtp_password", "")),
        from_address=str(email.get("from_address", "")),
        to_address=str(email.get("to_address", "")),
        use_tls=bool(email.get("use_tls", True)),
    )


def parse_duration(value: str) -> timedelta:
    text = value.strip().lower()
    if not text:
        raise ValueError("Duration cannot be empty.")

    total = timedelta()
    matches = list(re.finditer(r"(\d+(?:\.\d+)?)\s*(weeks?|w|days?|d|hours?|hrs?|h|minutes?|mins?|m)", text))
    if not matches:
        raise ValueError("Use a duration like '5h', '4 days', or '1w 2d 3h'.")

    for match in matches:
        amount = float(match.group(1))
        unit = match.group(2)
        if unit.startswith("w"):
            total += timedelta(weeks=amount)
        elif unit.startswith("d"):
            total += timedelta(days=amount)
        elif unit.startswith("h") or unit.startswith("hr"):
            total += timedelta(hours=amount)
        elif unit.startswith("m"):
            total += timedelta(minutes=amount)

    if total.total_seconds() <= 0:
        raise ValueError("Duration must be greater than zero.")
    return total


def parse_reset_time(args: argparse.Namespace) -> datetime:
    now = datetime.now()
    if args.at:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%H:%M"):
            try:
                parsed = datetime.strptime(args.at, fmt)
                if fmt == "%H:%M":
                    parsed = parsed.replace(year=now.year, month=now.month, day=now.day)
                    if parsed <= now:
                        parsed += timedelta(days=1)
                return parsed
            except ValueError:
                pass
        raise ValueError("Use --at 'YYYY-MM-DD HH:MM' or --at 'HH:MM'.")

    if args.in_duration:
        return now + parse_duration(args.in_duration)

    raise ValueError("Provide either --at or --in.")


def desktop_notify(title: str, message: str) -> None:
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.BalloonTipTitle = {json.dumps(title)}
$notify.BalloonTipText = {json.dumps(message)}
$notify.Visible = $true
$notify.ShowBalloonTip(10000)
Start-Sleep -Seconds 11
$notify.Dispose()
"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        print(f"{title}: {message}")


def send_email(config: EmailConfig, subject: str, body: str) -> None:
    required = [
        config.smtp_host,
        config.smtp_user,
        config.smtp_password,
        config.from_address,
        config.to_address,
    ]
    if not config.enabled or not all(required):
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.from_address
    message["To"] = config.to_address
    message.set_content(body)

    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as smtp:
        if config.use_tls:
            smtp.starttls()
        smtp.login(config.smtp_user, config.smtp_password)
        smtp.send_message(message)


def notify_all(config: EmailConfig, reset_at: datetime) -> None:
    subject = "Codex usage should be refreshed"
    body = (
        "Codex usage should be refreshed now.\n\n"
        f"Reset time: {reset_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    desktop_notify(subject, "Your Codex usage reset time has arrived.")
    send_email(config, subject, body)


def sleep_until(target: datetime) -> None:
    while True:
        remaining = (target - datetime.now()).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 60))


def command_init(_: argparse.Namespace) -> int:
    if CONFIG_PATH.exists():
        print(f"Config already exists: {CONFIG_PATH}")
        return 0
    save_json(CONFIG_PATH, default_config())
    print(f"Created config: {CONFIG_PATH}")
    return 0


def command_test(args: argparse.Namespace) -> int:
    config = parse_email_config(load_json(CONFIG_PATH, default_config()))
    reset_at = datetime.now()
    notify_all(config, reset_at)
    print("Sent test notification.")
    if config.enabled:
        print("Email was enabled; attempted to send test email.")
    return 0


def command_watch(args: argparse.Namespace) -> int:
    reset_at = parse_reset_time(args)
    config = parse_email_config(load_json(CONFIG_PATH, default_config()))
    save_json(
        STATE_PATH,
        {
            "reset_at": reset_at.isoformat(timespec="seconds"),
            "started_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    print(f"Watching Codex reset time: {reset_at.strftime('%Y-%m-%d %H:%M:%S')}")
    sleep_until(reset_at)
    notify_all(config, reset_at)
    save_json(
        STATE_PATH,
        {
            "reset_at": reset_at.isoformat(timespec="seconds"),
            "notified_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    print("Notification sent.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Notify when Codex usage refreshes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create the config file.")
    init_parser.set_defaults(func=command_init)

    test_parser = subparsers.add_parser("test", help="Send a test notification.")
    test_parser.set_defaults(func=command_test)

    watch_parser = subparsers.add_parser("watch", help="Wait until a Codex reset time.")
    watch_parser.add_argument("--at", help="Reset time, e.g. '2026-05-29 18:30' or '18:30'.")
    watch_parser.add_argument("--in", dest="in_duration", help="Reset duration, e.g. '5h' or '4 days 3h'.")
    watch_parser.set_defaults(func=command_watch)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("Stopped.")
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
