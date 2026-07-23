import sys
import subprocess
import json

AZ_BIN = "az"

def run_az_kql(workspace_id: str, query: str):
    """
    Executes a KQL query against Azure Log Analytics using Azure CLI.
    """
    workspace_id = workspace_id.strip()
    
    # If a workspace name or ARM ID was provided instead of a GUID, resolve it to customerId
    if len(workspace_id) != 36:
        try:
            lookup_cmd = [AZ_BIN, "monitor", "log-analytics", "workspace", "list", "-o", "json"]
            res = subprocess.run(lookup_cmd, capture_output=True, text=True)
            workspaces = json.loads(res.stdout or "[]")
            
            matches = [
                w for w in workspaces 
                if workspace_id.lower() in w.get("name", "").lower() or workspace_id.lower() in w.get("id", "").lower()
            ]
            
            if matches:
                exact = [w for w in matches if w.get("name", "").lower() == workspace_id.lower()]
                selected = exact[0] if exact else matches[-1]
                workspace_id = selected["customerId"]
                print(f"Targeting Workspace: {selected.get('name')} (Customer ID: {workspace_id})")
                if len(matches) > 1 and not exact:
                    print(f"Notice: {len(matches)} workspaces matched '{workspace_id}'. To target a specific one, pass its full name:")
                    for m in matches:
                        print(f"  - Name: {m.get('name')} | Customer ID: {m.get('customerId')}")
        except Exception:
            pass

    print(f"\n--- Running KQL Query (Workspace GUID: {workspace_id}) ---\n{query.strip()}\n")
    
    cmd = [
        AZ_BIN, "monitor", "log-analytics", "query",
        "--workspace", workspace_id,
        "--analytics-query", query,
        "-o", "json"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        if not data:
            print("No records found (ingestion may still be in progress).")
            return
            
        # Print results as formatted JSON or simple table
        print(f"Results ({len(data)} rows):")
        print(json.dumps(data, indent=2))
        
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr or ""
        if "Failed to resolve table" in err_msg or "AppRequests" in err_msg:
            print("Notice: The 'AppRequests' table schema has not been provisioned in this Log Analytics Workspace yet.")
            print("This happens when Application Insights has not yet ingested its first batch of HTTP telemetry.")
            print("Attempting fallback query on legacy 'requests' table...\n")
            fallback_query = query.replace("AppRequests", "requests").replace("ResultCode", "resultCode")
            cmd[5] = fallback_query
            try:
                res_fb = subprocess.run(cmd, capture_output=True, text=True, check=True)
                data_fb = json.loads(res_fb.stdout)
                print(f"Results from 'requests' table ({len(data_fb)} rows):")
                print(json.dumps(data_fb, indent=2))
            except Exception:
                print("Fallback query also returned no table. Please wait 2-3 minutes after sending traffic for schema creation.")
        else:
            print(f"Error running KQL query: {err_msg}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_kql_investigation.py <WORKSPACE_ID>")
        sys.exit(1)
        
    workspace_id = sys.argv[1]
    
    # Sample KQL Query 1: Summarize AppRequests over the last 24h
    kql_summary = """
    AppRequests
    | where TimeGenerated > ago(24h)
    | summarize RequestCount = count() by ResultCode
    | order by RequestCount desc
    """
    run_az_kql(workspace_id, kql_summary)

    # Sample KQL Query 2: Security Audit (401 & 403 Access Denials)
    kql_security = """
    AppRequests
    | where TimeGenerated > ago(24h)
    | where ResultCode in ("401", "403")
    | project TimeGenerated, Url, ResultCode, ClientIP, OperationId
    | take 5
    """
    run_az_kql(workspace_id, kql_security)

    # Sample KQL Query 3: Summarize Dependency Latency (P50, P90, P99)
    kql_dependencies = """
    AppDependencies
    | where TimeGenerated > ago(24h)
    | summarize 
        TotalQueries = count(),
        AvgDurationMs = avg(DurationMs),
        P50_Ms = percentiles(DurationMs, 50),
        P90_Ms = percentiles(DurationMs, 90),
        P99_Ms = percentiles(DurationMs, 99)
      by Target
    """
    run_az_kql(workspace_id, kql_dependencies)
