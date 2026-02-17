#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnostic tool for I/O Health Monitor

This script performs a one-time health check and displays results.
Useful for testing and validation without running the full bot.
"""

import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from io_health_monitor import IOHealthMonitor
from reboot_semaphore import RebootSemaphore

def print_header(text):
    """Print section header"""
    print()
    print("=" * 70)
    print(f"  {text}")
    print("=" * 70)

def print_status(label, success, message=""):
    """Print status line with emoji"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}  {label}")
    if message:
        print(f"       {message}")

def main():
    """Main diagnostic function"""
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║         I/O HEALTH MONITOR - DIAGNOSTIC TOOL                     ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    
    # Configuration
    db_path = "traffic_history.db"
    test_file_path = "/dev/shm/meshbot_io_test"
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"\n⚠️  WARNING: Database not found: {db_path}")
        print("   Using temporary database for testing")
        import tempfile
        import sqlite3
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        os.close(db_fd)
    
    # Initialize monitor
    print_header("INITIALIZATION")
    print(f"Database path:     {db_path}")
    print(f"Test file path:    {test_file_path}")
    print(f"Failure threshold: 3")
    print(f"Cooldown period:   900s (15 minutes)")
    
    try:
        monitor = IOHealthMonitor(
            db_path=db_path,
            test_file_path=test_file_path,
            failure_threshold=3,
            cooldown_seconds=0,  # Disable cooldown for testing
            enabled=True
        )
        print_status("Monitor initialized", True)
    except Exception as e:
        print_status("Monitor initialization", False, str(e))
        return 1
    
    # Test 1: Filesystem Write
    print_header("TEST 1: FILESYSTEM WRITE")
    try:
        success, error = monitor.verify_filesystem_writable()
        print_status("Filesystem write test", success, error if not success else "Write/read successful")
    except Exception as e:
        print_status("Filesystem write test", False, f"Exception: {e}")
    
    # Test 2: Database Integrity
    print_header("TEST 2: DATABASE INTEGRITY")
    try:
        success, error = monitor.verify_db_integrity()
        print_status("Database integrity check", success, error if not success else "PRAGMA quick_check = ok")
    except Exception as e:
        print_status("Database integrity check", False, f"Exception: {e}")
    
    # Test 3: Database Writable
    print_header("TEST 3: DATABASE WRITABLE")
    try:
        success, error = monitor.verify_db_writable()
        print_status("Database writable check", success, error if not success else "Database is accessible")
    except Exception as e:
        print_status("Database writable check", False, f"Exception: {e}")
    
    # Test 4: Complete Health Check
    print_header("TEST 4: COMPLETE HEALTH CHECK")
    try:
        healthy, status = monitor.perform_health_check()
        print_status("Complete health check", healthy, status)
        
        # Show statistics
        stats = monitor.get_statistics()
        print()
        print("Statistics:")
        print(f"  Total checks:         {stats['total_checks']}")
        print(f"  Total failures:       {stats['total_failures']}")
        print(f"  Consecutive failures: {stats['consecutive_failures']}/{stats['failure_threshold']}")
        
    except Exception as e:
        print_status("Complete health check", False, f"Exception: {e}")
    
    # Test 5: Reboot Trigger Logic
    print_header("TEST 5: REBOOT TRIGGER LOGIC")
    try:
        should_reboot, reason = monitor.should_trigger_reboot()
        print_status("Reboot threshold check", not should_reboot, 
                    "Threshold not reached (expected)" if not should_reboot else f"REBOOT WOULD TRIGGER: {reason}")
    except Exception as e:
        print_status("Reboot trigger logic", False, f"Exception: {e}")
    
    # Test 6: Reboot Semaphore Status
    print_header("TEST 6: REBOOT SEMAPHORE STATUS")
    try:
        reboot_pending = RebootSemaphore.check_reboot_signal()
        print_status("Reboot signal check", not reboot_pending,
                    "No reboot pending (expected)" if not reboot_pending else "⚠️  REBOOT IS PENDING!")
        
        if reboot_pending:
            info = RebootSemaphore.get_reboot_info()
            if info:
                print()
                print("Reboot Information:")
                for line in info.split('\n'):
                    if line.strip():
                        print(f"  {line}")
    except Exception as e:
        print_status("Reboot semaphore check", False, f"Exception: {e}")
    
    # Test 7: SysRq Availability
    print_header("TEST 7: SYSRQ AVAILABILITY")
    sysrq_enabled = False
    sysrq_value = -1
    
    try:
        if os.path.exists('/proc/sys/kernel/sysrq'):
            with open('/proc/sys/kernel/sysrq', 'r') as f:
                sysrq_value = int(f.read().strip())
            sysrq_enabled = sysrq_value > 0
            print_status("SysRq available", sysrq_enabled,
                        f"SysRq value: {sysrq_value} {'(enabled)' if sysrq_enabled else '(disabled)'}")
            
            if not sysrq_enabled:
                print()
                print("⚠️  SysRq is disabled. To enable:")
                print("   echo 1 | sudo tee /proc/sys/kernel/sysrq")
        else:
            print_status("SysRq available", False, "/proc/sys/kernel/sysrq not found")
    except Exception as e:
        print_status("SysRq check", False, f"Exception: {e}")
    
    # Test 8: Watcher Status
    print_header("TEST 8: REBOOTPI-WATCHER STATUS")
    try:
        import subprocess
        result = subprocess.run(
            ['systemctl', 'is-active', 'rebootpi-watcher'],
            capture_output=True,
            text=True,
            timeout=5
        )
        watcher_active = result.returncode == 0
        print_status("Watcher service running", watcher_active,
                    "Service is active" if watcher_active else "Service not running or not installed")
        
        if not watcher_active:
            print()
            print("ℹ️  To check watcher status:")
            print("   sudo systemctl status rebootpi-watcher")
    except FileNotFoundError:
        print_status("Watcher service check", False, "systemctl not found")
    except Exception as e:
        print_status("Watcher service check", False, f"Exception: {e}")
    
    # Summary
    print_header("SUMMARY")
    print()
    print("Status Report:")
    print(monitor.get_status_report(compact=False))
    print()
    
    # Recommendations
    print_header("RECOMMENDATIONS")
    all_checks_passed = monitor.consecutive_failures == 0
    
    if all_checks_passed and sysrq_enabled:
        print("✅ All systems operational!")
        print("   - I/O health monitoring is functional")
        print("   - SysRq is enabled for emergency reboots")
        print("   - Ready for production use")
    else:
        print("⚠️  Some issues detected:")
        if not all_checks_passed:
            print("   - I/O health checks have failures")
            print("     → Check filesystem and database status")
        if not sysrq_enabled:
            print("   - SysRq is disabled")
            print("     → Enable with: echo 1 | sudo tee /proc/sys/kernel/sysrq")
    
    print()
    print("For detailed testing guide, see: IO_HEALTH_TESTING.md")
    print()
    
    return 0 if all_checks_passed else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
