#!/usr/bin/env python3
"""
events.py  (Mist Site Event Fetcher — with Graceful Fallback)

Attempts to fetch historical events from the Mist /events endpoint.
If the events API is restricted or unavailable, it falls back to fetching
current real-time device stats (AP, Switch, Gateway) instead.

Usage:
    Set the environment variables below, then run:
        python events.py

Environment Variables:
    MIST_API_TOKEN  — Your Juniper Mist API token
    MIST_SITE_ID    — The Site ID to query
    MIST_API_HOST   — API base URL (default: https://api.gc4.mist.com)

Output:
    JSON files saved in the current working directory:
    - logs_all_site_events.json
    - logs_ap_events_filtered.json
    - logs_switch_events_filtered.json
    (or AP/Switch/Gateway stats as fallback)
"""

import os
import time
import requests
import json
from datetime import datetime, timedelta

# === CONFIGURATION ===
TOKEN    = os.getenv("MIST_API_TOKEN", "YOUR_MIST_API_TOKEN")
SITE_ID  = os.getenv("MIST_SITE_ID",  "YOUR_SITE_ID")
API_HOST = os.getenv("MIST_API_HOST", "https://api.gc4.mist.com")

HEADERS = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type": "application/json"
}

# ======================================================
# API Helpers
# ======================================================

def fetch_events_base(site_id, duration_hours=24):
    """
    Fetches all events for the last `duration_hours` from the site /events endpoint.

    Returns:
        list | None: List of event dicts, or None if the endpoint is unavailable.
    """
    end_time   = int(time.time())
    start_time = end_time - (duration_hours * 3600)

    url    = f"{API_HOST}/api/v1/sites/{site_id}/events"
    params = {"start": start_time, "end": end_time, "limit": 100}

    print(f"--> Fetching site events from: {url}")
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("results", []) if isinstance(data, dict) else data
    except requests.exceptions.HTTPError as e:
        print(f"    [!] Failed to fetch events: {e}")
        return None


def fetch_device_stats(site_id, device_type):
    """
    Fallback: fetches current real-time device statistics.

    Args:
        device_type (str): One of 'ap', 'switch', 'gateway'.
    """
    url    = f"{API_HOST}/api/v1/sites/{site_id}/stats/devices"
    params = {"type": device_type}

    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"    [!] Failed to fetch {device_type} stats: {e}")
        return []


def save_and_print(label, data):
    """Writes `data` to a JSON file and prints a short summary."""
    if not data:
        print(f"    [~] No data found for '{label}'.")
        return

    filename = f"logs_{label.lower().replace(' ', '_')}.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

    sample = json.dumps(data[0], indent=None)[:120]
    print(f"    [+] Saved {len(data)} items → {filename}")
    print(f"        Sample: {sample}…")

# ======================================================
# Entry Point
# ======================================================

def main():
    if "YOUR_MIST_API_TOKEN" in TOKEN:
        print("[ERROR] Please set the MIST_API_TOKEN environment variable before running.")
        return

    print(f"=== Mist Data Fetcher — Site {SITE_ID} ===\n")

    # 1. Try to fetch all site events in one call
    events = fetch_events_base(SITE_ID)

    if events is not None:
        # Filter locally by device type
        ap_events     = [e for e in events if e.get("type") == "ap"     or e.get("device_type") == "ap"]
        switch_events = [e for e in events if e.get("type") == "switch" or e.get("device_type") == "switch"]

        save_and_print("All Site Events",           events)
        save_and_print("AP Events Filtered",        ap_events)
        save_and_print("Switch Events Filtered",    switch_events)
    else:
        print("\n[!] /events endpoint restricted. Fetching current device stats as fallback.\n")
        save_and_print("AP Stats",      fetch_device_stats(SITE_ID, "ap"))
        save_and_print("Switch Stats",  fetch_device_stats(SITE_ID, "switch"))
        save_and_print("Gateway Stats", fetch_device_stats(SITE_ID, "gateway"))

    print("\n=== Done ===")

if __name__ == "__main__":
    main()
