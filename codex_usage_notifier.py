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
import sqlite3
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
LOG_PATH = APP_DIR / "notifier.log"
DEFAULT_TASK_NAME = "CodexUsageNotifier"
DEFAULT_MONITOR_TASK_NAME = "CodexUsageNotifierMonitor"
CODEX_LOG_DB = Path.home() / ".codex" / "logs_2.sqlite"


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


def log_event(message: str) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} {message}\n")


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


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def datetime_from_epoch(value: int | float | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(float(value))


def extract_json_after_marker(text: str, marker: str) -> dict[str, Any] | None:
    index = text.find(marker)
    if index < 0:
        return None
    candidate = text[index + len(marker) :].strip()
    decoder = json.JSONDecoder()
    try:
        value, _ = decoder.raw_decode(candidate)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def find_latest_codex_usage(log_db: Path = CODEX_LOG_DB, limit: int = 5000) -> dict[str, Any]:
    if not log_db.exists():
        raise FileNotFoundError(f"Codex log database was not found: {log_db}")

    con = sqlite3.connect(f"file:{log_db.as_posix()}?mode=ro", uri=True)
    try:
        rows = con.execute(
            """
            select ts, feedback_log_body
            from logs
            where feedback_log_body like '%codex.rate_limits%'
               or feedback_log_body like '%usage_limit_reached%'
            order by id desc
            limit ?
            """,
            (limit,),
        ).fetchall()
    finally:
        con.close()

    for ts, body in rows:
        body = body or ""
        event = extract_json_after_marker(body, "websocket event:")
        if event and event.get("type") == "codex.rate_limits":
            return {
                "source": "codex.rate_limits",
                "seen_at": int(ts),
                "plan_type": event.get("plan_type"),
                "rate_limits": event.get("rate_limits") or {},
            }

        if event and event.get("type") == "error":
            error = event.get("error") or {}
            headers = event.get("headers") or {}
            if error.get("type") == "usage_limit_reached":
                reset_at = error.get("resets_at")
                return {
                    "source": "usage_limit_reached",
                    "seen_at": int(ts),
                    "plan_type": error.get("plan_type") or headers.get("X-Codex-Plan-Type"),
                    "rate_limits": {
                        "allowed": False,
                        "limit_reached": True,
                        "primary": {
                            "used_percent": int(headers.get("X-Codex-Primary-Used-Percent", 100)),
                            "window_minutes": int(headers.get("X-Codex-Primary-Window-Minutes", 300)),
                            "reset_after_seconds": error.get("resets_in_seconds"),
                            "reset_at": reset_at,
                        },
                        "secondary": {
                            "used_percent": int(headers.get("X-Codex-Secondary-Used-Percent", 0)),
                        },
                    },
                }

    raise RuntimeError("No Codex usage events were found in the local Codex app logs.")


def format_usage(usage: dict[str, Any]) -> str:
    rate_limits = usage.get("rate_limits") or {}
    primary = rate_limits.get("primary") or {}
    secondary = rate_limits.get("secondary") or {}
    reset_at = datetime_from_epoch(primary.get("reset_at"))
    weekly_reset_at = datetime_from_epoch(secondary.get("reset_at"))
    lines = [
        f"Source: {usage.get('source')}",
        f"Plan: {usage.get('plan_type') or 'unknown'}",
        f"Allowed: {rate_limits.get('allowed')}",
        f"Limit reached: {rate_limits.get('limit_reached')}",
        f"5-hour usage: {primary.get('used_percent', 'unknown')}%",
    ]
    if reset_at:
        lines.append(f"5-hour reset: {reset_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if secondary:
        lines.append(f"Weekly usage: {secondary.get('used_percent', 'unknown')}%")
    if weekly_reset_at:
        lines.append(f"Weekly reset: {weekly_reset_at.strftime('%Y-%m-%d %H:%M:%S')}")
    seen_at = datetime_from_epoch(usage.get("seen_at"))
    if seen_at:
        lines.append(f"Last app usage event: {seen_at.strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)


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
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log_event(f"tray_notification_exit={result.returncode}")
    except OSError:
        log_event("tray_notification_failed=oserror")
        print(f"{title}: {message}")


def popup_notify(title: str, message: str) -> None:
    script = f"""
$shell = New-Object -ComObject WScript.Shell
$null = $shell.Popup({json.dumps(message)}, 30, {json.dumps(title)}, 64)
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log_event(f"popup_notification_exit={result.returncode}")
    except OSError:
        log_event("popup_notification_failed=oserror")


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
    log_event("email_sent")


def notify_all(config: EmailConfig, reset_at: datetime) -> None:
    subject = "Codex usage should be refreshed"
    body = (
        "Codex usage should be refreshed now.\n\n"
        f"Reset time: {reset_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    log_event(f"notify_start reset_at={reset_at.isoformat(timespec='seconds')}")
    desktop_notify(subject, "Your Codex usage reset time has arrived.")
    popup_notify(subject, "Your Codex usage reset time has arrived.")
    send_email(config, subject, body)
    log_event("notify_complete")


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


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
    log_event("config_created")
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


def command_status(args: argparse.Namespace) -> int:
    task_name = args.task_name
    print(f"Config: {CONFIG_PATH}")
    print(f"State:  {STATE_PATH}")
    print(f"Log:    {LOG_PATH}")

    if STATE_PATH.exists():
        print("\nState:")
        print(STATE_PATH.read_text(encoding="utf-8").rstrip())

    ps_script = f"""
$task = Get-ScheduledTask -TaskName {powershell_quote(task_name)} -ErrorAction SilentlyContinue
if ($null -eq $task) {{
  Write-Output "Scheduled task '{task_name}' was not found."
  exit 0
}}
$info = Get-ScheduledTaskInfo -TaskName {powershell_quote(task_name)}
$task | Select-Object TaskName,TaskPath,State | Format-List
$info | Select-Object LastRunTime,LastTaskResult,NextRunTime,NumberOfMissedRuns | Format-List
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        check=False,
    )

    if LOG_PATH.exists():
        print("\nRecent log:")
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()[-20:]
        for line in lines:
            print(line)
    return 0


def command_monitor_status(args: argparse.Namespace) -> int:
    args.task_name = args.task_name or DEFAULT_MONITOR_TASK_NAME
    return command_status(args)


def command_usage(args: argparse.Namespace) -> int:
    usage = find_latest_codex_usage(Path(args.log_db) if args.log_db else CODEX_LOG_DB)
    if args.json:
        print(json.dumps(usage, indent=2))
    else:
        print(format_usage(usage))
    return 0


def command_schedule_from_app(args: argparse.Namespace) -> int:
    usage = find_latest_codex_usage(Path(args.log_db) if args.log_db else CODEX_LOG_DB)
    rate_limits = usage.get("rate_limits") or {}
    primary = rate_limits.get("primary") or {}
    reset_at = datetime_from_epoch(primary.get("reset_at"))
    if reset_at is None:
        raise RuntimeError("The latest Codex app usage event did not include a 5-hour reset time.")
    if reset_at <= datetime.now():
        raise RuntimeError("The latest Codex app reset time is already in the past. Use Codex once, then retry.")

    args.at = reset_at.strftime("%Y-%m-%d %H:%M:%S")
    args.in_duration = None
    print(format_usage(usage))
    return command_schedule(args)


def command_notify(args: argparse.Namespace) -> int:
    config = parse_email_config(load_json(CONFIG_PATH, default_config()))
    reset_at = parse_reset_time(args) if args.at or args.in_duration else datetime.now()
    notify_all(config, reset_at)
    save_json(
        STATE_PATH,
        {
            "reset_at": reset_at.isoformat(timespec="seconds"),
            "notified_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "scheduled-task",
        },
    )
    log_event("notify_command_completed")
    print("Notification sent.")
    return 0


def command_schedule(args: argparse.Namespace) -> int:
    reset_at = parse_reset_time(args)
    script_path = Path(__file__).resolve()
    python_path = Path(sys.executable).resolve()
    reset_text = reset_at.strftime("%Y-%m-%d %H:%M:%S")
    task_name = args.task_name
    task_args = f'"{script_path}" notify --at "{reset_text}"'
    ps_script = f"""
$ErrorActionPreference = "Stop"
$runAt = [datetime]::ParseExact({powershell_quote(reset_text)}, "yyyy-MM-dd HH:mm:ss", $null)
$action = New-ScheduledTaskAction -Execute {powershell_quote(str(python_path))} -Argument {powershell_quote(task_args)}
$trigger = New-ScheduledTaskTrigger -Once -At $runAt
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -Compatibility Win8
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName {powershell_quote(task_name)} -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Notify when Codex usage should be refreshed." -Force | Out-Null
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        check=True,
    )
    save_json(
        STATE_PATH,
        {
            "reset_at": reset_at.isoformat(timespec="seconds"),
            "scheduled_at": datetime.now().isoformat(timespec="seconds"),
            "task_name": task_name,
            "mode": "scheduled-task",
        },
    )
    log_event(f"scheduled task_name={task_name} reset_at={reset_at.isoformat(timespec='seconds')}")
    print(f"Scheduled Windows task '{task_name}' for {reset_text}.")
    print("Check it with: python codex_usage_notifier.py status")
    return 0


def command_monitor_once(args: argparse.Namespace) -> int:
    usage = find_latest_codex_usage(Path(args.log_db) if args.log_db else CODEX_LOG_DB)
    rate_limits = usage.get("rate_limits") or {}
    primary = rate_limits.get("primary") or {}
    reset_at = datetime_from_epoch(primary.get("reset_at"))
    seen_at = datetime_from_epoch(usage.get("seen_at"))
    if reset_at is None:
        log_event("monitor_once skipped=no_primary_reset")
        print("Latest Codex usage did not include a 5-hour reset time.")
        return 0
    if reset_at <= datetime.now():
        log_event(f"monitor_once skipped=past_reset reset_at={reset_at.isoformat(timespec='seconds')}")
        print(f"Latest Codex reset is in the past: {reset_at.strftime('%Y-%m-%d %H:%M:%S')}")
        return 0

    current_state = load_json(STATE_PATH, {})
    reset_text = reset_at.isoformat(timespec="seconds")
    previous_app_reset = parse_iso_datetime(current_state.get("last_app_reset_at"))
    if previous_app_reset and previous_app_reset != reset_at and previous_app_reset <= datetime.now():
        config = parse_email_config(load_json(CONFIG_PATH, default_config()))
        log_event(
            "monitor_once detected_refresh "
            f"previous_reset_at={previous_app_reset.isoformat(timespec='seconds')} "
            f"new_reset_at={reset_text}"
        )
        notify_all(config, previous_app_reset)

    already_scheduled = (
        current_state.get("task_name") == args.reminder_task_name
        and current_state.get("reset_at") == reset_text
        and current_state.get("mode") == "scheduled-task"
    )
    if already_scheduled:
        current_state.update(
            {
                "last_app_reset_at": reset_text,
                "last_app_usage_seen_at": seen_at.isoformat(timespec="seconds") if seen_at else None,
                "last_app_used_percent": primary.get("used_percent"),
            }
        )
        save_json(STATE_PATH, current_state)
        log_event(f"monitor_once skipped=already_scheduled reset_at={reset_text}")
        print(f"Reminder already scheduled for {reset_at.strftime('%Y-%m-%d %H:%M:%S')}.")
        return 0

    schedule_args = argparse.Namespace(
        at=reset_at.strftime("%Y-%m-%d %H:%M:%S"),
        in_duration=None,
        task_name=args.reminder_task_name,
    )
    result = command_schedule(schedule_args)
    updated_state = load_json(STATE_PATH, {})
    updated_state.update(
        {
            "last_app_reset_at": reset_text,
            "last_app_usage_seen_at": seen_at.isoformat(timespec="seconds") if seen_at else None,
            "last_app_used_percent": primary.get("used_percent"),
        }
    )
    save_json(STATE_PATH, updated_state)
    log_event(
        "monitor_once scheduled "
        f"reset_at={reset_text} "
        f"usage_seen_at={seen_at.isoformat(timespec='seconds') if seen_at else 'unknown'} "
        f"used_percent={primary.get('used_percent', 'unknown')}"
    )
    return result


def command_install_monitor(args: argparse.Namespace) -> int:
    script_path = Path(__file__).resolve()
    python_path = Path(sys.executable).resolve()
    task_name = args.task_name
    interval = max(1, int(args.interval_minutes))
    task_args = (
        f'"{script_path}" monitor-once '
        f'--reminder-task-name "{args.reminder_task_name}"'
    )
    if args.log_db:
        task_args += f' --log-db "{args.log_db}"'

    ps_script = f"""
$ErrorActionPreference = "Stop"
$action = New-ScheduledTaskAction -Execute {powershell_quote(str(python_path))} -Argument {powershell_quote(task_args)}
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes {interval}) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -Compatibility Win8
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName {powershell_quote(task_name)} -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Monitor local Codex app usage and schedule refresh notifications." -Force | Out-Null
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        check=True,
    )
    log_event(f"monitor_installed task_name={task_name} interval_minutes={interval}")
    print(f"Installed monitor task '{task_name}' to check Codex usage every {interval} minute(s).")
    monitor_args = argparse.Namespace(
        log_db=args.log_db,
        reminder_task_name=args.reminder_task_name,
    )
    return command_monitor_once(monitor_args)


