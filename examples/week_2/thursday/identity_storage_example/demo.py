import os
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, BlobClient

account_name = "stsecurestore01"
container_name = "deployments"
blob_name = "health_check.txt"

# Method 1: Authenticating via account access key (static, high privelege)
def connect_using_access_key():
    print("--- COnnecitng using Account Access Key ---")
    # retrieve key from environment variables (never hardcode credentials)
    access_key = os.environ.get("AZURE_STORAGE_KEY", "mock-access-key-value-00000000000")
    connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={access_key};EndpointSuffix=core.windows.net"

    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        print("success: initialized blobserviceclient using account access key")
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        blob_client.upload_blob("System Status: Green", overwrite=True)
    except Exception as e:
        print(f"Error connecting: {e}")
    print()

# Method 2: Authenticating via Shared Access Signature (SAS) Token (Time-Bound)
def connect_using_sas_token():
    print("--- Connecting using SAS Token ---")
    # SAS tokens are appended to the URL query string
    sas_token = os.environ.get("AZURE_STORAGE_SAS")
    blob_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}{sas_token}"

    try:
        blob_client = BlobClient.from_blob_url(blob_url)
        print("Success: Initialized BlobClient using time-bound SAS Token")
        # blob_client.upload_blob("Hello", overwrite=True)
    except Exception as e:
        print(f"Error connecting: {e}")

# Method 3: Authenticating via Managed Identity (Secretless, Dynamic)
def connect_using_managed_identity():
    print("--- COnnecting using Managed Identity ---")
    account_url = f"https://{account_name}.blob.core.windows.net"

    try:
        # DefaultAzureCredential automatically pulls VM System-Assigned Managed Identity Token when run in Azure
        token_credential = DefaultAzureCredential()
        blob_service_client = BlobServiceClient(account_url, credential=token_credential)
        print("Success: Initialized BlobServiceClient using secretless DefaultAzureCredential (Managed Identity).")
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        blob_client.upload_blob("Hello there", overwrite=True)
    except Exception as e:
        print(f"Error connecting: {e}")
    print()

if __name__ == "__main__":
    print("=== Azure Blob Authentication Configuration Demo ===")
    # connect_using_access_key()
    # connect_using_sas_token()
    connect_using_managed_identity()