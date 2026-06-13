#!/usr/bin/env python3
"""
mist2.py  (Mist Automated Client Roaming — Dual-AP Enforcer with ML Model)

Features:
1. Loads a pre-trained ML model (wifi_model.pkl) and logs its status.
2. Monitors AP1 (kick source) → enforces 3-Strike Disconnect Rule on weak clients.
3. Monitors AP2 (safe zone)  → reports connected clients to verify roaming success.

Usage:
    Set the environment variables below, then run:
        python mist2.py

Environment Variables:
    MIST_API_TOKEN  — Your Juniper Mist API token
    MIST_SITE_ID    — The Site ID to monitor
    MIST_API_HOST   — API base URL (default: https://api.gc4.mist.com)

AP Configuration:
    Update AP1_MAC and AP2_MAC with the MAC addresses of your actual APs.
"""

import os
import time
import requests
import urllib3
import joblib
from datetime import datetime

# Disable SSL warnings for self-signed certs on the local network
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= CONFIGURATION =================
TOKEN    = os.getenv("MIST_API_TOKEN", "YOUR_MIST_API_TOKEN")
SITE_ID  = os.getenv("MIST_SITE_ID",  "YOUR_SITE_ID")
API_HOST = os.getenv("MIST_API_HOST", "https://api.gc4.mist.com")

# --- TARGET APs (update with your actual AP MAC addresses) ---
AP1_MAC = "YOUR_AP1_MAC"   # The AP to kick weak clients FROM (e.g. "04cdc092a8eb")
AP2_MAC = "YOUR_AP2_MAC"   # The AP to roam clients TO     (e.g. "04:cd:c0:92:ad:dc")

# --- ML MODEL ---
MODEL_FILE = "wifi_model.pkl"

# --- THRESHOLDS ---
RSSI_THRESHOLD  = -75    # Kick if signal is worse than this (dBm)
STRIKES_REQUIRED = 3     # Consecutive bad polls before disconnect
POLL_INTERVAL    = 2     # Seconds between each poll cycle
API_TIMEOUT      = 20

HEADERS = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type": "application/json"
}

bad_signal_counters = {}   # Tracks consecutive bad-signal strikes per client MAC

# ======================================================
# Helpers
# ======================================================

def normalize(mac):
    """Strips colons and lowercases a MAC address for safe string comparison."""
    if not mac:
        return ""
    return mac.lower().replace(":", "").strip()

def load_ml_model():
    """
    Loads the pre-trained sklearn model from wifi_model.pkl.
    Falls back gracefully if the file is missing.
    """
    print(f"\n[INIT] Loading AI Model from {MODEL_FILE}...")
    if os.path.exists(MODEL_FILE):
        try:
            model = joblib.load(MODEL_FILE)
            print(f"       [SUCCESS] Model '{MODEL_FILE}' loaded into memory.")
            return model
        except Exception as e:
            print(f"       [WARNING] Failed to load model: {e}")
    else:
        print("       [INFO] Model file not found. Continuing with Rule-Based Logic only.")
    return None

def fetch_clients():
    """Returns a list of all currently connected client dicts from the Mist API."""
    url = f"{API_HOST}/api/v1/sites/{SITE_ID}/stats/clients"
    try:
        r = requests.get(url, headers=HEADERS, timeout=API_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"\n[!] Connection Error: {e}")
        return None

def disconnect_client(mac):
    """Sends a disconnect (de-auth) request for the given client MAC via the Mist API."""
    url     = f"{API_HOST}/api/v1/sites/{SITE_ID}/clients/disconnect"
    payload = {"macs": [mac]}
    try:
        print(f"      >>> [ACTION] Sending Disconnect for {mac}...", end=" ")
        r = requests.post(url, headers=HEADERS, json=payload, timeout=API_TIMEOUT)
        r.raise_for_status()
        print("SUCCESS!")
        return True
    except requests.exceptions.HTTPError as e:
        print(f"\n      [!] KICK FAILED: {e}")
    except Exception as e:
        print(f"\n      [!] Connection Error: {e}")
    return False

# ======================================================
# Main Loop
# ======================================================

def main():
    if "YOUR_MIST_API_TOKEN" in TOKEN:
        print("[ERROR] Please set the MIST_API_TOKEN environment variable before running.")
        return

    print("\n--- Mist Smart Enforcer (Dual-AP) ---")
    load_ml_model()   # Load the pkl model; kick-logic uses rule-based RSSI thresholds

    target_ap1_clean = normalize(AP1_MAC)
    target_ap2_clean = normalize(AP2_MAC)

    while True:
        clients = fetch_clients()

        if clients is None:
            print(f"[!] Retrying in {POLL_INTERVAL}s...")
            time.sleep(POLL_INTERVAL)
            continue

        # Partition clients by AP
        ap1_clients = []
        ap2_clients = []

        for c in clients:
            client_ap = normalize(c.get("ap_mac", ""))
            if client_ap == target_ap1_clean:
                ap1_clients.append(c)
            elif client_ap == target_ap2_clean:
                ap2_clients.append(c)

        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] Status Update:")

        # --- AP2 Monitor (Safe / Roam target zone) ---
        if ap2_clients:
            print(f"  [AP2 - Safe] {len(ap2_clients)} clients (roaming successful):")
            for c in ap2_clients:
                print(f"    - {c.get('mac')} | Signal: {c.get('rssi')} dBm")
        else:
            print("  [AP2 - Safe] No clients.")

        # --- AP1 Monitor (Kick zone) ---
        if not ap1_clients:
            print("  [AP1 - Target] Empty. (Waiting for clients...)")
        else:
            print(f"  [AP1 - Target] Monitoring {len(ap1_clients)} clients:")

            active_macs_ap1 = set()

            for c in ap1_clients:
                mac  = c.get("mac")
                rssi = c.get("rssi", -100)
                active_macs_ap1.add(mac)

                strikes = bad_signal_counters.get(mac, 0)

                if rssi < RSSI_THRESHOLD:
                    strikes += 1
                    bad_signal_counters[mac] = strikes
                    print(f"    [BAD]  {mac} | Signal: {rssi} dBm | Strike {strikes}/{STRIKES_REQUIRED}")

                    if strikes >= STRIKES_REQUIRED:
                        print("        !!! STRIKE LIMIT REACHED. KICKING CLIENT !!!")
                        disconnect_client(mac)
                        bad_signal_counters[mac] = 0
                else:
                    if strikes > 0:
                        print(f"    [GOOD] {mac} | Signal: {rssi} dBm | RECOVERED (Strikes reset)")
                    else:
                        print(f"    [GOOD] {mac} | Signal: {rssi} dBm | Safe")
                    bad_signal_counters[mac] = 0

            # Remove memory for clients that left AP1
            for mac in list(bad_signal_counters.keys()):
                if mac not in active_macs_ap1:
                    del bad_signal_counters[mac]

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
