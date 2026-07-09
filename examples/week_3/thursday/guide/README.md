# Guide

This guide walks you step-by-step through configuring Azure Load Balancers, backend pools, TCP/HTTP health probes, Network Security Group (NSG) secure-by-default configurations, and diagnosing failed nodes.

You will build a highly available web server tier behind a Standard Public Load Balancer, and practice troubleshooting common real-world outages like web server process failures and health probe firewall blocks.

---

## 1. Architectural Topology Overview

Here is the network layout we will build:

- **Virtual Network:** `vnet-core-prod-01` (IP space: `10.0.0.0/16`)
- **Subnet:** `snet-web-01` (`10.0.1.0/24`) ¿ Subnet hosting our active web servers.
- **Backend Virtual Machines (Backend Pool):**
    - `vm-web-01` (Private IP: `10.0.1.4`)
    - `vm-web-02` (Private IP: `10.0.1.5`)
    - *Note: In standard enterprise architectures, backend instances do not receive public IP addresses to minimize surface exposure. All public ingress is mediated by the load balancer.*
- **Standard Public Load Balancer:** `lb-app-prod-01`
    - Frontend Public IP: `pip-lb-prod-01`
    - Backend Pool: `BackEndPool` (containing `vm-web-01` and `vm-web-02`)
    - Health Probe: HTTP GET to `/health` on port 80, checking every 5 seconds.
    - Load Balancing Rule: Maps public TCP Port 80 on the frontend to port 80 on the backend pool.

---

## 2. Core Concepts Reference

### Layer 4 vs. Layer 7 Load Balancing

- **Layer 4 (Transport Layer):** Azure Load Balancer operates at Layer 4, distributing traffic based on network details (source/destination IP, source/destination ports, protocol: TCP/UDP). It does not inspect the contents of HTTP packets, cookies, or SSL payloads.
- **Layer 7 (Application Layer):** Azure Application Gateway or Front Door operates at Layer 7. They inspect SSL headers, path routes (e.g. `/api/*` vs `/static/*`), and cookie sessions to perform advanced routing.

### Basic vs. Standard Load Balancer SKUs

- **Basic SKU:** Open-by-default (requires no NSG rules to pass traffic). Limited to 30 backend instances in a single availability set. Offers no SLA.
- **Standard SKU (Production Pattern):** Secure-by-default. Blocks all traffic to the backend instances unless you explicitly configure NSG rules to allow it. Supports up to 1000 instances across availability zones, with a $99.99\%$ SLA. We use the Standard SKU for this lab.

### Public vs. Private Subnets in Azure

Unlike AWS, where a subnet is flagged as "public" or "private" at the route table level (depending on an Internet Gateway route), **all subnets in Azure have direct outbound internet access by default** via `0.0.0.0/0 -> Internet`.
In Azure, a subnet is classified as public-facing or private based on:

1. **Public IP Addresses:** Whether resources (like VMs or load balancers) are assigned public IP addresses directly.
2. **Network Security Groups (NSGs):** Rules that block inbound internet traffic.
3. **User-Defined Routes (UDRs):** Rules that override the default internet egress route and send traffic to a firewall or drop it entirely.

For this lab:

- `snet-web-01` acts as a **private subnet** because the backend VMs (`vm-web-01` and `vm-web-02`) do not have Public IPs. They are secure from direct external scanning or SSH ingress.
- However, they are accessible to the public internet exclusively through the Standard Public Load Balancer frontend IP config, which maps inbound port 80 traffic to the backend pool.

### Health Probes & Azure Reserved IP `168.63.129.16`

Azure Load Balancers send periodic health probes to backend instances. If an instance fails to respond successfully (e.g. returns something other than HTTP `200 OK`, or the TCP connection times out), the load balancer flags it as unhealthy and stops routing client traffic to it.

- **Health probe source IP:** All health probes in Azure originate from the virtual reserved IP address `168.63.129.16`.
- **Crucial Rule:** If you block `168.63.129.16` in guest firewalls (`iptables`, Windows Firewall) or via NSGs, the load balancer will fail to poll the VM. The VM will be marked unhealthy and removed from the active pool, causing a service outage.

---

## 3. Step-by-Step Lab Execution

### Step 1: Provision the Virtual Network and Subnet

1. In the Portal Search bar, type **Virtual networks** and select it.
2. Click **+ Create**.
3. On the **Basics** tab, configure:
    - **Resource Group:** `rg-network-prod-eastus-01` (Create a new resource group if it does not exist)
    - **Name:** `vnet-core-prod-01`
    - **Region:** `East US`
4. On the **IP Addresses** tab:
    - Set the IPv4 address space to `10.0.0.0/16`.
    - Remove the default subnet if present, and click **+ Add subnet**:
        - **Subnet Name:** `snet-web-01`
        - **Subnet Address Range:** `10.0.1.0/24`
        - **Private subnet:** **Disabled** (or keep unchecked to ensure VMs have default outbound internet access to install Docker)