def command_uninstall_monitor(args: argparse.Namespace) -> int:
    for task_name in [args.task_name, args.reminder_task_name]:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                f"Unregister-ScheduledTask -TaskName {powershell_quote(task_name)} -Confirm:$false -ErrorAction SilentlyContinue",
            ],
            check=False,
        )
        log_event(f"task_uninstalled_if_present task_name={task_name}")
    print("Removed monitor/reminder tasks if they existed.")
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
    log_event(f"watch_started reset_at={reset_at.isoformat(timespec='seconds')}")
    sleep_until(reset_at)
    notify_all(config, reset_at)
    save_json(
        STATE_PATH,
        {
            "reset_at": reset_at.isoformat(timespec="seconds"),
            "notified_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    log_event("watch_notification_completed")
    print("Notification sent.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Notify when Codex usage refreshes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create the config file.")
    init_parser.set_defaults(func=command_init)

    test_parser = subparsers.add_parser("test", help="Send a test notification.")
    test_parser.set_defaults(func=command_test)

    status_parser = subparsers.add_parser("status", help="Show scheduled task and notifier state.")
    status_parser.add_argument("--task-name", default=DEFAULT_TASK_NAME, help="Windows scheduled task name.")
    status_parser.set_defaults(func=command_status)

    monitor_status_parser = subparsers.add_parser("monitor-status", help="Show background monitor task state.")
    monitor_status_parser.add_argument("--task-name", default=DEFAULT_MONITOR_TASK_NAME, help="Windows monitor task name.")
    monitor_status_parser.set_defaults(func=command_monitor_status)

    usage_parser = subparsers.add_parser("usage", help="Read latest Codex usage from local Codex app logs.")
    usage_parser.add_argument("--json", action="store_true", help="Print raw parsed usage JSON.")
    usage_parser.add_argument("--log-db", help="Path to Codex logs_2.sqlite.")
    usage_parser.set_defaults(func=command_usage)

    schedule_from_app_parser = subparsers.add_parser(
        "schedule-from-app",
        help="Read latest Codex app usage and schedule the 5-hour reset reminder.",
    )
    schedule_from_app_parser.add_argument("--task-name", default=DEFAULT_TASK_NAME, help="Windows scheduled task name.")
    schedule_from_app_parser.add_argument("--log-db", help="Path to Codex logs_2.sqlite.")
    schedule_from_app_parser.set_defaults(func=command_schedule_from_app)

    monitor_once_parser = subparsers.add_parser(
        "monitor-once",
        help="Read Codex app usage once and schedule a reminder if needed.",
    )
    monitor_once_parser.add_argument("--reminder-task-name", default=DEFAULT_TASK_NAME, help="Reminder task name.")
    monitor_once_parser.add_argument("--log-db", help="Path to Codex logs_2.sqlite.")
    monitor_once_parser.set_defaults(func=command_monitor_once)

    install_monitor_parser = subparsers.add_parser(
        "install-monitor",
        help="Install a recurring Windows task that monitors Codex app usage.",
    )
    install_monitor_parser.add_argument("--task-name", default=DEFAULT_MONITOR_TASK_NAME, help="Windows monitor task name.")
    install_monitor_parser.add_argument("--reminder-task-name", default=DEFAULT_TASK_NAME, help="Reminder task name.")
    install_monitor_parser.add_argument("--interval-minutes", type=int, default=15, help="How often to check Codex usage.")
    install_monitor_parser.add_argument("--log-db", help="Path to Codex logs_2.sqlite.")
    install_monitor_parser.set_defaults(func=command_install_monitor)

    uninstall_monitor_parser = subparsers.add_parser(
        "uninstall-monitor",
        help="Remove monitor and reminder scheduled tasks.",
    )
    uninstall_monitor_parser.add_argument("--task-name", default=DEFAULT_MONITOR_TASK_NAME, help="Windows monitor task name.")
    uninstall_monitor_parser.add_argument("--reminder-task-name", default=DEFAULT_TASK_NAME, help="Reminder task name.")
    uninstall_monitor_parser.set_defaults(func=command_uninstall_monitor)

    notify_parser = subparsers.add_parser("notify", help="Send the refresh notification now.")
    notify_parser.add_argument("--at", help="Reset time to include in the notification.")
    notify_parser.add_argument("--in", dest="in_duration", help="Reset duration to include in the notification.")
    notify_parser.set_defaults(func=command_notify)

    schedule_parser = subparsers.add_parser("schedule", help="Create a one-time Windows scheduled task.")
    schedule_parser.add_argument("--at", help="Reset time, e.g. '2026-05-30 18:30' or '18:30'.")
    schedule_parser.add_argument("--in", dest="in_duration", help="Reset duration, e.g. '5h' or '4 days 3h'.")
    schedule_parser.add_argument("--task-name", default=DEFAULT_TASK_NAME, help="Windows scheduled task name.")
    schedule_parser.set_defaults(func=command_schedule)

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
