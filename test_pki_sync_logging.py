#!/usr/bin/env python3
"""
Test PKI Sync Logging Reduction

Verifies that the PKI sync process logs less verbosely during reconnections,
reducing log spam while preserving important summary information.
"""

import sys
import io
from unittest.mock import Mock, MagicMock

# Mock the config before importing node_manager
sys.modules['config'] = MagicMock()

# Capture log output
captured_logs = []

def mock_info_print(msg):
    """Mock info_print to capture INFO logs"""
    captured_logs.append(('INFO', msg))
    print(f"[INFO] {msg}")

def mock_debug_print(msg):
    """Mock debug_print to capture DEBUG logs"""
    captured_logs.append(('DEBUG', msg))
    print(f"[DEBUG] {msg}")

def mock_error_print(msg):
    """Mock error_print to capture ERROR logs"""
    captured_logs.append(('ERROR', msg))
    print(f"[ERROR] {msg}")

# Patch utils functions
import utils
utils.info_print = mock_info_print
utils.debug_print = mock_debug_print
utils.error_print = mock_error_print

from node_manager import NodeManager

def test_pki_sync_logging_reduction():
    """
    Test that PKI sync logs at DEBUG level for per-key processing
    and INFO level only for summary
    """
    print("=" * 70)
    print("TEST: PKI Sync Logging Reduction")
    print("=" * 70)
    
    # Create a node manager
    nm = NodeManager()
    
    # Add some test nodes with public keys
    nm.node_names = {
        0x12345678: {
            'name': 'TestNode1',
            'shortName': 'TN1',
            'hwModel': 'T1000',
            'publicKey': b'test_key_1' * 4  # 40 bytes
        },
        0x87654321: {
            'name': 'TestNode2',
            'shortName': 'TN2',
            'hwModel': 'T2000',
            'publicKey': b'test_key_2' * 4  # 40 bytes
        },
        0xABCDEF00: {
            'name': 'TestNode3',
            'shortName': 'TN3',
            'hwModel': 'T3000',
            'publicKey': b'test_key_3' * 4  # 40 bytes
        }
    }
    
    # Create a mock interface with empty nodes
    mock_interface = Mock()
    mock_interface.nodes = {}
    
    # Clear captured logs
    captured_logs.clear()
    
    # Perform sync (forced, like during reconnection)
    print("\n--- Performing forced sync (like during TCP reconnection) ---")
    injected = nm.sync_pubkeys_to_interface(mock_interface, force=True)
    
    print(f"\nResult: {injected} keys synchronized")
    
    # Analyze logs
    info_logs = [log for level, log in captured_logs if level == 'INFO']
    debug_logs = [log for level, log in captured_logs if level == 'DEBUG']
    
    print(f"\n--- Log Analysis ---")
    print(f"Total INFO logs: {len(info_logs)}")
    print(f"Total DEBUG logs: {len(debug_logs)}")
    
    # Verify expectations
    print(f"\n--- Verification ---")
    
    # Check that we have summary INFO logs
    summary_logs = [log for log in info_logs if 'SYNC COMPLETE' in log or 'Starting public key' in log or 'interface.nodes count' in log or 'Keys to sync' in log]
    print(f"✓ Summary INFO logs found: {len(summary_logs)}")
    for log in summary_logs:
        print(f"  - {log}")
    
    # Check that per-key processing is at DEBUG level
    processing_logs = [log for log in debug_logs if 'Processing' in log or 'has key in DB' in log]
    print(f"\n✓ Per-key processing DEBUG logs: {len(processing_logs)}")
    print(f"  Expected: 3 (one per key)")
    
    # Check that injection status is at DEBUG level
    injection_logs = [log for log in debug_logs if 'Injected key' in log or 'Created node' in log]
    print(f"\n✓ Key injection DEBUG logs: {len(injection_logs)}")
    print(f"  Expected: 3 (one per key)")
    
    # Verify no excessive INFO logging for per-key operations
    per_key_info_logs = [log for log in info_logs if ('Processing' in log and 'has key in DB' in log) or 'Injected key' in log or 'Created node' in log]
    print(f"\n✓ Per-key INFO logs (should be 0): {len(per_key_info_logs)}")
    
    # Test results
    success = True
    if len(summary_logs) < 3:
        print("❌ FAIL: Missing summary INFO logs")
        success = False
    
    if len(processing_logs) != 3:
        print(f"❌ FAIL: Expected 3 processing DEBUG logs, got {len(processing_logs)}")
        success = False
    
    if len(per_key_info_logs) > 0:
        print(f"❌ FAIL: Found {len(per_key_info_logs)} per-key INFO logs (should be 0)")
        success = False
    
    if success:
        print("\n" + "=" * 70)
        print("✅ TEST PASSED: PKI sync logging reduced successfully")
        print("=" * 70)
        print("\nBenefits:")
        print("  - Per-key processing moved to DEBUG level")
        print("  - Summary information kept at INFO level")
        print("  - Significant reduction in log spam during TCP reconnections")
        print("  - DEBUG mode still provides detailed information when needed")
    else:
        print("\n" + "=" * 70)
        print("❌ TEST FAILED")
        print("=" * 70)
    
    return success

if __name__ == '__main__':
    success = test_pki_sync_logging_reduction()
    sys.exit(0 if success else 1)
