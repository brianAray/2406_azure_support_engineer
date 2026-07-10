# Guide

This guide walks you step-by-step through configuring Azure Private Endpoints, Service Endpoints, Private DNS Zones, and troubleshooting DNS resolution paths and firewalls in a hybrid networking architecture.

You will secure an Azure Storage Account by disabling all public internet ingress, routing traffic exclusively through a private VNet IP address, and verifying DNS queries.

---

## 1. Architectural Topology Overview

Here is the network layout we will build/verify:

- **Virtual Network:** `vnet-core-prod-01` (IP space: `10.0.0.0/16`)
- **Subnet 1:** `snet-backend-01` (`10.0.1.0/24`) ¿ Subnet hosting our client VM and endpoints.
- **Subnet 2:** `AzureBastionSubnet` (`10.0.2.0/26`) ¿ Subnet hosting the managed Bastion host.
- **Client VM (Internal Ingress):** `vm-client-01` (Private IP: `10.0.1.4`)
- **Secure Storage Account:** `stapplogs01`
    - Public Access: **Disabled** (secure from direct public internet access)
    - Private Endpoint: `pe-storage-prod-01`
    - Private IP Address: `10.0.1.5` (allocated from `snet-backend-01`)
    - Private DNS Zone: `privatelink.blob.core.windows.net` (Linked to `vnet-core-prod-01`)

---

## 2. Core Concepts Reference

### Service Endpoints vs. Private Endpoints

- **Service Endpoints:**
    - Provide secure direct connectivity to Azure services over the Microsoft backbone.
    - The resource (e.g. Storage Account) *retains its public IP address*.
    - Outbound traffic is allowed from specific VNet subnets by applying virtual network rules at the resource firewall.
- **Private Endpoints (Production Standard):**
    - Provision a Virtual Network Interface Card (NIC) with a private IP address from your subnet directly on the PaaS resource.
    - Allows you to shut down public internet endpoints completely.
    - Traffic enters the private IP, securing the service from scan boundaries.

### DNS Resolution and Private Link Zones

Azure Storage Accounts normally resolve to a public IP endpoint. To route to a Private Endpoint, we use **Private DNS Zones**:

- A Private DNS Zone (e.g., `privatelink.blob.core.windows.net`) is linked to the VNet.
- When `vm-client-01` queries `stapplogs01.blob.core.windows.net`, the Azure DNS resolver (`168.63.129.16`) intercepts it and routes to `stapplogs01.privatelink.blob.core.windows.net` returning the secure private IP `10.0.1.5`.

---

## 3. Step-by-Step Lab Execution

### Step 1: Provision the Virtual Network and Subnets

1. In the Portal Search bar, type **Virtual networks** and select it.
2. Click **+ Create**.
3. On the **Basics** tab, configure:
    - **Resource Group:** `rg-network-prod-eastus-01` (Create new if not existing)
    - **Name:** `vnet-core-prod-01`
    - **Region:** `East US`
4. On the **IP Addresses** tab:
    - Set the IPv4 address space to `10.0.0.0/16`.
    - Add Subnet 1:
        - **Subnet Name:** `snet-backend-01`
        - **Subnet Address Range:** `10.0.1.0/24`
    - Add Subnet 2:
        - **Subnet Name:** `AzureBastionSubnet` (Must be named exactly this, case-sensitive)
        - **Subnet Address Range:** `10.0.2.0/26`
5. Click **Review + create**, then click **Create**.

---

### Step 2: Provision Network Security Groups (NSGs)

Associate an NSG with the backend subnet to secure access rules:

1. Search for **Network security groups** in the Portal search bar and select it.
2. Click **+ Create**. Select Resource Group `rg-network-prod-eastus-01`, name it `nsg-backend-01`, and select region `East US`.
3. Once deployed, open `nsg-backend-01` -> Select **Inbound security rules** -> Click **+ Add**:
    - **SSH Rule (Bastion Inbound):** Source: `IP Addresses`, Source IP addresses: `10.0.2.0/26` (only allow incoming traffic originating from the Bastion subnet), Source Port: , Destination: `Any`, Destination Port: `22`, Protocol: `TCP`, Action: `Allow`, Priority: `100`, Name: `Allow-Bastion-SSH-Inbound`.
4. Select **Subnets** in the left menu -> Click **+ Associate**:
    - Virtual network: `vnet-core-prod-01`
    - Subnet: `snet-backend-01`

---

### Step 3: Deploy the Client Virtual Machine

Deploy a test VM to act as our secure client within the subnet, configuring it without a public IP:

