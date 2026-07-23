# Guide - Stage 2

This guide provides a hands-on lab walkthrough for querying Log Analytics, inspecting Application Insights telemetry, and performing SRE incident root-cause analysis on the Stage 1 deployed Banking Microservice.

---

## 1. Prerequisites & Setup

Ensure your Stage 1 Capstone Banking Microservice is currently running on Azure.

Find your Web App URL and Log Analytics Workspace ID:

```bash
# 1. Get Web App URL
WEBAPP_URL=$(az webapp list --query "[?contains(name, 'app-banking-api')].defaultHostName" -o tsv | tr -d '\r')
echo "Web App URL: https://$WEBAPP_URL"

# 2. Get Log Analytics Workspace Customer ID (GUID)
LAW_ID=$(az monitor log-analytics workspace list --query "[?contains(name, 'law-banking-prod')].customerId" -o tsv | tr -d '\r')
echo "Log Analytics Workspace Customer ID: $LAW_ID"
```

---

## 2. Hands-on Lab: Generating Telemetry Traffic

Navigate to the Stage 2 code directory:

```bash
cd weeklytechrepo/Identity-Security-Docker/demo/Observability-Troubleshooting-Demo/code/
```

Run the traffic generator script to produce healthy, unauthorized, and RBAC failure events:

```bash
./generate_telemetry_traffic.sh "https://$WEBAPP_URL"
```

*Note: Telemetry ingestion into Azure Log Analytics typically takes 1 to 3 minutes to appear in query results.*

---

## 3. Hands-on Lab: Executing KQL Diagnostic Queries

Open **Log Analytics Workspace** (`law-banking-prod-<RANDOM>`) in the Azure Portal -> **Logs** (or execute queries via Azure CLI).

### Task 3.1: Request Summary & HTTP Code Distribution

Run this KQL query to inspect total request volume grouped by HTTP status code:

```
AppRequests
| where TimeGenerated > ago(1h)
| summarize RequestCount = count() by ResultCode
| order by RequestCount desc
```

**SRE Analysis:** Compare the ratio of `200 OK` vs. `401 Unauthorized` and `403 Forbidden` responses.

---

### Task 3.2: Security Audit - Investigating Unauthorized Access

Filter specifically for security failure events (`401` and `403` HTTP status codes):

```
AppRequests
| where TimeGenerated > ago(1h)
| where ResultCode in ("401", "403")
| project TimeGenerated, OperationName, Url, ResultCode, ClientIP, OperationId
| order by TimeGenerated desc
```

**SRE Analysis:** Note down an `OperationId` from a `403 Forbidden` row to trace in Task 3.4.

---

### Task 3.3: PostgreSQL Dependency Latency Analysis

Calculate database response time percentiles (P50, P90, P99) for SQL queries executed by the microservice:

```
AppDependencies
| where TimeGenerated > ago(1h)
| summarize
    TotalQueries = count(),
    AvgDurationMs = avg(DurationMs),
    P50_Ms = percentiles(DurationMs, 50),
    P90_Ms = percentiles(DurationMs, 90),
    P99_Ms = percentiles(DurationMs, 99)
  by Target
```

**SRE Analysis:** Evaluate if P99 latency exceeds your team's Service Level Objective (SLO) threshold (e.g. < 200ms).

---

### Task 3.4: Distributed Trace Correlation via `OperationId`

Correlate an HTTP request log with its exact exception details using `OperationId`:

```
AppRequests
| where TimeGenerated > ago(1h)
| where ResultCode startswith "5" or ResultCode == "403"
| join kind=inner (
    AppTraces
    | project TimeGenerated, Message, OperationId
) on $left.OperationId == $right.OperationId
| project RequestTime = TimeGenerated, Url, ResultCode, Message, OperationId
```

**SRE Analysis:** Observe how the `OperationId` ties front-end HTTP requests to back-end trace messages across microservice boundaries.

---

## 4. Hands-on Lab: Running KQL from Terminal (Optional)

You can also run KQL queries directly from your local terminal using the Python runner script:

```bash
python run_kql_investigation.py "$LAW_ID"
```

---

## 5. Reference Troubleshooting Table

| Symptom / Error | Root Cause | SRE Remediation Action |
| --- | --- | --- |
| KQL queries return 0 rows. | Telemetry ingestion delay (1-3 minutes) or query time range filter (`ago(1h)`) is too narrow. | Wait 2 minutes and change time picker to `Past 4 hours`. |
| `AppDependencies` table is empty. | OpenTelemetry instrumentation string missing in Web App settings. | Verify `APPLICATIONINSIGHTS_CONNECTION_STRING` is set on Web App. |
| High P99 latency on PostgreSQL queries. | Missing database index or insufficient database compute SKU (`Standard_B1ms`). | Audit PostgreSQL query execution plans or scale up server SKU. |

---

## 6. Cost-Control Check

When finished with the lab, clean up all cloud resources:

```bash
RG_NAME=$(az webapp list --query "[?contains(name, 'app-banking-api')].resourceGroup" -o tsv | tr -d '\r')
az group delete --name $RG_NAME --yes --no-wait
```