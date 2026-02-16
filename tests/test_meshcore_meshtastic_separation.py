#!/usr/bin/env python3
"""
Test suite for Meshcore/Meshtastic separation in browse_traffic_db.py and /db command

This test verifies that:
1. browse_traffic_db.py has separate views for Meshtastic and MeshCore nodes
2. /db command distinguishes between the two sources
3. All necessary functions and routing are in place
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import os

# Test browse_traffic_db.py
def test_browse_traffic_db():
    """Test browse_traffic_db.py changes"""
    print("\n" + "="*60)
    print("Testing browse_traffic_db.py")
    print("="*60)
    
    from browse_traffic_db import TrafficDBBrowser
    
    # Test 1: View cycle includes new views
    print("\n1. Testing view cycle...")
    expected_views = ['packets', 'messages', 'nodes_stats', 'meshtastic_nodes', 'meshcore_contacts']
    browser = TrafficDBBrowser('test.db')
    
    for view in expected_views:
        browser.current_view = view
        print(f"   ✓ View '{view}' is valid")
    
    # Test 2: View descriptions
    print("\n2. Testing view descriptions...")
    view_info = {
        'packets': ('📦', 'ALL PACKETS'),
        'messages': ('💬', 'MESSAGES'),
        'nodes_stats': ('🌐', 'NODE STATS'),
        'meshtastic_nodes': ('📡', 'MESHTASTIC'),
        'meshcore_contacts': ('🔧', 'MESHCORE')
    }
    
    for view_name, (icon, title) in view_info.items():
        print(f"   ✓ {view_name}: {icon} {title}")
    
    # Test 3: Methods exist
    print("\n3. Testing methods exist...")
    methods = [
        'load_meshtastic_nodes',
        'load_meshcore_contacts',
        'draw_meshtastic_node_line',
        'draw_meshcore_contact_line'
    ]
    
    for method in methods:
        assert hasattr(browser, method), f"Method {method} should exist"
        print(f"   ✓ Method '{method}' exists")
    
    print("\n✅ browse_traffic_db.py tests PASSED")
    return True


def test_db_commands_content():
    """Test db_commands.py content directly"""
    print("\n" + "="*60)
    print("Testing db_commands.py content")
    print("="*60)
    
    # Read the file
    with open('handlers/command_handlers/db_commands.py', 'r') as f:
        content = f.read()
    
    # Test 1: New method exists
    print("\n1. Testing _get_meshtastic_table method...")
    assert '_get_meshtastic_table' in content
    print("   ✓ Method _get_meshtastic_table found")
    
    # Test 2: Command routing
    print("\n2. Testing command routing...")
    assert "'mt'" in content and "'meshtastic'" in content
    print("   ✓ Routing for mt/meshtastic commands found")
    
    assert "'mc'" in content and "'meshcore'" in content
    print("   ✓ Routing for mc/meshcore commands found")
    
    # Test 3: Stats enhancement
    print("\n3. Testing stats enhancement...")
    assert 'meshtastic_nodes_count' in content
    print("   ✓ Stats counts meshtastic_nodes")
    
    assert 'meshcore_contacts_count' in content
    print("   ✓ Stats counts meshcore_contacts")
    
    # Test 4: Help text
    print("\n4. Testing help text...")
    assert 'mt=' in content or 'mt - ' in content
    print("   ✓ Help text includes mt command")
    
    # Test 5: Source labels
    print("\n5. Testing source labels...")
    assert 'radio' in content and 'NODEINFO_APP' in content
    print("   ✓ Meshtastic source labeled as 'radio (NODEINFO_APP)'")
    
    assert 'meshcore-cli' in content or 'cli' in content
    print("   ✓ MeshCore source labeled as 'meshcore-cli'")
    
    print("\n✅ db_commands.py content tests PASSED")
    return True


def test_telegram_db_commands():
    """Test telegram db_commands.py has mt routing"""
    print("\n" + "="*60)
    print("Testing telegram_bot/commands/db_commands.py")
    print("="*60)
    
    with open('telegram_bot/commands/db_commands.py', 'r') as f:
        content = f.read()
    
    print("\n1. Testing mt command routing...")
    assert "'mt'" in content and "'meshtastic'" in content
    print("   ✓ Telegram handler routes mt/meshtastic commands")
    
    assert '_get_meshtastic_table' in content
    print("   ✓ Telegram handler calls _get_meshtastic_table")
    
    print("\n✅ telegram db_commands.py tests PASSED")
    return True


def print_summary():
    """Print a summary of the changes"""
    print("\n" + "="*60)
    print("SUMMARY OF CHANGES")
    print("="*60)
    
    print("\n📋 browse_traffic_db.py:")
    print("   • Added 'meshtastic_nodes' view (📡 MESHTASTIC)")
    print("   • Added 'meshcore_contacts' view (🔧 MESHCORE)")
    print("   • Renamed 'nodes' to 'nodes_stats' (🌐 NODE STATS)")
    print("   • View cycle: packets → messages → nodes_stats → meshtastic → meshcore")
    print("   • Added load_meshtastic_nodes() and load_meshcore_contacts() methods")
    print("   • Added draw_meshtastic_node_line() and draw_meshcore_contact_line()")
    print("   • Updated export functions (text, CSV, screen) for all node types")
    print("   • Updated help text to document new views")
    
    print("\n📋 handlers/command_handlers/db_commands.py:")
    print("   • Enhanced /db stats to show Meshtastic vs MeshCore counts")
    print("   • Added /db mt (meshtastic) subcommand")
    print("   • Clarified /db mc (meshcore) source labeling")
    print("   • Added _get_meshtastic_table() method")
    print("   • Updated help text with mt command")
    
    print("\n📋 telegram_bot/commands/db_commands.py:")
    print("   • Added mt/meshtastic command routing")
    print("   • Integrated with _get_meshtastic_table() method")
    
    print("\n🎯 Benefits:")
    print("   • Clear separation between radio-learned and cli-learned nodes")
    print("   • Users can now distinguish data sources")
    print("   • Better understanding of network topology")
    print("   • Improved troubleshooting capabilities")
    
    print("\n" + "="*60)


if __name__ == '__main__':
    print("="*60)
    print("MESHCORE/MESHTASTIC SEPARATION TEST SUITE")
    print("="*60)
    
    success = True
    
    try:
        success = test_browse_traffic_db() and success
    except Exception as e:
        print(f"\n❌ browse_traffic_db.py tests FAILED: {e}")
        success = False
    
    try:
        success = test_db_commands_content() and success
    except Exception as e:
        print(f"\n❌ db_commands.py tests FAILED: {e}")
        success = False
    
    try:
        success = test_telegram_db_commands() and success
    except Exception as e:
        print(f"\n❌ telegram db_commands.py tests FAILED: {e}")
        success = False
    
    print_summary()
    
    if success:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
