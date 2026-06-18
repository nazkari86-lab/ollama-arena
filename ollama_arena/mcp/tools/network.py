"""Network and system information tools."""
from __future__ import annotations

import datetime
import platform
import subprocess
from typing import Callable

import requests


def system_info(args: dict) -> str:
    try:
        import psutil

        mem = psutil.virtual_memory()
        return (
            f"System: {platform.system()}\n"
            f"CPU: {psutil.cpu_percent()}%\n"
            f"RAM: {mem.percent}%"
        )
    except ImportError:
        return f"System: {platform.system()} (install psutil for detailed stats)"
    except Exception as exc:
        return f"Error: {exc}"


def get_datetime(args: dict) -> str:
    return f"Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"


def ip_info(args: dict) -> str:
    try:
        resp = requests.get("https://ipapi.co/json/", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return (
            f"IP: {data.get('ip', 'unknown')}\n"
            f"City: {data.get('city', 'unknown')}\n"
            f"Country: {data.get('country_name', 'unknown')}\n"
            f"ISP: {data.get('org', 'unknown')}"
        )
    except Exception as exc:
        return f"Error: {exc}"


def ping(args: dict) -> str:
    host = args.get("host", "")
    if not host:
        return "Error: host required."
    try:
        flag = "-c" if platform.system() != "Windows" else "-n"
        count = str(args.get("count", 3))
        res = subprocess.run(
            ["ping", flag, count, host],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return res.stdout.strip() or res.stderr.strip() or "Ping completed."
    except Exception as exc:
        return f"Error: {exc}"


def tool_defs() -> list[tuple[str, Callable[[dict], str], dict, str]]:
    return [
        (
            "system_info",
            system_info,
            {
                "type": "function",
                "function": {
                    "name": "system_info",
                    "description": "Return CPU, RAM, and OS information.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            "safe",
        ),
        (
            "get_datetime",
            get_datetime,
            {
                "type": "function",
                "function": {
                    "name": "get_datetime",
                    "description": "Return the current local date and time.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            "safe",
        ),
        (
            "ip_info",
            ip_info,
            {
                "type": "function",
                "function": {
                    "name": "ip_info",
                    "description": "Return public IP, city, country, and ISP.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            "safe",
        ),
        (
            "ping",
            ping,
            {
                "type": "function",
                "function": {
                    "name": "ping",
                    "description": "Ping a host and return latency diagnostics.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "host": {"type": "string"},
                            "count": {"type": "integer"},
                        },
                        "required": ["host"],
                    },
                },
            },
            "safe",
        ),
    ]
