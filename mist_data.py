#!/usr/bin/env python3
"""
mist_data.py  (Mist Telemetry Dashboard & CSV Logger)

Monitors ALL connected clients across all APs at a Mist site, groups them
by their connected AP in a live terminal dashboard, and safely appends a
rich set of telemetry parameters to a CSV file for offline analysis.

Usage:
    Set the environment variables below, then run:
        python mist_data.py

Environment Variables:
    MIST_API_TOKEN  — Your Juniper Mist API token
    MIST_SITE_ID    — The Site ID to monitor
    MIST_API_HOST   — API base URL (default: https://api.gc4.mist.com)

Output:
    mist_site_analytics.csv — Appended every POLL_INTERVAL seconds.
    Columns: Timestamp, AP Name, AP MAC, Client MAC, Hostname, IP, SSID, VLAN,
             Manufacturer, Device OS, Band, Channel, Protocol, RSSI, SNR,
             Tx/Rx Bytes, Tx/Rx Rate, Tx/Rx Retries, DHCP/DNS/Roaming Latency,
             Uptime, Idle Time, Key Management
"""

import os
import time
import requests
import csv
from datetime import datetime

# === CONFIGURATION ===
TOKEN    = os.getenv("MIST_API_TOKEN", "YOUR_MIST_API_TOKEN")
SITE_ID  = os.getenv("MIST_SITE_ID",  "YOUR_SITE_ID")
API_HOST = os.getenv("MIST_API_HOST", "https://api.gc4.mist.com")

POLL_INTERVAL = 10           # Seconds between each poll cycle
CSV_FILENAME  = "mist_site_analytics.csv"

HEADERS = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type": "application/json"
}

# ======================================================
# Utilities
# ======================================================

def clean_mac(mac):
    if not mac:
        return ""
    return mac.replace(":", "").replace("-", "").lower()

def bytes_to_human(size):
    """Converts a byte count to a human-readable string (KB, MB, GB …)."""
    if not size:
        return "0B"
    power        = 1024
    n            = 0
    power_labels = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size > power:
        size /= power
        n    += 1
    return f"{size:.1f}{power_labels.get(n, 'B')}"

# ======================================================
# CSV Initialisation
# ======================================================

def init_csv():
    """Creates the CSV file and writes the header row if the file doesn't exist."""
    if not os.path.exists(CSV_FILENAME):
        try:
            with open(CSV_FILENAME, mode="w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Connected AP Name", "Connected AP MAC",
                    "Client MAC", "Hostname", "IP Address", "SSID", "VLAN",
                    "Manufacturer", "Device OS",
                    "Band", "Channel", "Protocol",
                    "RSSI (dBm)", "SNR (dB)",
                    "Tx Bytes", "Rx Bytes",
                    "Tx Rate (Mbps)", "Rx Rate (Mbps)",
                    "Tx Retries (%)", "Rx Retries (%)",
                    "DHCP Latency (ms)", "DNS Latency (ms)", "Roaming Latency (ms)",
                    "Uptime (s)", "Idle Time (s)", "Key Mgmt"
                ])
            print(f"[+] Created analytics log: {CSV_FILENAME}")
        except PermissionError:
            print(f"[!] FATAL: Cannot create {CSV_FILENAME}. Close it in any other program.")

# ======================================================
# CSV Append
# ======================================================

