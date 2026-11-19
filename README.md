# SUSCRCPY — Android Device Testing Desktop Application

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux%20%7C%20Kali%20%7C%20Debian%20%7C%20Ubuntu-orange.svg)](#requirements)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](#requirements)

**SUSCRCPY** is a focused, open-source Android testing desktop application for developers, QA engineers and security researchers.

It combines **low-latency interactive screen mirroring** (powered by `scrcpy`), **native window embedding**, **exact display aspect-ratio and resolution overrides**, and **real-time logcat monitoring with crash detection** in one small window: the live device screen on the left, three work tabs on the right.

---

## Table of Contents

- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Installation Guide](#installation-guide)
  - [Kali Linux / Debian / Ubuntu](#kali-linux--debian--ubuntu)
- [Android Device Setup](#android-device-setup)
- [Usage & Global Commands](#usage--global-commands)
  - [CLI Reference](#cli-reference)
- [Automatic Updates](#automatic-updates)
  - [Updating via CLI](#updating-via-cli)
  - [Updating via GUI](#updating-via-gui)
- [Uninstallation](#uninstallation)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Architecture & Security](#architecture--security)
- [Contributing](#contributing)
- [License](#license)

---

## Key Features

1. **Embedded scrcpy Screen Mirroring**:
   - The interactive Android screen is embedded natively into the left pane of the window (`QWindow.fromWinId`).
   - The mirror is left-anchored and fully visible for every aspect ratio; it never jumps centre or clips.
   - Direct mouse control, touch simulation, swipe gestures, text input and Android navigation.
   - `Fit` (whole screen), `Fill` (crop) and `Original` (1:1) scaling modes.

2. **Exact Display Resolution & Aspect Ratio Override**:
   - 20 presets: `1:1`, `3:2`, `4:3`, `5:4`, `16:9`, `16:10`, `18:9`, `19:9`, `19.5:9`, `20:9`, `21:9`, `22:9`, `32:9` and their portrait forms, plus `Custom` pixels.
   - Sizes are snapped to integer multiples of the ratio, so the applied resolution reduces to exactly the requested ratio (no off-by-one distortion).
   - Width and height fields stay linked to the selected ratio, in the device's current orientation.
   - Every applied size is verified by reading `wm size` back from the device.
   - The native resolution is restored automatically on exit or with **Reset**.

3. **Installed Application Selector**:
   - Lists user and system packages with search and filters.
   - Selecting an app narrows logcat to that application's processes.

4. **Real-Time Android Logcat Monitoring**:
   - Background streaming worker with a bounded view buffer (3000 lines) and a capped export buffer.
   - Real-time severity classification (Verbose, Debug, Info, Warning, Error, Fatal).
   - Confirmed-crash detection (`FATAL EXCEPTION`, ANR, `AndroidRuntime`, `Fatal signal`).
   - Counters are exact: errors are ERROR/FATAL lines, warnings are W lines, and crashes
     count events (stack frames are grouped, not counted again).
   - Category filters (All / Errors / Warnings / Crashes) re-filter retained lines instantly.
   - Reset counters without losing captured logs, and export all logs or a single category.
   - Full-device or per-application logging, text filter, pause and auto-scroll.

5. **Screenshot Capture**:
   - One click (or `Ctrl+Shift+S`) saves a PNG of the live device screen to `~/Pictures/SUSCRCPY` with verified pixel dimensions.

6. **Automatic GitHub Updates (CLI)**:
   - `sudo suscrcpy --update` with SHA-256 integrity verification, zip-slip protection, atomic staging and rollback.

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Shadab-2604/suscrcpy.git
cd suscrcpy

# 2. Run the global installer
sudo ./install.sh

# 3. Launch SUSCRCPY from any terminal
suscrcpy
```

---

## Installation Guide

### Kali Linux / Debian / Ubuntu

SUSCRCPY requires Python 3.10+, ADB, scrcpy, and PySide6. The installer automatically resolves dependencies via `apt-get`:

```bash
# Clone repository
git clone https://github.com/Shadab-2604/suscrcpy.git
cd suscrcpy

# Install globally to /opt/suscrcpy and /usr/local/bin/suscrcpy
sudo ./install.sh
```

The installer configures:
- System binaries in `/opt/suscrcpy`
- Global executable at `/usr/local/bin/suscrcpy`
- Desktop entry at `/usr/share/applications/suscrcpy.desktop`

> [!NOTE]
> Run the GUI as your normal desktop user (`suscrcpy`), **not** with `sudo`. Root privileges are only required for installation and updates.

---

## Android Device Setup

To connect your Android device:

1. Enable **Developer Options**:
   - Go to Android **Settings** → **About Phone**.
   - Tap **Build Number** 7 times until you see *"You are now a developer!"*.
2. Enable **USB Debugging**:
   - Go to **Settings** → **System** → **Developer Options**.
   - Enable **USB Debugging**.
3. Connect your Android device via USB.
4. When prompted on your phone, check *"Always allow from this computer"* and tap **Allow**.
5. Verify connection in your terminal:
   ```bash
   adb devices
   ```
   Your device serial should appear with the status `device`.

---

## Usage & Global Commands

Once installed, launch the application from your terminal:

```bash
suscrcpy
```

Or search for **SUSCRCPY** in your desktop application menu under *Development* or *Utility*.

### Window layout

- **Left** — the live Android screen with a small toolbar (Screenshot, Scaling, Quality, Fullscreen) and a status strip showing device size, stream size, view size and sync state.
- **Display** tab — aspect-ratio preset, width/height, Apply and Reset.
- **Apps** tab — search and select the app to follow in the logs.
- **Logs** tab — start/stop, pause, clear, reset counters, category filters and scoped export.

### CLI Reference

| Command | Description |
|---|---|
| `suscrcpy` | Launch the SUSCRCPY desktop GUI |
| `suscrcpy --help` | Display all available command-line flags |
| `suscrcpy --version` | Output the currently installed version |
| `suscrcpy --check-updates` | Check GitHub for new releases |
| `sudo suscrcpy --update` | Download, verify, and install the latest GitHub release |
| `suscrcpy --adb /path/to/adb` | Use a custom ADB binary |
| `suscrcpy --scrcpy /path/to/scrcpy` | Use a custom scrcpy binary |
| `suscrcpy --debug` | Enable verbose console diagnostic logging |

---

## Automatic Updates

SUSCRCPY includes a cryptographic update system communicating directly with the official GitHub repository.

### Updating via CLI

Check for available updates:
```bash
suscrcpy --check-updates
```

Install the latest release system-wide:
```bash
sudo suscrcpy --update
```

During an update:
1. The latest release archive (`suscrcpy-source.zip`) and checksums (`SHA256SUMS`) are fetched over HTTPS.
2. The archive's SHA-256 digest is verified before extraction.
3. Archive members are checked against directory traversal vulnerabilities.
4. The existing `/opt/suscrcpy` installation is backed up.
5. Files are staged and the new version runs an automated self-test.
6. If the self-test fails, the previous version is automatically restored.

Updates are applied through the CLI so that the archive is verified and installed with the privileges under your control.

---

## Uninstallation

To cleanly remove SUSCRCPY from your system:

```bash
sudo /opt/suscrcpy/uninstall.sh
```

Or from the cloned repository:
```bash
sudo ./uninstall.sh
```

This removes `/opt/suscrcpy`, `/usr/local/bin/suscrcpy`, and the desktop launcher. System dependencies (`adb`, `scrcpy`, `python3`) are preserved.

---

## Troubleshooting & FAQ

### 1. `adb: no devices/emulators found`
- Ensure USB debugging is enabled on your device.
- Try restarting the ADB server:
  ```bash
  adb kill-server && adb start-server
  ```
- Use a high-quality USB cable connected to a direct USB port (avoid unpowered hubs).

### 2. Device shows as `unauthorized`
- Unlock your phone screen and look for the USB Debugging permission prompt.
- Check *"Always allow from this computer"* and confirm.

### 3. Screen mirroring window opens externally on Wayland
- On Linux desktop sessions running GNOME/Wayland, SUSCRCPY automatically sets `QT_QPA_PLATFORM=xcb` to enable seamless XWayland foreign window reparenting.
- Ensure `xdotool` and `x11-utils` are installed:
  ```bash
  sudo apt-get install -y xdotool x11-utils
  ```

---

## Architecture & Security

- **Repository**: [https://github.com/Shadab-2604/suscrcpy](https://github.com/Shadab-2604/suscrcpy)
- **Language**: Python 3.10+
- **Framework**: PySide6 (Qt 6)
- **Modules**: `core/` (ADB, screen, scrcpy, logs, screenshots), `display_backend/` (native window embedding), `ui/` (window, panels)
- **Protocol**: Android Debug Bridge (ADB), scrcpy v2.x / v4.x
- **Update Verification**: SHA-256 checksum validation via `SHA256SUMS`

---

## Contributing

Contributions, bug reports, and pull requests are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) before submitting code.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