5. Click **Review + create**, then click **Create**.

---

### Step 2: Provision Network Security Groups (NSGs)

Standard Load Balancers are **secure-by-default**. You must associate an NSG that explicitly permits traffic from the load balancer probe and client sources.

1. **Create the Web Subnet NSG (`nsg-web-01`):**
    - Search for **Network security groups** in the Portal search bar and select it.
    - Click **+ Create**. Select Resource Group `rg-network-prod-eastus-01`, name it `nsg-web-01`, and select region `East US`.
    - Once deployed, open `nsg-web-01` -> Select **Inbound security rules** -> Click **+ Add**:
        - **SSH Rule (Management):** Source: `Any` (or your local IP for security), Source Port: , Destination: `Any`, Destination Port: `22`, Protocol: `TCP`, Action: `Allow`, Priority: `100`, Name: `Allow-SSH-Inbound`.
        - **HTTP Rule (Client Ingress):** Source: `Any`, Source Port: , Destination: `Any`, Destination Port: `80`, Protocol: `TCP`, Action: `Allow`, Priority: `110`, Name: `Allow-HTTP-Client-Inbound`.
        - **Azure Load Balancer Health Probe:** Source: `Service Tag`, Source Service Tag: `AzureLoadBalancer`, Source Port: , Destination: `Any`, Destination Port: `80`, Protocol: `TCP`, Action: `Allow`, Priority: `120`, Name: `Allow-Azure-LB-Probes`.
    - Select **Subnets** in the left menu -> Click **+ Associate**:
        - Virtual network: `vnet-core-prod-01`
        - Subnet: `snet-web-01`

---

### Step 3: Deploy the Backend Virtual Machines

Deploy two web server instances into the subnet. Because they will sit behind a public load balancer, we will configure them **without public IP addresses** for optimal security.

1. **Deploy `vm-web-01`:**
    - Search for **Virtual machines** -> Click **+ Create** -> **Azure virtual machine**.
    - **Basics Tab:**
        - Resource Group: `rg-network-prod-eastus-01`
        - VM Name: `vm-web-01`
        - Region: `East US`
        - Image: `Ubuntu Server 22.04 LTS - Gen2`
        - Size: `Standard_B1s` *(Cost-Awareness: Use B1s free-tier eligible VM sizes)*.
        - Authentication: `SSH public key`, Username: `azureuser`
        - Key pair name: `vm-web-pool-key`
        - Public inbound ports: **None**
    - **Networking Tab:**
        - Virtual network: `vnet-core-prod-01`
        - Subnet: `snet-web-01 (10.0.1.0/24)`
        - Public IP: **None** *(Ensures backend instances are isolated from direct public scans)*.
        - NIC network security group: **None** *(Subnet NSG is already associated)*.
    - **Management Tab:**
        - Auto-shutdown: **Enable auto-shutdown** (set to 7:00 PM local time) to avoid idle VM costs.
    - Click **Review + create** -> **Create** (Download the private key `.pem` file).
2. **Deploy `vm-web-02`:**
    - Repeat the VM creation steps with the following modifications:
        - VM Name: `vm-web-02`
        - Use the existing key pair: **Use existing key stored in Azure** (select `vm-web-pool-key`).
        - Subnet: `snet-web-01 (10.0.1.0/24)`
        - Public IP: **None**
        - Ensure Auto-shutdown is enabled.

---

### Step 4: Provision the Standard Public Load Balancer

1. **Create Public IP for the Load Balancer Frontend:**
    - Search for **Public IP addresses** -> Click **+ Create**.
    - Configure settings:
        - Resource Group: `rg-network-prod-eastus-01`
        - Name: `pip-lb-prod-01`
        - SKU: **Standard** *(Standard load balancers require Standard SKUs for Public IPs)*.
        - IP Version: `IPv4`
        - Routing Preference: `Microsoft network`
    - Click **Create**.
2. **Deploy the Load Balancer:**
    - Search for **Load balancers** -> Click **+ Create**.
    - **Basics Tab:**
        - Resource Group: `rg-network-prod-eastus-01`
        - Name: `lb-app-prod-01`
        - Region: `East US`
        - SKU: **Standard**
        - Type: **Public**
    - **Frontend IP configuration Tab:**
        - Click **+ Add a frontend IP configuration**:
            - Name: `FrontEndPool`
            - IP version: `IPv4`
            - IP type: `IP address`
            - Public IP address: Select `pip-lb-prod-01`
            - Click **Add**.
    - **Backend pools Tab:**
        - Click **+ Add a backend pool**:
            - Name: `BackEndPool`
            - Virtual network: `vnet-core-prod-01`
            - Backend Pool Configuration: **NIC**
            - IP Version: `IPv4`
            - Click **+ Add** under Virtual Machines, select `vm-web-01` and `vm-web-02`, check their interfaces, and click **Add**.
            - Click **Save/Create**.
    - Click **Review + create** -> **Create**.

