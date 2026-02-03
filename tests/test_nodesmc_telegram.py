#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for /nodesmc command with Telegram and MeshCore support
"""

import sys
import os
import time
from unittest.mock import Mock, MagicMock, patch
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock config before importing modules
config_mock = Mock()
config_mock.MAX_MESSAGE_SIZE = 180
config_mock.COLLECT_SIGNAL_METRICS = True
config_mock.DEBUG_MODE = True
config_mock.COMMAND_WINDOW_SECONDS = 300
config_mock.MAX_COMMANDS_PER_WINDOW = 5
sys.modules['config'] = config_mock

# Mock utils
utils_mock = Mock()
utils_mock.debug_print = lambda x: print(f"[DEBUG] {x}")
utils_mock.info_print = lambda x: print(f"[INFO] {x}")
utils_mock.error_print = lambda x: print(f"[ERROR] {x}")
utils_mock.conversation_print = lambda x: print(f"[CONV] {x}")
utils_mock.format_elapsed_time = lambda secs: f"{secs}s" if secs < 60 else f"{secs//60}m"
utils_mock.get_signal_quality_icon = lambda snr: "🟢" if snr >= 10 else "🟡"
utils_mock.truncate_text = lambda text, max_len, suffix: text[:max_len] + suffix if len(text) > max_len else text
utils_mock.validate_page_number = lambda page, total: max(1, min(page, total))
sys.modules['utils'] = utils_mock

# Now import the modules we want to test
from remote_nodes_client import RemoteNodesClient
from handlers.command_handlers.network_commands import NetworkCommands
from handlers.message_sender import MessageSender


def create_test_database():
    """Create a temporary test database with MeshCore contacts"""
    print("\n=== Creating test database ===")
    
    # Create in-memory database
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Create meshcore_contacts table
    cursor.execute('''
        CREATE TABLE meshcore_contacts (
            node_id INTEGER PRIMARY KEY,
            name TEXT,
            shortName TEXT,
            hwModel TEXT,
            lat REAL,
            lon REAL,
            alt REAL,
            last_updated REAL
        )
    ''')
    
    # Add test contacts
    now = datetime.now().timestamp()
    test_contacts = [
        (0x12345678, "Node-Alpha", "ALPH", "TBEAM", 47.5, 6.5, 500, now - 300),  # 5min ago
        (0x23456789, "Node-Bravo", "BRAV", "TBEAM", 47.6, 6.6, 600, now - 720),  # 12min ago
        (0x34567890, "Node-Charlie", "CHAR", "HELTEC_V3", 47.7, 6.7, 700, now - 3600),  # 1h ago
        (0x45678901, "Node-Delta", "DELT", "TBEAM", 47.8, 6.8, 800, now - 7200),  # 2h ago
        (0x56789012, "Node-Echo", "ECHO", "TBEAM", 47.9, 6.9, 900, now - 14400),  # 4h ago
        (0x67890123, "Node-Foxtrot", "FOXT", "HELTEC_V3", 48.0, 7.0, 1000, now - 28800),  # 8h ago
        (0x78901234, "Node-Golf", "GOLF", "TBEAM", 48.1, 7.1, 1100, now - 43200),  # 12h ago
        (0x89012345, "Node-Hotel", "HOTL", "TBEAM", 48.2, 7.2, 1200, now - 86400),  # 1d ago
        (0x90123456, "Node-India-With-A-Very-Long-Name", "INDI", "TBEAM", 48.3, 7.3, 1300, now - 172800),  # 2d ago
    ]
    
    for contact in test_contacts:
        cursor.execute('''
            INSERT INTO meshcore_contacts 
            (node_id, name, shortName, hwModel, lat, lon, alt, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', contact)
    
    conn.commit()
    print(f"✅ Created test database with {len(test_contacts)} contacts")
    return conn


def test_meshcore_paginated_split():
    """Test the get_meshcore_paginated_split method"""
    print("\n=== Test 1: MeshCore Split Method ===")
    
    # Create persistence mock with test database
    persistence_mock = Mock()
    persistence_mock.conn = create_test_database()
    
    # Create RemoteNodesClient with persistence
    client = RemoteNodesClient(persistence=persistence_mock)
    
    # Test pagination with splitting (160 char limit for MeshCore)
    print("\n--- Test with page 1, 160 char limit ---")
    messages = client.get_meshcore_paginated_split(page=1, days_filter=30, max_length=160)
    
    print(f"\n✅ Split into {len(messages)} messages:")
    for i, msg in enumerate(messages, 1):
        print(f"\nMessage {i} (length: {len(msg)} chars):")
        print(f"---\n{msg}\n---")
        assert len(msg) <= 160, f"❌ Message {i} exceeds 160 chars: {len(msg)}"
    
    print("\n--- Test with page 1, no split needed (300 char limit) ---")
    messages_no_split = client.get_meshcore_paginated_split(page=1, days_filter=30, max_length=300)
    print(f"✅ Result: {len(messages_no_split)} message(s)")
    for msg in messages_no_split:
        print(f"Length: {len(msg)} chars")
    
    print("\n✅ Test 1 PASSED")


def test_network_command_handler():
    """Test the NetworkCommands handler with /nodesmc"""
    print("\n=== Test 2: Network Command Handler ===")
    
    # Create persistence mock with test database
    persistence_mock = Mock()
    persistence_mock.conn = create_test_database()
    
    # Create RemoteNodesClient
    client = RemoteNodesClient(persistence=persistence_mock)
    
    # Create mocks for sender and interface
    interface_mock = Mock()
    interface_mock.sendText = Mock()
    
    sender_mock = Mock()
    sent_messages = []
    
    def capture_send(msg, sender_id, sender_info):
        sent_messages.append(msg)
        print(f"[SEND] To {sender_info} (ID: {sender_id:08x}): {msg[:50]}...")
    
    sender_mock.send_single = capture_send
    sender_mock.log_conversation = Mock()
    
    node_manager_mock = Mock()
    
    # Create NetworkCommands handler
    handler = NetworkCommands(
        remote_nodes_client=client,
        sender=sender_mock,
        node_manager=node_manager_mock
    )
    
    # Test /nodesmc command
    print("\n--- Test /nodesmc from MeshCore ---")
    sent_messages.clear()
    handler.handle_nodesmc("/nodesmc", 0x12345678, {"name": "TestUser", "id": 0x12345678})
    
    print(f"\n✅ Sent {len(sent_messages)} messages:")
    for i, msg in enumerate(sent_messages, 1):
        print(f"\nMessage {i} (length: {len(msg)} chars):")
        print(f"---\n{msg}\n---")
        if len(msg) > 160:
            print(f"⚠️  Warning: Message exceeds 160 chars")
    
    # Verify log_conversation was called
    assert sender_mock.log_conversation.called, "❌ log_conversation not called"
    print("\n✅ log_conversation called")
    
    print("\n✅ Test 2 PASSED")


def test_telegram_integration():
    """Test that the Telegram command is properly set up"""
    print("\n=== Test 3: Telegram Integration Check ===")
    
    # Check that the command method exists
    from telegram_bot.commands.network_commands import NetworkCommands as TelegramNetworkCommands
    
    # Create a mock telegram integration
    telegram_mock = Mock()
    telegram_mock.message_handler = Mock()
    telegram_mock.mesh_commands = Mock()
    telegram_mock.stats_commands = Mock()
    
    # Create the telegram network commands
    telegram_commands = TelegramNetworkCommands(telegram_mock)
    
    # Check that nodesmc_command exists
    assert hasattr(telegram_commands, 'nodesmc_command'), "❌ nodesmc_command method not found"
    print("✅ nodesmc_command method exists in TelegramNetworkCommands")
    
    # Check that it's a coroutine (async)
    import inspect
    assert inspect.iscoroutinefunction(telegram_commands.nodesmc_command), "❌ nodesmc_command is not async"
    print("✅ nodesmc_command is properly async")
    
    print("\n✅ Test 3 PASSED")


def test_empty_contacts():
    """Test handling of empty contacts list"""
    print("\n=== Test 4: Empty Contacts ===")
    
    # Create empty database
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE meshcore_contacts (
            node_id INTEGER PRIMARY KEY,
            name TEXT,
            shortName TEXT,
            hwModel TEXT,
            lat REAL,
            lon REAL,
            alt REAL,
            last_updated REAL
        )
    ''')
    conn.commit()
    
    persistence_mock = Mock()
    persistence_mock.conn = conn
    
    client = RemoteNodesClient(persistence=persistence_mock)
    
    # Test with empty database
    messages = client.get_meshcore_paginated_split(page=1, days_filter=30, max_length=160)
    
    print(f"✅ Empty contacts result: {messages}")
    assert len(messages) == 1, "❌ Should return exactly 1 message for empty list"
    assert "Aucun contact" in messages[0], "❌ Message should indicate no contacts found"
    
    print("\n✅ Test 4 PASSED")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing /nodesmc Telegram and MeshCore Support")
    print("=" * 60)
    
    try:
        test_meshcore_paginated_split()
        test_network_command_handler()
        test_telegram_integration()
        test_empty_contacts()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
