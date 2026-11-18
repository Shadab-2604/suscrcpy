# SUSCRCPY — Universal Screen Ratio Fitting & Left Panel Rendering Report

**Execution Date:** November 18, 2026  
**Target Environment:** Kali Linux, PySide6, scrcpy 4.1  
**Connected Android Device:** 0123456789ABCDEF (Model B610A115, Android 11, Native 800x1280)  
**Parent Container Constraints:** Left Panel 50% split (680 px width × 768 px height)  
**Final Verification Status:** **100% PASS**  

---

## 1. Architectural Principles Verified

1. **Fixed Left Panel Container (Contain Behavior):**
   - The application window, 50/50 splitter, and right workstation panels remained completely stationary during all ratio changes.
   - The Android screen scaled strictly inside the left panel using `scale = min(CW / SW, CH / SH)`.
   - Center offsets `x = (CW - rendered_w) // 2` and `y = (CH - rendered_h) // 2` introduce clean letterboxing or pillarboxing on `#0A0A0A` black canvas.

2. **Tri-Point Telemetry:**
   - Android logical dimensions (`wm size`), scrcpy stream dimensions, and preview geometry are tracked and displayed independently in the Sync HUD.

3. **Input Interaction Integrity:**
   - Native X11 window container bounds match the fitted geometry, allowing 1:1 touch, click, gesture, and keyboard event routing with zero coordinate offset.

---

## 2. Standardized Aspect Ratios Test Matrix

| Aspect Ratio Preset | Portrait Fit | Landscape Fit | Full Visibility (FIT) | Mouse & Key Interaction | Device ADB Apply & Reset |
|---|---|---|---|---|---|
| **1:1** | PASS (680x680) | PASS (680x680) | PASS | PASS | PASS |
| **3:2** | PASS (512x768) | PASS (680x453) | PASS | PASS | PASS |
| **4:3** | PASS (576x768) | PASS (680x510) | PASS | PASS | PASS |
| **5:4** | PASS (614x768) | PASS (680x544) | PASS | PASS | PASS |
| **9:16** | PASS (432x768) | PASS (680x382) | PASS | PASS | PASS |
| **9:18** | PASS (384x768) | PASS (680x340) | PASS | PASS | PASS |
| **9:19.5** | PASS (354x768) | PASS (680x314) | PASS | PASS | PASS |
| **9:20** | PASS (346x768) | PASS (680x306) | PASS | PASS | PASS |
| **9:21** | PASS (329x768) | PASS (680x291) | PASS | PASS | PASS |
| **16:9** | PASS (432x768) | PASS (680x382) | PASS | PASS | PASS |
| **16:10** | PASS (480x768) | PASS (680x425) | PASS | PASS | PASS |
| **18:9** | PASS (384x768) | PASS (680x340) | PASS | PASS | PASS |
| **19:9** | PASS (364x768) | PASS (680x322) | PASS | PASS | PASS |
| **20:9** | PASS (346x768) | PASS (680x306) | PASS | PASS | PASS |
| **21:9** | PASS (329x768) | PASS (680x291) | PASS | PASS | PASS |
| **32:9** | PASS (216x768) | PASS (680x191) | PASS | PASS | PASS |
| **Custom** | PASS (512x768) | PASS (680x453) | PASS | PASS | PASS |

---

## 3. Named Screen Profiles & Categories Test Matrix

| Profile Name | Category | Source Resolution | Rendered Preview (680×768 Pane) | Offsets (x, y) | FIT Visibility Status |
|---|---|---|---|---|---|
| **iPhone 11** | Smartphones | 828x1792 | 355x768 | x=162, y=0 | **PASS** |
| **iPhone 13** | Smartphones | 1170x2532 | 355x768 | x=162, y=0 | **PASS** |
| **Galaxy Z Fold (Unfolded)** | Foldables | 1812x2176 | 640x768 | x=20, y=0 | **PASS** |
| **Galaxy Z Flip (Cover)** | Foldables | 720x748 | 680x706 | x=0, y=31 | **PASS** |
| **iPad Pro 11** | Tablets | 1668x2388 | 536x768 | x=72, y=0 | **PASS** |
| **Galaxy Tab S8** | Tablets | 1600x2560 | 480x768 | x=100, y=0 | **PASS** |
| **Apple Watch 45mm** | Wearables | 396x484 | 628x768 | x=26, y=0 | **PASS** |
| **Galaxy Watch 4 (Round)** | Wearables | 450x450 | 680x680 | x=0, y=44 | **PASS** |
| **Standard Laptop (FHD)** | Laptops | 1920x1080 | 680x382 | x=0, y=193 | **PASS** |
| **Ultrawide Monitor (21:9)** | Desktop monitors | 3440x1440 | 680x285 | x=0, y=241 | **PASS** |
| **Super Ultrawide (32:9)** | Desktop monitors | 5120x1440 | 680x191 | x=0, y=288 | **PASS** |
| **XR Headset (Quest 2)** | XR Devices | 1832x1920 | 680x713 | x=0, y=27 | **PASS** |

---

## 4. Viewing Modes Verification

- **FIT Mode (Default):** Complete screen visible, aspect ratio strictly maintained, letterbox/pillarbox active, zero cropping.
- **FILL Mode:** Scaled to occupy complete available left panel (`scale = max(CW/SW, CH/SH)`), parent canvas clips overflow, `[FILL — ✂ Crop Active]` warning displayed.
- **ORIGINAL SIZE (1:1):** Rendered at native pixel dimensions without scaling distortion.

---

## 5. Conclusion

Every supported aspect ratio preset, orientation, and named device profile successfully fits within the LEFT panel of SUSCRCPY with zero distortion, zero unintentional cropping, and full interaction responsiveness.
