#!/usr/bin/env python3
"""
marvis_actions.py  (Mist Event Poller — All Device & Client Types)

Continuously polls the Mist /events endpoint every POLL_INTERVAL seconds
and pretty-prints a summary of recent events for:
  AP, Switch, WAN Gateway, Mist Edge, and Wi-Fi / Wired Clients.

Usage:
    Set the environment variables below, then run:
        python marvis_actions.py

Environment Variables:
    MIST_API_TOKEN  — Your Juniper Mist API token
    MIST_ORG_ID     — Your Mist Organisation ID
    MIST_SITE_ID    — The Site ID to monitor
    MIST_API_HOST   — API base URL (default: https://api.gc4.mist.com)
    POLL_INTERVAL   — Seconds between polls (default: 60)
"""

import os
import time
import requests
import json
from datetime import datetime, timedelta

# === CONFIG ===
TOKEN         = os.getenv("MIST_API_TOKEN", "YOUR_MIST_API_TOKEN")
ORG_ID        = os.getenv("MIST_ORG_ID",   "YOUR_ORG_ID")
SITE_ID       = os.getenv("MIST_SITE_ID",  "YOUR_SITE_ID")
API_HOST      = os.getenv("MIST_API_HOST", "https://api.gc4.mist.com")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))

HEADERS = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type": "application/json"
}

# ======================================================
# API Helpers
# ======================================================

def fetch_events(site_id, event_type, duration_minutes=10):
    """
    Fetches events of a specific type for the last `duration_minutes` minutes.

    Args:
        site_id         (str): Mist site ID.
        event_type      (str): One of 'ap', 'switch', 'gateway', 'mxedge', 'client'.
        duration_minutes(int): Look-back window in minutes.

    Returns:
        list: Event dicts from the Mist API.
    """
    end_time   = int(time.time())
    start_time = end_time - (duration_minutes * 60)

    url    = f"{API_HOST}/api/v1/sites/{site_id}/events"
    params = {
        "type":  event_type,
        "start": start_time,
        "end":   end_time,
        "limit": 100,
    }

    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])
    except requests.exceptions.HTTPError as e:
        print(f"[!] Error fetching '{event_type}' events: {e}")
        return []


def pretty_print(prefix, events):
    """Prints a concise summary (up to 3 sample events) for a batch of events."""
    print(f"\n--- {prefix} ({len(events)} events) @ {datetime.utcnow().isoformat()}Z")

    if not events:
        print("  No recent events.")
        return

    for event in events[:3]:
        ts     = datetime.fromtimestamp(event.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M:%S")
        summary = event.get("type",        "Unknown")
        text    = event.get("text",  "")  or event.get("reason", "")
        device  = event.get("device_name", "") or event.get("mac", "Unknown Device")
        print(f"  [{ts}] {device}: {summary} — {text}")

    if len(events) > 3:
        print(f"  … and {len(events) - 3} more.")

# ======================================================
# Entry Point
# ======================================================

def main():
    if "YOUR_MIST_API_TOKEN" in TOKEN:
        print("[ERROR] Please set the MIST_API_TOKEN environment variable before running.")
        return

    print(f"[+] Mist Event Poller — Site: {SITE_ID}")
    print(f"[+] Host: {API_HOST} | Poll interval: {POLL_INTERVAL}s")
    print("    Press Ctrl-C to stop.\n")

    try:
        while True:
            pretty_print("AP Events",        fetch_events(SITE_ID, "ap"))
            pretty_print("Switch Events",    fetch_events(SITE_ID, "switch"))
            pretty_print("WAN Edge Events",  fetch_events(SITE_ID, "gateway"))
            pretty_print("Mist Edge Events", fetch_events(SITE_ID, "mxedge"))

            client_events = fetch_events(SITE_ID, "client")
            wifi_events   = [e for e in client_events if not e.get("wired", False)]
            wired_events  = [e for e in client_events if     e.get("wired", False)]

            pretty_print("WiFi Client Events",  wifi_events)
            pretty_print("Wired Client Events", wired_events)

            print("\n" + "=" * 50 + "\n")
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n[+] Exiting event poller.")

if __name__ == "__main__":
    main()