---

### Step 5: Configure Health Probe and Load Balancing Rules

1. **Create the HTTP Health Probe:**
    - Navigate to your load balancer `lb-app-prod-01` resource screen.
    - In the left-hand menu, select **Health probes** -> Click **+ Add**:
        - Name: `HttpProbe`
        - Protocol: `TCP` or `HTTP` (For this lab, choose **HTTP**).
        - Port: `80`
        - Path: `/health`
        - Interval: `5` seconds *(Probes the instances every 5s)*.
        - Unhealthy threshold: `2` consecutive failures *(Removes the instance if it fails twice)*.
        - Click **Add**.
2. **Create the Load Balancing Rule:**
    - In the load balancer left menu, select **Load balancing rules** -> Click **+ Add**:
        - Name: `HttpRule`
        - IP Version: `IPv4`
        - Frontend IP address: Select `FrontEndPool`
        - Backend pool: Select `BackEndPool`
        - Protocol: `TCP`
        - Port: `80` *(Frontend inbound port)*
        - Backend port: `80` *(Port the app is listening on)*
        - Health probe: Select `HttpProbe`
        - Session persistence: **None**
        - Idle timeout (minutes): `4`
        - TCP Reset: **Disabled**
        - Floating IP (direct server return): **Disabled**
        - Click **Save/Add**.
3. **Create the Outbound Egress Rule (Crucial for Docker Installation):**
    - *Why this matters:* Azure Standard Load Balancers do not provide implicit outbound internet access to backend pool members. To allow private VMs (which have no public IPs) to download packages like Docker or pull images, you must explicitly create an Outbound Egress Rule.
    - In the load balancer left menu, select **Outbound rules** -> Click **+ Add**:
        - Name: `OutboundEgressRule`
        - Frontend IP configuration: Select `FrontEndPool`
        - Protocol: Select **All** (maps TCP, UDP, and ICMP traffic)
        - Idle timeout (minutes): `4`
        - Backend pool: Select `BackEndPool`
        - Port allocation: Select **Use the default number of outbound ports**
        - Click **Add**.

---

### Step 6: Configure Inbound Administration (NAT Rules vs. Jump Box)

Because our backend VMs are private (no public IPs), you cannot SSH into them directly from the internet. You must configure one of the following two connection methods:

#### Method A: Using Inbound NAT Rules on the Load Balancer (Recommended)

This method uses the Azure Load Balancer to forward SSH traffic on custom public ports to port 22 on the private VMs.

1. **Configure Inbound NAT Rules:**
    - Navigate to your Load Balancer `lb-app-prod-01` resource page.
    - In the left-hand menu, select **Inbound NAT rules** -> Click **+ Add**.
    - **Rule 1 (For vm-web-01):**
        - Name: `SSH-vm-web-01`
        - Frontend IP configuration: `FrontEndPool`
        - Frontend Port: `50001`
        - Target virtual machine: `vm-web-01`
        - Network IP configuration: Select the network interface IP (`10.0.1.4`)
        - Service: **Custom**
        - Protocol: **TCP**
        - Backend port: `22`
        - Click **Add**.
    - **Rule 2 (For vm-web-02):**
        - Click **+ Add** to create a second rule.
        - Name: `SSH-vm-web-02`
        - Frontend IP configuration: `FrontEndPool`
        - Frontend Port: `50002`
        - Target virtual machine: `vm-web-02`
        - Network IP configuration: Select the network interface IP (`10.0.1.5`)
        - Service: **Custom**
        - Protocol: **TCP**
        - Backend port: `22`
        - Click **Add**.
2. **Verify Inbound NSG Configuration:**
    - *Note to trainees:* The Load Balancer performs NAT Translation on incoming packets before forwarding them, changing the destination port from `50001`/`50002` to `22`. Therefore, the existing subnet-level NSG inbound rule (`Allow-SSH-Inbound` permitting port 22) is sufficient.
3. **SSH into the Private VMs:**
    - From your local terminal, SSH using the custom ports and the public IP of the Load Balancer (found on the `pip-lb-prod-01` public IP page):
        
        ```bash
        # SSH to vm-web-01
        ssh -i path/to/vm-web-pool-key.pem -p 50001 azureuser@<load-balancer-public-ip>
        
        # SSH to vm-web-02
        ssh -i path/to/vm-web-pool-key.pem -p 50002 azureuser@<load-balancer-public-ip>
        ```
        

#### Method B: Deploying and Using a Jump Box (VNet Bastion)

This method provisions a public-facing VM to act as a secure gateway/bastion inside the virtual network.

