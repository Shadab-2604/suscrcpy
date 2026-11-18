# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-11-18

### Added
- **Unified Single-Window Desktop Interface**: Complete UI/UX redesign combining live scrcpy mirror, display settings, and logcat viewer into one cohesive native layout.
- **Native Foreign Window Embedding**: Embedded scrcpy display using native X11/XWayland and Win32 reparenting APIs (`QWindow.fromWinId()`).
- **Universal Screen Profiles Library**: Support for 12 hardware categories (Smartphones, Tablets, Foldables, Wearables, Laptops, Desktops, TVs, Gaming Handhelds, Automotive, Signage, XR, E-readers).
- **Automated GitHub Update System**:
  - CLI update checks via `suscrcpy --check-updates`
  - Automated atomic updates via `sudo suscrcpy --update`
  - GUI Update dialog with background `QThread` release checking, release notes preview, and progress bar
  - Cryptographic SHA-256 integrity verification (`SHA256SUMS`)
  - Zip Slip / path traversal archive security validation
  - Automatic backup and rollback mechanism
- **Production Linux Packaging**:
  - Global system installation script `install.sh`
  - Clean uninstallation script `uninstall.sh`
  - Desktop entry integration (`suscrcpy.desktop`)
- **CI/CD Release Automation**: GitHub Actions workflow (`.github/workflows/release.yml`) for automated testing, packaging `suscrcpy-source.zip`, and GitHub release asset publishing.

### Changed
- Migrated legacy Tkinter codebase to modern PySide6 / Qt 6 architecture.
- Modularized core services into `AdbManager`, `DeviceManager`, `ScreenManager`, `ScrcpyManager`, `AppManager`, `LogManager`, and `UpdateManager`.

---

## [2.0.0] - 2026-11-18

### Added
- Real-time Android logcat capture with threadtime parsing.
- Pattern-based crash and error detection (`FATAL EXCEPTION`, `ANR`, stack traces).
- Application package manager with User vs System app categorization.
- Diagnostic log export functionality.

---

## [1.0.0] - 2026-11-18

### Added
- Initial release featuring Tkinter display aspect ratio calculations and standalone scrcpy execution.
