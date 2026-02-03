#!/usr/bin/env python3
"""Test if imports work from tests/ directory"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now try to import main modules
try:
    from node_manager import NodeManager
    print("✓ Successfully imported NodeManager from tests/ directory")
    success = True
except ImportError as e:
    print(f"✗ Failed to import NodeManager: {e}")
    success = False

try:
    from traffic_monitor import TrafficMonitor
    print("✓ Successfully imported TrafficMonitor from tests/ directory")
except ImportError as e:
    print(f"✗ Failed to import TrafficMonitor: {e}")
    success = False

if success:
    print("\n✓✓✓ Import strategy works! Safe to move files.")
else:
    print("\n✗✗✗ Import strategy failed!")
    sys.exit(1)
