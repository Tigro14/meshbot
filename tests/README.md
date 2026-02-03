# Tests Directory

This directory contains all test files for the Meshtastic-Llama Bot project.

## Structure

- **test_*.py** - Test files (160 files)
- **archive/** - Archived tests for old bug fixes and features
  - **fix-tests/** - Tests for specific bug fixes

## Running Tests

To run tests from this directory:

```bash
# Run a single test
python3 tests/test_config_separation.py

# Run all tests (from project root)
python3 -m pytest tests/

# Run specific test pattern
python3 -m pytest tests/test_meshcore_*.py
```

## Import Notes

All test files have been configured to import from the parent directory (project root) using:

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

This allows tests to import main modules like:
- `from node_manager import NodeManager`
- `from traffic_monitor import TrafficMonitor`
- `from handlers.message_router import MessageRouter`

## Test Categories

### Feature Tests
- **MeshCore**: test_meshcore_*.py
- **MQTT**: test_mqtt_*.py
- **TCP**: test_tcp_*.py
- **Database**: test_db_*.py
- **Network**: test_neighbors_*.py, test_node_*.py
- **Commands**: test_*_command*.py

### Integration Tests
- test_*_integration.py files test multiple components together

### Fix Tests
- Some tests verify specific bug fixes (candidates for archival)
- See TEST_CLEANUP_GUIDE.md in project root for details

## Contributing

When adding new tests:
1. Name them `test_<feature>.py`
2. Place them in the tests/ directory
3. Include the sys.path manipulation at the top
4. Add clear docstrings explaining what is tested
