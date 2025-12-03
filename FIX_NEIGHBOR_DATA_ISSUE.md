# Fix Summary: Neighbor Data Reduction Issue

## Problem

As noted in [PR #97 comment](https://github.com/Tigro14/meshbot/pull/97#issuecomment-3606334694), the neighbor data export reduced from **500 nodes to 42 nodes** after the database-based collection was implemented in PR #93.

## Root Cause

The database-based collection model is **fundamentally different** from the old TCP-based export:

### Old System (TCP-based)
```
export_neighbors.py → TCP → tigrog2 node → Full database query → 500 nodes
```
- Direct access to node's complete neighbor database
- Gets all neighbor relationships stored in node
- **Complete** but **conflicts** with bot's TCP connection

### New System (Database-based)
```
MeshBot receives NEIGHBORINFO_APP packets → Stores in SQLite → Export reads DB → 42 nodes
```
- Passive collection from packets bot receives
- NEIGHBORINFO_APP broadcasts every 15-30 minutes
- **Safe** but **incomplete** (only packets bot has received)

## Solution: Hybrid Mode

The updated `export_neighbors_from_db.py` now supports **two modes**:

### Mode 1: DATABASE-ONLY (Default, Safe)

```bash
./export_neighbors_from_db.py
```

**Characteristics:**
- ✅ Safe to run while bot is running
- ✅ No TCP connection conflicts
- ⚠️ May have incomplete data (42 nodes instead of 500)

**Best for:** Production systems where bot runs 24/7

### Mode 2: HYBRID (Complete, May Conflict)

```bash
./export_neighbors_from_db.py --tcp-query 192.168.1.38
```

**Characteristics:**
- ✅ Gets complete neighbor data (500+ nodes)
- ✅ Merges with database for maximum completeness
- ⚠️ May conflict with bot's TCP connection
- ⚠️ Requires bot to be stopped OR use different node

**Best for:** Getting complete maps when bot can be temporarily stopped

## How to Use

### Option A: Quick Fix (One-Time Complete Export)

Stop bot temporarily, run hybrid mode, restart:

```bash
# 1. Stop bot
sudo systemctl stop meshbot

# 2. Export complete neighbor data
cd /home/dietpi/bot/map
./export_neighbors_from_db.py --tcp-query 192.168.1.38 > info_neighbors.json

# 3. Check results
cat info_neighbors.json | jq '.statistics'
# Should show ~500 nodes

# 4. Restart bot
sudo systemctl start meshbot
```

### Option B: Configure `infoup_db.sh` for Hybrid Mode

Edit the script to always use hybrid mode:

```bash
# 1. Edit script
nano /home/dietpi/bot/map/infoup_db.sh

# 2. Set TCP query host (line ~22)
TCP_QUERY_HOST="192.168.1.38"  # Enable hybrid mode

# 3. Save and exit
```

**WARNING:** This will conflict with bot if both use the same node. Recommended to:
- Stop bot before running script, OR
- Use a different node for TCP query

### Option C: Scheduled Complete Exports

Create a cron job that stops bot, exports, restarts:

```bash
# Create script
cat > /home/dietpi/bot/map/infoup_hybrid_scheduled.sh << 'EOF'
#!/bin/bash
# Stop bot
sudo systemctl stop meshbot

# Run hybrid export
cd /home/dietpi/bot/map
TCP_QUERY_HOST="192.168.1.38" ./infoup_db.sh

# Restart bot
sudo systemctl start meshbot
EOF

chmod +x /home/dietpi/bot/map/infoup_hybrid_scheduled.sh

# Add to cron (every 6 hours)
crontab -e
# Add: 0 */6 * * * /home/dietpi/bot/map/infoup_hybrid_scheduled.sh
```

### Option D: Multi-Node Setup (No Conflicts!)

If you have multiple nodes, use one for bot and another for export:

```bash
# Bot uses: 192.168.1.38 (serial or TCP)
# Export uses: 192.168.1.39 (different node)

# In infoup_db.sh
TCP_QUERY_HOST="192.168.1.39"  # No conflict with bot!
```

## What Changed

### Files Modified

1. **`map/export_neighbors_from_db.py`** (+304 lines)
   - Added `query_tcp_neighbors()` function for TCP query
   - Added `merge_neighbor_data()` function for combining data
   - Added `--tcp-query` command-line option
   - Enhanced help message with mode explanations

2. **`map/infoup_db.sh`** (+16 lines)
   - Added `TCP_QUERY_HOST` configuration variable
   - Added `TCP_QUERY_PORT` configuration variable
   - Automatic mode selection based on configuration

3. **`map/HYBRID_MODE_GUIDE.md`** (NEW, 343 lines)
   - Complete guide to hybrid mode
   - Usage examples for all scenarios
   - Troubleshooting section
   - Recommendations based on setup

4. **`map/README_NEIGHBORS.md`** (+23 lines)
   - Added hybrid mode section
   - Enhanced troubleshooting for low node count
   - Cross-references to hybrid mode guide

5. **`map/test_hybrid_mode.py`** (NEW, 268 lines)
   - Comprehensive test suite
   - Database-only mode test
   - Merge logic test
   - Command-line parsing test

### Test Results

All tests pass successfully:

```
✅ Database-only mode test PASSED
✅ Merge logic test PASSED
✅ Command-line parsing test PASSED
✅ ALL TESTS PASSED
```

## Migration Path

### Current State (Database-Only)
- `infoup_db.sh` runs database-only export
- Gets 42 nodes (packets bot received)
- Safe, no conflicts

### To Get Complete Data

**Choose one:**

1. **One-time fix:** Run hybrid mode manually when needed
2. **Scheduled:** Stop bot periodically for hybrid export
3. **Multi-node:** Use different nodes (no conflicts)
4. **Accept partial:** Keep database-only, wait for data collection

## Recommendations

### For Your Setup

Based on your comment showing 500 → 42 node reduction:

**Immediate Action:**
```bash
# Get complete data once
sudo systemctl stop meshbot
cd /home/dietpi/bot/map
./export_neighbors_from_db.py --tcp-query 192.168.1.38 > info_neighbors.json
sudo systemctl start meshbot
```

**Long-term Strategy:**

If you need **complete data regularly**:
- Set up scheduled hybrid exports (stop bot, export, restart)
- Or: Use a different node for export (no conflicts)

If you can accept **partial data**:
- Keep database-only mode (safe)
- Wait for bot to collect more packets (will improve over days/weeks)

## Documentation

For detailed information, see:

- **`map/HYBRID_MODE_GUIDE.md`** - Complete hybrid mode guide
- **`map/README_NEIGHBORS.md`** - Neighbor collection overview
- **`--help`** - Command-line help: `./export_neighbors_from_db.py --help`

## Questions?

Common questions answered in `HYBRID_MODE_GUIDE.md`:

- Why only 42 nodes instead of 500?
- How to get complete neighbor data?
- What are the trade-offs between modes?
- How to avoid TCP conflicts?
- How to configure `infoup_db.sh`?

---

**Summary:**
- ✅ Problem identified and documented
- ✅ Hybrid mode implemented
- ✅ Comprehensive documentation added
- ✅ Tests passing
- ✅ Ready for deployment

**Action Required:**
Choose a strategy (one-time, scheduled, multi-node, or accept partial) and configure accordingly.