def save_to_csv(clients, ap_map):
    """Safely appends telemetry rows for all clients to the CSV log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with open(CSV_FILENAME, mode="a", newline="") as f:
            writer = csv.writer(f)

            if not clients:
                writer.writerow([timestamp, "No Clients Connected"] + [""] * 25)
            else:
                for c in clients:
                    try:
                        ap_mac_raw = c.get("ap_mac", "")
                        ap_name    = ap_map.get(clean_mac(ap_mac_raw), ap_mac_raw)

                        writer.writerow([
                            timestamp, ap_name, ap_mac_raw,
                            c.get("mac",          "Unknown"),
                            c.get("hostname",     "N/A"),
                            c.get("ip",           "N/A"),
                            c.get("ssid",         "N/A"),
                            c.get("vlan_id",      "N/A"),
                            c.get("manufacture",  "N/A"),
                            c.get("os",           "N/A"),
                            c.get("band",         "N/A"),
                            c.get("channel",      "N/A"),
                            c.get("proto",        "N/A"),
                            c.get("rssi",         "N/A"),
                            c.get("snr",          "N/A"),
                            c.get("tx_bytes",     0),
                            c.get("rx_bytes",     0),
                            c.get("tx_rate",      "N/A"),
                            c.get("rx_rate",      "N/A"),
                            c.get("tx_retries",   "N/A"),
                            c.get("rx_retries",   "N/A"),
                            c.get("dhcp_latency", "N/A"),
                            c.get("dns_latency",  "N/A"),
                            c.get("roam_latency", "N/A"),
                            c.get("uptime",       "N/A"),
                            c.get("idle_time",    "N/A"),
                            c.get("key_mgmt",     "N/A"),
                        ])
                    except Exception as row_err:
                        print(f"  [!] Skipped one client row: {row_err}")

    except PermissionError:
        print(f"\n  [!!!] File '{CSV_FILENAME}' is locked — close Excel and retry.")
    except Exception as e:
        print(f"\n  [!!!] Unexpected CSV write error: {e}")

# ======================================================
# API Helpers
# ======================================================

def get_ap_map(site_id):
    """Returns a dict mapping cleaned AP MAC → AP name for display purposes."""
    url    = f"{API_HOST}/api/v1/sites/{site_id}/stats/devices"
    ap_map = {}
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            for d in r.json():
                ap_map[clean_mac(d.get("mac", ""))] = d.get("name", "Unnamed AP")
    except Exception:
        pass
    return ap_map

def get_all_clients(site_id):
    """Returns a list of all connected client dicts from the Mist API."""
    url = f"{API_HOST}/api/v1/sites/{site_id}/stats/clients"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

# ======================================================
# Live Dashboard
# ======================================================

def display_dashboard(clients, ap_map):
    os.system("cls" if os.name == "nt" else "clear")
    print(f"=== MIST SITE DASHBOARD (GROUPED): {datetime.now().strftime('%H:%M:%S')} ===")
    print(f"Total Clients: {len(clients)} | Logging to: {CSV_FILENAME}\n")

    if not clients:
        print("  No clients currently connected to any AP.")
        return

    grouped_clients = {}
    for c in clients:
        ap_mac_raw = c.get("ap_mac", "")
        ap_name    = ap_map.get(clean_mac(ap_mac_raw), ap_mac_raw or "Unknown AP")
        grouped_clients.setdefault(ap_name, []).append(c)

    for ap_name, ap_clients in grouped_clients.items():
        print("=" * 80)
        print(f" [ AP: {ap_name} ] — {len(ap_clients)} Clients Connected")
        print("=" * 80)
        header = f"  {'Client MAC':<14} | {'Hostname':<18} | {'B/Ch':<5} | {'RSSI':<4} | {'SNR':<3} | {'Tx':>8} | {'Rx':>8}"
        print(header)
        print("  " + "-" * len(header))

        for c in ap_clients:
            mac      = c.get("mac", "Unknown")[-12:]
            hostname = c.get("hostname", "---")[:18]
            band_ch  = f"{c.get('band','?')[0]}/{c.get('channel','?')}"
            rssi     = c.get("rssi", 0)
            snr      = c.get("snr",  0)
            tx_fmt   = bytes_to_human(c.get("tx_bytes", 0))
            rx_fmt   = bytes_to_human(c.get("rx_bytes", 0))
            print(f"  {mac:<14} | {hostname:<18} | {band_ch:<5} | {rssi:<4} | {snr:<3} | {tx_fmt:>8} | {rx_fmt:>8}")
        print()

# ======================================================
# Entry Point
# ======================================================

def main():
    if "YOUR_MIST_API_TOKEN" in TOKEN:
        print("[ERROR] Please set the MIST_API_TOKEN environment variable before running.")
        return

    init_csv()
    print(f"[+] Starting site analytics monitor for Site: {SITE_ID}")
    print(f"[+] Polling every {POLL_INTERVAL}s. Press Ctrl-C to stop.\n")

    try:
        while True:
            ap_map      = get_ap_map(SITE_ID)
            client_data = get_all_clients(SITE_ID)
            display_dashboard(client_data, ap_map)
            save_to_csv(client_data, ap_map)
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n[+] Stopping monitor. Analytics saved to CSV.")

if __name__ == "__main__":
    main()
