#!/bin/bash

# Helper script to verify and fix MESHCORE_RX_LOG_ENABLED config
# This script helps users switch from manual decryption (RX_LOG) to library events (CHANNEL_MSG_RECV)

CONFIG_FILE="${1:-config.py}"

echo "=========================================="
echo "MeshCore Config Fixer"
echo "=========================================="
echo ""

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: Config file not found: $CONFIG_FILE"
    echo ""
    echo "Usage: $0 [path/to/config.py]"
    echo "Example: $0 /home/dietpi/bot/config.py"
    exit 1
fi

echo "📋 Checking config file: $CONFIG_FILE"
echo ""

# Check current setting
if grep -q "MESHCORE_RX_LOG_ENABLED" "$CONFIG_FILE"; then
    CURRENT_VALUE=$(grep "MESHCORE_RX_LOG_ENABLED" "$CONFIG_FILE" | grep -v "^#" | tail -1)
    echo "✓ Found setting: $CURRENT_VALUE"
    
    if echo "$CURRENT_VALUE" | grep -q "= False"; then
        echo "✅ Config is already correct!"
        echo ""
        echo "If bot still shows RX_LOG in logs, try:"
        echo "  1. rm -rf $(dirname $CONFIG_FILE)/__pycache__/"
        echo "  2. sudo systemctl restart meshtastic-bot"
        exit 0
    else
        echo "⚠️  Config needs to be changed to False"
    fi
else
    echo "⚠️  Setting not found in config"
fi

echo ""
echo "=========================================="
echo "Recommended Fix"
echo "=========================================="
echo ""
echo "Add or change this line in $CONFIG_FILE:"
echo ""
echo "  MESHCORE_RX_LOG_ENABLED = False"
echo ""
echo "This will:"
echo "  ✓ Disable failed manual PSK decryption"
echo "  ✓ Enable CHANNEL_MSG_RECV (library events)"
echo "  ✓ Make bot work like meshcore-cli"
echo "  ✓ Allow /echo and other commands to work"
echo ""
echo "=========================================="
echo "Manual Steps"
echo "=========================================="
echo ""
echo "1. Edit config:"
echo "   nano $CONFIG_FILE"
echo ""
echo "2. Add or change line:"
echo "   MESHCORE_RX_LOG_ENABLED = False"
echo ""
echo "3. Save and exit (Ctrl+O, Enter, Ctrl+X)"
echo ""
echo "4. Clear cache:"
echo "   rm -rf $(dirname $CONFIG_FILE)/__pycache__/"
echo "   rm -f $(dirname $CONFIG_FILE)/config.pyc"
echo ""
echo "5. Restart bot:"
echo "   sudo systemctl restart meshtastic-bot"
echo ""
echo "6. Verify logs show CHANNEL_MSG_RECV:"
echo "   sudo journalctl -u meshtastic-bot --since '1 minute ago' | grep -E 'CHANNEL_MSG|RX_LOG|Souscription'"
echo ""

# Offer to make backup and auto-fix
echo "=========================================="
echo "Auto-fix Available"
echo "=========================================="
echo ""
read -p "Would you like me to automatically fix the config? (yes/no): " CONFIRM

if [ "$CONFIRM" = "yes" ] || [ "$CONFIRM" = "y" ]; then
    # Make backup
    BACKUP_FILE="${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    echo ""
    echo "📋 Creating backup: $BACKUP_FILE"
    cp "$CONFIG_FILE" "$BACKUP_FILE"
    
    # Check if setting exists
    if grep -q "^MESHCORE_RX_LOG_ENABLED" "$CONFIG_FILE"; then
        # Replace existing setting
        echo "📝 Updating existing setting..."
        sed -i 's/^MESHCORE_RX_LOG_ENABLED.*$/MESHCORE_RX_LOG_ENABLED = False  # Use library events (CHANNEL_MSG_RECV)/' "$CONFIG_FILE"
    else
        # Add new setting at end
        echo "📝 Adding new setting..."
        echo "" >> "$CONFIG_FILE"
        echo "# Use library-decrypted events (not manual decryption)" >> "$CONFIG_FILE"
        echo "MESHCORE_RX_LOG_ENABLED = False  # Use CHANNEL_MSG_RECV (works like meshcore-cli)" >> "$CONFIG_FILE"
    fi
    
    echo "✅ Config updated!"
    echo ""
    echo "New setting:"
    grep "MESHCORE_RX_LOG_ENABLED" "$CONFIG_FILE" | grep -v "^#"
    echo ""
    echo "Now run:"
    echo "  rm -rf $(dirname $CONFIG_FILE)/__pycache__/"
    echo "  sudo systemctl restart meshtastic-bot"
    echo ""
else
    echo ""
    echo "No changes made. Please update manually using steps above."
    echo ""
fi
