#!/usr/bin/env python3
"""
webhook_server.py  (Mist Real-Time Event Webhook Receiver)

Starts a local Flask HTTP server on port 5000 that receives POST webhook
events pushed directly from the Juniper Mist cloud platform.  Each incoming
event is categorised by topic and appended to a corresponding JSON log file.

Usage:
    1. Run this server on a machine reachable by the Mist cloud.
    2. Configure a Mist Webhook pointing to: http://<your-ip>:5000/events
    3. Events are saved to:
       - logs_ap_events.json      (Access Point events)
       - logs_switch_events.json  (Switch events)
       - logs_gateway_events.json (WAN Gateway / SRX events)
       - logs_client_events.json  (Wi-Fi and wired client events)
       - logs_other_events.json   (Alarms and uncategorised events)

Install dependencies:
    pip install flask
"""

from flask import Flask, request, json
import os
from datetime import datetime

app = Flask(__name__)

# Mapping of event category → JSON log file path
LOG_FILES = {
    "ap":      "logs_ap_events.json",
    "switch":  "logs_switch_events.json",
    "gateway": "logs_gateway_events.json",
    "client":  "logs_client_events.json",
    "other":   "logs_other_events.json",
}

# ======================================================
# Helpers
# ======================================================

def append_to_log(filename, new_data):
    """
    Reads the existing JSON array from `filename`, appends `new_data`,
    and writes the updated list back.  Creates the file if it doesn't exist.
    """
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump([], f)

    try:
        with open(filename, "r") as f:
            data = json.load(f)
            if not isinstance(data, list):
                data = []
    except Exception:
        data = []

    new_data["_received_at"] = datetime.now().isoformat()
    data.append(new_data)

    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

    print(f"    [+] Saved event to {filename}")

# ======================================================
# Webhook Endpoint
# ======================================================

@app.route("/events", methods=["POST"])
def handle_webhook():
    """
    Receives Mist webhook POST requests.
    The payload must be JSON with fields: topic (str), events (list).
    """
    try:
        payload = request.json
        topic   = payload.get("topic", "unknown")
        events  = payload.get("events", [])

        print(f"\n[!] Received Webhook: Topic='{topic}' ({len(events)} events)")

        for event in events:
            if topic == "device-events":
                dev_type = event.get("device_type")
                if dev_type == "ap":
                    append_to_log(LOG_FILES["ap"],      event)
                elif dev_type == "switch":
                    append_to_log(LOG_FILES["switch"],  event)
                elif dev_type == "gateway":
                    append_to_log(LOG_FILES["gateway"], event)
                else:
                    append_to_log(LOG_FILES["other"],   event)

            elif "client" in topic:
                append_to_log(LOG_FILES["client"], event)

            elif topic == "alarms":
                append_to_log(LOG_FILES["other"], event)

            else:
                print(f"    [?] Unrecognised topic: {topic}. Using generic log.")
                append_to_log(LOG_FILES["other"], event)

        return "OK", 200

    except Exception as e:
        print(f"[!] Error processing webhook: {e}")
        return "Error", 500

# ======================================================
# Entry Point
# ======================================================

if __name__ == "__main__":
    print("=== Mist Webhook Listener ===")
    print("Listening on http://0.0.0.0:5000/events")
    print("Waiting for events...\n")
    app.run(host="0.0.0.0", port=5000)
