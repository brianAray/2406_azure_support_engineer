# Guide

This guide walks you step-by-step through configuring Azure Monitor action groups, setting up dynamic threshold alert rules on virtual machines, and simulating metric alerts.

---

## 1. Architectural Topology Overview

Here is the setup we will build/verify in this lab:

- **Virtual Machine:** `vm-appserver-prod-01` (we monitor its host-level CPU utilization).
- **Action Group:** `ag-sreoncall-01` (dispatches email warnings to `sre-oncall@company.com` when a threshold is breached).
- **Metric Alert Rule:** `alert-cpu-dynamic-01` (uses machine learning baselines to trigger alerts on CPU percentage anomalies).

---

## 2. Core Concepts Reference

### Metrics vs. Logs

- **Metrics:** Numerical time-series data points captured at regular intervals (e.g., 1-minute intervals). They are lightweight, query-efficient, and ideal for near real-time alerting.
- **Logs:** Detailed event records containing timestamps and message payloads (e.g. system audits, web server requests). Used for root-cause troubleshooting.

### Dynamic Thresholds Alerting

- **Static Alerts:** Trigger when a metric passes a hardcoded ceiling (e.g., CPU > 85%). This often results in false alarms during expected resource-intensive operations (like scheduled back-ups).
- **Dynamic Alerts:** Azure Monitor automatically audits historical metric data (typically 7 days) to calculate normal operating baselines. The alert triggers only when current measurements deviate significantly from this baseline, reducing alert fatigue.

---

## 3. Step-by-Step Lab Execution

### Step 1: Provision the Resource Group, Network Security Group, and Target VM

1. Open the Azure Portal.
2. Search for **Resource groups** in the top search bar -> select it -> click **+ Create**.
    - **Subscription:** Select your subscription.
    - **Resource Group:** `rg-monitoring-prod-eastus-01`
    - **Region:** `East US`
    - Click **Review + create** -> **Create**.
3. Search for **Network security groups** in the top search bar -> select it -> click **+ Create**.
    - **Resource Group:** `rg-monitoring-prod-eastus-01`
    - **Name:** `nsg-monitoring-prod-01`
    - **Region:** `East US`
    - Click **Review + create** -> **Create**.
4. Once the NSG is deployed, navigate to the `nsg-monitoring-prod-01` resource -> select **Inbound security rules** in the left menu -> click **+ Add**:
    - **Rule 1 (SSH Admin):** Source: `Any`, Destination port: `22`, Protocol: `TCP`, Action: `Allow`, Priority: `100`, Name: `Allow-SSH-Inbound`.
    - **Rule 2 (FastAPI port):** Source: `Any`, Destination port: `8000`, Protocol: `TCP`, Action: `Allow`, Priority: `110`, Name: `Allow-FastAPI-8000`.
5. Search for **Virtual machines** in the top search bar -> select it -> click **+ Create** -> **Azure virtual machine**.
6. **Basics Tab:**
    - **Resource Group:** `rg-monitoring-prod-eastus-01`
    - **VM Name:** `vm-appserver-prod-01`
    - **Region:** `East US`
    - **Image:** `Ubuntu Server 22.04 LTS`
    - **Size:** `Standard_B1s` (Cost Control)
    - **Authentication type:** `SSH public key`
    - **Username:** `azureuser`
    - **Key pair name:** `vm-appserver-key` (Download and save the PEM key pair when prompted)
7. **Networking Tab:** Allow default Virtual network and Subnet generation.
    - **Public IP:** Select **Create new** (assign standard public IP).
    - **NIC network security group:** Select **Advanced** -> select `nsg-monitoring-prod-01`.
8. **Management Tab:** Check **Enable auto-shutdown** (e.g. 7:00 PM local) to maintain cost control.
9. Click **Review + create** -> **Create**.

---

### Step 2: Create the Action Group

