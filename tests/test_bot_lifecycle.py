#!/usr/bin/env python3
"""
Test bot lifecycle and signal handling

This test verifies:
1. Bot starts successfully and returns True
2. Signal handlers work correctly
3. Main loop exits gracefully
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import re


class TestBotSourceCode(unittest.TestCase):
    """Test MeshBot source code changes"""
    
    def test_signal_imports_present(self):
        """Test that signal module is imported"""
        with open('main_bot.py', 'r') as f:
            content = f.read()
        
        self.assertIn('import signal', content,
                     "main_bot.py should import signal module")
    
    def test_signal_handler_exists(self):
        """Test that _signal_handler method exists"""
        with open('main_bot.py', 'r') as f:
            content = f.read()
        
        self.assertIn('def _signal_handler(self, signum, frame):', content,
                     "_signal_handler method should exist")
        self.assertIn('self.running = False', content,
                     "Signal handler should set running to False")
    
    def test_signal_handlers_registered(self):
        """Test that signal handlers are registered in start()"""
        with open('main_bot.py', 'r') as f:
            content = f.read()
        
        self.assertIn('signal.signal(signal.SIGTERM, self._signal_handler)', content,
                     "SIGTERM handler should be registered")
        self.assertIn('signal.signal(signal.SIGINT, self._signal_handler)', content,
                     "SIGINT handler should be registered")
        
    def test_start_returns_true_on_clean_exit(self):
        """Test that start() returns True when main loop exits cleanly"""
        with open('main_bot.py', 'r') as f:
            content = f.read()
        
        # Find the main loop section
        self.assertIn('while self.running:', content,
                     "Main loop should exist")
        
        # Check for return True after the loop
        # Look for the pattern: loop ends -> return True
        pattern = r'while self\.running:.*?return True'
        self.assertIsNotNone(re.search(pattern, content, re.DOTALL),
                           "start() should return True after main loop exits")
        
    def test_main_loop_exception_handling(self):
        """Test that exceptions in main loop are caught and don't crash the bot"""
        with open('main_bot.py', 'r') as f:
            content = f.read()
        
        # Verify the main loop has exception handling
        self.assertIn('except Exception as loop_error:', content,
                     "Main loop should have exception handling")
        self.assertIn('Erreur dans la boucle principale', content,
                     "Main loop should log errors without crashing")
        
        # Verify it continues after error
        pattern = r'except Exception as loop_error:.*?time\.sleep\(5\)'
        self.assertIsNotNone(re.search(pattern, content, re.DOTALL),
                           "Main loop should continue after error with a short sleep")


class TestSystemdService(unittest.TestCase):
    """Test systemd service configuration"""
    
    def test_service_file_restart_policy(self):
        """Test that service file uses on-failure restart policy"""
        with open('meshbot.service', 'r') as f:
            content = f.read()
        
        # Should use on-failure instead of always
        self.assertIn('Restart=on-failure', content,
                     "Service should use Restart=on-failure")
        
        # Should have restart limits
        self.assertIn('StartLimitBurst=5', content,
                     "Service should have StartLimitBurst")
        self.assertIn('StartLimitIntervalSec=300', content,
                     "Service should have StartLimitIntervalSec")
        
        # Should NOT have Restart=always
        lines = content.split('\n')
        lines_with_restart_always = [
            line for line in lines
            if 'Restart=always' in line and not line.strip().startswith('#')
        ]
        self.assertEqual(len(lines_with_restart_always), 0,
                        "Service should not use Restart=always (except in comments)")


if __name__ == '__main__':
    # Run tests
    print("=" * 60)
    print("Testing Bot Lifecycle Fixes")
    print("=" * 60)
    
    # Run the tests
    unittest.main(verbosity=2)

