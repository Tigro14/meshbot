# Demos Directory

This directory contains demonstration and diagnostic scripts for the Meshtastic-Llama Bot project.

## Structure

- **demo_*.py** - Demo and diagnostic files (33 files)
- **archive/** - Archived demo scripts

## Running Demos

To run demos from this directory:

```bash
# Run a demo
python3 demos/demo_db_neighbors.py

# Run with specific arguments (if supported)
python3 demos/demo_key_pair_validation.py --help
```

## Import Notes

Demo files that import main modules have been configured to import from the parent directory (project root) using:

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

This allows demos to import main modules like:
- `from node_manager import NodeManager`
- `from traffic_monitor import TrafficMonitor`
- `from meshcore_serial_interface import MeshCoreSerialInterface`

## Demo Categories

### Database Demos
- **demo_db_*.py** - Database functionality demonstrations

### MeshCore Demos
- **demo_meshcore_*.py** - MeshCore protocol and functionality
- **demo_meshcore_debug.py** - Debug MeshCore connections
- **demo_meshcore_decoder.py** - Decode MeshCore packets
- **demo_meshcore_dm_decryption.py** - DM decryption examples

### Network Demos
- **demo_mqtt_*.py** - MQTT connectivity and features
- **demo_neighbor_*.py** - Neighbor discovery and retention
- **demo_propag_*.py** - Message propagation

### Protocol Demos
- **demo_dm_decryption.py** - Direct message encryption/decryption
- **demo_packet_metadata.py** - Packet metadata handling
- **demo_pubkey_*.py** - Public key synchronization

### Command Demos
- **demo_ia_command.py** - AI command functionality
- **demo_info_with_hops.py** - Info command with hop data
- **demo_hop_*.py** - Hop analysis and routing

### System Demos
- **demo_semaphore_resilience.py** - Reboot semaphore system
- **demo_startup_messages.py** - Startup message handling
- **demo_vigilance_improvements.py** - Weather vigilance system

## Purpose

Demo scripts serve several purposes:

1. **Feature Demonstration** - Show how features work with real examples
2. **Diagnostics** - Help troubleshoot issues in production
3. **Documentation** - Provide executable examples of API usage
4. **Testing** - Quick manual testing of specific functionality

## Contributing

When adding new demos:
1. Name them `demo_<feature>.py`
2. Place them in the demos/ directory
3. Include the sys.path manipulation if needed
4. Add clear docstrings and usage examples
5. Make them runnable with minimal dependencies
