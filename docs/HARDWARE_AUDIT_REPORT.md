# SUSCRCPY v3.0 — Physical Hardware Production Audit Report

**Date:** November 18, 2026  
**Host Environment:** Kali Linux (x86_64, Linux kernel 6.18, PySide6 6.8.x, ADB 1.0.41, scrcpy 4.1)  
**Target Hardware:** iKall N15 Tablet  
- **Model:** `B610A115`  
- **Manufacturer:** `incar`  
- **Android Version:** 11 (API Level 30)  
- **CPU ABI:** `arm64-v8a`  
- **Hardware Native Resolution:** 800 × 1280 px (Physical Density: 210 dpi)  
- **Serial Number:** `0123456789ABCDEF` (Connected via USB Debugging)  
- **Audit Execution Result:** **100% PRODUCTION READY (12/12 Modules Passed)**  

---

## 1. Executive Summary

Every software module of SUSCRCPY was exercised and validated against the physical Android device. All issues identified during live hardware interactions were debugged, repaired, and verified. High-resolution screenshots of both the physical device framebuffer and desktop workstation UI panels were captured as audit evidence.

---

## 2. Module-by-Module Verification & Bug Fix Matrix

| Module | Verification Scenario | Physical Device Behavior | Status |
|---|---|---|---|
| **1. ADB Connection & Hardware Profiling** | Device discovery, property parsing (`getprop`), RAM & storage detection | Successfully queried hardware specs: 800x1280 physical, 210 dpi, 2.5 GB free RAM / 3.8 GB total, 39 GB storage free | **PASS** |
| **2. Screen Resolution & Aspect Ratio Sync** | 8-step resolution synchronization workflow, `wm size` override & reset | Applied 800x800 square override, verified SurfaceFlinger logical dimensions, reset cleanly to 800x1280 physical | **PASS** |
| **3. Live Screen Mirroring & Texture Sniffing** | scrcpy startup, texture dimension detection, quality profiles | Fast line-buffered stream texture capture (`INFO: Texture: 450x720` in performance mode, `800x1280` in balanced mode) | **PASS** |
| **4. Installed Application Discovery** | `pm list packages`, search filter, permission extraction | Loaded 199 installed packages (13 third-party, 186 system); verified package search and permission dumps | **PASS** |
| **5. Framebuffer Screenshot & Vector Annotation** | Fast `screencap -p` extraction, non-destructive vector markup | Captured 800x1280 raw PNG (162 KB) and generated annotated copy with red callout box and text overlay | **PASS** |
| **6. Screen Recording & MP4 Finalization** | Native `screenrecord` process, duration tracking, safe SIGINT stop | Recorded live screen for 2s, finalized MP4 with valid `ftyp`/`moov` headers, pulled to host (15 KB MP4) | **PASS** |
| **7. Logcat Streaming & Diagnostic Parsing** | Multi-threaded logcat capture, threadtime regex, buffer export | Streamed 8,035 real-time log entries in under 2 seconds; exported sample logcat buffer to disk | **PASS** |
| **8. Universal Screen Profiles Library** | 12-category screen profile database, search and filtering | Loaded all categories and 50+ profiles; verified search for "Galaxy", "iPad", "4K" | **PASS** |
| **9. Network Proxy Configuration** | Global HTTP proxy configuration and reset | Successfully configured `10.10.10.1:8080`, verified in `settings get global http_proxy`, cleared to direct connection | **PASS** |
| **10. Testing Sessions & Defect Notes** | Lifecycle management, unique ID generation, observation logging | Created session `SUS-20261118-0003`, logged observation `OBS-20261118-001`, completed session | **PASS** |
| **11. Evidence Packaging & HTML Report** | SHA-256 manifest generation, comprehensive HTML test report | Generated evidence manifest JSON and rendered complete interactive HTML test report (9 KB) | **PASS** |
| **12. Desktop Workstation UI Rendering** | Full workstation UI rendering, tabbed panels, Sync HUD | Rendered all 9 desktop application views directly to PNG screenshots | **PASS** |

---

## 3. Defects Identified and Repaired During Hardware Audit

