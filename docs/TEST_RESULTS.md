# SUSCRCPY v3.0 — Complete Test Results & Hardware Execution Report

**Date:** November 18, 2026  
**Environment:** Kali Linux (x86_64), Python 3.14.8, PySide6 6.8.x, ADB 1.0.41, scrcpy 3.1  
**Target Hardware:** iKall N15 Tablet (Model B610A115, Android 11 / API 30, Serial: `0123456789ABCDEF`)

---

## 1. Automated Test Suite Summary

Total Automated Tests: **56**  
Tests Passed: **56**  
Failures: **0**  
Errors: **0**  
Execution Duration: **1.389s**  
Pass Rate: **100% PASS**

```
test_parse_devices_output (test_adb.TestAdbManager.test_parse_devices_output) ... ok
test_parse_display_size (test_adb.TestAdbManager.test_parse_display_size) ... ok
test_parse_native_display_size_without_override (test_adb.TestAdbManager.test_parse_native_display_size_without_override) ... ok
test_serial_targeting (test_adb.TestAdbManager.test_serial_targeting) ... ok
test_enrich_details (test_apps.TestAppManager.test_enrich_details) ... ok
test_filter_apps_by_search_and_category (test_apps.TestAppManager.test_filter_apps_by_search_and_category) ... ok
test_load_and_categorize_apps (test_apps.TestAppManager.test_load_and_categorize_apps) ... ok
test_calculate_sha256 (test_checksums.TestChecksumsAndArchiveSecurity.test_calculate_sha256) ... ok
test_parse_checksums_file (test_checksums.TestChecksumsAndArchiveSecurity.test_parse_checksums_file) ... ok
test_valid_zip_archive_passes (test_checksums.TestChecksumsAndArchiveSecurity.test_valid_zip_archive_passes) ... ok
test_zip_slip_absolute_path_rejected (test_checksums.TestChecksumsAndArchiveSecurity.test_zip_slip_absolute_path_rejected) ... ok
test_zip_slip_parent_traversal_rejected (test_checksums.TestChecksumsAndArchiveSecurity.test_zip_slip_parent_traversal_rejected) ... ok
test_help_flag_output (test_cli.TestCommandLineInterface.test_help_flag_output) ... ok
test_parse_args_check_updates (test_cli.TestCommandLineInterface.test_parse_args_check_updates) ... ok
test_parse_args_options (test_cli.TestCommandLineInterface.test_parse_args_options) ... ok
test_parse_args_update (test_cli.TestCommandLineInterface.test_parse_args_update) ... ok
test_version_flag_output (test_cli.TestCommandLineInterface.test_version_flag_output) ... ok
test_directory_hierarchy_initialization (test_evidence.TestEvidenceManager.test_directory_hierarchy_initialization) ... ok
test_manifest_generation_and_checksums (test_evidence.TestEvidenceManager.test_manifest_generation_and_checksums) ... ok
test_crash_pattern_and_stack_trace_grouping (test_logs.TestLogs.test_crash_pattern_and_stack_trace_grouping) ... ok
test_error_severity_detection (test_logs.TestLogs.test_error_severity_detection) ... ok
test_log_export (test_logs.TestLogs.test_log_export) ... ok
test_no_false_positives_on_info_messages (test_logs.TestLogs.test_no_false_positives_on_info_messages) ... ok
test_threadtime_regex_parsing (test_logs.TestLogs.test_threadtime_regex_parsing) ... ok
test_custom_profile_lifecycle (test_profiles.TestProfileManager.test_custom_profile_lifecycle) ... ok
test_database_loads_all_categories (test_profiles.TestProfileManager.test_database_loads_all_categories) ... ok
test_search_and_filter (test_profiles.TestProfileManager.test_search_and_filter) ... ok
test_all_12_categories_exist (test_profiles.TestProfileModel.test_all_12_categories_exist) ... ok
test_foldable_properties (test_profiles.TestProfileModel.test_foldable_properties) ... ok
test_gcd_aspect_ratio_calculation (test_profiles.TestProfileModel.test_gcd_aspect_ratio_calculation) ... ok
test_invalid_profile_rejection (test_profiles.TestProfileModel.test_invalid_profile_rejection) ... ok
test_window_size_classes (test_profiles.TestProfileModel.test_window_size_classes) ... ok
test_xr_properties (test_profiles.TestProfileModel.test_xr_properties) ... ok
test_clear_device_proxy (test_proxy.TestProxyManager.test_clear_device_proxy) ... ok
test_get_device_proxy_configured (test_proxy.TestProxyManager.test_get_device_proxy_configured) ... ok
test_get_device_proxy_disabled (test_proxy.TestProxyManager.test_get_device_proxy_disabled) ... ok
test_set_device_proxy (test_proxy.TestProxyManager.test_set_device_proxy) ... ok
test_landscape_ratios (test_ratios.TestRatioCalculations.test_landscape_ratios) ... ok
test_pixel_bounds_validation (test_ratios.TestRatioCalculations.test_pixel_bounds_validation) ... ok
test_portrait_ratios (test_ratios.TestRatioCalculations.test_portrait_ratios) ... ok
test_resolution_restoration_lifecycle (test_ratios.TestRatioCalculations.test_resolution_restoration_lifecycle) ... ok
test_recording_lifecycle (test_recording.TestRecordingManager.test_recording_lifecycle) ... ok
test_generate_html_report_content (test_reports.TestReportGenerator.test_generate_html_report_content) ... ok
test_non_destructive_annotation (test_screenshots.TestScreenshotManager.test_non_destructive_annotation) ... ok
test_generate_session_id_format (test_sessions.TestSessionManager.test_generate_session_id_format) ... ok
test_interrupted_session_detection_and_recovery (test_sessions.TestSessionManager.test_interrupted_session_detection_and_recovery) ... ok
test_session_lifecycle_and_persistence (test_sessions.TestSessionManager.test_session_lifecycle_and_persistence) ... ok
test_parse_release_json_newer_available (test_updates.TestUpdateManager.test_parse_release_json_newer_available) ... ok
test_parse_release_json_no_update_available (test_updates.TestUpdateManager.test_parse_release_json_no_update_available) ... ok
test_rollback_on_failed_verification (test_updates.TestUpdateManager.test_rollback_on_failed_verification) ... ok
test_update_aborts_on_checksum_mismatch (test_updates.TestUpdateManager.test_update_aborts_on_checksum_mismatch) ... ok
test_app_version_is_valid_semver (test_versions.TestVersionManagement.test_app_version_is_valid_semver) ... ok
test_final_versus_prerelease_comparison (test_versions.TestVersionManagement.test_final_versus_prerelease_comparison) ... ok
test_parse_semver_basic (test_versions.TestVersionManagement.test_parse_semver_basic) ... ok
test_parse_semver_prerelease (test_versions.TestVersionManagement.test_parse_semver_prerelease) ... ok
test_version_comparisons (test_versions.TestVersionManagement.test_version_comparisons) ... ok

Ran 56 tests in 1.389s
OK
```

