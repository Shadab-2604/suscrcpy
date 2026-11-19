#!/usr/bin/env bash
# ==============================================================================
# SUSCRCPY — Linux Production Installation Script (Kali / Debian / Ubuntu)
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================================================="
echo "          SUSCRCPY Global Linux Installation                      "
echo "=================================================================="

# Enforce root / sudo
if [ "$(id -u)" -ne 0 ]; then
    echo "[-] Error: Global installation requires administrator privileges."
    echo "    Please run: sudo ./install.sh"
    exit 1
fi

# 1. Operating System Detection
echo "[1/5] Detecting Linux operating system..."
OS_NAME="Linux"
if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    OS_NAME="${PRETTY_NAME:-$ID}"
fi
echo "[+] Detected OS: $OS_NAME"

# 2. Check System Tools
echo "[2/5] Checking core dependencies (Python 3, ADB, scrcpy, X11 tools)..."
MISSING_PKGS=()

if ! command -v python3 >/dev/null 2>&1; then
    MISSING_PKGS+=(python3 python3-pip)
fi

if ! command -v adb >/dev/null 2>&1; then
    MISSING_PKGS+=(adb)
fi

if ! command -v scrcpy >/dev/null 2>&1; then
    MISSING_PKGS+=(scrcpy)
fi

if ! command -v xdotool >/dev/null 2>&1; then
    MISSING_PKGS+=(xdotool)
fi

if ! command -v xwininfo >/dev/null 2>&1; then
    MISSING_PKGS+=(x11-utils)
fi

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo "[*] Installing missing system packages: ${MISSING_PKGS[*]}..."
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update -qq
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${MISSING_PKGS[@]}"
    else
        echo "[-] Non-Debian package manager detected. Please manually install: ${MISSING_PKGS[*]}"
    fi
else
    echo "[✓] All core system utilities are present."
fi

# 3. Install Python Dependencies
echo "[3/5] Installing Python dependencies..."
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    python3 -m pip install -r "$SCRIPT_DIR/requirements.txt" --break-system-packages -q 2>/dev/null || \
    python3 -m pip install -r "$SCRIPT_DIR/requirements.txt" -q
fi

# 4. Deploy Application Files to /opt/suscrcpy
TARGET_DIR="/opt/suscrcpy"
echo "[4/5] Deploying application files to $TARGET_DIR..."
mkdir -p "$TARGET_DIR"

# Clean previous files while preserving any user logs or configs
for item in core ui display_backend resources main.py version.py update_manager.py uninstall.sh requirements.txt LICENSE README.md; do
    if [ -e "$SCRIPT_DIR/$item" ]; then
        rm -rf "${TARGET_DIR:?}/$item"
        cp -r "$SCRIPT_DIR/$item" "$TARGET_DIR/"
    fi
done

# Set permissions
chmod -R 755 "$TARGET_DIR"

# 5. Create Global Executable and Desktop Launcher
echo "[5/5] Creating global CLI executable and desktop launcher..."

cat << 'EOF' > /usr/local/bin/suscrcpy
#!/usr/bin/env bash
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
exec /usr/bin/python3 /opt/suscrcpy/main.py "$@"
EOF
chmod 755 /usr/local/bin/suscrcpy

mkdir -p /usr/share/icons/hicolor/scalable/apps
if [ -f "$TARGET_DIR/resources/icons/suscrcpy.svg" ]; then
    cp "$TARGET_DIR/resources/icons/suscrcpy.svg" /usr/share/icons/hicolor/scalable/apps/suscrcpy.svg
    chmod 644 /usr/share/icons/hicolor/scalable/apps/suscrcpy.svg
fi

mkdir -p /usr/share/applications
cat << 'EOF' > /usr/share/applications/suscrcpy.desktop
[Desktop Entry]
Type=Application
Name=SUSCRCPY
GenericName=Android Device Testing Desktop Application
Comment=Live screen mirroring, display ratio controller, and logcat monitor
Exec=/usr/local/bin/suscrcpy
Icon=suscrcpy
Terminal=false
Categories=Development;Utility;Security;
Keywords=android;scrcpy;adb;testing;security;qa;
StartupWMClass=suscrcpy
EOF
chmod 644 /usr/share/applications/suscrcpy.desktop

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi

echo ""
echo "=================================================================="
echo "[✓] SUSCRCPY has been successfully installed system-wide!"
echo ""
echo "You can now run SUSCRCPY from any terminal location:"
echo "    suscrcpy               # Launch GUI (do NOT run with sudo)"
echo "    suscrcpy --help        # View command-line options"
echo "    suscrcpy --version     # Display installed version"
echo "    suscrcpy --check-updates # Check GitHub for latest releases"
echo "    sudo suscrcpy --update   # Update to the latest version"
echo ""
echo "To uninstall anytime:"
echo "    sudo /opt/suscrcpy/uninstall.sh"
echo "=================================================================="
