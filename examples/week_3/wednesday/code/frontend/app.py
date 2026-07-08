import time
import socket
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Define targets and their associated metadata/simulated UDR paths
TARGETS = {
    "backend": {
        "name": "Backend API Service",
        "ip": "10.0.2.4",
        "port": 5000,
        "type": "http",
        "url": "http://10.0.2.4:5000/api/data",
        "udr_info": "UDR: RouteToBackendViaNVA -> Next Hop: VirtualAppliance (10.0.3.4)",
        "expected": "Success (Inspected by NVA & permitted by Backend NSG)"
    },
    "ssh": {
        "name": "Backend SSH Management",
        "ip": "10.0.2.4",
        "port": 22,
        "type": "socket",
        "udr_info": "UDR: RouteToBackendViaNVA -> Next Hop: VirtualAppliance (10.0.3.4)",
        "expected": "Timeout / Blocked (Tuesday's Backend NSG filters out SSH)"
    },
    "external-api": {
        "name": "High-Performance External API",
        "ip": "198.51.100.50",
        "port": 80,
        "type": "socket",
        "udr_info": "UDR: BypassNVAForExtAPI -> Next Hop: Internet (Bypass NVA)",
        "expected": "Success / Connection Refused (Bypasses NVA directly to Internet)"
    },
    "malicious": {
        "name": "Known Malicious Range",
        "ip": "203.0.113.15",
        "port": 80,
        "type": "socket",
        "udr_info": "UDR: DropMaliciousTraffic -> Next Hop: None (Black-hole drop)",
        "expected": "Timeout (Silent drop - packet discarded by UDR)"
    },
    "onprem": {
        "name": "On-Premises Database Server",
        "ip": "172.16.5.10",
        "port": 443,
        "type": "socket",
        "udr_info": "UDR: RouteToOnPrem -> Next Hop: VirtualNetworkGateway (VPN)",
        "expected": "Timeout / Route Error (Routed to Gateway; fails if gateway is down)"
    }
}

@app.route("/")
def index():
    return render_template("index.html", targets=TARGETS)

@app.route("/test-route", methods=["POST"])
def test_route():
    target_key = request.json.get("target")
    if target_key not in TARGETS:
        return jsonify({"error": "Invalid target"}), 400

    target = TARGETS[target_key]
    status = "Failed"
    detail = ""
    start_time = time.time()

    try:
        if target["type"] == "http":
            # Attempt HTTP request with a short timeout
            response = requests.get(target["url"], timeout=3.0)
            duration = int((time.time() - start_time) * 1000)
            if response.status_code == 200:
                status = "Success"
                detail = f"HTTP 200 OK: {response.json().get('message', 'No response message')}"
            else:
                status = "Failed"
                detail = f"HTTP {response.status_code} received."
        else:
            # Socket connection attempt
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((target["ip"], target["port"]))
            s.close()
            duration = int((time.time() - start_time) * 1000)
            status = "Success"
            detail = "TCP socket connection established successfully."
    except requests.exceptions.Timeout:
        duration = int((time.time() - start_time) * 1000)
        status = "Timeout"
        detail = "Connection timed out after 3.0 seconds (packets dropped)."
    except socket.timeout:
        duration = int((time.time() - start_time) * 1000)
        status = "Timeout"
        detail = "TCP connection timed out after 3.0 seconds (packets dropped)."
    except requests.exceptions.ConnectionError as e:
        duration = int((time.time() - start_time) * 1000)
        # Often connection refused is successful routing but no service listening
        status = "Connection Refused"
        detail = "Connection reached destination but was refused (no service running on port)."
    except Exception as e:
        duration = int((time.time() - start_time) * 1000)
        status = "Error"
        detail = str(e)

    return jsonify({
        "status": status,
        "duration": duration,
        "detail": detail,
        "udr_info": target["udr_info"],
        "expected": target["expected"]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
