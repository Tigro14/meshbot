# Understanding Neighbor Data on Maps

## Why Do Some Nodes Have No Neighbor Info?

If you're seeing nodes without neighbor information on the map (no direct neighbor links), this is **normal behavior** and here's why:

### How Neighbor Data Collection Works

The MeshBot collects neighbor information **passively** by listening to NEIGHBORINFO_APP packets broadcast by nodes in the mesh network.

```
┌─────────────────────────────────────────────────┐
│  Meshtastic Network Topology                    │
│                                                  │
│  Node A broadcasts: "My neighbors: [B, C, D]"   │
│         │                                        │
│         ├──> Bot hears ──> Saves to database    │
│         │                                        │
│         └──> Other nodes may/may not hear       │
└─────────────────────────────────────────────────┘
```

### Key Points

1. **Passive Collection**: Bot only records NEIGHBORINFO packets it receives directly
2. **Broadcast Interval**: Nodes broadcast their neighbor lists every 15-30 minutes
3. **Radio Range**: Bot can only hear nodes within radio range
4. **Retention Period**: Database keeps 30 days of neighbor data (720 hours)

### Why a Node Might Have No Neighbor Data

| Reason | Explanation | Solution |
|--------|-------------|----------|
| **New Node** | Discovered < 30 minutes ago | Wait for next broadcast cycle |
| **Radio Range** | Bot didn't receive NEIGHBORINFO broadcast | Normal - bot has limited range |
| **Feature Disabled** | Node has neighbor_info disabled | Check node config: `meshtastic --get neighbor_info` |
| **Old Data Expired** | No broadcast in last 30 days | Node may be offline or moved |
| **MQTT-Only** | Node heard via MQTT gateway | Enable MQTT neighbor collection |

### What the Map Shows Instead

When a node has no neighbor data, the map uses **fallback visualization**:

#### 1. "Heard Via" Links (Brown Dashed Lines)
- Shows probable relay node based on hop distance
- Helps visualize network topology even without formal neighbor data
- **Example**: Node at 2 hops shows link to nearest 1-hop node

#### 2. Inferred Links (Gray Dashed Lines)
- Created based on hop count and signal strength
- Used when NO neighbor data exists for any node
- Less accurate but provides network overview

### Your Own Nodes

If **your own nodes** don't show neighbor info:

1. **Check if neighbor_info is enabled:**
   ```bash
   meshtastic --host <your-node-ip> --get neighbor_info
   ```
   Should show: `neighbor_info.enabled: True`

2. **Enable if disabled:**
   ```bash
   meshtastic --host <your-node-ip> --set neighbor_info.enabled true
   ```

3. **Wait for broadcast:**
   - Nodes broadcast every 15-30 minutes
   - Check bot logs for NEIGHBORINFO_APP packets:
     ```bash
     journalctl -u meshbot -f | grep NEIGHBORINFO
     ```

4. **Verify database collection:**
   ```bash
   sqlite3 traffic_history.db "SELECT COUNT(*) FROM neighbors;"
   ```
   Should show increasing count over time

### Getting Complete Neighbor Data

If you need **complete neighbor information** for all nodes:

#### Option 1: Database-Only Mode (Safe, Recommended)
```bash
# Uses only data bot has collected
cd /home/dietpi/bot/map
./export_neighbors_from_db.py ../traffic_history.db 720 > info_neighbors.json
```

**Pros:**
- ✅ No TCP conflicts with bot
- ✅ Safe to run anytime
- ✅ Shows what bot has actually heard

**Cons:**
- ❌ May miss nodes outside bot's radio range
- ❌ Requires waiting for broadcasts

#### Option 2: Hybrid Mode (Complete, May Conflict)
```bash
# Stop bot first!
sudo systemctl stop meshbot

# Query node directly via TCP + merge with database
cd /home/dietpi/bot/map
./export_neighbors_from_db.py --tcp-query 192.168.1.38 ../traffic_history.db 720 > info_neighbors.json

# Restart bot
sudo systemctl start meshbot
```

**Pros:**
- ✅ Complete data from node's memory
- ✅ Shows all neighbors node knows about

**Cons:**
- ❌ Must stop bot first (TCP conflict)
- ❌ Only works if you have a Meshtastic node accessible via TCP

### Expected Behavior Summary

| Node Type | Expected Neighbor Data | Map Visualization |
|-----------|------------------------|-------------------|
| **Your Node** (direct) | Should have neighbor list if enabled | Direct links (colored by SNR) |
| **1-hop Nodes** | May have neighbor list if bot heard broadcast | Direct links OR "heard via" link |
| **2+ hop Nodes** | Unlikely to have neighbor list | "Heard via" links (brown) OR inferred (gray) |
| **MQTT Nodes** | May have neighbor list if MQTT collector active | Direct links with "MQTT" source |

### Troubleshooting

#### Map shows very few neighbor links

1. **Check database:**
   ```bash
   sqlite3 traffic_history.db "SELECT COUNT(DISTINCT node_id) FROM neighbors;"
   ```
   This shows how many unique nodes have neighbor data.

2. **Check recent activity:**
   ```bash
   sqlite3 traffic_history.db "SELECT node_id, COUNT(*) as neighbor_count FROM neighbors WHERE timestamp > (strftime('%s', 'now') - 86400) GROUP BY node_id ORDER BY neighbor_count DESC LIMIT 10;"
   ```
   Shows top 10 nodes with most neighbors in last 24 hours.

3. **Enable MQTT collection (optional):**
   If you have MQTT access, enable MQTT neighbor collector to get data from beyond radio range:
   ```python
   # config.py
   MQTT_NEIGHBOR_ENABLED = True
   MQTT_NEIGHBOR_SERVER = "your.mqtt.server"
   MQTT_NEIGHBOR_USER = "username"
   MQTT_NEIGHBOR_PASSWORD = "password"
   ```

#### Owner node (your node) has no neighbors

This is unusual! Check:

1. **Is neighbor_info enabled?**
   ```bash
   meshtastic --host <ip> --get neighbor_info
   ```

2. **Is the node actually hearing other nodes?**
   - Check node's display - should show neighbor count
   - Check bot logs for received packets from other nodes

3. **Database permissions:**
   ```bash
   ls -l traffic_history.db
   ```
   Should be readable by bot user (dietpi)

## See Also

- **`map/README_NEIGHBORS.md`** - Technical details on neighbor data collection
- **`map/HYBRID_MODE_GUIDE.md`** - Using hybrid mode for complete data
- **`CLAUDE.md`** - Full system architecture
- **Issue #97** - Map visualization discussion

## Summary

**It's normal for many nodes to not have neighbor data on the map.** This is because:
- Bot can only collect data from packets it receives
- Nodes broadcast neighbor info every 15-30 minutes
- Radio range limits what the bot can hear

The map uses **fallback visualizations** ("heard via" links, inferred links) to show network topology even when formal neighbor data is missing. This is **expected behavior** and provides valuable network insights without requiring complete neighbor data from all nodes.
