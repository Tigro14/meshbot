#!/usr/bin/env python3
"""
Test to verify MeshAlertManager initialization order fix

This test verifies that:
1. mesh_alert_manager is initialized AFTER message_handler
2. References are correctly updated in vigilance_monitor and blitz_monitor
3. No AttributeError occurs during initialization
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch
from io import StringIO


class TestMeshAlertInitOrder(unittest.TestCase):
    """Test MeshAlertManager initialization order"""

    def test_initialization_order_in_code(self):
        """Verify that mesh_alert_manager init comes after message_handler in main_bot.py"""
        with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Find line numbers
        message_handler_init_line = None
        mesh_alert_init_line = None
        mesh_alert_early_init_line = None
        
        for i, line in enumerate(lines):
            if 'self.message_handler = MessageHandler(' in line:
                message_handler_init_line = i
            if 'self.mesh_alert_manager = MeshAlertManager(' in line:
                mesh_alert_init_line = i
            if 'self.mesh_alert_manager = None' in line and 'NOTE:' in lines[max(0, i-2):i+1][0]:
                mesh_alert_early_init_line = i
        
        # Verify message_handler is initialized first
        self.assertIsNotNone(message_handler_init_line, 
                           "MessageHandler initialization not found")
        self.assertIsNotNone(mesh_alert_init_line, 
                           "MeshAlertManager initialization not found")
        
        print(f"✅ MessageHandler initialized at line {message_handler_init_line + 1}")
        print(f"✅ MeshAlertManager initialized at line {mesh_alert_init_line + 1}")
        print(f"✅ Early mesh_alert_manager = None at line {mesh_alert_early_init_line + 1}")
        
        # The key assertion: MeshAlertManager must be initialized AFTER MessageHandler
        self.assertGreater(mesh_alert_init_line, message_handler_init_line,
                          f"MeshAlertManager (line {mesh_alert_init_line + 1}) must be "
                          f"initialized AFTER MessageHandler (line {message_handler_init_line + 1})")
        
        # Verify early initialization with None happens before MessageHandler
        self.assertIsNotNone(mesh_alert_early_init_line,
                           "Early mesh_alert_manager = None not found")
        self.assertLess(mesh_alert_early_init_line, message_handler_init_line,
                       f"Early mesh_alert_manager = None (line {mesh_alert_early_init_line + 1}) "
                       f"should come before MessageHandler (line {message_handler_init_line + 1})")

    def test_blitz_monitor_deferred_connection(self):
        """Verify blitz_monitor is initialized with mesh_alert_manager=None"""
        with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
            content = f.read()
        
        # Find BlitzMonitor initialization
        blitz_init_start = content.find('self.blitz_monitor = BlitzMonitor(')
        self.assertGreater(blitz_init_start, 0, "BlitzMonitor initialization not found")
        
        # Extract the BlitzMonitor initialization block
        blitz_init_end = content.find(')', blitz_init_start + 100) + 1
        blitz_init_block = content[blitz_init_start:blitz_init_end + 300]  # Extra chars for context
        
        # Verify mesh_alert_manager=None is in the initialization
        self.assertIn('mesh_alert_manager=None', blitz_init_block,
                     "BlitzMonitor should be initialized with mesh_alert_manager=None")
        print("✅ BlitzMonitor initialized with mesh_alert_manager=None")
        
        # Verify there's a comment explaining deferred connection (less strict check)
        if 'Sera mis' in blitz_init_block or '# ' in blitz_init_block:
            print("✅ Comment found explaining deferred connection")
        else:
            print("⚠️ No comment found, but not critical")

    def test_vigilance_monitor_deferred_connection(self):
        """Verify vigilance_monitor connection is deferred"""
        with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
            content = f.read()
        
        # Find vigilance_monitor mesh_alert_manager update
        vigilance_update = content.find('self.vigilance_monitor.mesh_alert_manager = self.mesh_alert_manager')
        self.assertGreater(vigilance_update, 0, "Vigilance monitor update not found")
        
        # Find MeshAlertManager initialization
        mesh_alert_init = content.find('self.mesh_alert_manager = MeshAlertManager(')
        self.assertGreater(mesh_alert_init, 0, "MeshAlertManager init not found")
        
        # Verify update happens after initialization
        self.assertGreater(vigilance_update, mesh_alert_init,
                          "Vigilance monitor update should happen after MeshAlertManager init")
        print("✅ Vigilance monitor connection happens after MeshAlertManager init")

    def test_blitz_monitor_deferred_connection_code(self):
        """Verify blitz_monitor connection is deferred"""
        with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
            content = f.read()
        
        # Find blitz_monitor mesh_alert_manager update
        blitz_update = content.find('self.blitz_monitor.mesh_alert_manager = self.mesh_alert_manager')
        self.assertGreater(blitz_update, 0, "Blitz monitor update not found")
        
        # Find MeshAlertManager initialization
        mesh_alert_init = content.find('self.mesh_alert_manager = MeshAlertManager(')
        self.assertGreater(mesh_alert_init, 0, "MeshAlertManager init not found")
        
        # Verify update happens after initialization
        self.assertGreater(blitz_update, mesh_alert_init,
                          "Blitz monitor update should happen after MeshAlertManager init")
        print("✅ Blitz monitor connection happens after MeshAlertManager init")

    def test_no_premature_router_access(self):
        """Verify no premature access to self.message_handler.router during initialization"""
        with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
            content = f.read()
            lines = content.split('\n')
        
        message_handler_init_line = None
        router_accesses_before = []
        
        for i, line in enumerate(lines):
            if 'self.message_handler = MessageHandler(' in line:
                message_handler_init_line = i
            elif 'self.message_handler.router' in line and message_handler_init_line is None:
                # Check if it's inside a safe conditional check
                # Look at previous lines for "if self.message_handler:"
                safe = False
                for j in range(max(0, i-10), i):
                    if 'if self.message_handler:' in lines[j] or 'if self.message_handler and' in lines[j]:
                        safe = True
                        break
                
                if not safe:
                    # Found unsafe access to router before MessageHandler initialization
                    router_accesses_before.append(i + 1)
        
        # There should be no unsafe access to router before MessageHandler init
        self.assertEqual(len(router_accesses_before), 0,
                        f"Found premature unsafe access to self.message_handler.router at lines: "
                        f"{router_accesses_before}")
        print(f"✅ No premature unsafe access to self.message_handler.router found")


if __name__ == '__main__':
    # Run tests with verbose output
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshAlertInitOrder)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
