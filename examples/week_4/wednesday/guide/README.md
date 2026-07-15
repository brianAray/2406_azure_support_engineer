# Guide

This guide walks you step-by-step through running, optimizing, and verifying Kusto Query Language (KQL) queries. 

---

## 1. Architectural & Query Pipeline Overview

Below is the conceptual pipeline data flow of a KQL query. Telemetry is ingested from your production resources (like `vm-kqlserver-prod-01` syslog logs and `nsg-kqldiags-prod-01` diagnostics) into your Log Analytics Workspace database. The KQL query operates sequentially from top-to-bottom:

```
        Raw Log Table (e.g. AppRequests)
                      |
                      v [Pipe operator '|']
        where TimeGenerated > ago(12h)  <-- Filter early to reduce memory scan
                      |
                      v [Pipe operator '|']
        project TimeGenerated, Url, ... <-- Prune columns to reduce width
                      |
                      v [Pipe operator '|']
        summarize count() by bin(...)    <-- Bucket data for trend analysis
                      |
                      v
             Output Chart/Table
```

---

## 2. Core Concepts Reference

### Tabular Operators

- **`where`**: Filters records. Keep it at the top of the query (especially the `TimeGenerated` filters) to limit data scanned.
- **`project`**: Selects specific columns to include in the output, keeping query operations light.
- **`extend`**: Computes a new column dynamically on-the-fly without altering the database schema.
- **`summarize`**: Groups data rows by a key and calculates aggregations (e.g., `count()`, `avg()`, `max()`).
- **`take` / `limit`**: Returns up to the specified number of rows. Excellent for checking schemas without triggering massive data scans.

### Advanced Operators

- **`bin()`**: Rounds a timestamp down to a standard time bucket (e.g. `10m`, `15m`, `1h`) to allow grouping logs over time.
- **`parse`**: Extracts structured columns from unstructured text-based log entries.
- **`join`**: Merges records from two tables by matching key columns. Remember: **Place the smaller table on the left** of the join to optimize database engine performance.

### Optimization Rules

1. **Filter Early:** Check `TimeGenerated` first.
2. **Use Indexed Word Filters:** Use `has` instead of `contains` where possible, because `has` leverages indexes for full words, while `contains` scans substrings character-by-character.
3. **Column Pruning:** Drop unnecessary columns early with `project`.

---

## 3. Step-by-Step Lab Execution

### Step 0: Tuesday's Workspace Setup (If Starting Fresh)

If you do not have Tuesday's lab infrastructure active, you can quickly provision the entire environment using the Azure CLI or through the Azure Portal:

#### Option A: Quick Provisioning via Azure CLI

Run the following commands in your terminal to deploy the required resource group, network filters, virtual machine, and Log Analytics workspace:

