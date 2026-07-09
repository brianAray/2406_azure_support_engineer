import os
import time
from flask import Flask, jsonify, request

app = Flask(__name__)

# State flags for simulation
is_running = True
firewall_allows_probe_ip = True

# Read node name and IP from environment variables, defaulting to vm-web-01
NODE_NAME = os.environ.get("NODE_NAME", "vm-web-01")
NODE_IP = os.environ.get("NODE_IP", "10.0.1.4")

@app.route("/")
def index():
    if not is_running:
        return "Service Unavailable", 503
    return f"Hello from {NODE_NAME} ({NODE_IP})! The web application is responding normally."

@app.route("/health")
def health():
    # If the process is killed
    if not is_running:
        return "Service Unavailable", 503
    
    # If firewall blocks probe IP (168.63.129.16)
    if not firewall_allows_probe_ip:
        # Sleep to simulate a network packet drop / connection timeout
        time.sleep(4.0)
        return "Gateway Timeout (Firewall Blocked)", 504
        
    return jsonify({
        "status": "Healthy",
        "node": NODE_NAME,
        "ip": NODE_IP,
        "timestamp": int(time.time())
    })

@app.route("/api/status")
def status():
    # Diagnostic status endpoint (always returns status regardless of simulated failure)
    return jsonify({
        "node": NODE_NAME,
        "ip": NODE_IP,
        "is_running": is_running,
        "firewall_allows_probe_ip": firewall_allows_probe_ip,
        "health_probe_status": "Healthy" if (is_running and firewall_allows_probe_ip) else ("Down (Process offline)" if not is_running else "Unhealthy (Security rule blocks probe IP 168.63.129.16)")
    })

@app.route("/api/toggle-process", methods=["POST"])
def toggle_process():
    global is_running
    is_running = not is_running
    return jsonify({"success": True, "is_running": is_running})

@app.route("/api/toggle-firewall", methods=["POST"])
def toggle_firewall():
    global firewall_allows_probe_ip
    firewall_allows_probe_ip = not firewall_allows_probe_ip
    return jsonify({"success": True, "firewall_allows_probe_ip": firewall_allows_probe_ip})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
