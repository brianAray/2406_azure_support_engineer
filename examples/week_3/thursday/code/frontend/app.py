import time
import requests
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# List of backend configurations (matching IP naming conventions of Wednesday)
BACKENDS = [
    {
        "id": "vm-web-01",
        "name": "vm-web-01",
        "ip": "10.0.1.4",
        "port": 80,
        "health_endpoint": "http://10.0.1.4:80/health",
        "status_endpoint": "http://10.0.1.4:80/api/status",
        "toggle_process_endpoint": "http://10.0.1.4:80/api/toggle-process",
        "toggle_firewall_endpoint": "http://10.0.1.4:80/api/toggle-firewall"
    },
    {
        "id": "vm-web-02",
        "name": "vm-web-02",
        "ip": "10.0.1.5",
        "port": 80,
        "health_endpoint": "http://10.0.1.5:80/health",
        "status_endpoint": "http://10.0.1.5:80/api/status",
        "toggle_process_endpoint": "http://10.0.1.5:80/api/toggle-process",
        "toggle_firewall_endpoint": "http://10.0.1.5:80/api/toggle-firewall"
    }
]

# Track the round robin distribution index
round_robin_index = 0

def probe_backend_health(backend):
    """
    Simulates Azure Load Balancer health probe (TCP/HTTP GET to /health on port 80).
    Timeout is set to 2.5 seconds.
    """
    start_time = time.time()
    try:
        # Check HTTP /health page
        response = requests.get(backend["health_endpoint"], timeout=2.5)
        duration = int((time.time() - start_time) * 1000)
        if response.status_code == 200:
            return "Healthy", f"HTTP 200 OK (Probe response in {duration}ms)", duration
        else:
            return "Unhealthy", f"HTTP {response.status_code} received", duration
    except requests.exceptions.Timeout:
        duration = int((time.time() - start_time) * 1000)
        return "Unhealthy", "Probe timed out (No response from instance)", duration
    except requests.exceptions.ConnectionError:
        duration = int((time.time() - start_time) * 1000)
        return "Unhealthy", "Connection refused (Process offline)", duration
    except Exception as e:
        duration = int((time.time() - start_time) * 1000)
        return "Unhealthy", str(e), duration

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/lb-status")
def lb_status():
    """
    Returns the real-time status of the Load Balancer, backend pool, and health check state.
    """
    pool_status = []
    for backend in BACKENDS:
        # Get diagnostic configuration flags directly from backend api
        try:
            status_resp = requests.get(backend["status_endpoint"], timeout=1.0).json()
            is_running = status_resp["is_running"]
            firewall_allows_probe_ip = status_resp["firewall_allows_probe_ip"]
        except Exception:
            is_running = False
            firewall_allows_probe_ip = False
        
        # Audit health probe status
        probe_state, probe_msg, probe_duration = probe_backend_health(backend)
        
        pool_status.append({
            "id": backend["id"],
            "name": backend["name"],
            "ip": backend["ip"],
            "port": backend["port"],
            "is_running": is_running,
            "firewall_allows_probe_ip": firewall_allows_probe_ip,
            "probe_state": probe_state,
            "probe_message": probe_msg,
            "probe_duration": probe_duration
        })

    return jsonify({
        "lb_name": "lb-app-prod-01",
        "frontend_ip": "198.51.100.99",
        "backend_pool": pool_status
    })

@app.route("/api/route-request", methods=["POST"])
def route_request():
    """
    Simulates routing a client request across the healthy backends.
    """
    global round_robin_index
    client_ip = request.json.get("client_ip", "203.0.113.10")
    
    # 1. Audit backend pool health
    healthy_backends = []
    for backend in BACKENDS:
        probe_state, _, _ = probe_backend_health(backend)
        if probe_state == "Healthy":
            healthy_backends.append(backend)
            
    # 2. Route request if healthy backends exist
    if not healthy_backends:
        return jsonify({
            "status": "Failed",
            "code": 503,
            "detail": "HTTP 503 Service Unavailable: Load balancer frontend has no healthy instances in pool.",
            "node": "None",
            "ip": "N/A",
            "duration": 0
        })
        
    # Round-robin selection
    selected_backend = healthy_backends[round_robin_index % len(healthy_backends)]
    round_robin_index += 1
    
    # Send request to the selected backend
    start_time = time.time()
    try:
        resp = requests.get(f"http://{selected_backend['ip']}:80/", timeout=2.5)
        duration = int((time.time() - start_time) * 1000)
        if resp.status_code == 200:
            return jsonify({
                "status": "Success",
                "code": 200,
                "detail": resp.text,
                "node": selected_backend["name"],
                "ip": selected_backend["ip"],
                "duration": duration
            })
        else:
            return jsonify({
                "status": "Failed",
                "code": resp.status_code,
                "detail": f"HTTP {resp.status_code} received from backend.",
                "node": selected_backend["name"],
                "ip": selected_backend["ip"],
                "duration": duration
            })
    except requests.exceptions.Timeout:
        duration = int((time.time() - start_time) * 1000)
        return jsonify({
            "status": "Timeout",
            "code": 504,
            "detail": "HTTP 504 Gateway Timeout: Connection to backend timed out.",
            "node": selected_backend["name"],
            "ip": selected_backend["ip"],
            "duration": duration
        })
    except Exception as e:
        duration = int((time.time() - start_time) * 1000)
        return jsonify({
            "status": "Error",
            "code": 500,
            "detail": str(e),
            "node": selected_backend["name"],
            "ip": selected_backend["ip"],
            "duration": duration
        })

@app.route("/api/toggle-backend", methods=["POST"])
def toggle_backend():
    """
    Sends toggle command to target backend.
    """
    target_id = request.json.get("target")
    toggle_type = request.json.get("type") # "process" or "firewall"
    
    target_backend = None
    for backend in BACKENDS:
        if backend["id"] == target_id:
            target_backend = backend
            break
            
    if not target_backend:
        return jsonify({"error": "Backend not found"}), 400
        
    url = target_backend["toggle_process_endpoint"] if toggle_type == "process" else target_backend["toggle_firewall_endpoint"]
    try:
        resp = requests.post(url, timeout=2.0)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": f"Failed to reach backend VM: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
