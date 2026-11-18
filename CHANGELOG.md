# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-11-18

### Critical Fixes & UI/UX Audit
- **Android Display Ratio Synchronization**: Fixed critical defect where changing screen resolution on Android did not update the embedded scrcpy screen inside SUSCRCPY.
- **Responsive ViewportCanvas**: Re-architected embedded scrcpy container to calculate strict letterboxing and pillarboxing, eliminating stretching, distortion, or cropping.
- **Dynamic Resize Recalculation**: Container geometry automatically re-fits on window resize, maximize, restore, pane splitter drag, and device rotation.
- **Real-Time Stream Sniffing**: Integrated real-time reader thread capturing `INFO: Texture: WxH` and frame rate (`fps`) directly from scrcpy stream output.
- **Tri-Point Synchronization HUD**: Added bottom status bar displaying:
  - `📱 Android Logical: WxH px`
  - `📺 scrcpy Stream: WxH px`
  - `🖥 SUSCRCPY Preview: WxH px (Ratio)`
  - Real-time synchronization status pill (`● Synchronized` vs `⚠️ Mismatch`)
  - Quick action buttons for `↻ Re-Sync` and `↺ Reset`.
- **All 19 Standardized Aspect Ratio Presets**: Full support for `1:1`, `3:2`, `4:3`, `5:4`, `9:16`, `9:18`, `9:19`, `9:19.5`, `9:20`, `9:21`, `9:22`, `16:9`, `16:10`, `18:9`, `19:9`, `19.5:9`, `20:9`, `21:9`, `32:9`.
- **8-Step Synchronization Workflow**: Implemented Step 1-8 workflow with Step 4 `wm size` verification and complete preservation of testing sessions, logs, app context, and quality profiles.

### Added
- **Testing Session Manager**:
  - Full session lifecycle (`Created`, `Running`, `Paused`, `Completed`, `Interrupted`).
  - Unique session ID generation (`SUS-YYYYMMDD-XXXX`).
  - Binds device specifications, target application, test types, and tester notes into a unified context.
  - Startup detection and recovery of interrupted testing sessions.
- **Device Screenshot Capture & Non-Destructive Annotation**:
  - Direct ADB framebuffer extraction (`screencap -p`), avoiding desktop window overlap.
  - Interactive review dialog with non-destructive vector annotation tools (Boxes, Arrows, Text, Redaction/Blur).
  - Preserves original raw capture while saving `_annotated.png` copy.
- **Native Android Screen Recording**:
  - Device display recording with real-time duration counter and file size tracking.
  - Safe MP4 finalization via signal interruption before device pull (guaranteeing valid MP4 `moov` atoms).
  - Device disconnect recovery preserving partial recordings.
- **Network Proxy Manager**:
  - Global Android HTTP/HTTPS proxy configuration (`settings put global http_proxy`).
  - Socket-level reachability and connectivity testing.
  - Security testing guidance panel for Burp Suite, OWASP ZAP, and mitmproxy.
- **Defect Observations & Bug Notes**:
  - Structured observation logging (Severity, Category, Expected, Actual).
  - Direct attachment of captured screenshots and error log excerpts.
- **Session Event Timeline**:
  - Chronological event tracking across device connections, app actions, resolution changes, captures, and errors.
  - Exportable to `timeline.json`.
- **Evidence Integrity & File System**:
  - Structured evidence hierarchy (`SUSCRCPY-Evidence/<Project>/<Session_ID>/`).
  - Automated cryptographic SHA-256 manifest generation (`evidence_manifest.json`).
  - Low disk space warning system.
- **Comprehensive HTML Test Session Report Generator**:
  - Standalone, responsive dark/light HTML report for developer sharing.
  - Compiles diagnostics, timeline, observations, screenshot gallery, recordings, and SHA-256 manifest.
- **Testing Workstation UI/UX**:
  - Embedded quick toolbar (Screenshot `Ctrl+Shift+S`, Record `Ctrl+Shift+R`, Note `Ctrl+Shift+O`, Quality, Fullscreen).
  - Tabbed right-side workstation: `Device & Apps`, `Screen Profiles`, `Testing Session`, `Network & Proxy`, `Test Notes`, `Evidence Files`.
  - Header session badge indicator and quick session switcher.

## [2.1.0] - 2026-11-18

### Added
- **Unified Single-Window Desktop Interface**: Complete UI/UX redesign combining live scrcpy mirror, display settings, and logcat viewer into one cohesive native layout.
- **Native Foreign Window Embedding**: Embedded scrcpy display using native X11/XWayland and Win32 reparenting APIs (`QWindow.fromWinId()`).
- **50/50 Balanced Splitter Layout & Persistence**: True 50/50 default splitter proportions, layout persistence via `QSettings`, and one-click `⊞ Reset Layout` / <kbd>Ctrl+L</kbd> shortcut.
- **Real-Time Application Package Search**: Instant search bar for filtering through hundreds of installed device applications by package name and label.
- **Universal Screen Profiles Library**: Support for 12 hardware categories (Smartphones, Tablets, Foldables, Wearables, Laptops, Desktops, TVs, Gaming Handhelds, Automotive, Signage, XR, E-readers).
- **Stream Quality Profiles**: Added `performance` (720p 4M 30fps), `balanced` (1080p 8M 60fps), and `high` (native 16M 60fps) scrcpy modes.
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

### Fixed
- **Log Priority & False-Positive Counters**: Android log priority (`V, D, I, W, E, F`) is now strictly authoritative. Fixed false positives where informational video cache misses, try-catch notifications, and framework debug messages inflated error and crash counters.
- **Aspect Ratio Orientation Inversion**: Fixed dimension calculation on portrait screens where landscape presets (e.g., 16:9) incorrectly shrank height instead of computing proper portrait proportions.
- **Update Dialog 404 Handling**: Proper classification of HTTP 404 (when no releases are yet published) with retry options and automatic disabling of the "Update Now" action.
- **Device Details Compatibility**: Added `cpu_architecture` alias property on `DeviceDetails` for backwards compatibility.

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
