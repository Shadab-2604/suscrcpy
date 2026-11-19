#!/usr/bin/env bash
# ==============================================================================
# SUSCRCPY 2.0 — Linux Installation Script (Debian / Kali / Ubuntu)
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== SUSCRCPY 2.0 Linux Installer ==="

# Check Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "[-] Python 3 not found. Installing..."
    sudo apt-get update && sudo apt-get install -y python3 python3-pip
fi

# Check adb and scrcpy
echo "[1/4] Checking core system tools (adb, scrcpy)..."
MISSING_PKGS=()
if ! command -v adb >/dev/null 2>&1; then
    MISSING_PKGS+=(adb)
fi
if ! command -v scrcpy >/dev/null 2>&1; then
    MISSING_PKGS+=(scrcpy)
fi

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo "[+] Installing missing system packages: ${MISSING_PKGS[*]}..."
    sudo apt-get update
    sudo apt-get install -y "${MISSING_PKGS[@]}"
fi

# Install Python requirements
echo "[2/4] Installing Python dependencies (PySide6)..."
python3 -m pip install -r "$SCRIPT_DIR/requirements.txt" --break-system-packages 2>/dev/null || \
python3 -m pip install -r "$SCRIPT_DIR/requirements.txt"

# Install application directory
TARGET_DIR="/opt/suscrcpy"
echo "[3/4] Deploying application to $TARGET_DIR..."
sudo mkdir -p "$TARGET_DIR"
sudo cp -r "$SCRIPT_DIR/core" "$TARGET_DIR/"
sudo cp -r "$SCRIPT_DIR/ui" "$TARGET_DIR/"
sudo cp -r "$SCRIPT_DIR/display_backend" "$TARGET_DIR/"
sudo cp -r "$SCRIPT_DIR/resources" "$TARGET_DIR/"
sudo cp "$SCRIPT_DIR/main.py" "$TARGET_DIR/main.py"
sudo cp "$SCRIPT_DIR/requirements.txt" "$TARGET_DIR/requirements.txt"
sudo chmod -R 755 "$TARGET_DIR"

# Create global command
echo "[4/4] Creating global 'suscrcpy' executable command..."
sudo tee /usr/local/bin/suscrcpy > /dev/null << 'EOF'
#!/usr/bin/env bash
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
exec /usr/bin/python3 /opt/suscrcpy/main.py "$@"
EOF
sudo chmod 755 /usr/local/bin/suscrcpy

# Install desktop entry
DESKTOP_FILE="/usr/share/applications/suscrcpy.desktop"
sudo mkdir -p /usr/share/applications
sudo tee "$DESKTOP_FILE" > /dev/null << 'EOF'
[Desktop Entry]
Type=Application
Name=SUSCRCPY 2.0
Comment=Android Device Testing Desktop Application
Exec=/usr/local/bin/suscrcpy
Icon=/opt/suscrcpy/resources/icons/suscrcpy.svg
Terminal=false
Categories=Development;Utility;Security;
Keywords=android;scrcpy;adb;testing;security;
EOF
sudo chmod 644 "$DESKTOP_FILE"

echo ""
echo "=============================================================================="
echo "[✓] SUSCRCPY 2.0 successfully installed!"
echo "Run globally from any terminal (do NOT use sudo):"
echo "    suscrcpy"
echo "Or launch from your Applications menu under Development / Utility."
echo "=============================================================================="