1. Search for **Virtual machines** -> Click **+ Create** -> **Azure virtual machine**.
2. **Basics Tab:**
    - Resource Group: `rg-network-prod-eastus-01`
    - VM Name: `vm-client-01`
    - Region: `East US`
    - Image: `Ubuntu Server 22.04 LTS`
    - Size: `Standard_B1s` (Cost Control)
    - Auth: `SSH public key`, Username: `azureuser`, Key pair name: `vm-client-key`.
3. **Networking Tab:**
    - Subnet: `snet-backend-01 (10.0.1.0/24)`
    - Public IP: Select **None** (to enforce private VNet routing limits. The VM will receive the first available private IP, which is `10.0.1.4`).
4. **Management Tab:** Enable auto-shutdown (7:00 PM local).
5. Click **Review + create** -> **Create** (Save the private key file).

---

### Step 4: Deploy and Connect via Azure Bastion

Deploy Azure Bastion to establish a secure browser-based SSH session to your private VM:

1. Navigate to the `vm-client-01` page in the Azure Portal.
2. Under **Operations** or at the top header, click **Connect** -> select **Bastion**.
3. Under the Bastion page, click **Deploy Bastion**. This will automatically configure the Bastion host using `AzureBastionSubnet`.
4. Once deployment completes, enter the VM credentials:
    - Username: `azureuser`
    - Authentication Type: `SSH Private Key from Local File` (Upload your `vm-client-key.pem` private key).
5. Click **Connect**. A secure web-based CLI session will open inside your browser window.

---

### Step 5: Provision the Storage Account & Disable Public Ingress

1. In the Portal Search bar, type **Storage accounts** and click **+ Create**.
2. **Basics Tab:**
    - **Resource Group:** `rg-network-prod-eastus-01`
    - **Storage Account Name:** `stapplogs01` (or a unique variant, e.g. `stapplogs01<yourname>`)
    - **Region:** `East US`
    - **Primary service:** `Blob storage`
    - **Redundancy:** `Locally-redundant storage (LRS)` (Cost Control)
3. **Networking Tab:**
    - **Network connectivity:** Select **Disable public access and use private endpoints**.
4. Click **Review + create** -> **Create**.

---

### Step 6: Configure the Private Endpoint

1. Once the Storage Account is deployed, navigate to the `stapplogs01` resource.
2. Select **Networking** in the left sidebar under *Security + networking*.
3. Click the **Private endpoint connections** tab -> click **+ Private endpoint**.
4. **Basics Tab:** Resource Group: `rg-network-prod-eastus-01`, Name: `pe-storage-prod-01`, Region: `East US`.
5. **Resource Tab:** Target sub-resource: `blob`.
6. **Virtual Network Tab:**
    - **Virtual Network:** `vnet-core-prod-01`
    - **Subnet:** `snet-backend-01 (10.0.1.0/24)` (The Private Endpoint will take the next available private IP, which is `10.0.1.5`).
7. **DNS Tab:**
    - **Integrate with private DNS zone:** Select **Yes** (to automatically provision `privatelink.blob.core.windows.net`).
8. Click **Review + create** -> **Create**.

---

## 4. Verification and Troubleshooting

### Verification 1: Internal DNS & Network Connectivity

1. In your active Azure Bastion browser session on `vm-client-01` (IP: `10.0.1.4`), perform a DNS lookup for your storage account:
    
    ```bash
    nslookup stapplogs01.blob.core.windows.net
    ```
    
2. **Expected Output:**
    - The query resolves as a CNAME to `stapplogs01.privatelink.blob.core.windows.net` and returns the private VNet IP: `10.0.1.5`.
3. Test HTTP connection:
    
    ```bash
    curl -I <https://stapplogs01.blob.core.windows.net>
    ```
    
    - Connection will handshake successfully (returning `400 Bad Request` or `200 OK` rather than timeout, indicating that the network layer path is clear).

---

### Verification 2: Production SRE Use-Case (Automated Log Upload)

Now, simulate a real-world production task: uploading VM performance logs to your secure storage account entirely over the private link connection.

1. **Create the Blob Container in Portal**:
    - Go to your `stapplogs01` Storage Account -> select **Containers** in the left sidebar under *Data storage*.
    - Click **+ Container**. Name it `prod-system-logs`, set Public access level to **Private (no anonymous access)**. Click **Create**.