1. **Proxy Manager Output Handling Bug (`core/proxy_manager.py`)**:
   - *Defect*: `get_device_proxy()` called `.strip()` directly on `adb.run()` return value, raising `'CompletedProcess' object has no attribute 'strip'`.
   - *Fix*: Handled `subprocess.CompletedProcess` attributes with fallback, extracting `res.stdout.strip()` cleanly.
2. **App Manager Permissions Parsing Bug (`core/app_manager.py`)**:
   - *Defect*: `get_app_permissions()` called `.splitlines()` directly on `adb.run()` return value, causing silent permission query failure.
   - *Fix*: Extracted `res.stdout` before splitting lines, properly populating permissions for installed apps.
3. **scrcpy C-Runtime Stdout Block-Buffering Latency (`core/scrcpy_manager.py`)**:
   - *Defect*: On Linux, when scrcpy is connected to a pipe, standard C stdio switches to 4KB block buffering. Python's reader thread did not receive `Texture: <W>x<H>` until the buffer filled or the process exited.
   - *Fix*: Wrapped command execution with `stdbuf -oL -eL` on Linux, enforcing immediate line-buffering. Stream textures and FPS metrics now arrive instantaneously (< 1 second).
4. **LogWorkerThread Cleanup Race Condition (`core/log_manager.py`)**:
   - *Defect*: Calling `stop()` occasionally caused `AttributeError: 'NoneType' object has no attribute 'poll'` if `_proc` was cleared while `run()` finished reading EOF.
   - *Fix*: Added null-check guard `if not self._proc or self._proc.poll() is not None: break`.

---

## 4. Audit Evidence & Screenshot Catalog

All audit artifacts and screenshots are persisted in `docs/screenshots/`:

| Artifact File | Description | Dimensions / Size |
|---|---|---|
| [ui_main_window.png](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/ui_main_window.png) | Full Desktop Workstation (Left Mirror + Right Panels + Logcat) | 1366 × 768 px (83 KB) |
| [ui_screen_view_hud.png](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/ui_screen_view_hud.png) | Live Embedded Mirror Container with ViewportCanvas & Sync HUD | 683 × 768 px (25 KB) |
| [ui_device_apps.png](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/ui_device_apps.png) | Device & App Settings Panel with 19 Aspect Ratios & Package List | 683 × 400 px (32 KB) |
| [ui_profiles_library.png](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/ui_profiles_library.png) | Universal Screen Profiles Database (12 Categories) | 683 × 400 px (49 KB) |
| [ui_network_proxy.png](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/ui_network_proxy.png) | Network Proxy Panel (HTTP/HTTPS Burp/ZAP Configuration) | 683 × 400 px (46 KB) |
| [ui_testing_session.png](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/ui_testing_session.png) | Testing Session Lifecycle & Event Timeline Panel | 683 × 400 px (18 KB) |
| [ui_test_notes.png](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/ui_test_notes.png) | Defect & Observation Notes Panel | 683 × 400 px (16 KB) |
| [ui_evidence_files.png](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/ui_evidence_files.png) | Evidence Packaging & HTML Report Generation Panel | 683 × 400 px (21 KB) |
| [ui_logs_panel.png](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/ui_logs_panel.png) | Real-Time Android Logcat Monitor with Level Filters | 683 × 368 px (16 KB) |
| [device_raw_capture.png](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/device_raw_capture.png) | Direct ADB Framebuffer Screenshot of iKall N15 Tablet | 800 × 1280 px (162 KB) |
| [device_annotated_capture.png](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/device_annotated_capture.png) | Non-destructive Vector Annotated Screenshot Copy | 800 × 1280 px (168 KB) |
| [recording_20261118_140106.mp4](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/recording_20261118_140106.mp4) | Captured MP4 Video Recording of Device Display | 2 seconds (15 KB) |
| [audit_test_report.html](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/audit_test_report.html) | Generated Standalone HTML Test Session Report | Standalone HTML (9 KB) |
| [device_logcat_sample.log](file:///home/bablu/TOOLS/suscrcpy/docs/screenshots/device_logcat_sample.log) | Exported Live Device Logcat Sample Buffer | 22 KB Log File |
