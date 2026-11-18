#!/usr/bin/env bash
# ==============================================================================
# SUSCRCPY — Official Linux Uninstallation Script
# ==============================================================================
set -Eeuo pipefail

echo "=================================================================="
echo "          SUSCRCPY Linux Uninstallation Script                    "
echo "=================================================================="

# Enforce root / sudo
if [ "$(id -u)" -ne 0 ]; then
    echo "[-] Error: Uninstallation requires administrator privileges."
    echo "    Please run: sudo ./uninstall.sh or sudo /opt/suscrcpy/uninstall.sh"
    exit 1
fi

echo "[1/3] Removing global binary and desktop launcher..."
rm -f /usr/local/bin/suscrcpy
rm -f /usr/share/applications/suscrcpy.desktop

# Update desktop database if available
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi

echo "[2/3] Removing application files from /opt/suscrcpy..."
rm -rf /opt/suscrcpy

echo "[3/3] User configuration and diagnostic logs check..."
# Determine actual user who invoked sudo
TARGET_USER="${SUDO_USER:-$(logname 2>/dev/null || echo "")}"
if [ -n "$TARGET_USER" ] && [ "$TARGET_USER" != "root" ]; then
    USER_HOME=$(eval echo "~$TARGET_USER")
    USER_CONFIG="$USER_HOME/.suscrcpy"
    if [ -d "$USER_CONFIG" ]; then
        read -r -p "Do you want to delete user configuration and logs in $USER_CONFIG? [y/N]: " REMOVE_CONF || REMOVE_CONF="n"
        case "$REMOVE_CONF" in
            [yY][eE][sS]|[yY])
                rm -rf "$USER_CONFIG"
                echo "[+] Removed $USER_CONFIG"
                ;;
            *)
                echo "[*] Preserved user configuration at $USER_CONFIG"
                ;;
        esac
    fi
fi

echo ""
echo "=================================================================="
echo "[✓] SUSCRCPY has been successfully uninstalled from this system."
echo "    System dependencies (adb, scrcpy, python3) have been kept intact."
echo "=================================================================="
