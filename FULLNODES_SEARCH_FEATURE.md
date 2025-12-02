# /fullnodes Search Feature

## Overview

The `/fullnodes` command now supports an optional search parameter to filter nodes by name. This allows users to quickly find specific nodes or groups of nodes without having to scroll through the entire list.

## Usage

### Command Syntax

```
/fullnodes [days] [search_expr]
```

### Parameters

- **days** (optional, default: 30): Number of days to look back in the node database
  - Range: 1-365 days
  - Example: `7` for last week, `90` for last 3 months
  
- **search_expr** (optional): Search expression to filter nodes
  - Case-insensitive substring match
  - Searches in both shortname and longname
  - Can be multiple words (e.g., "test node")

### Usage Examples

#### 1. List all nodes (default behavior)
```
/fullnodes
```
Returns: All nodes seen in the last 30 days

#### 2. List all nodes with custom time range
```
/fullnodes 7
```
Returns: All nodes seen in the last 7 days

#### 3. Search for nodes containing "tigro"
```
/fullnodes tigro
```
Returns: Only nodes with "tigro" in their name (last 30 days)
Example matches:
- `TIG1 tigrobot`
- `TIG2 tigrog2`
- `XYZ TestTigro`

#### 4. Search with custom time range
```
/fullnodes 7 tigro
```
Returns: Nodes containing "tigro" seen in the last 7 days

#### 5. Search for nodes containing "router"
```
/fullnodes router
```
Returns: Nodes with "router" in their name (case-insensitive)
Example matches:
- `ROT1 Router`
- `MAIN MainRouter`

#### 6. Multi-word search
```
/fullnodes test node
```
Returns: Nodes containing "test node"
Example match:
- `ABC1 Test Node`

## Implementation Details

### Modified Files

1. **remote_nodes_client.py**
   - Updated `get_all_nodes_alphabetical()` method
   - Added `search_expr` parameter (optional, default: None)
   - Implemented case-insensitive substring filtering
   - Updated header to show search term when used
   - Returns helpful message when no matches found

2. **telegram_bot/commands/network_commands.py**
   - Updated `fullnodes_command()` to parse search parameter
   - Smart argument parsing:
     - First arg as number → days
     - First arg as string → search expression
     - Two args → days + search
   - Logging includes search parameter

3. **telegram_bot/commands/basic_commands.py**
   - Updated help text to show `[recherche]` parameter

4. **handlers/command_handlers/utility_commands.py**
   - Updated detailed help text with examples

### Search Algorithm

```python
if search_expr:
    search_lower = search_expr.lower()
    filtered_nodes = []
    
    for node in remote_nodes:
        name = node.get('name', 'Unknown')
        # Search in full name (contains both shortname and longname)
        if search_lower in name.lower():
            filtered_nodes.append(node)
    
    remote_nodes = filtered_nodes
```

### Node Name Format

Nodes in the Meshtastic network typically have names in the format:
```
SHORTNAME LongName
```

Examples:
- `TIG1 tigrobot` (short: TIG1, long: tigrobot)
- `ROT1 Router` (short: ROT1, long: Router)
- `ABC Test Node` (short: ABC, long: Test Node)

The search matches against the complete name string, so it will find matches in either the shortname or longname.

### Case Sensitivity

The search is **case-insensitive** for maximum flexibility:
- `tigro` matches `TIG1 tigrobot`
- `TIGRO` matches `TIG2 tigrog2`
- `TiGrO` matches `XYZ TestTigro`

### Backwards Compatibility

The feature is fully backwards compatible:
- `/fullnodes` → Works as before (all nodes, 30 days)
- `/fullnodes 7` → Works as before (all nodes, 7 days)
- `search_expr=None` in code → Returns all nodes

### Error Handling

When no nodes match the search:
```
❌ Aucun nœud trouvé avec 'nonexistent' (<30j)
```

The message clearly indicates:
1. No matches were found
2. The search term used
3. The time range searched

## Testing

### Unit Tests

A comprehensive unit test suite is provided in `test_fullnodes_search.py`:

```bash
python test_fullnodes_search.py
```

The test suite covers:
1. ✓ Backwards compatibility (no search parameter)
2. ✓ Basic search functionality
3. ✓ Case-insensitive matching
4. ✓ Single-word searches
5. ✓ Partial name matching
6. ✓ No matches scenario
7. ✓ Multi-word searches

All tests pass successfully.

### Manual Testing

To test manually:
1. Start the Telegram bot
2. Send `/fullnodes` to verify basic functionality
3. Send `/fullnodes tigro` to test search
4. Send `/fullnodes 7 router` to test combined params
5. Verify results match expected nodes

## Performance Considerations

- **Search Complexity**: O(n) where n = number of nodes
- **Memory Impact**: Minimal (creates filtered list, original preserved)
- **Network Impact**: None (filtering done locally after data fetch)
- **Cache**: Leverages existing 60-second cache in RemoteNodesClient

For typical networks (50-200 nodes), the search is instant.

## Future Enhancements

Potential improvements for future versions:

1. **Regular Expression Support**
   ```python
   import re
   pattern = re.compile(search_expr, re.IGNORECASE)
   if pattern.search(name):
   ```

2. **Multiple Search Terms**
   ```
   /fullnodes tigro router
   # Returns nodes matching either "tigro" OR "router"
   ```

3. **Exclude Patterns**
   ```
   /fullnodes -test
   # Returns all nodes EXCEPT those containing "test"
   ```

4. **Field-Specific Search**
   ```
   /fullnodes short:TIG
   # Search only in shortname
   /fullnodes long:robot
   # Search only in longname
   ```

## Summary

The `/fullnodes` search feature provides a simple, intuitive way to filter the node list without changing the existing behavior. It's backwards compatible, well-tested, and documented for both users and developers.

**Key Benefits:**
- ✓ Quick node lookup by name
- ✓ Case-insensitive for ease of use
- ✓ Backwards compatible
- ✓ No breaking changes
- ✓ Clear error messages
- ✓ Comprehensive testing
