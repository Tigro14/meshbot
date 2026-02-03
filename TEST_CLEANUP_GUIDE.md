# Test & Demo Files Cleanup Guide

## Current Situation

The repository contains:
- **221 test files** (test_*.py)
- **55 demo files** (demo_*.py)

Many of these are for specific bug fixes, diagnostics, or old features that have been superseded.

## Categorization

### Fix-Specific Tests (Candidates for Archive)

These tests were created to verify specific bug fixes and may not be needed long-term:

**CPU/Performance Fixes:**
- test_cpu_fix_explanation.py
- test_cpu_fix_simple.py
- test_cpu_usage_fix.py
- test_readbytes_cpu_fix.py
- test_readbytes_fix.py

**Connection/Network Fixes:**
- test_connection_logic_fix.py
- test_empty_route_fix.py
- test_nameerror_fix.py
- test_shutdown_fix.py
- test_serial_port_conflict_detection.py

**Broadcast/Echo Fixes:**
- test_broadcast_dedup_fix.py
- test_broadcast_logging_fix.py
- test_cli_echo_fix.py
- test_echo_tcp_fix.py

**Contact/Message Fixes:**
- test_contact_message_fix.py
- test_contacts_dirty_fix.py
- test_sender_id_fix.py

**Key/PKI Fixes:**
- test_keys_check.py
- test_keys_decimal_fix.py
- test_keys_multiformat.py
- test_keys_string_fix.py
- test_unchanged_key_sync.py

**MeshCore Fixes:**
- test_meshcore_contact_lookup_fix.py
- test_meshcore_dm_lambda_fix.py
- test_meshcore_integration_fix.py
- test_meshcore_pubkey_derive_fix.py

**TCP Fixes:**
- test_tcp_heartbeat_fix.py
- test_tcp_interface_fix.py
- test_tcp_reconnection_fix.py
- test_tcp_silent_timeout_fix.py

**Other Fixes:**
- test_gateway_longname_fix.py
- test_hop_broadcast_fix.py
- test_info_print_logging.py
- test_save_packet_fix.py
- test_system_monitor_fix.py
- test_trace_id_parsing_fix.py
- test_warning_logic.py

### Feature Tests (Keep for Now)

Tests for active features that should be maintained:

**MeshCore Features:**
- test_meshcore_companion.py
- test_meshcore_debug.py
- test_meshcore_decoder_integration.py
- test_meshcore_diagnostics.py
- test_meshcore_dm_decryption.py
- test_meshcore_nodeinfo_storage.py

**Network Features:**
- test_mqtt_neighbor_collector.py
- test_mqtt_nodeinfo_translation.py
- test_mqtt_via_info.py
- test_tcp_health_improvements.py
- test_tcp_keepalive.py

**Database Features:**
- test_db_auto_reboot.py
- test_db_mc_command.py
- test_db_nb_integration.py
- test_db_password.py
- test_db_neighbors_stats.py

**Node Management:**
- test_neighbors_distance_filter.py
- test_neighbors_integration.py
- test_node_metrics_export.py
- test_node_name_sanitization.py
- test_node_stats_retention.py

**Command Features:**
- test_propag_command.py
- test_ia_command.py
- test_info_command.py
- test_stats_consolidation.py
- test_fullnodes_search.py

### Core/Integration Tests (Keep)

Tests for core functionality:
- test_bot_lifecycle.py
- test_broadcast_integration.py
- test_dual_interface.py
- test_config_*.py
- test_auto_reboot.py

## Demo Files Analysis

### Fix-Specific Demos (Can Archive)
- demo_cli_echo_fix.py
- demo_contact_message_fix.py
- demo_contacts_dirty_fix.py
- demo_dm_key_lookup_fix.py
- demo_echo_tcp_fix.py
- demo_emoticon_fix.py
- demo_gateway_longname_fix.py
- demo_keys_fix.py
- demo_sender_id_fix.py
- demo_source_detection_fix.py
- demo_tcp_timeout_fix.py
- demo_trace_fix.py

### Diagnostic Demos (Can Archive)
- demo_improved_pki_diagnostics.py
- demo_meshcore_contact_sync_diagnostics.py
- demo_meshcore_diagnostics.py
- demo_traceroute_debug_improvement.py

### Feature Demos (Review/Keep)
- demo_db_neighbors.py
- demo_db_password.py
- demo_dm_decryption.py
- demo_hop_alias.py
- demo_hop_analysis.py
- demo_ia_command.py
- demo_info_with_hops.py
- demo_mesh_alerts.py
- demo_meshcore_decoder.py
- demo_propag_broadcast.py
- demo_stats_hop.py

## Recommended Actions

### Immediate Actions

1. **Archive Fix Tests** - Move ~50 fix-specific tests to `tests/archive/fix-tests/`
2. **Archive Fix Demos** - Move ~15 fix-specific demos to `demos/archive/`
3. **Document Remaining** - Create test documentation for active tests

### Future Actions

1. **Review Feature Tests** - Periodically review if feature tests are still needed
2. **Consolidate Tests** - Merge similar tests to reduce count
3. **Add Test Documentation** - Document purpose and scope of each test suite
4. **CI Integration** - Set up automated testing for core tests only

## Test Organization Strategy

### Proposed Structure

```
tests/
├── unit/                  # Unit tests for individual modules
├── integration/           # Integration tests for features
├── feature/              # Feature-specific test suites
│   ├── meshcore/
│   ├── mqtt/
│   ├── tcp/
│   └── database/
├── archive/              # Archived tests
│   └── fix-tests/        # Bug fix verification tests
└── README.md             # Test documentation
```

### Demo Organization Strategy

```
demos/
├── features/             # Active feature demonstrations
│   ├── commands/
│   ├── meshcore/
│   └── network/
├── archive/              # Archived demos
└── README.md             # Demo documentation
```

## Statistics

- **Total Tests:** 221 files
- **Fix-specific (archive candidates):** ~50 files (23%)
- **Feature tests (keep):** ~63 files (28%)
- **Core tests (keep):** ~108 files (49%)

- **Total Demos:** 55 files
- **Fix-specific (archive candidates):** ~15 files (27%)
- **Feature demos (review):** ~40 files (73%)

## Implementation

Due to the large number of files and the need for careful review, test/demo cleanup should be done incrementally:

1. **Phase 1:** Archive obvious fix-specific tests (completed tests for resolved bugs)
2. **Phase 2:** Review and consolidate feature tests
3. **Phase 3:** Organize remaining tests by category
4. **Phase 4:** Document test coverage and purposes

**Note:** This document serves as a guide. Actual archiving should be done carefully with verification that tests are truly obsolete before removal.
