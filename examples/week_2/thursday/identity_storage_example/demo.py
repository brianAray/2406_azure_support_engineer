import os
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, BlobClient

account_name = "stsecurestore01"
container_name = "deployments"

# Method 1: Authenticating via account access key (static, high privelege)
def connect_using_access_key():
    print("--- COnnecitng using Account Access Key ---")
    # retrieve key from environment variables (never hardcode credentials)
    access_key = os.environ.get("AZURE_STORAGE_KEY", "mock-access-key-value-00000000000")
    connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={access_key};EndpointSuffix=core.windows.net"

    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        print("success: initialized blobserviceclient using account access key")
        blob_client = blob_service_client.get_blob_client(container=container_name, blob="health_check.txt")
        blob_client.upload_blob("System Status: Green", overwrite=True)
    except Exception as e:
        print(f"Error connecting: {e}")
    print()

if __name__ == "__main__":
    print("=== Azure Blob Authentication Configuration Demo ===")
    connect_using_access_key()