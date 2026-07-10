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
