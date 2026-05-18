#!/bin/bash

# --- CONFIGURATION ---
SERVER_FILE="servers.txt"

# --- CHECK SERVER FILE ---
if [ ! -f "$SERVER_FILE" ]; then
    echo "Error: '$SERVER_FILE' not found."
    exit 1
fi

echo "========================================================"
echo "   GCP MULTI-SERVER FILE UPLOADER"
echo "========================================================"

# --- STEP 1: ASK FOR LOCAL FILE ---
while true; do
    read -e -p "Enter path of LOCAL file to upload: " LOCAL_PATH
    # -e allows tab completion in Git Bash
    
    # Remove quotes if user dragged-and-dropped file
    LOCAL_PATH="${LOCAL_PATH%\"}"
    LOCAL_PATH="${LOCAL_PATH#\"}"

    if [ -z "$LOCAL_PATH" ]; then
        echo "   [!] You must enter a path."
    elif [ ! -e "$LOCAL_PATH" ]; then
        echo "   [!] Error: File '$LOCAL_PATH' does not exist locally."
    else
        break
    fi
done

# --- STEP 2: ASK FOR REMOTE DESTINATION ---
echo ""
echo "Enter REMOTE path (e.g., /tmp/ or /home/user/script.sh)"
read -e -p "Destination: " REMOTE_PATH

if [ -z "$REMOTE_PATH" ]; then
    echo "   [!] No destination provided. Defaulting to home (~/)"
    REMOTE_PATH="~/"
fi

# Determine filename for verification
BASENAME=$(basename "$LOCAL_PATH")

echo ""
echo "Summary:"
echo "  Source:      $LOCAL_PATH"
echo "  Destination: $REMOTE_PATH"
echo "--------------------------------------------------------"

# --- EXECUTION LOOP ---
while read -r line || [ -n "$line" ]; do
    # 1. Clean invisible Windows characters
    clean_line=$(echo "$line" | tr -d '\r')
    
    # 2. Skip empty/comment lines
    [[ -z "$clean_line" || "$clean_line" =~ ^# ]] && continue

    # 3. Read variables
    read -r ZONE INSTANCE PROJECT <<< "$clean_line"

    echo "Target: $INSTANCE ($ZONE)"

    # --- UPLOAD ---
    echo "  > Uploading..."
    gcloud compute scp --recurse "$LOCAL_PATH" "$INSTANCE:$REMOTE_PATH" \
        --zone="$ZONE" \
        --project="$PROJECT" \
        --tunnel-through-iap \
        --quiet 2>/dev/null

    if [ $? -eq 0 ]; then
        echo "  > Upload Success."
        
        # --- VERIFY (List the file) ---
        # We try to list the specific file to confirm it exists
        # If user gave a directory (ends in /), we append the filename
        if [[ "$REMOTE_PATH" == */ ]]; then
             CHECK_PATH="${REMOTE_PATH}${BASENAME}"
        else
             CHECK_PATH="$REMOTE_PATH"
        fi

        echo "  > Verifying..."
        gcloud compute ssh "$INSTANCE" \
            --zone="$ZONE" \
            --project="$PROJECT" \
            --tunnel-through-iap \
            --command="ls -ld '$CHECK_PATH'" \
            --quiet 2>/dev/null
            
        if [ $? -eq 0 ]; then
            echo "  > [OK] File confirmed on server."
        else
            echo "  > [?] Upload worked, but could not list '$CHECK_PATH'. (Check path permissions?)"
        fi

    else
        echo "  > [ERROR] Upload failed."
    fi

    echo "--------------------------------------------------------"

done < "$SERVER_FILE"