def parse_log_line(line):
    """
    Parses a single log line in Common Log Format.
    Example line:
    192.168.1.10 - - [10/Jun/2026:10:15:30 +0000] "GET /api/v1/users HTTP/1.1" 200 45
    """
    try:
        parts = line.strip().split()
        if len(parts) < 10:
            return None
        
        ip = parts[0]
        # Method and Path are inside the HTTP request string quotes
        method = parts[5].replace('"', '')
        path = parts[6]
        status = int(parts[8])
        latency = int(parts[9])
        
        return {
            "ip": ip,
            "method": method,
            "path": path,
            "status": status,
            "latency": latency
        }
    except Exception as e:
        print(f"Error parsing line: {line}. Detail: {e}")
        return None

def analyze_logs(file_path):
    """
    Reads the logs file, parses each line, and aggregates metrics using lists, sets, and dicts.
    """
    all_requests = []
    unique_ips = set()
    status_counts = {}
    slow_requests = []

    with open(file_path, 'r') as file:
        for line in file:
            parsed = parse_log_line(line)
            if not parsed:
                continue
            
            all_requests.append(parsed)
            unique_ips.add(parsed["ip"])
            
            # Increment status code count
            status = parsed["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Slow requests filter (>100ms)
            if parsed["latency"] > 100:
                slow_requests.append(parsed)

    print("=========================================")
    print("SRE LOG ANALYSIS SUMMARY REPORT")
    print("=========================================")
    print(f"Total Requests Processed: {len(all_requests)}")
    print(f"Unique Client IPs: {len(unique_ips)}")
    print(f"HTTP Status Code Breakdown: {status_counts}")
    print(f"Slow Requests (>100ms) Count: {len(slow_requests)}")
    print("-----------------------------------------")
    print("Detailed List of Unique Client IPs:")
    for ip in sorted(unique_ips):
        print(f"  ¿ {ip}")
    
    print("\nDetailed List of Slow Requests:")
    for req in slow_requests:
        print(f"  ¿ {req['method']} {req['path']} - Latency: {req['latency']}ms (Status: {req['status']})")
    print("=========================================")

if __name__ == "__main__":
    import os
    # Find logs.txt relative to this script's directory (handles running from solution subfolder)
    # Check current directory, parent directory, etc.
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "logs.txt"),
        os.path.join(os.path.dirname(__file__), "..", "starter_code", "logs.txt")
    ]
    logs_file = None
    for p in possible_paths:
        if os.path.exists(p):
            logs_file = p
            break
            
    if logs_file:
        analyze_logs(logs_file)
    else:
        print("Error: logs.txt not found.")