1. **Deploy the Jump Box VM (`vm-jump-01`):**
    - Create a third virtual machine named `vm-jump-01` in the resource group `rg-network-prod-eastus-01` and region `East US`.
    - Place it in the VNet `vnet-core-prod-01` and subnet `snet-web-01`.
    - **Public IP:** Set to **Yes** (Create a Standard Public IP).
    - **NSG:** Attach `nsg-web-01` (permitting port 22).
2. **SSH to Private VMs using SSH Agent Forwarding:**
    - On your local machine, add your SSH key to your ssh-agent:
        
        ```bash
        eval "$(ssh-agent -s)"
        ssh-add path/to/vm-web-pool-key.pem
        ```
        
    - Connect to the jump box, forwarding your credentials using the `A` flag:
        
        ```bash
        ssh -A azureuser@<jumpbox-public-ip>
        ```
        
    - Once logged into the jump box, directly SSH to the private IP addresses of your backend servers:
        
        ```bash
        ssh azureuser@10.0.1.4  # vm-web-01
        ssh azureuser@10.0.1.5  # vm-web-02
        ```
        
3. **SSH to Private VMs using ProxyJump (Alternative):**
    - Connect directly in one command from your local host:
        
        ```bash
        ssh -J azureuser@<jumpbox-public-ip> -i path/to/vm-web-pool-key.pem azureuser@10.0.1.4
        ```
        

---

### Step 7: VM Environment Setup and Code Transfer

Once connected to each virtual machine terminal using one of the methods above, run the following:

1. **Install Docker on both `vm-web-01` and `vm-web-02`:**
    
    ```bash
    sudo apt-get update
    sudo apt-get install -y docker.io
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker azureuser
    newgrp docker
    ```
    
2. **Copy the Backend Code to the VMs:**
Transfer the files located in `weeklytechrepo/Networking/demo/4-Thursday/code/backend/` to both hosts (into `~/backend`).
3. **Build and Run the Backend Container on both hosts:**
    
    ```bash
    cd ~/backend
    # Build the image
    docker build -t backend-api .
    
    # On vm-web-01:
    docker run -d --name web-service -p 80:80 -e NODE_NAME=vm-web-01 -e NODE_IP=10.0.1.4 backend-api
    
    # On vm-web-02:
    docker run -d --name web-service -p 80:80 -e NODE_NAME=vm-web-02 -e NODE_IP=10.0.1.5 backend-api
    ```
    

---

## 4. Troubleshooting and Diagnostics

### Scenario 1: Traffic Load Balancing

- Open a browser and navigate to the public IP of your load balancer (find it on `pip-lb-prod-01` page).
- Refresh the page. You will see traffic alternate between `Hello from vm-web-01 (10.0.1.4)` and `Hello from vm-web-02 (10.0.1.5)`. This validates standard Round Robin distribution.

### Scenario 2: Simulating Process Outage

- SSH into `vm-web-02` and kill the web server process container:
    
    ```bash
    docker stop web-service
    ```
    
- In the Azure Portal, open the load balancer page and observe the Health Probes status. Within 10 seconds, the load balancer detects the HTTP GET connection failure.
- Refresh your browser pointing to the Load Balancer IP. All traffic is automatically and cleanly routed to the remaining active instance (`vm-web-01`), preventing client drops.

### Scenario 3: Simulating Firewall Probe Block (168.63.129.16)

What happens if the app process is running, but an admin blocks the health probe IP?

- Restore the web service on `vm-web-02` (`docker start web-service`).
- SSH into `vm-web-01` and configure local host iptables firewall rules to block the Azure Reserved service IP. Because our Flask service runs inside a Docker container with port mapping, the traffic is forwarded and bypasses the host's `INPUT` chain. We must insert (`I`) the drop rule into Docker's dedicated `DOCKER-USER` chain:
    
    ```bash
    sudo iptables -I DOCKER-USER -s 168.63.129.16 -j DROP
    ```
    
- The load balancer probe checks now fail on `vm-web-01` due to connection timeouts. `vm-web-01` is marked unhealthy and removed from the routing pool.
- *SRE Concept Note:* You may notice that the VM is removed from load balancer rotation immediately, but it does **not** trigger a VM Resource Health event (the VM status in the portal still shows "Running" and "Available"). This is because **Resource Health** is a platform-level monitor (checking hypervisor and VM guest agent heartbeat). The health probe is an **application-level audit** (checking port 80). Application-level failures drop the node from the load balancer backend pool but do not raise platform-level VM alarms. Additionally, there is an inherent 1-5 minute lag before metric graphs in the portal update.
- Check traffic routing. All requests now go exclusively to `vm-web-02`.
- To restore the node, delete the rule from the `DOCKER-USER` chain:
    
    ```bash
    sudo iptables -D DOCKER-USER -s 168.63.129.16 -j DROP
    ```
