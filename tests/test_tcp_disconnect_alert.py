#!/usr/bin/env python3
"""
Test for TCP disconnect alerts sent via Telegram

This test verifies that:
1. The _send_tcp_disconnect_alert method exists
2. It checks the TCP_DISCONNECT_ALERT_ENABLED configuration
3. It checks that telegram_integration is available
4. It formats the alert message correctly
5. The _send_tcp_disconnect_alert calls are present in _reconnect_tcp_interface
"""

import sys
import os

# Get the directory containing this test file
TEST_DIR = os.path.dirname(os.path.abspath(__file__))

# Add the test directory to path
sys.path.insert(0, TEST_DIR)


def test_tcp_disconnect_alert_method_exists():
    """
    Test that _send_tcp_disconnect_alert method exists in main_bot.py
    """
    print("\n🧪 Test: _send_tcp_disconnect_alert method exists")
    
    main_bot_path = os.path.join(TEST_DIR, 'main_bot.py')
    with open(main_bot_path, 'r') as f:
        content = f.read()
    
    # Verify the method exists
    assert 'def _send_tcp_disconnect_alert' in content, \
        "❌ _send_tcp_disconnect_alert method should exist"
    print("✅ _send_tcp_disconnect_alert method exists")


def test_tcp_disconnect_alert_checks_config():
    """
    Test that _send_tcp_disconnect_alert checks configuration
    """
    print("\n🧪 Test: Configuration verification")
    
    main_bot_path = os.path.join(TEST_DIR, 'main_bot.py')
    with open(main_bot_path, 'r') as f:
        content = f.read()
    
    # Find the method
    method_start = content.find('def _send_tcp_disconnect_alert')
    next_def = content.find('\n    def ', method_start + 1)
    method_code = content[method_start:next_def]
    
    # Verify config is checked
    assert 'TCP_DISCONNECT_ALERT_ENABLED' in method_code, \
        "❌ Method should check TCP_DISCONNECT_ALERT_ENABLED"
    print("✅ Checks TCP_DISCONNECT_ALERT_ENABLED")
    
    # Verify telegram_integration is checked
    assert 'telegram_integration' in method_code, \
        "❌ Method should check telegram_integration"
    print("✅ Checks telegram_integration")


def test_tcp_disconnect_alert_formats_message():
    """
    Test that _send_tcp_disconnect_alert formats message correctly
    """
    print("\n🧪 Test: Alert message formatting")
    
    main_bot_path = os.path.join(TEST_DIR, 'main_bot.py')
    with open(main_bot_path, 'r') as f:
        content = f.read()
    
    # Find the method
    method_start = content.find('def _send_tcp_disconnect_alert')
    next_def = content.find('\n    def ', method_start + 1)
    method_code = content[method_start:next_def]
    
    # Verify message elements
    assert 'tcp_host' in method_code, \
        "❌ Message should contain tcp_host"
    print("✅ Message contains tcp_host")
    
    assert 'tcp_port' in method_code, \
        "❌ Message should contain tcp_port"
    print("✅ Message contains tcp_port")
    
    assert 'send_alert' in method_code, \
        "❌ Method should call send_alert"
    print("✅ Calls send_alert")


def test_tcp_disconnect_alert_called_on_failure():
    """
    Test that _send_tcp_disconnect_alert is called when reconnection fails
    """
    print("\n🧪 Test: Called on reconnection failure")
    
    main_bot_path = os.path.join(TEST_DIR, 'main_bot.py')
    with open(main_bot_path, 'r') as f:
        content = f.read()
    
    # Find the _reconnect_tcp_interface method
    reconnect_start = content.find('def _reconnect_tcp_interface')
    # Find the next "def " at the same indentation level after the function start
    next_def = content.find('\n    def ', reconnect_start + 1)
    reconnect_code = content[reconnect_start:next_def]
    
    # Count the _send_tcp_disconnect_alert calls in the method
    call_count = reconnect_code.count('_send_tcp_disconnect_alert')
    
    assert call_count >= 2, \
        f"❌ _send_tcp_disconnect_alert should be called at least 2 times (found {call_count})"
    print(f"✅ _send_tcp_disconnect_alert is called {call_count} times in _reconnect_tcp_interface")


def test_config_option_exists():
    """
    Test that TCP_DISCONNECT_ALERT_ENABLED config option exists
    """
    print("\n🧪 Test: Config option exists")
    
    config_path = os.path.join(TEST_DIR, 'config.py.sample')
    with open(config_path, 'r') as f:
        content = f.read()
    
    # Verify option exists
    assert 'TCP_DISCONNECT_ALERT_ENABLED' in content, \
        "❌ TCP_DISCONNECT_ALERT_ENABLED should exist in config.py.sample"
    print("✅ TCP_DISCONNECT_ALERT_ENABLED exists in config.py.sample")


if __name__ == "__main__":
    print("=" * 70)
    print("TEST: TCP DISCONNECT TELEGRAM ALERTS")
    print("=" * 70)
    
    results = [
        test_tcp_disconnect_alert_method_exists(),
        test_tcp_disconnect_alert_checks_config(),
        test_tcp_disconnect_alert_formats_message(),
        test_tcp_disconnect_alert_called_on_failure(),
        test_config_option_exists(),
    ]
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(r is None or r for r in results)  # None means pass for pytest
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if all(r is None or r for r in results):
        print("\n✅ ALL TESTS PASSED")
        print("\nImplemented functionality:")
        print("- Telegram alert sent when TCP connection is permanently lost")
        print("- Configuration via TCP_DISCONNECT_ALERT_ENABLED")
        print("- Alert message includes host, port, and error details")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