1. Open the Azure Portal.
2. Search for **Monitor** in the top portal search bar and select it.
3. In the Monitor left sidebar, click **Alerts**, and then select **Action groups** in the top horizontal menu bar. Click **+ Create**.
4. **Basics Tab:**
    - **Resource Group:** `rg-monitoring-prod-eastus-01`
    - **Action group name:** `ag-sreoncall-01`
    - **Short name:** `sreoncall` *(Note: This must be 12 characters or fewer to satisfy CLI and SMS gateway limits)*
5. **Notifications Tab:**
    - **Notification type:** Select **Email/SMS message/Push/Voice**.
    - **Name:** `SRE-OnCall-Email`.
    - **Configuration details:** Check **Email** and enter `sre-oncall@company.com`. Click **OK**.
6. Click **Review + create** -> **Create**.

---

### Step 3: Configure the Static Metric Alert

1. In the Monitor left menu, click **Alerts** -> click **+ Create** -> select **Alert rule**.
2. **Scope Tab:**
    - Click **Select a resource**. Filter by Resource Type: `Virtual machines`.
    - Select `vm-appserver-prod-01`. Click **Done**.
3. **Condition Tab:**
    - Under Signal name, search for and select **Percentage CPU**.
    - Under Alert logic:
        - **Threshold:** Select **Static**.
        - **Aggregation type:** Select **Average** (or select **Maximum** to bypass sliding-window delays).
        - **Operator:** Select **Greater than**.
        - **Threshold value:** **80** (representing 80% CPU usage).
        - **Evaluation frequency:** Select **1m** (audits metrics every 1 minute).
        - **Window size:** Select **1m** (aggregates metrics over a 1-minute window).
4. **Actions Tab:**
    - Click **Select action groups** -> check the box for `ag-sreoncall-01` and click **Select**.
5. **Details Tab:**
    - **Alert rule name:** `alert-cpu-static-01`
    - **Description:** `Trigger alert when VM CPU percentage exceeds 80%.`
6. Click **Review + create**, then click **Create**.

> [!NOTE]
**Why not deploy a Dynamic alert immediately?** Although Dynamic alerts are standard in SRE production environments because they use machine learning to establish operating baselines and reduce false alarms, they require **3 to 7 days of historical metric data** to train. If deployed on a newly provisioned VM, they will not evaluate or fire immediately. Thus, for rapid verification in this lab, we deploy a Static Threshold rule.
> 

---

### Step 4: Generate Real VM Host CPU Load (To test Azure Monitor Alert Rule)

The Python application simulates alert checks within its code logs, but to trigger the actual **Azure Monitor Alert Rule** (`alert-cpu-static-01`) created in the Azure portal, you must generate real CPU load on the VM itself.

1. SSH into your target VM and install the `stress` utility:
    
    ```bash
    sudo apt-get update && sudo apt-get install -y stress
    ```
    
2. Run `stress` in the background for 10 minutes to assert sustained load:*(Note: If you cannot install stress, use: `timeout 300 bash -c 'while true; do true; done' &`)*
    
    ```bash
    stress --cpu 1 --timeout 600 &
    ```
    
3. Audit the CPU status locally on the VM:
    
    ```bash
    top
    ```
    
4. Navigate to **Monitor -> Alerts** in the Azure Portal after 1-2 minutes. The static alert rule will evaluate immediately, detect your active `stress` test load (~100% CPU), transition to a **Fired** state, and dispatch a notification via the Action Group.

> [!WARNING]
**Troubleshooting Alert Ingestion Delays:**
If the VM's internal CPU shows ~100% load (e.g. in `top`), but the alert rule has not fired after 1-2 minutes:
> 
> 1. **Alert Rule Warmup Latency:** Newly deployed or modified Azure alert rules take up to **5 minutes** to initialize in the Monitor backend.
> 2. **Telemetry Ingestion Lag:** Host-level CPU metrics are gathered and pushed via a pipeline that has a **1 to 2-minute indexing delay** before they appear in the metrics database. Keep the `stress` test active for at least 5 minutes.
