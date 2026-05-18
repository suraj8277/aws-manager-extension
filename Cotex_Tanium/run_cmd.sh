#!/bin/bash

# --- CONFIGURATION ---
SERVER_FILE="servers.txt"

# --- CHECK INPUT ---
if [ ! -f "$SERVER_FILE" ]; then
    echo "Error: '$SERVER_FILE' not found."
    exit 1
fi

# --- CAPTURE USER COMMAND ---
echo "========================================================"
echo "  MULTI-SERVER COMMAND RUNNER"
echo "========================================================"
echo "Targets: All servers listed in $SERVER_FILE"
echo ""
echo "Enter the command you want to run (e.g. 'df -h | grep sda'):"
# -r prevents backslashes from being interpreted as escapes
read -r USER_CMD

if [ -z "$USER_CMD" ]; then
    echo "No command entered. Exiting."
    exit 0
fi

echo ""
echo "Command to run: [ $USER_CMD ]"
read -p "Are you sure? (y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

echo "========================================================"

# --- EXECUTION LOOP ---
while read -r line || [ -n "$line" ]; do
    # 1. Clean invisible Windows characters (CRLF)
    clean_line=$(echo "$line" | tr -d '\r')

    # 2. Skip empty lines or comments
    [[ -z "$clean_line" || "$clean_line" =~ ^# ]] && continue

    # 3. Read variables
    read -r ZONE INSTANCE PROJECT <<< "$clean_line"

    echo "HOST: $INSTANCE ($ZONE)"
    echo "--------------------------------------------------------"

    # 4. Run the command
    # We pass "$USER_CMD" in quotes so it is treated as a single argument.
    # Bash variables preserve the inner quotes user typed, making complex commands safe.
    gcloud compute ssh "$INSTANCE" \
        --zone="$ZONE" \
        --project="$PROJECT" \
        --tunnel-through-iap \
        --command="$USER_CMD" \
        --quiet 2>&1

    # Check exit status of the SSH command (0 = Success, Non-zero = Error)
    if [ $? -ne 0 ]; then
        echo "   [!] Command failed or connection error on $INSTANCE"
    fi

    echo "========================================================"

done < "$SERVER_FILE"