---

## 2. Real Physical Device End-to-End Workflow Execution

Executed on connected hardware **iKall N15** (`0123456789ABCDEF`):

```
=== STARTING SUSCRCPY 3.0 E2E HARDWARE INTEGRATION TEST ===
[1/10] Target hardware detected: 0123456789ABCDEF (B610A115)
[2/10] Testing session initiated: SUS-20261118-0002 in /home/bablu/SUSCRCPY-Evidence/HardwareE2E/SUS-20261118-0002
[3/10] Device screenshot captured: screenshot_20261118_125553.png (1280x1280)
[4/10] Annotated copy generated: screenshot_20261118_125553_annotated.png
[5/10] Starting device screen recording for 3 seconds...
[6/10] Recording finalized: recording_20261118_125554.mp4 (3s, 12546 bytes)
[7/10] Streaming device logs to session file...
[8/10] Session log created: full_device.log (119 bytes)
[9/10] Logged test observation: OBS-20261118-001 - Automated Test Observation
[10/10] Cryptographic Manifest generated (5 evidence files)
=== E2E SUCCESS: HTML Report generated at /home/bablu/SUSCRCPY-Evidence/HardwareE2E/SUS-20261118-0002/reports/session_report.html (11530 bytes) ===
```

### Verified Evidence Assets (`SUS-20261118-0002`):
- `session.json`: Session metadata, device parameters, target app, and status `Completed`.
- `recordings/recording_20261118_125554.mp4`: Valid MP4 container (12,546 bytes, SHA-256 verified).
- `screenshots/screenshot_20261118_125553.png`: Native device framebuffer capture (281,744 bytes).
- `screenshots/screenshot_20261118_125553_annotated.png`: Non-destructive vector overlay (286,224 bytes).
- `logs/full_device.log`: Incremental session disk log.
- `exports/evidence_manifest.json`: Tamper-evident SHA-256 digest manifest.
- `reports/session_report.html`: Self-contained standalone HTML report (11,530 bytes).
