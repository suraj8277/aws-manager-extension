#!/bin/bash

# --- Configuration (Adjust these variables) ---
CORTEX_RPM_FILENAME="cortex-agent.deb" # Ensure you use the .deb version for Debian
CORTEX_CONF_FILE="cortex.conf"         # Path to your local config file
CORTEX_INSTALL_TMP_DIR="/tmp/cortex_install"

# --- 1. Check if already installed ---
if dpkg -l | grep -q "cortex-agent"; then
    echo "Cortex XDR is already installed. Exiting."
    exit 0
fi

echo "Starting Cortex XDR installation for Debian..."

# --- 2. Install Prerequisite Packages ---
# Note: policycoreutils is the Debian equivalent for SELinux management
echo "Installing prerequisites..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y openssl ca-certificates unzip tar policycoreutils

# --- 3. Create Required Directories ---
mkdir -p /etc/panw
mkdir -p "$CORTEX_INSTALL_TMP_DIR"

# --- 4. Place Files ---
# Assuming the files are in the same directory as the script
if [ -f "$CORTEX_RPM_FILENAME" ]; then
    cp "$CORTEX_RPM_FILENAME" "$CORTEX_INSTALL_TMP_DIR/"
else
    echo "Error: $CORTEX_RPM_FILENAME not found!"
    exit 1
fi

if [ -f "$CORTEX_CONF_FILE" ]; then
    cp "$CORTEX_CONF_FILE" /etc/panw/cortex.conf
    chmod 0644 /etc/panw/cortex.conf
else
    echo "Error: $CORTEX_CONF_FILE not found!"
    exit 1
fi

# --- 5. Install Cortex XDR ---
echo "Installing Cortex XDR package..."
apt-get install -y "$CORTEX_INSTALL_TMP_DIR/$CORTEX_RPM_FILENAME"

# --- 6. Service Management & Verification ---
systemctl enable traps_pmd
systemctl start traps_pmd

echo "Waiting for successful check-in (this may take a few minutes)..."
MAX_RETRIES=15
RETRY_COUNT=0
until /opt/traps/bin/cytool status | grep -q "Last Successful Check-In time" || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
    sleep 15
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Retry $RETRY_COUNT/$MAX_RETRIES..."
done

if /opt/traps/bin/cytool status | grep -q "Last Successful Check-In time"; then
    CHECKIN_TIME=$(/opt/traps/bin/cytool status | grep "Last Successful Check-In time")
    echo "Cortex XDR is Functional. $CHECKIN_TIME"
else
    echo "Warning: Cortex installed but check-in not detected yet."
fi

# --- 7. Cleanup ---
rm -rf "$CORTEX_INSTALL_TMP_DIR"