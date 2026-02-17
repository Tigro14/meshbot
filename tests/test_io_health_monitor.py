#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for I/O Health Monitor
"""

import unittest
import tempfile
import os
import sqlite3
import time
from io_health_monitor import IOHealthMonitor


class TestIOHealthMonitor(unittest.TestCase):
    """Test cases for IOHealthMonitor"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        
        # Initialize a valid SQLite database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                data TEXT
            )
        """)
        conn.commit()
        conn.close()
        
        # Create temporary test file path
        self.test_file_path = tempfile.mktemp(prefix='io_health_test_')
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Close and remove database
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        # Remove test file if exists
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)
    
    def test_initialization(self):
        """Test monitor initialization"""
        monitor = IOHealthMonitor(
            db_path=self.db_path,
            test_file_path=self.test_file_path,
            failure_threshold=3,
            cooldown_seconds=60,
            enabled=True
        )
        
        self.assertEqual(monitor.db_path, self.db_path)
        self.assertEqual(monitor.failure_threshold, 3)
        self.assertEqual(monitor.cooldown_seconds, 60)
        self.assertTrue(monitor.enabled)
        self.assertEqual(monitor.consecutive_failures, 0)
    
    def test_filesystem_writable_success(self):
        """Test filesystem write check succeeds"""
        monitor = IOHealthMonitor(
            db_path=self.db_path,
            test_file_path=self.test_file_path
        )
        
        success, error = monitor.verify_filesystem_writable()
        self.assertTrue(success)
        self.assertIsNone(error)
        # Test file should be cleaned up
        self.assertFalse(os.path.exists(self.test_file_path))
    
    def test_db_integrity_success(self):
        """Test database integrity check succeeds"""
        monitor = IOHealthMonitor(db_path=self.db_path)
        
        success, error = monitor.verify_db_integrity()
        self.assertTrue(success)
        self.assertIsNone(error)
    
    def test_db_writable_success(self):
        """Test database writable check succeeds"""
        monitor = IOHealthMonitor(db_path=self.db_path)
        
        success, error = monitor.verify_db_writable()
        self.assertTrue(success)
        self.assertIsNone(error)
    
    def test_health_check_success(self):
        """Test complete health check succeeds"""
        monitor = IOHealthMonitor(
            db_path=self.db_path,
            test_file_path=self.test_file_path,
            cooldown_seconds=0  # No cooldown for testing
        )
        
        healthy, status = monitor.perform_health_check()
        self.assertTrue(healthy)
        self.assertEqual(monitor.consecutive_failures, 0)
        self.assertGreater(monitor.total_checks, 0)
    
    def test_cooldown_mechanism(self):
        """Test cooldown prevents frequent checks"""
        monitor = IOHealthMonitor(
            db_path=self.db_path,
            cooldown_seconds=60
        )
        
        # First check should run
        self.assertTrue(monitor.should_run_check())
        monitor.perform_health_check()
        
        # Second check should be blocked by cooldown
        self.assertFalse(monitor.should_run_check())
    
    def test_disabled_monitor(self):
        """Test disabled monitor doesn't run checks"""
        monitor = IOHealthMonitor(
            db_path=self.db_path,
            enabled=False
        )
        
        self.assertFalse(monitor.should_run_check())
        healthy, status = monitor.perform_health_check()
        self.assertTrue(healthy)
        self.assertEqual(status, "Health checks disabled")
    
    def test_failure_threshold_logic(self):
        """Test reboot trigger logic with threshold"""
        monitor = IOHealthMonitor(
            db_path=self.db_path,
            failure_threshold=3
        )
        
        # No failures - should not trigger
        should_reboot, reason = monitor.should_trigger_reboot()
        self.assertFalse(should_reboot)
        
        # Simulate failures below threshold
        monitor.consecutive_failures = 2
        should_reboot, reason = monitor.should_trigger_reboot()
        self.assertFalse(should_reboot)
        
        # Simulate failures at threshold
        monitor.consecutive_failures = 3
        should_reboot, reason = monitor.should_trigger_reboot()
        self.assertTrue(should_reboot)
        self.assertIn("consecutive", reason)
    
    def test_db_integrity_with_bad_path(self):
        """Test integrity check with non-existent database"""
        monitor = IOHealthMonitor(db_path="/nonexistent/path/db.sqlite")
        
        success, error = monitor.verify_db_integrity()
        self.assertFalse(success)
        self.assertIsNotNone(error)
    
    def test_statistics(self):
        """Test statistics collection"""
        monitor = IOHealthMonitor(
            db_path=self.db_path,
            cooldown_seconds=0
        )
        
        # Perform some checks
        monitor.perform_health_check()
        monitor.perform_health_check()
        
        stats = monitor.get_statistics()
        self.assertEqual(stats['total_checks'], 2)
        self.assertEqual(stats['consecutive_failures'], 0)
        self.assertTrue(stats['enabled'])
    
    def test_status_report_compact(self):
        """Test compact status report"""
        monitor = IOHealthMonitor(
            db_path=self.db_path,
            cooldown_seconds=0
        )
        
        monitor.perform_health_check()
        report = monitor.get_status_report(compact=True)
        
        self.assertIn("I/O Health", report)
        self.assertIn("OK", report)
    
    def test_status_report_full(self):
        """Test full status report"""
        monitor = IOHealthMonitor(
            db_path=self.db_path,
            cooldown_seconds=0
        )
        
        monitor.perform_health_check()
        report = monitor.get_status_report(compact=False)
        
        self.assertIn("I/O Health Monitor Status", report)
        self.assertIn("Total checks", report)
        self.assertIn("Enabled", report)
    
    def test_failure_counter_reset(self):
        """Test failure counter resets on success"""
        monitor = IOHealthMonitor(
            db_path=self.db_path,
            cooldown_seconds=0
        )
        
        # Simulate some failures
        monitor.consecutive_failures = 2
        
        # Perform successful health check
        monitor.perform_health_check()
        
        # Counter should be reset
        self.assertEqual(monitor.consecutive_failures, 0)


if __name__ == '__main__':
    unittest.main()
