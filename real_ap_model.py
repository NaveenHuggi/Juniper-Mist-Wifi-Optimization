#!/usr/bin/env python3
"""
real_ap_model.py  (Mist Automated Client Roaming — ML Pipeline v3)

Features:
1. Suppresses ALL warnings for clean terminal output.
2. Visual RSSI signal-strength bars for quick readability.
3. HYBRID LOGIC: If RSSI < RSSI_CRITICAL, the hard failsafe overrides the
   LSTM model and forces a 'Degraded' label — no buffering needed.
4. 3-Strike hysteresis: only disconnects after 3 consecutive 'Degraded' polls.

Usage:
    Set the environment variables below, then run:
        python real_ap_model.py

Environment Variables:
    MIST_API_TOKEN  — Your Juniper Mist API token
    MIST_ORG_ID     — Your Mist Organisation ID
    MIST_SITE_ID    — The Site ID to monitor
    MIST_API_HOST   — API base URL (default: https://api.gc4.mist.com)
"""

import os
import logging
import warnings

# --- 1. SILENCE WARNINGS (Must be done before imports) ---
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'   # Silence TensorFlow C++ logs
logging.getLogger('tensorflow').setLevel(logging.FATAL)
warnings.filterwarnings("ignore")           # Silence Sklearn / Python warnings

import time
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from collections import deque

# ML Libraries
from sklearn.preprocessing import LabelEncoder, StandardScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.utils import to_categorical

# ================= CONFIGURATION =================
TOKEN   = os.getenv("MIST_API_TOKEN", "YOUR_MIST_API_TOKEN")
ORG_ID  = os.getenv("MIST_ORG_ID",   "YOUR_ORG_ID")
SITE_ID = os.getenv("MIST_SITE_ID",  "YOUR_SITE_ID")
API_HOST = os.getenv("MIST_API_HOST", "https://api.gc4.mist.com")

FEATURES = ["rssi", "snr", "retries", "tx_rate", "rx_rate", "channel_util"]

POLL_INTERVAL            = 5     # seconds between API polls
DATA_COLLECTION_SECONDS  = 120   # seconds to collect training data
SEQ_LEN                  = 5     # LSTM sequence length
RSSI_SAFETY              = -65   # signals better than this → skip (Safe zone)
RSSI_CRITICAL            = -75   # hard failsafe: worse than this → force Degraded
DEGRADED_THRESHOLD       = 3     # strikes before disconnect
CSV_FILE                 = "client_dataset_clean.csv"

HEADERS = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type": "application/json"
}

client_buffers            = {}
consecutive_degraded_counts = {}

# ======================================================
# Helpers
# ======================================================

def get_signal_bars(rssi):
    """Returns a visual signal-strength bar string for the given RSSI value."""
    if rssi > -60: return "[|||||] Excellent"
    if rssi > -70: return "[||||.] Good"
    if rssi > -75: return "[||...] Fair"
    if rssi > -80: return "[|....] Weak"
    return "[.....] CRITICAL"

def fetch_clients():
    url = f"{API_HOST}/api/v1/sites/{SITE_ID}/stats/clients"
    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

def disconnect_client(mac):
    url = f"{API_HOST}/api/v1/sites/{SITE_ID}/clients/disconnect"
    payload = {"macs": [mac]}
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=5)
        print(f"\n >>> [ACTION] DISCONNECTED {mac} <<<")
    except Exception as e:
        print(f"[!] Kick failed: {e}")

# ======================================================
# Data Collection
# ======================================================

def collect_training_data(duration_sec):
    """
    Polls the Mist API for `duration_sec` seconds, labels each sample as
    'Good' or 'Degraded' based on RSSI and retry-rate thresholds, and
    returns the resulting DataFrame.

    Tip: Walk far from the AP during collection to generate 'Degraded' samples.
    """
    print(f"\n[INFO] Collecting Data ({duration_sec}s). Please WALK AWAY from AP to generate bad data.")
    start = time.time()
    rows = []

    while time.time() - start < duration_sec:
        clients = fetch_clients()
        if not clients:
            print(".", end="", flush=True)

        for c in clients:
            rssi       = c.get("rssi", -100)
            retries    = c.get("retries", 0)
            tx_pkts    = c.get("tx_pkts", 1)
            retry_rate = (retries / tx_pkts) * 100 if tx_pkts > 0 else 0

            label = "Degraded" if rssi < -75 or retry_rate > 15 else "Good"

            rows.append({
                "timestamp":    datetime.now(timezone.utc),
                "mac":          c.get("mac"),
                "rssi":         rssi,
                "snr":          c.get("snr", 0),
                "retries":      retries,
                "tx_rate":      c.get("tx_rate", 0),
                "rx_rate":      c.get("rx_rate", 0),
                "channel_util": c.get("channel_util", 0),
                "label":        label
            })

        print(f"\rCollecting... {int(time.time()-start)}s | Samples: {len(rows)}", end="")
        time.sleep(POLL_INTERVAL)

    print("\n")
    df = pd.DataFrame(rows)
    if df.empty or len(df["label"].unique()) < 2:
        print("[ERROR] Data imbalance (Did you walk?). Results may be poor.")

    return df

