#!/bin/bash

# ==============================================================================
# Tanium Debian Manager - Minimalist Version
# ==============================================================================

# --- CONFIGURATION ---
DEFAULT_VERSION="7.8.1.3126"
INIT_FILE="tanium-init.dat"
INSTALL_DIR="/opt/Tanium/TaniumClient"
TANIUM_SERVER="141.147.65.58"
TANIUM_PORT="17472"

# --- FUNCTIONS ---

check_root() {
    if [[ $EUID -ne 0 ]]; then
       echo "[-] Error: This script must be run as root."
       exit 1
    fi
}

connectivity_test() {
    echo -n "Checking connectivity to $TANIUM_SERVER:$TANIUM_PORT... "
    if timeout 2 bash -c "</dev/tcp/$TANIUM_SERVER/$TANIUM_PORT" 2>/dev/null; then
        echo "SUCCESSFUL"
    else
        echo "FAILED"
    fi
}

# --- MAIN ---

check_root

echo "------------------------------------------------"
echo "  Tanium Operations (Debian Only)"
echo "------------------------------------------------"
echo "1) Install Tanium Client & Place Config"
echo "2) Remove Tanium Client"
echo "3) Status Check Only"
read -p "Select action [1-3]: " CHOICE

case $CHOICE in
    1)
        # 1. Version Selection
        read -p "Enter version [$DEFAULT_VERSION]: " USER_VERSION
        TANIUM_VERSION=${USER_VERSION:-$DEFAULT_VERSION}

        # 2. Package Path Construction
        source /etc/os-release
        RAW_ARCH=$(uname -m)
        ARCH=$([[ "$RAW_ARCH" == "x86_64" ]] && echo "amd64" || echo "arm64")
        DEB_FILENAME="taniumclient_${TANIUM_VERSION}-debian${VERSION_ID}_${ARCH}.deb"

        echo "[*] Targeted Package: $DEB_FILENAME"
        read -p "Proceed with install? (y/n): " CONFIRM
        [[ "$CONFIRM" != "y" ]] && { echo "Aborted."; exit 0; }

        if [[ ! -f "$DEB_FILENAME" ]]; then
            echo "[-] Error: $DEB_FILENAME not found in current directory."
            exit 1
        fi

        # 3. Installation
        echo "[*] Installing package..."
        dpkg -i "$DEB_FILENAME"

        # 4. Config Copy
        if [[ -f "$INIT_FILE" ]]; then
            echo "[*] Placing $INIT_FILE..."
            mkdir -p "$INSTALL_DIR"
            cp "$INIT_FILE" "$INSTALL_DIR/$INIT_FILE"
            chmod 0644 "$INSTALL_DIR/$INIT_FILE"
        else
            echo "[!] Warning: $INIT_FILE not found. Skipping config placement."
        fi

        # 5. Service Start (No Reboot)
        echo "[*] Starting service..."
        systemctl enable taniumclient
        systemctl restart taniumclient
        ;;

    2)
        echo -e "\n--- REMOVAL ---"
        read -p "Confirm removal? (y/n): " CONFIRM
        [[ "$CONFIRM" != "y" ]] && { echo "Aborted."; exit 0; }

        echo "[*] Stopping service and removing package..."
        systemctl stop taniumclient 2>/dev/null
        dpkg --purge taniumclient
        rm -rf "$INSTALL_DIR"
        echo "[+] Removed."
        ;;
    
    3)
        echo -e "\n--- STATUS CHECK ---"
        ;;

    *)
        echo "Invalid choice."
        exit 1
        ;;
esac

# --- FINAL VALIDATION ---
echo -e "\n------------------------------------------------"
echo "  FINAL STATUS"
echo "------------------------------------------------"

# Check if service is running
if systemctl is-active --quiet taniumclient; then
    echo "Tanium Service:   RUNNING"
else
    echo "Tanium Service:   NOT RUNNING / NOT INSTALLED"
fi

# Port check
connectivity_test
echo "------------------------------------------------"