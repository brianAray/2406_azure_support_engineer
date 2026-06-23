#!/usr/bin/env bash

# This script demonstrates core Linux commands used by SREs to monitor and diagnose system status.
# Running these commands directly outputs system performance snapshots.

# To execute run chmod +x demo_linux_diagnostics.sh
# ./demo_linux_diagnostics.sh

echo "=== Linux Diagnostics Commands Demo ==="

echo "--- 1. PROCESS DIAGNOSTICS (ps) ---"
# Show top 5 processes consuming CPU/Memory (using standard ps flags)
ps aux --sort=-%cpu | head -n 6

echo ""
echo "--- 2. MEMORY DIAGNOSTICS (free) ---"
# Check memory allocation and swap space size
free -h

echo ""
echo "--- 3. SYSTEM METRICS OVERVIEW (top snapshot) ---"
# Run top once to show system load average and CPU usage statistics
top -b -n 1 | head -n 12

echo ""
echo "--- 4. DISK UTILIZATION (df) ---"
# Check disk partition usage boundaries
df -h /

echo ""
echo "--- 5. NETWORK CONNECTIONS AND PORTS (ss/netstat) ---"
# List listening TCP ports (using ss if available, otherwise netstat)
if command -v ss &> /dev/null; then
    ss -tuln
else
    netstat -an | grep -i "listen" | head -n 10
fi

echo "=== End of Diagnostics Run ==="