# ======================================================
# Model Training
# ======================================================

def train_lstm(df):
    """
    Trains a lightweight LSTM model on the collected telemetry DataFrame.
    Returns: (model, scaler, label_encoder)
    """
    print("[INFO] Training Model (Silence Mode)...")
    X = df[FEATURES]
    y = df["label"]

    label_encoder = LabelEncoder()
    y_enc = label_encoder.fit_transform(y)
    y_cat = to_categorical(y_enc)

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_seq, y_seq = [], []
    for i in range(len(X_scaled) - SEQ_LEN):
        X_seq.append(X_scaled[i:i + SEQ_LEN])
        y_seq.append(y_cat[i + SEQ_LEN])

    model = Sequential([
        LSTM(32, input_shape=(SEQ_LEN, len(FEATURES))),
        Dense(16, activation="relu"),
        Dense(2,  activation="softmax")
    ])
    model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
    model.fit(np.array(X_seq), np.array(y_seq), epochs=5, batch_size=16, verbose=0)

    print("[INFO] Training Complete.")
    return model, scaler, label_encoder

# ======================================================
# Live Loop (With Failsafe)
# ======================================================

def live_prediction_loop(model, scaler, encoder):
    """
    Continuously polls all clients, predicts their connection quality with the
    LSTM model, and disconnects clients that remain 'Degraded' for
    DEGRADED_THRESHOLD consecutive polls (or breach the RSSI_CRITICAL hard limit).
    """
    print("\n[INFO] Starting Live Monitor.")
    print(f"       Policy: Kick if Degraded x{DEGRADED_THRESHOLD} OR RSSI < {RSSI_CRITICAL} dBm\n")

    while True:
        clients = fetch_clients()
        print(".", end="", flush=True)

        for c in clients:
            mac  = c.get("mac")
            rssi = c.get("rssi", -100)
            bars = get_signal_bars(rssi)

            # Skip clients with a strong signal
            if rssi > RSSI_SAFETY:
                if consecutive_degraded_counts.get(mac, 0) > 0:
                    print(f"\n[RESET] {mac} recovered. {bars} ({rssi} dBm)")
                    consecutive_degraded_counts[mac] = 0
                continue

            # Buffer features for the LSTM sequence
            features = [
                c.get("rssi", -100), c.get("snr", 0), c.get("retries", 0),
                c.get("tx_rate", 0), c.get("rx_rate", 0), c.get("channel_util", 0)
            ]

            if mac not in client_buffers:
                client_buffers[mac] = deque(maxlen=SEQ_LEN)
            client_buffers[mac].append(features)

            if len(client_buffers[mac]) < SEQ_LEN:
                continue

            # LSTM Prediction
            X_live = scaler.transform(np.array(client_buffers[mac])).reshape(1, SEQ_LEN, len(FEATURES))
            pred   = model.predict(X_live, verbose=0)
            label  = encoder.inverse_transform([np.argmax(pred)])[0]
            conf   = np.max(pred)

            # HYBRID FAILSAFE: hard RSSI override
            forced_logic = False
            if rssi < RSSI_CRITICAL and label == "Good":
                label        = "Degraded"
                forced_logic = True

            status_msg = f"\n[{datetime.now().strftime('%H:%M:%S')}] {mac} | {bars} {rssi}dBm | AI: {label} ({conf:.2f})"
            if forced_logic:
                status_msg += " [FAILSAFE TRIGGERED]"
            print(status_msg)

            # 3-Strike Logic
            if label == "Degraded":
                strikes = consecutive_degraded_counts.get(mac, 0) + 1
                consecutive_degraded_counts[mac] = strikes
                print(f"   >>> STRIKE {strikes}/{DEGRADED_THRESHOLD}")

                if strikes >= DEGRADED_THRESHOLD:
                    disconnect_client(mac)
                    consecutive_degraded_counts[mac] = 0
                    client_buffers[mac].clear()
            else:
                consecutive_degraded_counts[mac] = 0

        time.sleep(POLL_INTERVAL)

# ======================================================
# Entry Point
# ======================================================

def main():
    if "YOUR_MIST_API_TOKEN" in TOKEN:
        print("[ERROR] Please set the MIST_API_TOKEN environment variable before running.")
        return

    df = collect_training_data(DATA_COLLECTION_SECONDS)
    model, scaler, encoder = train_lstm(df)
    live_prediction_loop(model, scaler, encoder)

if __name__ == "__main__":
    main()
