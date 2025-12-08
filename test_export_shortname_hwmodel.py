#!/usr/bin/env python3
"""
Test to verify shortName and hwModel are correctly exported in info.json.
"""

import json
import os
import sys
import tempfile
import time
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_export_shortname_hwmodel():
    """Test that export_nodes_from_db.py correctly exports shortName and hwModel."""
    
    print("=" * 70)
    print("TEST: Export shortName and hwModel to info.json")
    print("=" * 70)
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix='meshbot_export_test_')
    
    try:
        # Create test node_names.json with shortName and hwModel
        node_names_file = os.path.join(temp_dir, 'node_names.json')
        
        test_nodes = {
            "385536988": {  # !16fad3dc (tigrobot G2 PV from problem statement)
                "name": "tigro G2 PV",
                "shortName": "\U0001F64A",  # 🙊 folded hands emoji
                "hwModel": "TBEAM",
                "lat": 47.123,
                "lon": 6.456,
                "alt": 500,
                "last_update": time.time()
            },
            "232993566": {  # !0de3331e (tigro 2 t1000E from problem statement)
                "name": "tigro 2 t1000E",
                "shortName": "\U0001F60E",  # 😎 smiling face with sunglasses
                "hwModel": "T1000E",
                "lat": 47.234,
                "lon": 6.567,
                "alt": 600,
                "last_update": time.time()
            },
            "2809086170": {  # !a76f40da (tigro t1000E from problem statement)
                "name": "tigro t1000E",
                "shortName": "TIGR",  # Regular text shortName
                "hwModel": "T1000E",
                "lat": 47.345,
                "lon": 6.678,
                "alt": 700,
                "last_update": time.time()
            }
        }
        
        print("\n1. Creating test node_names.json with shortName and hwModel...")
        with open(node_names_file, 'w', encoding='utf-8') as f:
            json.dump(test_nodes, f, ensure_ascii=False, indent=2)
        
        print(f"   ✓ Created {len(test_nodes)} test nodes")
        for node_id, node_data in test_nodes.items():
            print(f"   • {node_data['name']}: shortName='{node_data['shortName']}', hwModel={node_data['hwModel']}")
        
        # Run export script
        print("\n2. Running export_nodes_from_db.py...")
        
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), 'map', 'export_nodes_from_db.py')
        
        # Create empty db (optional for this test)
        db_path = os.path.join(temp_dir, 'traffic_history.db')
        
        result = subprocess.run(
            ['python3', script_path, node_names_file, db_path, '48'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"   ✗ Export script failed with exit code {result.returncode}")
            print(f"   STDERR:\n{result.stderr}")
            return False
        
        print("   ✓ Export script executed successfully")
        
        # Parse output JSON
        print("\n3. Parsing exported JSON...")
        try:
            output_data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            print(f"   ✗ Failed to parse JSON output: {e}")
            print(f"   STDOUT:\n{result.stdout}")
            return False
        
        nodes = output_data.get('Nodes in mesh', {})
        print(f"   ✓ Found {len(nodes)} nodes in exported data")
        
        # Verify each node has correct shortName and hwModel
        print("\n4. Verifying exported shortName and hwModel...")
        
        all_correct = True
        for node_id_hex, node_entry in nodes.items():
            node_num = node_entry.get('num')
            user_info = node_entry.get('user', {})
            long_name = user_info.get('longName', '')
            short_name = user_info.get('shortName', '')
            hw_model = user_info.get('hwModel', '')
            
            # Find original test data
            test_node = test_nodes.get(str(node_num))
            if not test_node:
                print(f"   ⚠️  Node {node_id_hex} not in test data, skipping")
                continue
            
            print(f"\n   Node: {long_name} ({node_id_hex})")
            print(f"   • Expected shortName: '{test_node['shortName']}'")
            print(f"   • Actual shortName:   '{short_name}'")
            print(f"   • Expected hwModel:   '{test_node['hwModel']}'")
            print(f"   • Actual hwModel:     '{hw_model}'")
            
            # Verify
            if short_name != test_node['shortName']:
                print(f"   ✗ shortName mismatch!")
                all_correct = False
            elif hw_model != test_node['hwModel']:
                print(f"   ✗ hwModel mismatch!")
                all_correct = False
            else:
                print(f"   ✓ shortName and hwModel correct")
        
        print("\n" + "=" * 70)
        if all_correct:
            print("✅ TEST PASSED: All shortName and hwModel exported correctly")
            print("   • Emoticons are preserved in shortName")
            print("   • Hardware models are correctly exported")
            print("=" * 70)
            return True
        else:
            print("❌ TEST FAILED: Some shortName or hwModel values incorrect")
            print("=" * 70)
            return False
        
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 70)
        return False
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    success = test_export_shortname_hwmodel()
    sys.exit(0 if success else 1)
