# SUSCRCPY v2.1.0 — Comprehensive Quality Assurance & System Audit Report

**Date:** November 18, 2026  
**Auditor:** Principal Software Engineer & QA Lead  
**Target Hardware:** iKall N15 (Model B610A115, Android 11 / API 30, 4 GB RAM, 64 GB Storage, USB Serial: `0123456789ABCDEF`)  
**Host Environment:** Kali Linux (x86_64), Linux Kernel 6.12+, Python 3.14.8, PySide6 6.8.x, scrcpy 3.1 (Debian package), ADB 1.0.41  
**Project Repository:** [https://github.com/Shadab-2604/suscrcpy](https://github.com/Shadab-2604/suscrcpy)

---

## 1. Executive Summary

SUSCRCPY v2.1.0 underwent a complete architectural, functional, security, and UI/UX audit. All critical issues identified in user testing and desktop inspection have been identified, root causes analyzed, repaired, verified via automated test suites (44 passing tests), and validated on physical hardware (iKall N15).

| Issue Category | Severity | Status | Verification |
|---|---|---|---|
| Main Window 50/50 Splitter & Persistence | High | RESOLVED | Tested with QSettings, 50/50 enforce, `Ctrl+L` reset |
| Native scrcpy Embedded Window Reparenting | Critical | RESOLVED | Confirmed embedded into Qt container (`fromWinId`) |
| Log Classification & False Positive Counters | High | RESOLVED | Android logcat priority authoritative; 0 false crashes |
| Aspect Ratio Orientation Inversion | High | RESOLVED | Orientation-aware calculation (portrait & landscape) |
| GitHub Update Manager 404 & UI State | Medium | RESOLVED | Clean handling of non-published releases & retry |
| App Discovery Real-Time Search Bar | Medium | RESOLVED | Instant filtering across package name and label |
| DeviceDetails Backward Compatibility | Low | RESOLVED | Added `cpu_architecture` alias for `cpu_abi` |

---

## 2. Detailed Bug Reports, Root Causes & Fixes

### Bug A: Main Window Splitter Sizing & Layout Persistence
- **Symptom:** The main application window was not maintaining a 50/50 balance between the live Android screen container and the right-hand settings/logs panels. Resizing or restarting the application collapsed panels or left uneven proportions.
- **Root Cause:** Calling `setStretchFactor(0, 1)` and `setStretchFactor(1, 1)` in PySide6 only controls resize weight; it does not set initial or restored pixel dimensions when child widgets carry differing default `sizeHint()` recommendations.
- **Fix:**
  - Implemented `_restore_or_init_splitter_layout()` in `ui/main_window.py`.
  - Set explicit `minimumWidth(380)` on `screen_view` and `minimumWidth(400)` on `right_splitter`.
  - Stored and restored binary splitter states (`main_splitter` and `right_splitter`) using `QSettings("SUSCRCPY", "SUSCRCPY-Workstation")`.
  - Added a dedicated `⊞ Reset Layout` button in `ui/header_bar.py` and global shortcut `<kbd>Ctrl+L</kbd>` which resets the split to exact 50/50 (`setSizes([width // 2, width // 2])`).
- **Retest:** Verified on desktop resolutions 1366x768, 1920x1080, and 2560x1440. Layout cleanly splits 50/50 and restores across restarts.

---

### Bug B: Native scrcpy Embedded Window Reparenting
- **Symptom:** In earlier versions, scrcpy opened in a detached floating window separate from the control interface.
- **Root Cause:** Launching `scrcpy` without window ID targeting or without platform-appropriate window reparenting resulted in a standalone SDL2 window.
- **Fix:**
  - Standardized on Linux X11/XWayland foreign window embedding via `QWindow.fromWinId(win_id)` and `QWidget.createWindowContainer(foreign_window)`.
  - Enforced `QT_QPA_PLATFORM=xcb` in launch scripts (`suscrcpy`, `suscrcpy.py`, `main.py`) to ensure reliable X11 window parenting even when running under Wayland desktops (via XWayland).
  - Implemented fallback scrcpy options (`--window-title=suscrcpy_embed`, `--window-borderless`, `--no-audio`, `--stay-awake`).
- **Retest:** Confirmed scrcpy window is reparented strictly inside the left pane of the SUSCRCPY window without titlebar duplication or detached windows.

---

### Bug C: Log Classification & False Positive Counters
- **Symptom:** Logcat monitoring reported hundreds of errors and crashes (e.g., 353 errors / 432 warnings) during normal device idle or app startup, primarily due to video cache misses, internal try-catch messages, and normal framework notifications.
- **Root Cause:** `ErrorDetector` used naive regex matching on the entire raw log line before inspecting the Android log priority. Keywords like `error`, `exception`, `null` or `failed` inside `DEBUG` or `INFO` messages triggered error/crash counters.
- **Fix:**
  - Refactored `core/error_detector.py` to make the official Android logcat level (`V, D, I, W, E, F`) the authoritative filter.
  - Priority `V` (Verbose), `D` (Debug), and `I` (Info) are never counted as errors or warnings regardless of textual content.
  - Priority `W` (Warn) maps strictly to `WARNING`.
  - Priority `E` (Error) maps to `ERROR`.
  - Priority `F` (Fatal) maps to `CRASH`.
  - Crash detection requires genuine system crash markers (`FATAL EXCEPTION`, `AndroidRuntime: FATAL`, `Process ... has died`, `ANR in ...`, `Fatal signal ...`).
- **Retest:** Added unit test `test_no_false_positives_on_info_messages`. Streaming 5,800 live logs from the connected iKall N15 yielded 0 crashes and accurately categorized MTK vendor errors.

---

### Bug D: Display Resolution Aspect Ratio Calculation Orientation Inversion
- **Symptom:** Selecting a 16:9 preset on a portrait display (800x1280) inverted the calculation, producing a height of 450px instead of 1422px.
- **Root Cause:** Aspect ratio presets (e.g. `16:9`) assumed landscape orientation (`width > height`). For portrait devices, applying `(width * 9) / 16` shrinks the height rather than extending it proportionally.
- **Fix:**
  - Updated `core/screen_manager.py`'s `calculate_dimensions_for_ratio()` to be orientation-aware:
    - If `current_h >= current_w` (portrait), `height` is the major dimension and `width` is computed as `height * minor / major` (or vice-versa when maintaining width).
  - In `ui/settings_panel.py`, implemented `_get_active_ratio_factors()` and dynamically updated width/height spinboxes without triggering recursive signal loops.
  - Added live GCD ratio label with orientation indicator (`Computed: 5:8 (portrait)`).
- **Retest:** Automated unit tests `test_portrait_ratios` and `test_landscape_ratios` pass. Physical `wm size 720 1280` and `wm size reset` tested and verified on the iKall N15 tablet.

---

### Bug E: Update Manager 404 & UI State
- **Symptom:** When no GitHub releases were published on the new repository, the update dialog displayed generic network error messages and left the "Update Now" button active or confusing.
- **Root Cause:** HTTP 404 from GitHub's Releases API was caught as an unspecified `UpdateNetworkError`.
- **Fix:**
  - Added `NoReleasesPublishedError` in `update_manager.py`.
  - Updated `ui/update_dialog.py` to display "No published releases yet" with a friendly explanation, hide the `Update Now` button, and provide a `↻ Retry` button.
- **Retest:** Verified update dialog with mock responses, offline network conditions, and GitHub API responses.

---

### Bug F: Real-Time Application Package Search
- **Symptom:** With 199 installed applications on the test device, locating target test apps in a standard dropdown was cumbersome.
- **Root Cause:** Lack of search/filtering in the package selection UI.
- **Fix:**
  - Added real-time search input (`QLineEdit`) above the application combo box.
  - Filters across package names (e.g. `com.whatsapp`) and friendly application labels in real time.
- **Retest:** Verified search filtering with 199 loaded packages on iKall N15.

---

## 3. Physical Hardware Test Matrix (iKall N15)

| Test Item | Command / Procedure | Expected Result | Actual Result | Status |
|---|---|---|---|---|
| ADB Detection | `adb devices -l` | Device found with serial `0123456789ABCDEF` | `0123456789ABCDEF device ... model:B610A115` | PASS |
| Device Specs | `adb getprop` queries | Model: B610A115, Android 11, 4GB RAM | Correctly fetched and displayed in UI | PASS |
| Physical Resolution | `wm size` | `Physical size: 800x1280` | `(800, 1280)` correctly parsed | PASS |
| Resolution Override | `wm size 720x1280` | Device resolution changes to 720x1280 | Applied immediately, UI scales properly | PASS |
| Resolution Reset | `wm size reset` | Override cleared, returns to 800x1280 | Cleared to `None`, physical restored | PASS |
| Clean Exit Restoration | Signal `SIGINT` / App Exit | Any active override restored to native | `restore_all()` executed cleanly | PASS |
| Package Enumeration | `pm list packages -3` / `-s` | List all 199 installed packages | 13 user apps + 186 system apps loaded | PASS |
| Live Log Streaming | `logcat -v threadtime` | Continuous log parsing without freezing UI | 5,801 log entries parsed smoothly | PASS |
| Log Export | CSV / JSON export | Output file created with timestamped logs | Exported valid JSON and CSV reports | PASS |

---

## 4. Known Platform Behaviors & Notes
1. **Wayland Display Protocol:** When running on modern Wayland desktop sessions, scrcpy embedded window reparenting requires XWayland. SUSCRCPY automatically sets `QT_QPA_PLATFORM=xcb` to guarantee window embedding stability.
2. **Mediatek Vendor Daemons:** On certain low-cost MTK devices (like iKall N15), vendor daemons (`MtkOmxVenc`, `RmcNwHdlr`) log benign internal states with level `E`. While SUSCRCPY preserves these genuine `E` level entries from the OS buffer, it avoids triggering false crash alerts.
