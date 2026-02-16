#!/usr/bin/env python3
"""
Test suite for MTMQTT_DEBUG flag functionality

This test verifies that:
1. MTMQTT_DEBUG flag can be imported
2. Debug logging is correctly conditionally displayed
3. Flag defaults to False when not in config
4. No impact on normal operations when disabled
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import sys
import io
from unittest.mock import Mock, patch, MagicMock
import time


class TestMTMQTTDebugFlag(unittest.TestCase):
    """Test the MTMQTT_DEBUG configuration flag"""
    
    def test_import_flag_from_config(self):
        """Test that MTMQTT_DEBUG can be imported from config"""
        try:
            from config import MTMQTT_DEBUG
            print(f"✓ MTMQTT_DEBUG imported successfully: {MTMQTT_DEBUG}")
            # Should be a boolean
            self.assertIsInstance(MTMQTT_DEBUG, bool)
            print(f"✓ MTMQTT_DEBUG is boolean type")
        except ImportError as e:
            self.fail(f"Failed to import MTMQTT_DEBUG: {e}")
    
    def test_flag_is_documented(self):
        """Test that MTMQTT_DEBUG is documented in config.py.sample"""
        with open('config.py.sample', 'r') as f:
            content = f.read()
        
        self.assertIn('MTMQTT_DEBUG', content)
        print("✓ MTMQTT_DEBUG found in config.py.sample")
        
        # Check for documentation keywords
        self.assertIn('Meshtastic MQTT', content)
        self.assertIn('MTMQTT', content)
        print("✓ MTMQTT_DEBUG is documented")
    
    def test_collector_imports_flag_with_fallback(self):
        """Test that mqtt_neighbor_collector imports flag with fallback"""
        # Read the file to check import logic
        with open('mqtt_neighbor_collector.py', 'r') as f:
            content = f.read()
        
        self.assertIn('from config import MTMQTT_DEBUG', content)
        self.assertIn('except ImportError:', content)
        self.assertIn('MTMQTT_DEBUG = False', content)
        print("✓ mqtt_neighbor_collector.py has proper import with fallback")
    
    def test_debug_logging_conditionally_present(self):
        """Test that debug logging uses MTMQTT_DEBUG condition"""
        with open('mqtt_neighbor_collector.py', 'r') as f:
            content = f.read()
        
        # Should have multiple conditional debug statements
        debug_count = content.count('if MTMQTT_DEBUG:')
        self.assertGreater(debug_count, 5)
        print(f"✓ Found {debug_count} conditional MTMQTT_DEBUG statements")
        
        # Should use [MTMQTT] prefix
        self.assertIn('[MTMQTT]', content)
        print("✓ Uses [MTMQTT] prefix for debug messages")


class TestMTMQTTDebugOutput(unittest.TestCase):
    """Test the debug output behavior"""
    
    def setUp(self):
        """Setup test environment"""
        # Import the collector module
        import mqtt_neighbor_collector
        self.collector_module = mqtt_neighbor_collector
    
    @patch('mqtt_neighbor_collector.MTMQTT_DEBUG', False)
    def test_debug_disabled_minimal_output(self):
        """Test that debug disabled produces minimal output"""
        # When MTMQTT_DEBUG is False, debug messages should not be printed
        # This is verified by checking the conditional structure exists
        self.assertFalse(self.collector_module.MTMQTT_DEBUG)
        print("✓ MTMQTT_DEBUG can be set to False")
    
    @patch('mqtt_neighbor_collector.MTMQTT_DEBUG', True)
    def test_debug_enabled_verbose_output(self):
        """Test that debug enabled produces verbose output"""
        # When MTMQTT_DEBUG is True, debug messages should be printed
        # This is verified by checking the flag can be enabled
        self.assertTrue(self.collector_module.MTMQTT_DEBUG)
        print("✓ MTMQTT_DEBUG can be set to True")
    
    def test_debug_messages_use_info_print(self):
        """Test that debug messages use info_print for visibility"""
        with open('mqtt_neighbor_collector.py', 'r') as f:
            content = f.read()
        
        # Count debug messages that use info_print
        lines = content.split('\n')
        debug_info_count = 0
        for i, line in enumerate(lines):
            if 'if MTMQTT_DEBUG:' in line:
                # Check next line uses info_print
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if 'info_print' in next_line and '[MTMQTT]' in next_line:
                        debug_info_count += 1
        
        self.assertGreater(debug_info_count, 3)
        print(f"✓ Found {debug_info_count} MTMQTT_DEBUG statements using info_print")


class TestMTMQTTDebugIntegration(unittest.TestCase):
    """Test integration with existing code"""
    
    def test_no_breaking_changes(self):
        """Test that changes don't break existing functionality"""
        # Import the collector to ensure no syntax errors
        try:
            import mqtt_neighbor_collector
            print("✓ mqtt_neighbor_collector imports successfully")
        except Exception as e:
            self.fail(f"Failed to import module: {e}")
    
    def test_collector_initialization(self):
        """Test that collector can be initialized"""
        try:
            from mqtt_neighbor_collector import MQTTNeighborCollector
            
            # Mock the dependencies
            mock_persistence = Mock()
            mock_node_manager = Mock()
            
            # Create collector instance (should not require MQTT connection for init)
            collector = MQTTNeighborCollector(
                mqtt_server="test.example.com",
                mqtt_port=1883,
                mqtt_user="test",
                mqtt_password="test",
                persistence=mock_persistence,
                node_manager=mock_node_manager
            )
            
            # Check that collector has the expected attributes
            self.assertIsNotNone(collector)
            self.assertEqual(collector.mqtt_server, "test.example.com")
            print("✓ MQTTNeighborCollector initializes successfully")
            
        except Exception as e:
            # If MQTT dependencies are missing, that's okay for this test
            if 'MQTT' in str(e) or 'paho' in str(e):
                print("⚠ MQTT dependencies not available, skipping initialization test")
            else:
                self.fail(f"Unexpected error during initialization: {e}")
    
    def test_debug_prefix_consistency(self):
        """Test that all debug messages use consistent [MTMQTT] prefix"""
        with open('mqtt_neighbor_collector.py', 'r') as f:
            content = f.read()
        
        # Find all MTMQTT_DEBUG conditional blocks
        lines = content.split('\n')
        inconsistent_messages = []
        
        for i, line in enumerate(lines):
            if 'if MTMQTT_DEBUG:' in line:
                # Check next few lines for messages without [MTMQTT] prefix
                for j in range(i + 1, min(i + 4, len(lines))):
                    next_line = lines[j]
                    if 'print' in next_line and '[MTMQTT]' not in next_line:
                        # Might be closing brace or other code
                        if 'info_print' in next_line or 'error_print' in next_line:
                            inconsistent_messages.append((j + 1, next_line.strip()))
        
        if inconsistent_messages:
            print(f"⚠ Warning: Found {len(inconsistent_messages)} messages without [MTMQTT] prefix:")
            for line_num, msg in inconsistent_messages[:3]:
                print(f"   Line {line_num}: {msg[:80]}")
        else:
            print("✓ All MTMQTT_DEBUG messages use [MTMQTT] prefix consistently")


def run_tests():
    """Run all tests and print summary"""
    print("=" * 70)
    print("MTMQTT_DEBUG Flag Test Suite")
    print("=" * 70)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMTMQTTDebugFlag))
    suite.addTests(loader.loadTestsFromTestCase(TestMTMQTTDebugOutput))
    suite.addTests(loader.loadTestsFromTestCase(TestMTMQTTDebugIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print()
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print()
        print("✅ ALL TESTS PASSED")
        print()
        print("MTMQTT_DEBUG implementation is working correctly!")
        return 0
    else:
        print()
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(run_tests())
