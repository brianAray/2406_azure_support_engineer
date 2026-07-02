# Phase 1 : Setup Azure

### 1. Storage Account & Blob Container Setup

- **Create Storage Account**:
    - Navigate to **Storage accounts** in the Azure Portal and click **Create**.
    - **Basics Tab**: Select your subscription and resource group. Name the storage account (e.g., `stsecurestore01` - must be globally unique).
    - Select your region.
    - **Performance/Redundancy**: Select **Standard** performance, and crucially, select **Locally-redundant storage (LRS)** to control replication costs.
    - **Advanced Tab**: Ensure "Allow Blob public access" is **unchecked (disabled)** for strict security.
    - Click **Review + Create**, then **Create**.
- **Create Container**:
    - Once deployed, navigate to the storage account resource, click **Containers** under *Data storage*.
    - Click **+ Container**, name it `deployments`, set Public access level to **Private (no anonymous access)**, and click **Create**.

### 2. Virtual Machine Provisioning

- Navigate to **Virtual machines** and click **Create** -> **Azure virtual machine**.
- Select the same resource group and region. Name the VM (e.g., `vm-app-prod-01`).
- Select **Ubuntu Server 22.04 LTS** (Standard x64) as the image.
- Set the size to a cost-effective standard SKU (e.g., **Standard_B1s** or **Standard_B2s**).
- Configure SSH public key authentication.
- In the **Networking** tab, place the VM in your lab VNet.
- Click **Review + Create**, then **Create**.

### 3. Enable Managed Identity on the VM

- Navigate to your VM resource (`vm-app-prod-01`) page.
- Under **Settings** in the left sidebar menu, click **Identity**.
- Under the **System assigned** tab, toggle **Status** to **On**.
- Click **Save**, then click **Yes** to confirm.
- Azure will register the VM in Microsoft Entra ID. Take note of the generated **Object (principal) ID** (this is the unique service principal for the VM).

### 4. Assign RBAC Roles

- Navigate back to the Storage Account (`stsecurestore01`).
- Click **Access Control (IAM)** in the left sidebar.
- Click **+ Add** -> **Add role assignment**.
- **Role**: Search for and select **Storage Blob Data Contributor**.
    - *Teaching Point*: Emphasize that standard subscription-level roles like *Owner* or *Contributor* only manage the control plane (creating/deleting storage accounts) but do **not** grant data plane access to read/write blobs. The *Storage Blob Data Contributor* role is specifically required for data plane operations.
- **Members**:
    - Under *Assign access to*, select **Managed identity**.
    - Click **+ Select members**, select the Subscription, choose **Virtual machine** from the Managed identity dropdown, select `vm-app-prod-01`, and click **Select**.
- Click **Review + assign**, then confirm the assignment.

### 5. Retrieve Keys and Generate SAS Tokens (For SDK Comparison)

- **Account Access Keys**:
    - Navigate to the Storage Account -> **Access keys** (under Security + networking).
    - Show how to copy `key1` or the connection string. Explain that this key has root privileges.
- **Shared Access Signatures (SAS)**:
    - Navigate to the Storage Account -> **Shared access signature**.
    - Check **Blob** under Allowed services, **Container** and **Object** under Allowed resource types.
    - Set the expiration date/time (recommend setting it to expire in 2 hours for security)
    - Click **Generate SAS and connection string** and copy the **SAS token** query string (starts with `?`).

## Phase 2: Setup VM

- **Step 1: SSH into the VM**:
    
    ```bash
    ssh -i vm-app-portal_key azureuser@<APP_VM_PUBLIC_IP>
    ```

- **Step 1.5: Code**:
    - Make sure you either have the training repo cloned or your own code on the VM
    
- **Step 2: Setup Virtual Environment & Install Dependencies**:
Ensure system dependencies are installed, create a virtual environment, and install the Azure Python SDK packages:
    
    ```bash
    cd ~/code
    sudo apt-get update && sudo apt-get install -y python3-pip python3-venv
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    ```
    
- **Step 3: Set Environment Variables (for Keys & SAS Tokens)**:
Expose the key and SAS token retrieved from the portal (so the script can test Method 1 and Method 2):
    
    ```bash
    export AZURE_STORAGE_KEY="your-actual-storage-account-key"
    export AZURE_STORAGE_SAS="?sv=2020-08-04&ss=b&srt=co&sp=w..."
    ```
    
- **Step 4: Run the script**:
    
    ```bash
    python demo_secure_storage_access.py
    ```