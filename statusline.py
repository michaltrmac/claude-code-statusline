#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import urllib.error
import subprocess
import platform
from pathlib import Path
from datetime import datetime, timezone

# ANSI colors
BLUE = "\033[34m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"

USAGE_API_URL = "https://api.anthropic.com/api/oauth/usage"
USAGE_THRESHOLD_HIGH = 80
USAGE_THRESHOLD_MEDIUM = 50
CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"

def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except Exception:
        print("statusline: no data")
        return

    # Extract fields
    project = os.path.basename(data.get("cwd", ""))
    model = data.get("model", {}).get("display_name", "")
    context_window = data.get("context_window", {})
    context_percentage = context_window.get("used_percentage", 0) or 0

    # Fetch usage from API
    access_token = get_access_token()

    if access_token:
        usage_data = fetch_usage(access_token)
        usage_str = format_usage(usage_data)
    else:
        usage_str = f"{RED}No credentials{RESET}"
    
    context_usage_str = f"{get_usage_color(context_percentage)}{context_percentage:.0f}%{RESET}"

    line = f"{project} | {BLUE}{model}{RESET} | Ctx: {context_usage_str} | {usage_str}"

    print(line)


def get_access_token() -> str | None:
    """Retrieve the access token based on the platform."""
    system = platform.system()

    if system == "Darwin":  # macOS
        return get_access_token_macos()
    elif system == "Linux":
        return get_access_token_linux()
    else:
        return None # Windows not supported


def get_access_token_macos() -> str | None:
    """Retrieve access token from macOS Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True
        )
        credentials = result.stdout.strip()
        if credentials:
            creds = json.loads(credentials)
            return creds.get("claudeAiOauth", {}).get("accessToken")
        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
        return None


def get_access_token_linux() -> str | None:
    """Read access token from credentials file on Linux."""
    try:
        with open(CREDENTIALS_PATH) as f:
            creds = json.load(f)
        return creds.get("claudeAiOauth", {}).get("accessToken")
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def fetch_usage(access_token: str) -> dict | None:
    """Fetch usage data from Anthropic API."""
    try:
        req = urllib.request.Request(
            USAGE_API_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "anthropic-beta": "oauth-2025-04-20",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None

def format_reset_time(resets_at_str: str | None) -> str:
    """Formats the reset time into a human-readable string like '1d 4h' or '3h 4m'."""
    if not resets_at_str:
        return ""
    try:
        if resets_at_str.endswith('Z'):
            resets_at_str = resets_at_str[:-1] + '+00:00'
        
        resets_at = datetime.fromisoformat(resets_at_str)
        
        if resets_at.tzinfo is None:
            resets_at = resets_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        delta = resets_at - now

        if delta.total_seconds() <= 0:
            return " (now)"

        total_seconds = int(delta.total_seconds())
        
        days = total_seconds // (24 * 3600)
        remainder_after_days = total_seconds % (24 * 3600)
        hours = remainder_after_days // 3600
        minutes = (remainder_after_days % 3600) // 60

        if days > 0:
            return f" ({days}d {hours}h)"
        elif hours > 0:
            return f" ({hours}h {minutes}m)"
        elif minutes > 0:
            return f" ({minutes}m)"
        else:
            return " (<1m)"
    except (ValueError, TypeError):
        return ""


def format_usage(usage_data: dict) -> str:
    """Format usage data for statusline display."""
    if not usage_data:
        return f"{RED}Usage: N/A{RESET}"

    # Extract 5-hour and 7-day limits
    five_hour_usage = usage_data.get("five_hour", {})
    weekly_usage = usage_data.get("seven_day", {})

    five_hour_percentage = five_hour_usage.get("utilization", 0) or 0
    weekly_percentage = weekly_usage.get("utilization", 0) or 0

    five_hour_reset_str = format_reset_time(five_hour_usage.get("resets_at"))
    weekly_reset_str = format_reset_time(weekly_usage.get("resets_at"))

    five_hour_str = f"{get_usage_color(five_hour_percentage)}{five_hour_percentage:.0f}%{RESET}{five_hour_reset_str}"
    weekly_str = f"{get_usage_color(weekly_percentage)}{weekly_percentage:.0f}%{RESET}{weekly_reset_str}"

    return f"5h: {five_hour_str} | 7d: {weekly_str}"

def get_usage_color(percentage: float) -> str:
    if percentage >= USAGE_THRESHOLD_HIGH:
        return RED
    elif percentage >= USAGE_THRESHOLD_MEDIUM:
        return YELLOW
    return GREEN

if __name__ == "__main__":
    main()