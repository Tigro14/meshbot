#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test for /nodesmc splitting logic
Tests only the core splitting functionality without full module imports
"""

import sys
import sqlite3
from datetime import datetime


def format_elapsed_time(elapsed_seconds):
    """Format elapsed time"""
    if elapsed_seconds < 60:
        return f"{int(elapsed_seconds)}s"
    elif elapsed_seconds < 3600:
        return f"{int(elapsed_seconds // 60)}m"
    elif elapsed_seconds < 86400:
        return f"{int(elapsed_seconds // 3600)}h"
    else:
        return f"{int(elapsed_seconds // 86400)}j"


def format_node_line(node):
    """Format a node line (simplified version)"""
    try:
        name = node.get('name', 'Unknown')[:15]  # Truncate long names
        elapsed = datetime.now().timestamp() - node.get('last_heard', 0)
        elapsed_str = format_elapsed_time(elapsed)
        return f"• {name} {elapsed_str}"
    except Exception:
        return "• Err"


def get_meshcore_paginated_split(contacts, page=1, days_filter=30, max_length=160):
    """
    Format MeshCore contacts with pagination and splitting
    Simplified version of the actual implementation
    """
    if not contacts:
        return [f"📡 Aucun contact MeshCore trouvé (<{days_filter}j)"]
    
    # Sort by date
    contacts.sort(key=lambda x: x['last_heard'], reverse=True)
    
    # Pagination
    nodes_per_page = 7
    total_contacts = len(contacts)
    total_pages = (total_contacts + nodes_per_page - 1) // nodes_per_page
    
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * nodes_per_page
    end_idx = min(start_idx + nodes_per_page, total_contacts)
    page_contacts = contacts[start_idx:end_idx]
    
    lines = []
    
    if page == 1:
        lines.append(f"📡 Contacts MeshCore (<{days_filter}j) ({total_contacts}):")
    
    for contact in page_contacts:
        line = format_node_line(contact)
        lines.append(line)
    
    if total_pages > 1:
        lines.append(f"{page}/{total_pages}")
    
    full_report = "\n".join(lines)
    
    # If it fits in one message, return as-is
    if len(full_report) <= max_length:
        return [full_report]
    
    # Otherwise, split intelligently by line
    messages = []
    current_msg = []
    current_length = 0
    
    for line in lines:
        line_length = len(line) + 1  # +1 for \n
        
        if current_length + line_length > max_length and current_msg:
            messages.append('\n'.join(current_msg))
            current_msg = [line]
            current_length = line_length
        else:
            current_msg.append(line)
            current_length += line_length
    
    if current_msg:
        messages.append('\n'.join(current_msg))
    
    # Add message numbers if multiple messages
    if len(messages) > 1:
        numbered = []
        for i, msg in enumerate(messages, 1):
            numbered.append(f"({i}/{len(messages)}) {msg}")
        return numbered
    
    return messages


def create_test_contacts():
    """Create test contacts"""
    now = datetime.now().timestamp()
    return [
        {'id': 0x12345678, 'name': "Node-Alpha", 'last_heard': now - 300},
        {'id': 0x23456789, 'name': "Node-Bravo", 'last_heard': now - 720},
        {'id': 0x34567890, 'name': "Node-Charlie", 'last_heard': now - 3600},
        {'id': 0x45678901, 'name': "Node-Delta", 'last_heard': now - 7200},
        {'id': 0x56789012, 'name': "Node-Echo", 'last_heard': now - 14400},
        {'id': 0x67890123, 'name': "Node-Foxtrot", 'last_heard': now - 28800},
        {'id': 0x78901234, 'name': "Node-Golf", 'last_heard': now - 43200},
        {'id': 0x89012345, 'name': "Node-Hotel", 'last_heard': now - 86400},
        {'id': 0x90123456, 'name': "Node-India-With-A-Very-Long-Name", 'last_heard': now - 172800},
    ]


def test_basic_split():
    """Test basic splitting functionality"""
    print("\n=== Test 1: Basic MeshCore Splitting (160 chars) ===")
    
    contacts = create_test_contacts()
    messages = get_meshcore_paginated_split(contacts, page=1, max_length=160)
    
    print(f"\n✅ Split into {len(messages)} messages:")
    for i, msg in enumerate(messages, 1):
        print(f"\n--- Message {i} (length: {len(msg)} chars) ---")
        print(msg)
        print("---")
        
        if len(msg) > 160:
            print(f"❌ FAIL: Message {i} exceeds 160 chars!")
            return False
    
    print("\n✅ Test 1 PASSED - All messages <= 160 chars")
    return True


def test_no_split_needed():
    """Test when no splitting is needed"""
    print("\n=== Test 2: No Split Needed (Large Limit) ===")
    
    contacts = create_test_contacts()[:3]  # Only 3 contacts
    messages = get_meshcore_paginated_split(contacts, page=1, max_length=300)
    
    print(f"\n✅ Result: {len(messages)} message(s)")
    for i, msg in enumerate(messages, 1):
        print(f"\nMessage {i} (length: {len(msg)} chars):")
        print(msg)
    
    if len(messages) != 1:
        print(f"❌ FAIL: Expected 1 message, got {len(messages)}")
        return False
    
    print("\n✅ Test 2 PASSED - Single message as expected")
    return True


def test_empty_contacts():
    """Test with empty contacts"""
    print("\n=== Test 3: Empty Contacts ===")
    
    messages = get_meshcore_paginated_split([], page=1, max_length=160)
    
    print(f"\n✅ Result: {len(messages)} message(s)")
    print(f"Message: {messages[0]}")
    
    if len(messages) != 1:
        print(f"❌ FAIL: Expected 1 message, got {len(messages)}")
        return False
    
    if "Aucun contact" not in messages[0]:
        print(f"❌ FAIL: Expected 'Aucun contact' in message")
        return False
    
    print("\n✅ Test 3 PASSED - Empty list handled correctly")
    return True


def test_message_numbering():
    """Test that multi-part messages are numbered"""
    print("\n=== Test 4: Message Numbering ===")
    
    contacts = create_test_contacts()
    messages = get_meshcore_paginated_split(contacts, page=1, max_length=160)
    
    if len(messages) > 1:
        # Check that messages are numbered
        for i, msg in enumerate(messages, 1):
            expected_prefix = f"({i}/{len(messages)})"
            if not msg.startswith(expected_prefix):
                print(f"❌ FAIL: Message {i} doesn't start with {expected_prefix}")
                print(f"Actual: {msg[:30]}...")
                return False
        
        print(f"✅ All {len(messages)} messages properly numbered")
    else:
        print(f"✅ Single message (no numbering needed)")
    
    print("\n✅ Test 4 PASSED - Numbering correct")
    return True


def main():
    """Run all tests"""
    print("=" * 70)
    print("Testing /nodesmc Message Splitting Logic")
    print("=" * 70)
    
    all_passed = True
    
    try:
        all_passed &= test_basic_split()
        all_passed &= test_no_split_needed()
        all_passed &= test_empty_contacts()
        all_passed &= test_message_numbering()
        
        print("\n" + "=" * 70)
        if all_passed:
            print("✅ ALL TESTS PASSED")
            print("=" * 70)
            return 0
        else:
            print("❌ SOME TESTS FAILED")
            print("=" * 70)
            return 1
        
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ TEST FAILED WITH EXCEPTION: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
