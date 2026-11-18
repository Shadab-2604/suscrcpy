# SUSCRCPY — Android Device Testing Desktop Application

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux%20%7C%20Kali%20%7C%20Debian%20%7C%20Ubuntu-orange.svg)](#requirements)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](#requirements)

**SUSCRCPY** is an open-source, cross-platform Android Device Testing Desktop Application designed for application developers, QA engineers, and cybersecurity security researchers. 

It combines **low-latency interactive screen mirroring** (powered by `scrcpy`), **native foreign window embedding**, **display aspect ratio and resolution overrides**, **installed application package management**, and **real-time logcat monitoring with crash detection** into a single desktop utility.

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
   - The interactive Android screen is embedded natively into the main SUSCRCPY application window using native OS window adoption (`QWindow.fromWinId`).
   - Direct mouse control, touch simulation, swipe gestures, text input, and Android navigation.
   - Smooth letterboxed scaling preserving the target aspect ratio without visual distortion.

2. **Display Resolution & Aspect Ratio Management**:
   - Preset ratios: `1:1`, `4:3`, `5:4`, `16:9`, `16:10`, `18:9`, `19.5:9`, `20:9`, and `Custom (pixels)`.
   - Dynamic dimension linkage: changing Width updates Height according to the selected ratio.
   - Live greatest common divisor (GCD) aspect ratio computation.
   - Instant resolution overrides via `wm size` and clean restoration to native physical hardware resolution via `wm size reset`.
   - Universal Screen Profiles Library featuring 12 device categories (phones, tablets, foldables, smartwatches, monitors, TVs, XR, etc.).

3. **Installed Application Discovery**:
   - Enumerates third-party user applications and core system packages via ADB.
   - Package search, category filtering (`All`, `User Apps`, `System Apps`), and metadata inspection.
   - One-click target binding for application-specific log filtering.

4. **Real-Time Android Logcat Monitoring**:
   - Background streaming worker with bounded GUI memory buffer (prevents freezing on high log volume).
   - Real-time severity classification (Verbose, Debug, Info, Warning, Error, Fatal).
   - Pattern-based crash and error detection (`FATAL EXCEPTION`, `ANR`, `AndroidRuntime`, `NullPointerException`, etc.).
   - Full device logging vs application-specific logging.
   - Search filtering, live counters, hardware buffer clearing (`adb logcat -c`), and timestamped diagnostic report export.

5. **Integrated Automatic GitHub Updates**:
   - Single-command automated updates (`sudo suscrcpy --update`).
   - In-app GUI release checker with non-blocking background workers.
   - Cryptographic SHA-256 integrity verification (`SHA256SUMS`).
   - Zip Slip / path traversal protection, atomic staging, and automated rollback if self-test verification fails.

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

### Updating via GUI

1. Click the **🔄 Updates** button in the header bar.
2. The dialog will check GitHub in the background without freezing the interface.
3. Review the release notes and version number.
4. Click **Update Now** to apply the release.

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
- **Protocol**: Android Debug Bridge (ADB), scrcpy v1.x / v2.x / v4.x
- **Update Verification**: SHA-256 checksum validation via `SHA256SUMS`

---

## Contributing

Contributions, bug reports, and pull requests are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) before submitting code.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
