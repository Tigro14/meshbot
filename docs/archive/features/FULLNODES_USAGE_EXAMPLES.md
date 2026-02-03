# /fullnodes Command Usage Examples

## Quick Reference Card

| Command | Days Filter | Search | Result |
|---------|-------------|--------|--------|
| `/fullnodes` | 30 (default) | None | All nodes (last 30 days) |
| `/fullnodes 7` | 7 | None | All nodes (last 7 days) |
| `/fullnodes tigro` | 30 (default) | "tigro" | Nodes matching "tigro" (30 days) |
| `/fullnodes 7 tigro` | 7 | "tigro" | Nodes matching "tigro" (7 days) |
| `/fullnodes router` | 30 (default) | "router" | Nodes matching "router" (30 days) |
| `/fullnodes 90 test` | 90 | "test" | Nodes matching "test" (90 days) |

## Real-World Examples

### Example 1: Find all "tigro" nodes
**Command:** `/fullnodes tigro`

**Sample Output:**
```
📡 Nœuds 'tigro' sur RemoteNode (<30j) - 3 nœuds:

• TIG1 tigrobot (direct, 5m)
• TIG2 tigrog2 (1 hop, 12m)
• XYZ TestTigro (2 hops, 1h)
```

### Example 2: Find routers seen in last week
**Command:** `/fullnodes 7 router`

**Sample Output:**
```
📡 Nœuds 'router' sur RemoteNode (<7j) - 2 nœuds:

• ROT1 Router (direct, 2m)
• MAIN MainRouter (direct, 8m)
```

### Example 3: Search with no matches
**Command:** `/fullnodes xyz123`

**Sample Output:**
```
❌ Aucun nœud trouvé avec 'xyz123' (<30j)
```

### Example 4: All nodes (traditional usage)
**Command:** `/fullnodes`

**Sample Output:**
```
📡 TOUS les nœuds de RemoteNode (<30j) - 25 nœuds:

• ABC1 Test Node (2 hops, 3h)
• ROT1 Router (direct, 2m)
• TIG1 tigrobot (direct, 5m)
• TIG2 tigrog2 (1 hop, 12m)
... (21 more nodes)
```

## Search Behavior

### Case Insensitivity
All searches are case-insensitive:
- `tigro` = `TIGRO` = `TiGrO` = `Tigro`

### Substring Matching
Searches match anywhere in the node name:
- Search: `"test"` matches:
  - ✓ `ABC1 Test Node`
  - ✓ `TST TestNode`
  - ✓ `XYZ MyTestDevice`

### Multi-Word Search
Spaces are preserved in search terms:
- Search: `"test node"` matches:
  - ✓ `ABC1 Test Node`
  - ✗ `TST TestNode` (no space between "Test" and "Node")

### Shortname and Longname
Search applies to the complete node name string:
- Node: `TIG1 tigrobot`
  - Search: `"TIG1"` → ✓ Match (shortname)
  - Search: `"tigro"` → ✓ Match (longname)
  - Search: `"bot"` → ✓ Match (part of longname)
  - Search: `"router"` → ✗ No match

## Command Flow Diagram

```
User Input: /fullnodes [arg1] [arg2...]
                 |
                 v
        ┌────────────────┐
        │ Parse Arguments│
        └────────┬───────┘
                 |
                 v
        Is arg1 a number?
         /              \
       YES              NO
        |                |
        v                v
    days = arg1      search = arg1
    search = arg2    days = 30
        |                |
        └────────┬───────┘
                 |
                 v
    ┌────────────────────────────┐
    │ get_all_nodes_alphabetical │
    │   (days, search_expr)      │
    └────────────┬───────────────┘
                 |
                 v
        Fetch all nodes from
        remote (last 'days' days)
                 |
                 v
        search_expr provided?
         /              \
       YES              NO
        |                |
        v                v
    Filter nodes     Use all nodes
    by search term       |
        |                |
        └────────┬───────┘
                 |
                 v
        Sort alphabetically
        (by longname)
                 |
                 v
        Format and return
        results to user
```

## Argument Parsing Logic

The command handler uses smart parsing to determine if arguments are days or search:

```python
# Try to parse first argument as integer
try:
    days = int(args[0])
    search = ' '.join(args[1:]) if len(args) > 1 else None
except ValueError:
    # First arg is not a number, so it's a search term
    days = 30  # default
    search = ' '.join(args)
```

### Parsing Examples

| Input | Parsed Days | Parsed Search |
|-------|-------------|---------------|
| `/fullnodes` | 30 | None |
| `/fullnodes 7` | 7 | None |
| `/fullnodes tigro` | 30 | "tigro" |
| `/fullnodes 7 tigro` | 7 | "tigro" |
| `/fullnodes test node` | 30 | "test node" |
| `/fullnodes 90 test node` | 90 | "test node" |

## Tips and Tricks

### 1. Quick Node Lookup
Instead of scrolling through 50+ nodes, search directly:
```
/fullnodes tigro
```

### 2. Recent Activity Only
Combine time filter with search to find recently active nodes:
```
/fullnodes 1 test
# Shows nodes matching "test" seen in last 24 hours
```

### 3. Network Monitoring
Search for specific node types:
```
/fullnodes router    # Find all routers
/fullnodes client    # Find all clients
/fullnodes relay     # Find all relays
```

### 4. Troubleshooting
Find when a node was last seen:
```
/fullnodes 365 problemnode
# Search up to 1 year back
```

### 5. Group Management
Find all nodes in a group/area:
```
/fullnodes paris     # All Paris nodes
/fullnodes sector5   # All Sector 5 nodes
```

## Error Messages

| Scenario | Error Message |
|----------|---------------|
| No matches | `❌ Aucun nœud trouvé avec 'xyz' (<30j)` |
| Remote host not configured | `❌ REMOTE_NODE_HOST non configuré dans config.py` |
| No nodes in database | `Aucun nœud trouvé sur RemoteNode (<30j)` |

## Performance Notes

- **Search Speed**: O(n) where n = number of nodes
  - Typical: 50-200 nodes → instant results
  - Large networks: 500+ nodes → still < 100ms
  
- **Network Impact**: None
  - Filtering done locally after fetching node list
  - Leverages existing 60-second cache
  
- **Memory Impact**: Minimal
  - Creates filtered copy of node list
  - Original list preserved for sorting

## Compatibility

- ✅ **Backwards Compatible**: All existing commands work unchanged
- ✅ **No Breaking Changes**: Default behavior preserved
- ✅ **Telegram Bot**: Fully integrated
- ✅ **Multi-platform**: Works with any Meshtastic node
- ✅ **Cache-friendly**: Uses existing caching mechanism

## Related Commands

- `/nodes` - List direct nodes only (no search, no time filter)
- `/nodeinfo <name>` - Detailed info about specific node
- `/rx [page]` - Paginated view of direct nodes
- `/stats channel` - Channel utilization statistics

