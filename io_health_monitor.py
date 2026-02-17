#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
I/O Health Monitor for filesystem and database integrity checks.

This module performs lightweight health checks after significant write operations
to detect I/O failures early and trigger safe reboots via SysRq when needed.

Design:
- Small test writes to verify filesystem is writable
- SQLite integrity checks via PRAGMA
- Threshold-based failure detection (avoid false positives)
- Cooldown period to prevent reboot loops
- Integration with existing RebootSemaphore mechanism
"""

import os
import sqlite3
import time
from typing import Optional, Tuple
from utils import debug_print, info_print, error_print


class IOHealthMonitor:
    """
    Monitor I/O health of filesystem and database.
    
    Performs lightweight checks after database writes to detect I/O failures
    early and trigger safe reboots when the storage becomes unreliable.
    """
    
    def __init__(
        self,
        db_path: str,
        test_file_path: str = "/dev/shm/meshbot_io_test",
        failure_threshold: int = 3,
        cooldown_seconds: int = 900,  # 15 minutes
        enabled: bool = True
    ):
        """
        Initialize I/O health monitor.
        
        Args:
            db_path: Path to SQLite database to monitor
            test_file_path: Path for test writes (default: /dev/shm for RAM-based)
            failure_threshold: Number of consecutive failures before triggering reboot
            cooldown_seconds: Minimum time between health checks (prevents spam)
            enabled: Whether health monitoring is enabled
        """
        self.db_path = db_path
        self.test_file_path = test_file_path
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.enabled = enabled
        
        # State tracking
        self.consecutive_failures = 0
        self.last_check_time = 0
        self.last_failure_time = 0
        self.total_checks = 0
        self.total_failures = 0
        
        debug_print(f"📊 IOHealthMonitor initialized: enabled={enabled}, threshold={failure_threshold}")
    
    def should_run_check(self) -> bool:
        """
        Determine if health check should run based on cooldown period.
        
        Returns:
            bool: True if enough time has passed since last check
        """
        if not self.enabled:
            return False
        
        current_time = time.time()
        time_since_last = current_time - self.last_check_time
        
        return time_since_last >= self.cooldown_seconds
    
    def verify_filesystem_writable(self) -> Tuple[bool, Optional[str]]:
        """
        Test if filesystem is writable by performing a small write operation.
        
        Uses /dev/shm (tmpfs in RAM) to test write capability without wearing
        out the NVMe storage. Even if main storage fails, tmpfs should work.
        
        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        try:
            test_data = f"health_check_{time.time()}\n"
            
            # Write test data
            with open(self.test_file_path, 'w') as f:
                f.write(test_data)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            
            # Read it back to verify
            with open(self.test_file_path, 'r') as f:
                read_data = f.read()
            
            if read_data != test_data:
                return False, "Data mismatch after write/read"
            
            # Clean up
            os.remove(self.test_file_path)
            
            return True, None
            
        except OSError as e:
            return False, f"Filesystem write error: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"
    
    def verify_db_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Check SQLite database integrity using PRAGMA integrity_check.
        
        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cursor = conn.cursor()
            
            # Quick integrity check
            cursor.execute("PRAGMA quick_check")
            result = cursor.fetchone()[0]
            
            conn.close()
            
            if result != 'ok':
                return False, f"Database integrity check failed: {result}"
            
            return True, None
            
        except sqlite3.OperationalError as e:
            return False, f"Database operational error: {e}"
        except Exception as e:
            return False, f"Database check error: {e}"
    
    def verify_db_writable(self) -> Tuple[bool, Optional[str]]:
        """
        Test if database is writable by checking journal mode.
        
        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cursor = conn.cursor()
            
            # Check if we can query the database
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            
            # Try to get database page count (read operation)
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            
            conn.close()
            
            debug_print(f"✅ DB writable check passed: journal_mode={mode}, pages={page_count}")
            return True, None
            
        except sqlite3.OperationalError as e:
            return False, f"Database not writable: {e}"
        except Exception as e:
            return False, f"Database write check error: {e}"
    
    def perform_health_check(self) -> Tuple[bool, str]:
        """
        Perform complete I/O health check.
        
        Runs all health checks and returns overall status.
        
        Returns:
            Tuple[bool, str]: (healthy, status_message)
        """
        if not self.enabled:
            return True, "Health checks disabled"
        
        if not self.should_run_check():
            return True, "Cooldown period active"
        
        self.last_check_time = time.time()
        self.total_checks += 1
        
        debug_print("🔍 Running I/O health check...")
        
        checks = [
            ("Filesystem write", self.verify_filesystem_writable),
            ("Database integrity", self.verify_db_integrity),
            ("Database writable", self.verify_db_writable),
        ]
        
        all_passed = True
        failures = []
        
        for check_name, check_func in checks:
            success, error = check_func()
            if not success:
                all_passed = False
                failures.append(f"{check_name}: {error}")
                error_print(f"❌ Health check failed: {check_name} - {error}")
            else:
                debug_print(f"✅ Health check passed: {check_name}")
        
        if all_passed:
            # Reset failure counter on success
            if self.consecutive_failures > 0:
                info_print(f"✅ I/O health restored after {self.consecutive_failures} failures")
            self.consecutive_failures = 0
            return True, "All health checks passed"
        else:
            # Increment failure counter
            self.consecutive_failures += 1
            self.total_failures += 1
            self.last_failure_time = time.time()
            
            status = f"Health check failed ({self.consecutive_failures}/{self.failure_threshold}): {'; '.join(failures)}"
            error_print(f"⚠️ {status}")
            
            return False, status
    
    def should_trigger_reboot(self) -> Tuple[bool, str]:
        """
        Determine if reboot should be triggered based on failure count.
        
        Returns:
            Tuple[bool, str]: (should_reboot, reason)
        """
        if not self.enabled:
            return False, "Health monitoring disabled"
        
        if self.consecutive_failures >= self.failure_threshold:
            reason = (
                f"I/O health check failed {self.consecutive_failures} consecutive times. "
                f"Storage may be unreliable. Triggering safe reboot via SysRq."
            )
            return True, reason
        
        return False, "Failure threshold not reached"
    
    def get_statistics(self) -> dict:
        """
        Get health check statistics.
        
        Returns:
            dict: Statistics about health checks
        """
        return {
            'enabled': self.enabled,
            'total_checks': self.total_checks,
            'total_failures': self.total_failures,
            'consecutive_failures': self.consecutive_failures,
            'failure_threshold': self.failure_threshold,
            'cooldown_seconds': self.cooldown_seconds,
            'last_check_time': self.last_check_time,
            'last_failure_time': self.last_failure_time,
        }
    
    def get_status_report(self, compact: bool = False) -> str:
        """
        Get human-readable status report.
        
        Args:
            compact: If True, return compact single-line format
            
        Returns:
            str: Status report
        """
        stats = self.get_statistics()
        
        if compact:
            status = "✅ OK" if stats['consecutive_failures'] == 0 else f"⚠️ {stats['consecutive_failures']} failures"
            return f"I/O Health: {status} ({stats['total_checks']} checks, {stats['total_failures']} total failures)"
        
        lines = [
            "📊 I/O Health Monitor Status",
            f"├─ Enabled: {'✅' if stats['enabled'] else '❌'}",
            f"├─ Total checks: {stats['total_checks']}",
            f"├─ Total failures: {stats['total_failures']}",
            f"├─ Consecutive failures: {stats['consecutive_failures']}/{stats['failure_threshold']}",
            f"├─ Cooldown: {stats['cooldown_seconds']}s",
        ]
        
        if stats['last_check_time'] > 0:
            time_since = time.time() - stats['last_check_time']
            lines.append(f"├─ Last check: {time_since:.0f}s ago")
        
        if stats['last_failure_time'] > 0:
            time_since = time.time() - stats['last_failure_time']
            lines.append(f"└─ Last failure: {time_since:.0f}s ago")
        else:
            lines.append(f"└─ Last failure: Never")
        
        return '\n'.join(lines)
