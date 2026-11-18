# SUSCRCPY v2.1.0 — Test Execution Results

**Date:** November 18, 2026  
**Environment:** Python 3.14.8, PySide6 6.8.x, ADB 1.0.41, scrcpy 3.1, Kali Linux x86_64  
**Hardware Tested:** iKall N15 Tablet (Android 11 / API 30, Serial: `0123456789ABCDEF`)

---

## 1. Automated Test Suite Summary

Total Tests Executed: **44**  
Tests Passed: **44**  
Failures: **0**  
Errors: **0**  
Execution Time: **0.311s**  
Overall Test Result: **100% PASS**

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
test_landscape_ratios (test_ratios.TestRatioCalculations.test_landscape_ratios) ... ok
test_pixel_bounds_validation (test_ratios.TestRatioCalculations.test_pixel_bounds_validation) ... ok
test_portrait_ratios (test_ratios.TestRatioCalculations.test_portrait_ratios) ... ok
test_resolution_restoration_lifecycle (test_ratios.TestRatioCalculations.test_resolution_restoration_lifecycle) ... ok
test_parse_release_json_newer_available (test_updates.TestUpdateManager.test_parse_release_json_newer_available) ... ok
test_parse_release_json_no_update_available (test_updates.TestUpdateManager.test_parse_release_json_no_update_available) ... ok
test_rollback_on_failed_verification (test_updates.TestUpdateManager.test_rollback_on_failed_verification) ... ok
test_update_aborts_on_checksum_mismatch (test_updates.TestUpdateManager.test_update_aborts_on_checksum_mismatch) ... ok
test_app_version_is_valid_semver (test_versions.TestVersionManagement.test_app_version_is_valid_semver) ... ok
test_final_versus_prerelease_comparison (test_versions.TestVersionManagement.test_final_versus_prerelease_comparison) ... ok
test_parse_semver_basic (test_versions.TestVersionManagement.test_parse_semver_basic) ... ok
test_parse_semver_prerelease (test_versions.TestVersionManagement.test_parse_semver_prerelease) ... ok
test_version_comparisons (test_versions.TestVersionManagement.test_version_comparisons) ... ok

----------------------------------------------------------------------
Ran 44 tests in 0.311s

OK
```

---

## 2. Module Test Breakdown

### ADB Manager (`tests/test_adb.py`)
- Device list parsing from standard and multi-device `adb devices -l` output.
- Physical resolution and override resolution parsing.
- Device serial targeting ensuring multi-device safety (`-s <serial>` argument injection).

### Screen Manager (`tests/test_ratios.py`)
- Portrait aspect ratio calculation without height shrinking.
- Landscape aspect ratio calculations.
- Safe pixel bounds validation (`[100, 10000]`).
- Restoration lifecycle ensuring all modified devices are reverted to physical size upon exit.

### Error Detector & Logcat Streamer (`tests/test_logs.py`)
- Strict Android log priority enforcement (`V, D, I, W, E, F`).
- Prevention of false positives on informational cache misses and try-catch messages.
- True crash grouping and stack trace aggregation.
- Log exporting in JSON and CSV formats.

### Profile Manager (`tests/test_profiles.py`)
- Database loading across all 12 hardware categories.
- Search and filtering across form factors and DPI classes.
- Custom profile creation, editing, and deletion lifecycle.

### Update Manager & Packaging (`tests/test_updates.py`, `tests/test_checksums.py`, `tests/test_versions.py`)
- SemVer comparison handling final and pre-release releases.
- SHA-256 checksum verification before extract.
- Zip-slip archive traversal attack protection.
- Rollback mechanisms if self-test fails after update.