2. **Generate a Shared Access Signature (SAS) Token**:
    - In the Storage Account left sidebar, click **Shared access signature**.
    - Allowed services: Check **Blob**. Allowed resource types: Check **Container** and **Object**.
    - Allowed permissions: Check **Read** and **Write**.
    - Click **Generate SAS and connection string**. Copy the generated **SAS token** (starts with `?sv=...`).
3. **Execute Ingestion Script on the VM**:
    - In your active Bastion SSH terminal session, create the log collection script:
        
        ```bash
        cat << 'EOF' > collect_metrics.sh
        #!/bin/bash
        # SRE Automated System Logging Script
        METRICS_FILE="health-metrics-$(date +%F-%H%M).json"
        echo "{" > $METRICS_FILE
        echo "  \"timestamp\": \"$(date -u +%FT%TZ)\"," >> $METRICS_FILE
        echo "  \"cpu_load\": \"$(uptime | awk -F'load average:' '{print $2}' | xargs)\"," >> $METRICS_FILE
        echo "  \"disk_usage\": \"$(df -h / | awk 'NR==2 {print $5}')\"" >> $METRICS_FILE
        echo "}" >> $METRICS_FILE
        
        # Environment configuration variables
        STORAGE_ACCOUNT="stapplogs01"
        CONTAINER="prod-system-logs"
        SAS_TOKEN="<PASTE_YOUR_SAS_TOKEN_HERE>"
        
        echo "[INFO] Uploading system metrics payload privately..."
        curl -X PUT -H "x-ms-blob-type: BlockBlob" \
             -H "Content-Type: application/json" \
             -T "$METRICS_FILE" \
             "<https://$>{STORAGE_ACCOUNT}.blob.core.windows.net/${CONTAINER}/${METRICS_FILE}${SAS_TOKEN}"
        
        echo -e "\n[SUCCESS] Script execution complete."
        EOF
        chmod +x collect_metrics.sh
        ```
        
    - Open the script and paste your SAS token into the `SAS_TOKEN` variable.
    - Run the script:
        
        ```bash
        ./collect_metrics.sh
        ```
        
4. **Verify Container Blobs Privately via VM Console**:
    - Because public access is disabled, we cannot browse blobs in the Portal directly from home. Verify the upload privately from inside the VM using `curl` to query the blob listing API:
        
        ```bash
        curl -s "<https://$>{STORAGE_ACCOUNT}.blob.core.windows.net/${CONTAINER}?restype=container&comp=list${SAS_TOKEN}" | grep -oP '(?<=<Name>)[^<]+'
        ```
        
    - **Expected Outcome**: The terminal prints the file name of your uploaded health-metrics file.
5. **Verify Blobs in Azure Portal (Temporary Firewall Exception)**:
    - To view the files visually in the Portal GUI, temporarily add your public IP:
        1. In the Portal, go to the Storage Account -> **Networking**.
        2. Under **Firewalls and virtual networks**, select **Enabled from selected virtual networks and IP addresses**.
        3. Check the box **Add your client IP address** to whitelist your home machine. Click **Save**.
        4. Go to **Containers -> prod-system-logs** and check the uploaded JSON files.
        5. *Security Reversion*: Remove your IP, change back to **Disabled**, and click **Save** to restore security.
6. **Audit Security Restrictions**:
    - Attempt to run the same `curl` upload command from your **local computer (outside Azure VNet)**.
    - **Expected Outcome**: The request is blocked with a `403 NetworkConnectionBlocked` response. The data is secured within the private VNet boundary.

---

### Troubleshooting Scenario: DNS Link Misconfiguration

If a VM inside the VNet cannot access the Storage Account and receives a `403 Forbidden` response, verify the Virtual Network Link:

1. **Simulate Outage:**
    - Navigate to **Private DNS zones** -> select `privatelink.blob.core.windows.net`.
    - Select **Virtual network links** in the left sidebar.
    - Delete the link connecting to `vnet-core-prod-01`.
2. **Diagnose Outage:**
    - Open your Bastion terminal session on `vm-client-01` and execute:
        
        ```bash
        nslookup stapplogs01.blob.core.windows.net
        ```
        
    - **Observation:** Notice that the hostname resolves to the public IP address (e.g. `20.38.45.101`) instead of the private IP.
    - Run `curl` to verify:
        
        ```bash
        curl -I <https://stapplogs01.blob.core.windows.net>
        ```
        
        - **Result:** You will receive a `403 Forbidden` response because public traffic is disabled at the Storage Firewall.
3. **Remediation:**
    - Re-add the virtual network link between the Private DNS Zone `privatelink.blob.core.windows.net` and `vnet-core-prod-01` in the portal.