```bash
# 1. Create Resource Group
az group create --name rg-kql-diagnostics-eastus --location eastus

# 2. Create Network Security Group and Inbound Rules
az network nsg create -g rg-kql-diagnostics-eastus -n nsg-kqldiags-prod-01
az network nsg rule create -g rg-kql-diagnostics-eastus --nsg-name nsg-kqldiags-prod-01 -n Allow-SSH-Inbound --priority 100 --destination-port-ranges 22 --access Allow --protocol Tcp
az network nsg rule create -g rg-kql-diagnostics-eastus --nsg-name nsg-kqldiags-prod-01 -n Allow-FastAPI-8000 --priority 110 --destination-port-ranges 8000 --access Allow --protocol Tcp

# 3. Create Ubuntu VM (Standard_B1s to avoid high costs, with system-assigned identity)
az vm create -g rg-kql-diagnostics-eastus -n vm-kqlserver-prod-01 --image Ubuntu2204 --size Standard_B1s --admin-username azureuser --nsg nsg-kqldiags-prod-01 --generate-ssh-keys --assign-identity

> [!IMPORTANT]
> **WSL SSH Key Configuration:**
> If you ran `az vm create` in PowerShell on the Windows host and want to SSH via WSL, copy the generated private key into WSL and restrict its permissions:
> ```bash
> mkdir -p ~/.ssh
> cp /mnt/c/Users/BrianArayathel/.ssh/id_rsa ~/.ssh/id_rsa
> chmod 600 ~/.ssh/id_rsa
> ```
> *Note: Adjust the username `BrianArayathel` in the path to match your Windows profile name.*

# 4. Create Log Analytics Workspace (set to cost-efficient 30-day retention)
az monitor log-analytics workspace create -g rg-kql-diagnostics-eastus -n law-kqldiags-01 --retention-time 30

# 5. Connect NSG Diagnostic Setting
NSG_ID=$(az network nsg show -g rg-kql-diagnostics-eastus -n nsg-kqldiags-prod-01 --query id -o tsv | tr -d '\r')
WORKSPACE_ID=$(az monitor log-analytics workspace show -g rg-kql-diagnostics-eastus -n law-kqldiags-01 --query id -o tsv | tr -d '\r')
az monitor diagnostic-settings create --name ds-nsgkqldiags-prod-01 --resource $NSG_ID --workspace $WORKSPACE_ID --logs '[{"categoryGroup": "allLogs", "enabled": true}]'

# 6. Create Data Collection Rule (DCR) for Guest VM Syslog Ingestion
cat <<EOF > dcr.json
{
  "location": "eastus",
  "properties": {
    "dataSources": {
      "syslog": [
        {
          "name": "syslogDataSource",
          "streams": ["Microsoft-Syslog"],
          "facilityNames": ["*"],
          "logLevels": ["Debug", "Info", "Notice", "Warning", "Error", "Critical", "Alert", "Emergency"]
        }
      ]
    },
    "destinations": {
      "logAnalytics": [
        {
          "workspaceResourceId": "$WORKSPACE_ID",
          "name": "la-workspace"
        }
      ]
    },
    "dataFlows": [
      {
        "streams": ["Microsoft-Syslog"],
        "destinations": ["la-workspace"]
      }
    ]
  }
}
EOF

az monitor data-collection rule create -g rg-kql-diagnostics-eastus -n dcr-kqlvmlogs-prod-01 --location eastus --rule-file dcr.json
rm dcr.json

# 7. Associate VM with the Data Collection Rule (DCR)
VM_ID=$(az vm show -g rg-kql-diagnostics-eastus -n vm-kqlserver-prod-01 --query id -o tsv | tr -d '\r')
DCR_ID=$(az monitor data-collection rule show -g rg-kql-diagnostics-eastus -n dcr-kqlvmlogs-prod-01 --query id -o tsv | tr -d '\r')
az monitor data-collection rule association create --name "assoc-kqlvmlogs-prod-01" --resource $VM_ID --rule-id $DCR_ID

# 8. Deploy the Azure Monitor Agent VM Extension
az vm extension set -g rg-kql-diagnostics-eastus --vm-name vm-kqlserver-prod-01 --name AzureMonitorLinuxAgent --publisher Microsoft.Azure.Monitor
```

> [!NOTE]
**Understanding the Data Collection Rule (DCR) JSON Schema:**
A DCR consists of three main block components:
> 
> 1. **`dataSources`**: Defines *what* telemetry is collected from the VM. We define a `syslog` data source targeting the standard `Microsoft-Syslog` stream, using `"facilityNames": ["*"]` and a list of `logLevels` to capture all system events.
> 2. **`destinations`**: Defines *where* to route the collected logs. We target `logAnalytics` using the workspace resource ID (`$WORKSPACE_ID`) and assign it a friendly alias (`"la-workspace"`).
> 3. **`dataFlows`**: Binds the data sources to the destinations. It defines the flow logic: "Take all telemetry from the `Microsoft-Syslog` stream and deliver it to `la-workspace`."

#### Option B: Provisioning via Azure Portal

