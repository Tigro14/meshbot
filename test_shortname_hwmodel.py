#!/usr/bin/env python3
"""
Test to verify shortName and hwModel are correctly stored and exported.
"""

import json
import os
import sys
import tempfile
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from node_manager import NodeManager

def test_shortname_hwmodel_storage():
    """Test that NodeManager correctly stores shortName and hwModel."""
    
    print("=" * 70)
    print("TEST: NodeManager shortName and hwModel Storage")
    print("=" * 70)
    
    # Create temporary node_names.json
    temp_dir = tempfile.mkdtemp(prefix='meshbot_test_')
    node_names_file = os.path.join(temp_dir, 'node_names.json')
    
    # Override NODE_NAMES_FILE
    import config
    original_file = config.NODE_NAMES_FILE
    
    # IMPORTANT: Override globally for both the import and the instance
    import node_manager
    node_manager.NODE_NAMES_FILE = node_names_file
    config.NODE_NAMES_FILE = node_names_file
    
    try:
        # Create NodeManager instance
        manager = NodeManager()
        
        # Simulate receiving a NODEINFO_APP packet with shortName and hwModel
        print("\n1. Testing update_node_from_packet with shortName and hwModel...")
        
        test_packet = {
            'from': 385536988,  # !16fad3dc (tigrobot from problem statement)
            'decoded': {
                'portnum': 'NODEINFO_APP',
                'user': {
                    'longName': 'tigro G2 PV',
                    'shortName': '\U0001F64A',  # Emoticon (folded hands emoji)
                    'hwModel': 'TBEAM'
                }
            }
        }
        
        manager.update_node_from_packet(test_packet)
        
        # Wait for timer to complete (timer delay is 10s, but we can force save)
        manager.save_node_names(force=True)
        
        # Verify data is stored correctly
        node_id = 385536988
        assert node_id in manager.node_names, f"Node {node_id} not found in node_names"
        
        node_data = manager.node_names[node_id]
        print(f"\n   Stored node data for {node_id}:")
        print(f"   • name: {node_data.get('name')}")
        print(f"   • shortName: {node_data.get('shortName')}")
        print(f"   • hwModel: {node_data.get('hwModel')}")
        
        assert node_data.get('name') == 'tigro G2 PV', "longName not stored correctly"
        assert node_data.get('shortName') == '\U0001F64A', "shortName not stored correctly"
        assert node_data.get('hwModel') == 'TBEAM', "hwModel not stored correctly"
        
        print("   ✓ shortName and hwModel stored correctly")
        
        # Verify JSON file was written correctly
        print("\n2. Verifying node_names.json file...")
        with open(node_names_file, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        saved_node = saved_data.get(str(node_id))
        assert saved_node is not None, "Node not found in saved JSON"
        
        print(f"   Saved node data from file:")
        print(f"   • name: {saved_node.get('name')}")
        print(f"   • shortName: {saved_node.get('shortName')}")
        print(f"   • hwModel: {saved_node.get('hwModel')}")
        
        assert saved_node.get('shortName') == '\U0001F64A', "shortName not saved correctly to JSON"
        assert saved_node.get('hwModel') == 'TBEAM', "hwModel not saved correctly to JSON"
        
        print("   ✓ node_names.json contains correct shortName and hwModel")
        
        # Test loading from file
        print("\n3. Testing load_node_names with shortName and hwModel...")
        manager2 = NodeManager()
        manager2.load_node_names()
        
        loaded_node = manager2.node_names.get(node_id)
        assert loaded_node is not None, "Node not loaded from file"
        
        print(f"   Loaded node data:")
        print(f"   • name: {loaded_node.get('name')}")
        print(f"   • shortName: {loaded_node.get('shortName')}")
        print(f"   • hwModel: {loaded_node.get('hwModel')}")
        
        assert loaded_node.get('shortName') == '\U0001F64A', "shortName not loaded correctly"
        assert loaded_node.get('hwModel') == 'TBEAM', "hwModel not loaded correctly"
        
        print("   ✓ shortName and hwModel loaded correctly from file")
        
        print("\n" + "=" * 70)
        print("✅ TEST PASSED: shortName and hwModel correctly stored and loaded")
        print("=" * 70)
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        print("=" * 70)
        return False
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 70)
        return False
    finally:
        # Restore original config
        config.NODE_NAMES_FILE = original_file
        import node_manager
        node_manager.NODE_NAMES_FILE = original_file
        
        # Cleanup
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    success = test_shortname_hwmodel_storage()
    sys.exit(0 if success else 1)