1. **Resource Group & VM:** Create `rg-kql-diagnostics-eastus`. Provision `vm-kqlserver-prod-01` (Ubuntu 22.04, size `Standard_B1s`) with inbound port rules for TCP `22` (SSH) and `8000` (FastAPI).
2. **Log Analytics Workspace:** Search for and create workspace `law-kqldiags-01` in your resource group. In the **Usage and estimated costs** -> **Data Retention** section, confirm it is set to **30 days** to comply with free tier boundaries.
3. **NSG Diagnostic Settings:** Navigate to **Monitor** -> **Diagnostic Settings** -> select **Network Security Groups** -> select `nsg-kqldiags-prod-01`. Click **+ Add diagnostic setting**, name it `ds-nsgkqldiags-prod-01`, check **allLogs**, and check **Send to Log Analytics workspace** (targeting `law-kqldiags-01`).
4. **Data Collection Rule (DCR) for Syslog:** Search for **Data Collection Rules** -> Click **+ Create**. Rule Name: `dcr-kqlvmlogs-prod-01`. Resources: select `vm-kqlserver-prod-01`. Data source type: select **Linux Syslog** (select **LOG_INFO** facilities). Destination: select your Log Analytics Workspace `law-kqldiags-01`. Click **Create**.

---

### Step 1: Accessing the Log Analytics Workspace

1. Open the Azure Portal.
2. In the top search bar, search for **Log Analytics workspaces** and select it.
3. Select `law-kqldiags-01` (provisioned during Tuesday's lab).
4. In the left sidebar under General, click **Logs**. Close any default query cards to view the query console.

---

### Step 2: Running Reference Queries

Copy and run each of the following queries from `code/demo_kql_queries.kql` in the query editor:

> [!TIP]
**Understanding KQL Time Comparisons:**
In KQL, timestamps increase as you move forward in time. Therefore:
> 
> - `>` (greater than) means **chronologically after** (newer/more recent). E.g., `TimeGenerated > ago(4h)` retrieves logs generated in the **last 4 hours** (newer than 4 hours ago).
> - `<` (less than) means **chronologically before** (older). E.g., `TimeGenerated < ago(4h)` retrieves logs generated **more than 4 hours ago**.
> - If a query using `> ago(N)` returns no results but removing the filter does, the logs were either generated outside that window or the host machine's clock has drifted.

#### Query 1: Basic Ingress Search and Filtering (Filter Early Pattern)

Filter failed HTTP web requests on the application server in the last 4 hours:

```
AppRequests
| where TimeGenerated > ago(4h)
| where Computer == "vm-kqlserver-prod-01"
| where Success == false
| project TimeGenerated, Computer, Url, ResultCode, DurationMs
| take 50
```

#### Query 2: Aggregated Latency Trends (Summarize & Bin)

Group request traffic into 15-minute buckets to identify average latency spikes:

```
AppRequests
| where TimeGenerated > ago(12h)
| summarize RequestCount = count(), AvgLatencyMs = avg(DurationMs), MaxLatencyMs = max(DurationMs)
  by bin(TimeGenerated, 15m), ResultCode
| order by TimeGenerated asc
```

## 4. Troubleshooting Reference Matrix

Use this table to diagnose common query compilation failures and performance drops:

| Issue / Error Message | Root Cause | SRE Remediation Action |
| --- | --- | --- |
| **`Table or scalar expression not found`** | Case-sensitivity typo. For example, querying `syslog` or `apprequests` in lowercase. | Change the table name to capitalize matching the schema (e.g. `Syslog`, `AppRequests`). |
| **`Query exceeds memory limits`** | Query scanned a massive volume of historical database blocks without filtering. | Add a `where TimeGenerated > ago(N)` filter as the very first operator line. |
| **`Query timeout / sluggish results`** | Using unindexed text searches like `contains` instead of full word matching. | Replace `contains` with `has` (e.g., `SyslogMessage has "failed password"`). |
| **Join returns 0 matches** | Mismatched casing or joining on wrong keys. | Confirm keys represent identical data types and value formats. Use `$left.Computer == $right.Computer` for clarity. |
| **Calculations fail on parsed fields** | Parsed fields are treated as strings. | Explicitly typecast fields in the parse line: `FieldName:int` or `FieldName:real`. |

> [!WARNING]
**KQL Case Sensitivity:**
Remember that KQL tables, columns, variables, and operator names are case-sensitive. `where` must be lowercase. `TimeGenerated` must have capital `T` and `G`. Pay close attention to syntax errors in your console.
>
