# CLAUDE.md - AI Assistant Guide for Meshtastic-Llama Bot

**Last Updated**: 2026-02-03
**Project**: Meshtastic-Llama Bot with Telegram Integration
**Language**: Python 3.8+
**Platform**: Raspberry Pi 5 / Linux

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Recent Architectural Changes](#recent-architectural-changes-november-2025)
3. [Architecture](#architecture)
4. [Codebase Structure](#codebase-structure)
5. [Key Conventions](#key-conventions)
6. [Development Workflows](#development-workflows)
7. [Common Tasks](#common-tasks)
8. [Configuration Management](#configuration-management)
9. [Testing Strategy](#testing-strategy)
10. [Performance Patterns](#performance-patterns)
11. [Security Considerations](#security-considerations)
12. [Troubleshooting](#troubleshooting)
13. [Platforms Architecture](#platforms-architecture)
14. [Map Generation](#map-generation)
15. [External Integrations](#external-integrations)

---

## Project Overview

### What is MeshBot?

A sophisticated Meshtastic bot running on Raspberry Pi 5 that integrates:
- **Meshtastic LoRa Network**: Serial + TCP connections to mesh nodes
- **Llama AI**: Local LLM via llama.cpp for conversational AI
- **Telegram**: Bidirectional bridge for richer interactions
- **ESPHome**: Solar/battery telemetry monitoring
- **Traffic Analytics**: Comprehensive SQLite-based packet monitoring

### Use Case Architecture

```
┌────────────────────────────────────────────────┐
│         Raspberry Pi 5 (Bot Host)              │
│  ┌──────────────┐      ┌──────────────┐       │
│  │  MeshBot     │◄────►│  Telegram    │       │
│  │  main_bot.py │      │  Integration │       │
│  └──────┬───────┘      └──────────────┘       │
│         │                                       │
│    ┌────┴────────────────┐                    │
│    │  Message Processing  │                    │
│    │  Router + Handlers   │                    │
│    └────┬────────────┬────┘                    │
│         │            │                          │
│    ┌────▼────┐  ┌───▼──────┐                  │
│    │ Llama   │  │ Traffic  │                  │
│    │ Client  │  │ Monitor  │                  │
│    └─────────┘  └──────────┘                  │
└─────┬────────────────────────┬─────────────────┘
      │                        │
   ┌──▼──────┐            ┌───▼────────┐
   │ Serial  │            │ TCP (WiFi) │
   │ UART    │            │ 192.168.x.x│
   └──┬──────┘            └───┬────────┘
      │                       │
┌─────▼──────────┐     ┌─────▼───────────────┐
│ Meshtastic BOT │     │ Meshtastic ROUTER   │
│ Node (Serial)  │     │ (tigrog2) via TCP   │
└────────────────┘     └─────────────────────┘
```

### Key Statistics
- **~19,306 lines** of Python code
- **64 modules** with clear separation of concerns
- **Dual-channel design**: Constrained LoRa (180 chars) vs Rich Telegram (3000 chars)
- **Multi-platform ready**: Pluggable architecture for Telegram, Discord, Matrix
- **SQLite persistence**: 48-hour traffic history with automatic cleanup
- **Unified statistics**: Single `/stats` command with multiple sub-commands
- **Enhanced weather**: Rain graphs, astronomical data, lightning detection, vigilance alerts
- **Real-time monitoring**: Blitzortung lightning strikes and Météo-France alerts

---

## Recent Architectural Changes (November 2025)

### DM Decryption for Meshtastic 2.7.15+ (December 2025)

Added support for decrypting DM messages in Meshtastic firmware 2.7.15+:

**Problem Solved:**
- Meshtastic 2.7.15+ encrypts all DM (Direct Messages) by default
- Bot received encrypted DMs but couldn't read them
- DMs appeared as "ENCRYPTED" in logs and were not processed
- Users couldn't send commands via DM to the bot

**Implementation:**
- Added `_decrypt_packet()` method in `traffic_monitor.py` using AES-128-CTR
- Detects encrypted DMs addressed to our node
- Decrypts using default channel 0 PSK
- Converts decrypted protobuf to dict format
- Updates original packet with decoded data
- Logs decryption status (success/failure)

**Benefits:**
1. ✅ Bot can now read and process DM messages in Meshtastic 2.7.15+
2. ✅ Respects privacy: only decrypts DMs to our node
3. ✅ Backward compatible: non-encrypted messages work as before
4. ✅ Graceful fallback: keeps as ENCRYPTED if decryption fails
5. ✅ Comprehensive testing: test suite verifies all scenarios

**Files Modified:**
- `traffic_monitor.py` - Added decryption logic and imports
- `test_dm_decryption.py` - Comprehensive test suite (NEW)
- `demo_dm_decryption.py` - Interactive demo (NEW)
- `DM_DECRYPTION_2715.md` - Complete documentation (NEW)

**Log Example:**
```
[DEBUG] 🔐 Attempting to decrypt DM from 0x0de3331e to us
[DEBUG] ✅ Successfully decrypted DM packet from 0x0de3331e
[DEBUG] 📨 Decrypted DM message: /help
[DEBUG] ✅ DM decrypted successfully: TEXT_MESSAGE_APP
[DEBUG] 📦 TEXT_MESSAGE_APP de tigro t1000E f40da [direct] (SNR:12.0dB)
```

### Neighbor Data Retention Extension (December 2025)

Extended neighbor data retention from 48 hours to 30 days for better network visualization:

**Problem Solved:**
- Map generation was producing nearly empty maps despite having neighbor data in the database
- The 48-hour retention period was too short for networks with infrequent updates
- Export scripts and database cleanup were using different retention periods

**Changes:**
- Added `NEIGHBOR_RETENTION_HOURS` configuration option (default: 720 hours = 30 days)
- Updated `main_bot.py` cleanup to use configurable retention period
- Updated `map/infoup_db.sh` to export 30 days of neighbor data consistently
- Both neighbor and node exports now use the same 30-day retention period

**Configuration:**
```python
# config.py
NEIGHBOR_RETENTION_HOURS = 720  # 30 jours de rétention
```

**Benefits:**
1. ✅ More populated network topology maps
2. ✅ Better visibility of network evolution over time
3. ✅ Configurable retention period for different use cases
4. ✅ Consistent retention across cleanup and export operations

**Files Modified:**
- `config.py.sample` - Added `NEIGHBOR_RETENTION_HOURS` configuration
- `main_bot.py` - Uses config value for cleanup instead of hardcoded 48h
- `map/infoup_db.sh` - Export scripts use 720h (30 days) for all exports

### Multi-Platform Architecture (v2.0)

The codebase has undergone a significant refactoring to support multiple messaging platforms:

**Key Changes:**
- **Platform Manager**: New `PlatformManager` orchestrates multiple messaging platforms
- **Platform Interface**: Abstract `MessagingPlatform` base class for all platforms
- **Telegram Refactoring**: Telegram integration moved to modular `telegram_bot/` structure
- **Alert System**: New `AlertManager` for sending alerts to Telegram users
- **Configuration Split**: Platform configs separated into `platform_config.py`

**Benefits:**
- Support for Telegram, Discord, Matrix simultaneously
- Better separation of concerns
- Easier testing and maintenance
- Platform-independent core logic

**Migration Notes:**
- Legacy `telegram_integration.py` still exists but is deprecated
- New code should use `platforms/telegram_platform.py`
- Commands now organized by category in `telegram_bot/commands/`

### TCP Disconnect Alerts (November 2025)

New Telegram alerting when TCP connection to Meshtastic node is permanently lost:

**Problem Solved:**
- In TCP mode, if the bot loses connection to the Meshtastic node, there was no way to remotely know about it
- Without the Meshtastic connection, remote reboot commands via mesh are not possible
- Users need to be notified via Telegram to check the hardware

**Implementation:**
- Added `_send_tcp_disconnect_alert()` method in `main_bot.py`
- Alert sent after all reconnection attempts fail (3 retries with exponential backoff)
- Message includes: node name, host:port, timestamp, and error details
- Configurable via `TCP_DISCONNECT_ALERT_ENABLED` in config.py

**Configuration:**
```python
TCP_DISCONNECT_ALERT_ENABLED = True  # Enable/disable TCP disconnect alerts
```

**Alert Message:**
```
🔴 ALERTE: Connexion TCP perdue

📡 Nœud: MyNode
🌐 Host: 192.168.1.38:4403
⏱️ Heure: 14:23:45
❌ Erreur: Socket mort après stabilisation

⚠️ Le bot ne peut plus communiquer avec le réseau Meshtastic.
🔄 Reconnexion automatique en échec après plusieurs tentatives.
💡 Action recommandée: Vérifier l'alimentation et le réseau du nœud.
```

### Network Visualization

New map generation tools added in `map/` directory:
- Interactive HTML network topology maps
- Geographic node visualization
- Link quality analysis
- Automated map updates via `infoup.sh`

**Use Cases:**
- Network planning and optimization
- Coverage gap identification
- Community engagement and transparency

### Unified Statistics System

New unified statistics command system consolidates all statistics functionality:
- **Single Entry Point**: `/stats` command with sub-commands
- **Channel Adaptation**: Automatically adapts output for Mesh (180 chars) vs Telegram (longer)
- **Business Logic Centralization**: All statistics logic in `unified_stats.py`
- **Backward Compatibility**: Legacy commands (`/top`, `/packets`, `/histo`) remain as aliases

**Sub-commands:**
- `/stats` or `/stats global` - Network overview
- `/stats top [hours] [n]` - Top talkers
- `/stats packets [hours]` - Packet type distribution
- `/stats channel [hours]` - Channel utilization
- `/stats histo [type] [hours]` - Type-specific histogram
- `/stats traffic [hours]` - Public message history (Telegram only)

See `STATS_CONSOLIDATION_PLAN.md` for detailed architecture.

### CLI Server Platform (November 2025)

New TCP-based CLI server for local command-line access to the bot:

**Key Features:**
- **TCP Server**: Listens on `127.0.0.1:9999` for local connections
- **No Serial Competition**: CLI doesn't access `/dev/ttyACM0`, runs in parallel with bot
- **Client-Server Architecture**: Standalone `cli_client.py` connects via socket
- **Full Command Support**: All bot commands available via CLI
- **No LoRa Limits**: No 180-char constraint or throttling
- **Platform Integration**: Implements `MessagingPlatform` interface

**Architecture:**
- `platforms/cli_server_platform.py` - TCP server accepting CLI connections
- `cli_client.py` - Standalone client (interactive prompt)
- `CLIMessageSender` - Redirects responses to TCP socket instead of Meshtastic
- `CLIInterfaceWrapper` - Intercepts `sendText()` calls for unified_stats

**Use Cases:**
- Development and debugging without touching Meshtastic
- Testing commands locally before deploying
- Admin access without consuming LoRa bandwidth
- Parallel operation with mesh network

**Configuration:**
```python
CLI_ENABLED = True
CLI_SERVER_HOST = '127.0.0.1'  # Local only (security)
CLI_SERVER_PORT = 9999
```

**Security:**
- Listens only on localhost (no remote access)
- No authentication (relies on local-only binding)
- Ideal for development/debug environments

### Command Improvements (November 2025)

**`/trace` Command Fixed:**
- **Bug**: Always traced message sender, ignored target node argument
- **Fix**: Now accepts node name or ID as argument
- **Usage**:
  - `/trace` → trace your own message (original behavior)
  - `/trace F547F` → trace node by ID (partial match)
  - `/trace tigro` → trace node by name (partial match)
- **Output**: Signal strength, distance, last heard, GPS coordinates

**`/g2` Command Removed:**
- Deprecated command for tigrog2 config display
- Not documented in help or configured for Telegram
- Superseded by `/stats` command
- ~60 lines of code removed

### Hybrid Node Configuration (November 2025)

New configuration option to enable dual-node command processing:

**Key Features:**
- **PROCESS_TCP_COMMANDS**: Toggle to accept commands from both serial and TCP nodes
- **Backward Compatible**: Default to False preserves historical serial-only behavior
- **Gradual Migration**: Test external node (tigrog2) while keeping serial node (tigrobot) active
- **Stats Collection**: Both nodes continue to feed traffic statistics regardless of setting

**Configuration:**
```python
PROCESS_TCP_COMMANDS = False  # Default: serial-only (historical)
PROCESS_TCP_COMMANDS = True   # Enable: accept commands from both serial and TCP
```

**Architecture Change:**
- **Before**: Only serial interface (tigrobot) could trigger commands, TCP (tigrog2) was stats-only
- **After**: Both serial (tigrobot) and TCP (tigrog2) can trigger commands when enabled
- **Phase 2 Filtering**: Modified in `main_bot.py` to respect PROCESS_TCP_COMMANDS setting

**Use Cases:**
- Test external node (tigrog2) reliability before full migration
- Compare performance between serial and TCP command processing
- Gradually transition from indoor antenna (tigrobot) to outdoor antenna (tigrog2)
- Maintain redundancy during testing period

**Migration Path:**
1. Set `PROCESS_TCP_COMMANDS = True` in `config.py` - Enable hybrid mode
2. Test tigrog2 command processing for 24-48h
3. Monitor logs and performance
4. If stable, can disable tigrobot or set `PROCESS_TCP_COMMANDS = False` for rollback

**Implementation Details:**
- Configuration option added to `config.py.sample` after line 20
- Phase 2 filtering logic in `main_bot.py` uses `globals().get('PROCESS_TCP_COMMANDS', False)`
- Clear debug messages differentiate stats-only vs command processing modes
- No impact on statistics collection (both nodes always contribute to traffic analytics)

### Mesh Neighbors Feature (December 2025)

New functionality to display and export mesh network neighbor relationships:

**Key Features:**
- **NEIGHBORINFO_APP Collection**: Automatic extraction from Meshtastic packets
- **SQLite Storage**: Persistent neighbor data with 48h retention
- **User Command**: `/neighbors [node]` for querying topology
- **Map Export**: Database-based JSON export (no TCP conflicts)
- **Dual Output**: Compact for LoRa (180 chars), detailed for Telegram

**Usage:**
```
/neighbors               → All neighbors (compact)
/neighbors tigro         → Filter by node name
/neighbors F547F         → Filter by node ID
```

**Database Schema:**
- Table: `neighbors`
- Columns: node_id, neighbor_id, snr, last_rx_time, node_broadcast_interval, timestamp
- Indexes: timestamp, node_id, composite (node_id, neighbor_id, timestamp)
- Cleanup: Automatic with 48h retention

**Map Integration:**
- `export_neighbors_from_db.py` - Database-based export script
- `infoup_db.sh` - Updated map generation workflow
- Eliminates TCP connection conflicts
- Compatible with existing HTML maps

**Implementation:**
- `traffic_persistence.py::save_neighbor_info()` - Save to database
- `traffic_persistence.py::load_neighbors()` - Query with time filters
- `traffic_persistence.py::export_neighbors_to_json()` - JSON export
- `traffic_monitor.py::_extract_neighbor_info()` - Packet parsing
- `traffic_monitor.py::get_neighbors_report()` - Format for display
- `network_commands.py::handle_neighbors()` - Command handler

**Benefits:**
1. ✅ No TCP session conflicts (map vs bot)
2. ✅ Historical neighbor data
3. ✅ User-accessible topology info
4. ✅ Automatic data collection
5. ✅ Compatible with existing maps

See `map/README_NEIGHBORS.md` for detailed documentation and migration guide.

### Database Management System (November 2025)

New unified `/db` command for database operations:

**Key Features:**
- **Single Entry Point**: `/db` command with sub-commands
- **Maintenance Operations**: Stats, vacuum, cleanup, reset
- **Channel Adaptation**: Compact output for Mesh (180 chars), detailed for Telegram
- **Safety Checks**: Confirmations required for destructive operations

**Sub-commands:**
- `/db` or `/db help` - Show help
- `/db stats` - Database statistics (size, records, age)
- `/db vacuum` - Optimize database (reclaim space)
- `/db cleanup [hours]` - Remove old data (default: 48h retention)
- `/db reset` - Full database reset (requires confirmation)

**Architecture:**
- `handlers/command_handlers/db_commands.py` - Database operations handler
- Integrated with `TrafficPersistence` for safe operations
- Throttling and authorization checks

### Weather Enhancements (November 2025)

The `/weather` command has been significantly enhanced with new subcommands:

**New Subcommands:**
- `/weather` - Standard weather forecast (geolocated or custom city)
- `/weather rain [city] [days]` - Precipitation graphs with hourly resolution
  - Sparkline rain graphs for 1 or 3 days
  - 72-point resolution (hourly data)
  - Max-window sampling to preserve rain peaks
  - Day-by-day messages for clarity
- `/weather astro [city]` - Astronomical data
  - Sunrise/sunset times
  - Moon phase with emoji representation
  - Solar noon and day length
  - UV index

**Usage Examples:**
```
/weather                    → Local forecast
/weather Paris             → Paris forecast
/weather rain              → Local rain graph (today)
/weather rain 3            → Local rain graph (3 days)
/weather rain Paris 3      → Paris rain graph (3 days)
/weather astro             → Local astronomical data
/weather astro London      → London astronomical data
/weather blitz             → Lightning strikes detected (15min window)
/weather vigi              → Météo-France VIGILANCE status
```

**Implementation:**
- `utils_weather.py::get_rain_graph()` - Rain graph generation
- `utils_weather.py::get_weather_astro()` - Astronomical data fetching
- `blitz_monitor.py::_format_report()` - Lightning strike reporting
- `vigilance_monitor.py::format_alert_message()` - Vigilance status formatting
- Integration with wttr.in API for weather data
- Integration with Blitzortung.org MQTT for lightning
- Integration with Météo-France vigilance website via web scraping
- Multi-message support for 3-day rain forecasts

### CLI Improvements (November 2025)

**Command History Navigation:**
- Interactive command history with ↑/↓ arrow keys
- Persistent history across CLI sessions
- Readline integration for full terminal experience
- UTF-8 encoding fixes for special characters

**Enhanced User Experience:**
- Fixed UTF-8 encoding errors in CLI client/server communication
- Improved error handling and connection management
- Better response formatting for CLI output
- Command history documented in `CLI_USAGE.md`

**Documentation:**
- New `CLI_USAGE.md` file with comprehensive CLI usage guide
- Examples for all CLI-specific features
- Troubleshooting section for common issues

### Statistics Display Improvements (November 2025)

**Channel Stats with LongName:**
- Display human-readable node names in `/stats channel`
- Convert numeric node IDs to LongName for better readability
- Comprehensive channel utilization summaries for Telegram
- Ultra-compact format for Mesh (under 180 chars)

**Sparkline Histograms:**
- Visual sparkline representation of data distributions
- Compact histogram display for mesh channel
- `get_histogram_report()` method for packet type visualization

**Stats Command Behavior:**
- `/stats` without parameters now shows help (instead of global stats)
- More intuitive for new users
- Help text adapts to channel (Mesh vs Telegram)

### Codebase Cleanup (November 2025)

**Removed Obsolete Components:**
- `debug_interface.py` - 578 lines removed (replaced by CLI platform)
- `packet_history.py` - Old packet storage system (superseded by TrafficPersistence)
- Reduced debug noise in `/trace` and `/my` commands

**Code Quality:**
- Better separation of concerns
- Reduced redundancy
- Improved maintainability

### Real-Time Monitoring Systems (November 2025)

New automated monitoring capabilities for environmental alerts:

#### Lightning Detection (BlitzMonitor)

**Key Features:**
- **Real-time Detection**: MQTT connection to Blitzortung.org public server
- **Geographic Filtering**: Geohash-based filtering for configurable radius (default: 50km)
- **Auto-positioning**: Automatic GPS detection from Meshtastic node
- **Deque-based History**: Recent strikes stored with timestamp, distance, polarity
- **Periodic Reporting**: Configurable check intervals (default: 15 minutes)
- **Dual Output**: Compact format for LoRa (180 chars), detailed for Telegram

**Architecture:**
- `blitz_monitor.py` - Standalone lightning monitoring module
- MQTT client running in background thread
- Haversine distance calculations for radius filtering
- Multi-geohash subscription for edge coverage

**Configuration:**
```python
BLITZ_ENABLED = True
BLITZ_LATITUDE = 0.0  # 0.0 = auto-detect from node GPS
BLITZ_LONGITUDE = 0.0
BLITZ_RADIUS_KM = 50
BLITZ_CHECK_INTERVAL = 900  # 15 minutes
BLITZ_WINDOW_MINUTES = 15
```

**Use Cases:**
- Automatic storm warnings to mesh network
- Lightning proximity alerts for outdoor activities
- Weather safety monitoring for field operations

#### Weather Vigilance Monitoring (VigilanceMonitor)

**Key Features:**
- **Météo-France Integration**: Official French weather vigilance API
- **Department-based**: Monitor specific French departments by number
- **Alert Levels**: Vert/Jaune/Orange/Rouge color-coded severity
- **Smart Throttling**: Configurable alert frequency (default: 1 hour minimum)
- **Automatic Alerts**: Trigger on Orange/Rouge levels only
- **Bulletin Tracking**: Avoid duplicate alerts for same bulletin

**Architecture:**
- `vigilance_monitor.py` - Weather vigilance monitoring module
- `vigilance_scraper.py` - Web scraper for Météo-France vigilance data
- Periodic checks with configurable intervals
- State tracking for color changes

**Configuration:**
```python
VIGILANCE_ENABLED = True
VIGILANCE_DEPARTEMENT = '25'  # Department number (Doubs)
VIGILANCE_CHECK_INTERVAL = 28800  # 8 hours
VIGILANCE_ALERT_THROTTLE = 3600  # 1 hour minimum between alerts
VIGILANCE_ALERT_LEVELS = ['Orange', 'Rouge']
```

**Use Cases:**
- Automatic severe weather warnings
- Community safety alerts
- Emergency preparedness notifications

#### Integration into Main Bot

Both monitors are integrated into `main_bot.py`:
- Initialized during bot startup
- Periodic checks run in `periodic_cleanup()` method
- BlitzMonitor runs MQTT client in background thread
- Automatic alert generation to mesh network
- Optional integration with Telegram alert system

---

## Architecture

### Core Design Principles

1. **Modularity**: Each component has a single, well-defined responsibility
2. **Fail-Safe**: Graceful degradation when external services are unavailable
3. **Observability**: Comprehensive logging at every layer
4. **Resource-Conscious**: Memory cleanup, caching, rate limiting
5. **Dual-Channel Philosophy**: LoRa ≠ Telegram (different constraints, different configs)

### Three-Phase Message Processing

All incoming messages go through this pipeline (see `main_bot.py::on_message()`):

```python
# Phase 1: COLLECTION (no filtering)
# ALL packets (serial + TCP) are collected for statistics
node_manager.update_node_from_packet(packet)
traffic_monitor.add_packet(packet, source=source)

# Phase 2: FILTERING
# Only serial interface messages trigger commands
# TCP packets (from tigrog2) are stats-only
if not is_from_serial:
    return  # Don't process commands from TCP

# Phase 3: COMMAND PROCESSING
# Route text messages to appropriate handlers
if portnum == 'TEXT_MESSAGE_APP':
    message_handler.process_text_message(packet, decoded, message)
```

**Critical**: This prevents duplicate command execution while maintaining complete traffic statistics.

### Component Hierarchy

```
MeshBot (Orchestrator)
├── MessageHandler (Backward compat wrapper)
│   └── MessageRouter (Command dispatcher)
│       ├── AICommands (/bot)
│       ├── NetworkCommands (/nodes, /my, /trace)
│       ├── SystemCommands (/sys, /rebootpi)
│       ├── UnifiedStatsCommands (/stats with sub-commands)
│       ├── StatsCommands (Legacy: /top, /histo, /packets)
│       ├── MeshCommands (/echo)
│       └── UtilityCommands (/help, /power, /weather, etc.)
├── MessageSender (Throttling + chunking)
├── NodeManager (Node database + GPS)
├── TrafficMonitor (Packet analytics)
│   └── TrafficPersistence (SQLite layer)
├── ContextManager (AI conversation history)
├── LlamaClient (AI queries)
├── ESPHomeClient (Solar/battery telemetry)
├── RemoteNodesClient (TCP queries to tigrog2)
├── BlitzMonitor (Real-time lightning detection)
├── VigilanceMonitor (Météo-France alerts)
└── PlatformManager (Multi-platform orchestrator)
    └── TelegramPlatform (Telegram integration)
        ├── AlertManager (Alert notifications)
        └── Command Modules
            ├── BasicCommands (/help, /start)
            ├── AICommands (/bot)
            ├── NetworkCommands (/nodes, /my)
            ├── StatsCommands (/top, /histo, /stats)
            ├── SystemCommands (/sys, /reboot)
            ├── MeshCommands (/echo)
            ├── AdminCommands (Admin operations)
            ├── TraceCommands (/trace)
            └── UtilityCommands (Misc utilities)
```

---

## Codebase Structure

### Directory Layout

```
/home/user/meshbot/
├── main_script.py              # Entry point (CLI arg parsing)
├── main_bot.py                 # MeshBot class (orchestrator)
├── config.py.sample            # Configuration template
├── platform_config.py          # Platform-specific configs
│
├── handlers/                   # Message processing layer (Mesh)
│   ├── message_router.py       # Command dispatcher
│   ├── message_sender.py       # Delivery + throttling
│   └── command_handlers/       # Domain-specific handlers
│       ├── ai_commands.py      # /bot
│       ├── network_commands.py # /nodes, /my, /trace
│       ├── system_commands.py  # /sys, /rebootpi
│       ├── stats_commands.py   # Legacy stats commands
│       ├── unified_stats.py    # Unified /stats command (NEW)
│       ├── mesh_commands.py    # /echo
│       ├── utility_commands.py # /help, /power, /weather, etc.
│       ├── db_commands.py      # /db database operations (NEW)
│       └── signal_utils.py     # Signal formatting utilities
│
├── platforms/                  # Multi-platform architecture
│   ├── __init__.py             # Platform exports
│   ├── platform_interface.py   # Abstract platform interface
│   ├── platform_manager.py     # Platform orchestrator
│   ├── telegram_platform.py    # Telegram platform implementation
│   ├── cli_server_platform.py  # CLI TCP server platform (localhost:9999)
│   └── discord_platform.py     # Discord platform (future)
│
├── telegram_bot/               # Telegram-specific implementation
│   ├── command_base.py         # Base class for Telegram commands
│   ├── alert_manager.py        # Alert notification system
│   ├── traceroute_manager.py   # Traceroute functionality
│   └── commands/               # Telegram command modules
│       ├── basic_commands.py   # /help, /start
│       ├── ai_commands.py      # /bot
│       ├── network_commands.py # /nodes, /my
│       ├── stats_commands.py   # /top, /histo, /stats
│       ├── system_commands.py  # /sys, /reboot
│       ├── mesh_commands.py    # /echo
│       ├── admin_commands.py   # Admin operations
│       ├── trace_commands.py   # /trace
│       └── utility_commands.py # Misc utilities
│
├── map/                        # Mesh network visualization
│   ├── generate_mesh_map.py    # Generate network topology map
│   ├── export_neighbors.py     # Export neighbor relationships
│   ├── info_json_clean.py      # Clean node info JSON
│   ├── infoup.sh               # Update script
│   ├── mesh_map.html           # Network topology visualization
│   ├── map.html                # Node map
│   └── meshlink.html           # Link map
│
├── node_manager.py             # Node database (JSON)
├── traffic_monitor.py          # Packet analytics (deques + SQLite)
├── traffic_persistence.py      # SQLite layer
├── context_manager.py          # AI conversation context
│
├── llama_client.py             # Llama.cpp integration
├── esphome_client.py           # ESPHome telemetry
├── esphome_history.py          # ESPHome data storage
├── remote_nodes_client.py      # Remote mesh node queries (TCP)
├── blitz_monitor.py            # Lightning detection (Blitzortung.org MQTT)
├── vigilance_monitor.py        # Weather vigilance (Météo-France)
│
├── blitz_monitor.py            # Blitzortung lightning monitoring (NEW)
├── vigilance_monitor.py        # Météo-France vigilance alerts (NEW)
│
├── telegram_integration.py     # Legacy Telegram bot (deprecated)
├── telegram_command_base.py    # Legacy base class (deprecated)
│
├── cli_client.py               # Standalone CLI client (interactive)
│
├── utils.py                    # Logging utilities
├── utils_weather.py            # Weather fetching (wttr.in)
├── system_monitor.py           # CPU/RAM monitoring
├── system_checks.py            # Pre-flight checks (temp, battery)
│
├── safe_serial_connection.py   # Serial wrapper
├── safe_tcp_connection.py      # TCP wrapper
├── tcp_interface_patch.py      # Meshtastic TCP fixes
│
├── message_handler.py          # Legacy wrapper (use MessageRouter)
│
├── diagnostic_traffic.py       # Diagnostic script
├── migrate_packets_to_db.py    # Migration script
├── browse_traffic_db.py        # Web UI for traffic DB
├── view_traffic_db.py          # CLI DB viewer
│
├── meshbot.service             # Systemd service (bot)
├── README.md                   # User documentation
├── CLAUDE.md                   # This file (AI assistant guide)
├── BROWSE_TRAFFIC_DB.md        # Traffic DB web UI docs
├── TRAFFIC_DB_VIEWER.md        # Traffic DB CLI docs
└── .gitignore                  # Git ignore rules
```

### Critical Files for Understanding Message Flow

1. **`main_bot.py::on_message()`** - Entry point for all packets
2. **`handlers/message_router.py`** - Command routing logic
3. **`handlers/message_sender.py`** - Throttling and delivery
4. **Command handlers** - Domain-specific logic

### Critical Files for Data Management

1. **`node_manager.py`** - Node database (names, GPS, RX history)
2. **`traffic_monitor.py`** - In-memory + SQLite packet analytics
3. **`traffic_persistence.py`** - SQLite schema and queries
4. **`context_manager.py`** - AI conversation context

---

## Key Conventions

### Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Files | `snake_case.py` | `message_handler.py` |
| Classes | `PascalCase` | `MeshBot`, `NodeManager` |
| Functions | `snake_case()` | `get_node_name()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_MESSAGE_SIZE` |
| Private methods | `_prefix()` | `_format_node_line()` |
| Global config | `UPPER_SNAKE_CASE` | `SERIAL_PORT` |

### Code Organization Patterns

#### 1. Handler Pattern (Strategy)

New commands follow this pattern:

```python
# In handlers/command_handlers/<domain>_commands.py
class DomainCommands:
    def __init__(self, sender, node_manager, ...):
        self.sender = sender
        self.node_manager = node_manager

    def handle_mycommand(self, sender_id, sender_info, args):
        # 1. Check throttling
        if not self.sender.check_throttling(sender_id, sender_info):
            return

        # 2. Generate response
        response = self._generate_response(args)

        # 3. Send (handles chunking)
        self.sender.send_chunks(response, sender_id, sender_info)

    def _generate_response(self, args):
        # Private helper for response generation
        return "Response text"

# In handlers/message_router.py
def process_text_message(self, packet, decoded, message):
    ...
    elif message.startswith('/mycommand'):
        args = message[11:].strip()
        self.domain_handler.handle_mycommand(sender_id, sender_info, args)
```

#### 2. Client Pattern (External Services)

```python
class ServiceClient:
    def __init__(self):
        self._cache = {}  # Optional caching

    def query(self, params):
        try:
            # Make HTTP request
            response = requests.get(url, timeout=5)
            data = response.json()

            # Cleanup (important!)
            response.close()
            del response
            gc.collect()

            return self._format_response(data)

        except Exception as e:
            error_print(f"Service error: {e}")
            return "Error: Service unavailable"

    def _format_response(self, data):
        # Format data for display
        return formatted_text
```

#### 3. Persistence Pattern

```python
# Write path
traffic_monitor.add_packet(packet)
  → persistence.save_packet(packet)  # Immediate SQLite write

# Read path (with time filtering)
packets = persistence.load_packets(hours=24)
stats = traffic_monitor.generate_stats_from_packets(packets)

# Cleanup (periodic)
persistence.cleanup_old_data(max_age_hours=48)
```

### Error Handling Patterns

#### Pattern 1: Try-Except-Log

```python
try:
    result = risky_operation()
    return result
except Exception as e:
    error_print(f"Operation failed: {e}")
    error_print(traceback.format_exc())
    return fallback_value
```

#### Pattern 2: Graceful Degradation

```python
# Example: LlamaClient pre-flight checks
allowed, block_reason = SystemChecks.check_llm_conditions()
if not allowed:
    return block_reason  # User-friendly message

# If check itself fails, continue anyway (fail-open)
try:
    # Check system
except Exception as check_error:
    error_print(f"Check failed: {check_error}")
    # Continue with request
```

#### Pattern 3: Resource Cleanup

```python
try:
    response = requests.get(url, timeout=5)
    data = response.json()
    return process(data)
finally:
    response.close()
    del response
    gc.collect()  # Explicit memory cleanup
```

### Logging Utilities (`utils.py`)

```python
from utils import debug_print, info_print, error_print, conversation_print

debug_print("Verbose debug info")     # Only if DEBUG_MODE=True, stderr
info_print("Important event")         # Always shown, stdout
conversation_print("AI says: ...")    # AI conversations
error_print("Error occurred")         # Timestamped errors with trace
```

**Convention**: Use appropriate log level for each message type.

---

## Development Workflows

### Git Workflow

#### Branching Strategy

```bash
# Feature branches follow pattern: claude/<description>-<session-id>
claude/fix-french-text-01E9d9UjuZxwVQSU79pBabuu
claude/analyze-packet-traffic-diagnostics-01VVMUenRjQUwTb6KCh8uodL

# Main branch: main (no separate develop branch observed)
```

#### Typical Development Cycle

```bash
# 1. Create feature branch
git checkout -b claude/feature-name-<session-id>

# 2. Make changes
# ... edit files ...

# 3. Test manually (no automated tests)
python main_script.py --debug

# 4. Commit with descriptive messages
git add <files>
git commit -m "Fix: Correct French text encoding in README.md"

# 5. Push to remote
git push -u origin claude/feature-name-<session-id>

# 6. Create pull request (via GitHub web UI or gh cli)
# 7. Merge to main after review
```

#### Commit Message Style

From recent history:
```
Fix: <description>      # Bug fixes
Add: <description>      # New features
Update: <description>   # Enhancements
Refactor: <description> # Code restructuring
```

### Configuration Changes

1. **Never commit `config.py`** (gitignored)
2. **Always update `config.py.sample`** with new options
3. **Document new config options** in comments
4. **Provide sensible defaults**

Example:
```python
# Configuration for new feature
NEW_FEATURE_ENABLED = True  # Enable/disable new feature
NEW_FEATURE_THRESHOLD = 42  # Threshold value in units
```

### Adding New Commands

#### Step-by-Step Process

```python
# 1. Choose appropriate handler file
#    - AI features → ai_commands.py
#    - Network/node queries → network_commands.py
#    - System management → system_commands.py
#    - Statistics → stats_commands.py
#    - Mesh operations → mesh_commands.py
#    - General utilities → utility_commands.py

# 2. Add handler method to class
# File: handlers/command_handlers/utility_commands.py
class UtilityCommands:
    def handle_newcmd(self, sender_id, sender_info):
        # Throttling is critical
        if not self.sender.check_throttling(sender_id, sender_info):
            return

        # Generate response
        response = self._generate_newcmd_response()

        # Send (auto-chunks if > MAX_MESSAGE_SIZE)
        self.sender.send_chunks(response, sender_id, sender_info)

    def _generate_newcmd_response(self):
        # Keep it under 180 chars for LoRa
        return "Response text"

# 3. Route in MessageRouter
# File: handlers/message_router.py
def process_text_message(self, packet, decoded, message):
    ...
    elif message.startswith('/newcmd'):
        self.utility_handler.handle_newcmd(sender_id, sender_info)

# 4. Add to help text
# File: handlers/command_handlers/utility_commands.py
def handle_help(self, ...):
    help_text = """
    ...
    /newcmd - Description of new command
    """

# 5. Test manually
# Send "/newcmd" via Meshtastic or Telegram
```

### Adding New Clients/Integrations

```python
# 1. Create new client file
# File: new_service_client.py
import requests
from utils import error_print, debug_print
import gc

class NewServiceClient:
    def __init__(self, host, port):
        self.base_url = f"http://{host}:{port}"
        self._cache = {}

    def query_data(self, param):
        try:
            url = f"{self.base_url}/endpoint"
            response = requests.get(url, timeout=5)
            data = response.json()

            # Cleanup
            response.close()
            del response
            gc.collect()

            return self._format_data(data)

        except Exception as e:
            error_print(f"NewService error: {e}")
            return None

    def _format_data(self, data):
        return f"Formatted: {data}"

# 2. Add to MeshBot initialization
# File: main_bot.py
class MeshBot:
    def __init__(self):
        ...
        self.new_service = NewServiceClient(
            host=config.NEW_SERVICE_HOST,
            port=config.NEW_SERVICE_PORT
        )

# 3. Add config to config.py.sample
NEW_SERVICE_HOST = "192.168.1.100"
NEW_SERVICE_PORT = 8080

# 4. Use in command handler
# File: handlers/command_handlers/utility_commands.py
def handle_newdata(self, sender_id, sender_info):
    data = self.meshbot.new_service.query_data("param")
    if data:
        self.sender.send_chunks(data, sender_id, sender_info)
```

---

## Common Tasks

### Task 1: Adding a New Statistic to Traffic Monitor

```python
# 1. Update TrafficMonitor data structures
# File: traffic_monitor.py
class TrafficMonitor:
    def __init__(self):
        ...
        self.new_metric = defaultdict(int)  # Add new metric

    def add_packet(self, packet, source='local'):
        ...
        # Calculate and store new metric
        self.new_metric[from_id] += calculate_new_metric(packet)

# 2. Add SQLite persistence (optional)
# File: traffic_persistence.py
# Add column to appropriate table or create new table

# 3. Create reporting method
# File: traffic_monitor.py
def get_new_metric_report(self, hours=24):
    packets = self.persistence.load_packets(hours=hours)
    # Calculate metric from packets
    return formatted_report

# 4. Add command handler
# File: handlers/command_handlers/stats_commands.py
def handle_newmetric(self, sender_id, sender_info):
    report = self.traffic_monitor.get_new_metric_report(hours=24)
    self.sender.send_chunks(report, sender_id, sender_info)

# 5. Route command
# File: handlers/message_router.py
elif message.startswith('/newmetric'):
    self.stats_handler.handle_newmetric(sender_id, sender_info)
```

### Task 2: Modifying AI Behavior

```python
# AI config is in config.py
MESH_AI_CONFIG = {
    "system_prompt": "Your new instructions here...",
    "max_tokens": 1500,
    "temperature": 0.7,  # Adjust creativity (0.0-1.0)
    "top_p": 0.95,
    "top_k": 20,
    "timeout": 60,
    "max_response_chars": 320  # LoRa constraint
}

TELEGRAM_AI_CONFIG = {
    # Longer, more detailed responses
    "max_tokens": 4000,
    "max_response_chars": 3000
}

# LlamaClient automatically uses correct config based on channel
# See: llama_client.py::query()
```

### Task 3: Adding System Protection Checks

```python
# File: system_checks.py
class SystemChecks:
    @staticmethod
    def check_llm_conditions():
        # CPU temp check
        cpu_temp = SystemChecks.get_cpu_temp()
        if cpu_temp and cpu_temp > 60:
            return False, f"⚠️ CPU: {cpu_temp:.1f}°C (trop chaud)"

        # Battery check
        battery_voltage = SystemChecks.get_battery_voltage()
        if battery_voltage and battery_voltage < 12.0:
            return False, f"🔋 Batterie: {battery_voltage:.1f}V (faible)"

        # Add new check here
        if new_condition_not_met():
            return False, "Reason for blocking"

        return True, None

# LlamaClient calls this before each query
# See: llama_client.py::query()
```

### Task 4: Adjusting Throttling Limits

```python
# File: config.py
MAX_COMMANDS_PER_WINDOW = 5  # Number of commands allowed
COMMAND_WINDOW_SECONDS = 300  # Time window (5 minutes)

# Example: Allow 10 commands per 10 minutes
MAX_COMMANDS_PER_WINDOW = 10
COMMAND_WINDOW_SECONDS = 600

# MessageSender automatically enforces these limits
# See: handlers/message_sender.py::check_throttling()
```

### Task 5: Adding Database Tables/Columns

```python
# File: traffic_persistence.py
def _init_db(self):
    cursor = self.conn.cursor()

    # Add new table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS new_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            data TEXT,
            value INTEGER
        )
    """)

    # Add index
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_new_table_timestamp
        ON new_table(timestamp)
    """)

    self.conn.commit()

# Add save/load methods
def save_new_data(self, data):
    cursor = self.conn.cursor()
    cursor.execute("""
        INSERT INTO new_table (timestamp, data, value)
        VALUES (?, ?, ?)
    """, (time.time(), data['text'], data['value']))
    self.conn.commit()

def load_new_data(self, hours=24):
    cutoff = time.time() - (hours * 3600)
    cursor = self.conn.cursor()
    cursor.execute("""
        SELECT * FROM new_table
        WHERE timestamp > ?
        ORDER BY timestamp DESC
    """, (cutoff,))
    return cursor.fetchall()
```

---

## Configuration Management

### Configuration File Structure

The bot uses a **three-tier configuration system** for better security and organization:

1. **`config.py`** - Public configuration (hardware, features, limits, AI)
2. **`config_priv.py`** - Private configuration (tokens, passwords, user IDs) - **gitignored**
3. **`platform_config.py`** - Platform-specific configurations (Telegram, Discord, etc.)

#### Private Configuration (`config_priv.py`)

**NEW:** Sensitive parameters are now isolated in a separate gitignored file.

```python
# config_priv.py.sample - Template (committed to git)
# config_priv.py - Local instance (gitignored, never committed)

# SENSITIVE PARAMETERS ONLY
TELEGRAM_BOT_TOKEN = "******************"
TELEGRAM_AUTHORIZED_USERS = [123456789]
TELEGRAM_ALERT_USERS = [123456789]
TELEGRAM_TO_MESH_MAPPING = {...}
MQTT_NEIGHBOR_PASSWORD = "your_mqtt_password_here"
REBOOT_AUTHORIZED_USERS = [123456789, 0x16fad3dc]
REBOOT_PASSWORD = "your_password_secret"
MESH_ALERT_SUBSCRIBED_NODES = []
CLI_TO_MESH_MAPPING = {}
```

#### Main Configuration (`config.py`)

**PUBLIC PARAMETERS** - Safe to share, commit examples

```python
# config.py.sample - Template (committed to git)
# config.py - Local instance (gitignored)

# IMPORTS PRIVATE CONFIG (with fallback if missing)
try:
    from config_priv import *
except ImportError:
    # Fallback defaults if config_priv.py doesn't exist
    print("⚠️  config.priv.py introuvable!")
    TELEGRAM_BOT_TOKEN = "******************"
    # ... other defaults

# Structure
# ========================================
# HARDWARE CONFIGURATION
# ========================================
SERIAL_PORT = "/dev/ttyACM0"
REMOTE_NODE_HOST = "192.168.1.38"

# ========================================
# EXTERNAL SERVICES
# ========================================
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080
ESPHOME_HOST = "192.168.1.27"

# ========================================
# LIMITS & CONSTRAINTS
# ========================================
MAX_MESSAGE_SIZE = 180  # LoRa constraint
MAX_COMMANDS_PER_WINDOW = 5
COMMAND_WINDOW_SECONDS = 300

# ========================================
# AI CONFIGURATION
# ========================================
MESH_AI_CONFIG = {
    "system_prompt": "...",
    "max_tokens": 1500,
    "temperature": 0.7,
    "max_response_chars": 320  # LoRa constraint
}

TELEGRAM_AI_CONFIG = {
    "system_prompt": "...",
    "max_tokens": 4000,
    "temperature": 0.8,
    "max_response_chars": 3000  # Telegram allows longer
}

# ========================================
# PLATFORM CONFIGURATION
# ========================================
TELEGRAM_ENABLED = True
# NOTE: TELEGRAM_BOT_TOKEN, TELEGRAM_AUTHORIZED_USERS, etc.
#       are imported from config_priv.py

# ========================================
# MONITORING & ALERTS
# ========================================
TEMP_WARNING_THRESHOLD = 60
CPU_WARNING_THRESHOLD = 90
TCP_DISCONNECT_ALERT_ENABLED = True

# ========================================
# DEBUG
# ========================================
DEBUG_MODE = False
```

#### Platform Configuration (`platform_config.py`)

```python
# platform_config.py - Platform-specific settings
from platforms import PlatformConfig
from config import *

# Telegram platform
TELEGRAM_PLATFORM_CONFIG = PlatformConfig(
    platform_name='telegram',
    enabled=TELEGRAM_ENABLED,
    max_message_length=4096,
    chunk_size=4000,
    ai_config=TELEGRAM_AI_CONFIG,
    authorized_users=TELEGRAM_AUTHORIZED_USERS,
    user_to_mesh_mapping=TELEGRAM_TO_MESH_MAPPING,
    extra_config={
        'bot_token': TELEGRAM_BOT_TOKEN,
        'alert_users': TELEGRAM_ALERT_USERS,
        'polling_interval': 5.0,
    }
)

# Discord platform (future)
DISCORD_PLATFORM_CONFIG = PlatformConfig(
    platform_name='discord',
    enabled=False,  # Not yet implemented
    max_message_length=2000,
    chunk_size=1900,
    ai_config={...},
    authorized_users=[],
    user_to_mesh_mapping={},
    extra_config={'bot_token': '...'}
)
```

### Configuration Best Practices

1. **Always update `config.py.sample`** when adding new public options
2. **Always update `config.priv.py.sample`** when adding new sensitive options
3. **Never commit `config.py`** or **`config_priv.py`** (both gitignored)
4. **Separate concerns**: Public params in config.py, sensitive in config_priv.py
5. **Update `platform_config.py`** when adding new platforms
6. **Use descriptive comments** for each option
7. **Group related options** with section headers
8. **Provide sensible defaults** where possible
9. **Document units** (seconds, characters, percent, etc.)
10. **Test platform configs** independently before enabling

#### What Goes Where?

**config.py (Public - Safe to share)**
- Hardware configuration (ports, hosts, IPs)
- Feature enable/disable flags
- Thresholds and intervals
- AI configuration (prompts, limits)
- System limits and tuning parameters
- Non-sensitive network settings

**config_priv.py (Private - Never share)**
- API tokens (Telegram bot token)
- Passwords (reboot, MQTT, etc.)
- User IDs (authorized users, alert recipients)
- User-to-mesh mappings
- Subscribed node lists
- Any data that could compromise security

### Environment-Specific Configuration

```python
# Development
DEBUG_MODE = True
LLAMA_HOST = "localhost"

# Production
DEBUG_MODE = False
LLAMA_HOST = "127.0.0.1"
```

---

## Testing Strategy

### Current State

**No formal automated test suite exists.** Testing is manual and production-based.

### Manual Testing Approach

#### 1. Debug Mode

```bash
# Enable verbose logging
# In config.py:
DEBUG_MODE = True

# Run bot
python main_script.py --debug
```

#### 2. Debug Console

```python
# Available via debug_interface.py
# Commands:
#   test - Test Llama connection
#   mem - Memory stats
#   context - Show conversation context
#   update - Force node DB update
```

#### 3. Testing New Commands

```bash
# Via Meshtastic
# Send message to bot: "/newcommand"

# Via Telegram
# Send message: /newcommand

# Check logs for errors
tail -f /var/log/syslog | grep meshbot
```

#### 4. Testing External Integrations

```python
# Llama
curl http://localhost:8080/health

# ESPHome
curl http://192.168.1.27/sensor/battery_voltage

# Remote node (tigrog2)
# Check if accessible via TCP
```

### Recommended Testing Practices

When making changes, manually verify:

1. **Throttling**: Send rapid commands → verify rate limit works
2. **Chunking**: Send long text → verify splits correctly at 180 chars
3. **Deduplication**: Same packet via serial+TCP → verify counted once
4. **Error handling**: Kill external service → verify graceful failure
5. **Memory**: Monitor with `gc.get_count()` after operations
6. **Character limits**: LoRa messages must stay under 180 chars

### Future Testing Recommendations

```python
# tests/test_message_router.py
def test_command_routing():
    router = MessageRouter(...)
    router.process_text_message(mock_packet, mock_decoded, "/help")
    # Assert help response sent

# tests/test_traffic_monitor.py
def test_deduplication():
    monitor = TrafficMonitor(...)
    monitor.add_packet(packet1, source='local')
    monitor.add_packet(packet1, source='tigrog2')  # Same packet
    assert len(monitor.all_packets) == 1  # Not duplicated

# tests/test_node_manager.py
def test_distance_calculation():
    manager = NodeManager()
    distance = manager.calculate_distance(lat1, lon1, lat2, lon2)
    assert distance == pytest.approx(expected_km, rel=0.01)
```

---

## Performance Patterns

### Memory Management

#### 1. Explicit Cleanup

```python
# After large HTTP requests
response = requests.get(url)
data = response.json()
response.close()
del response
gc.collect()  # Force garbage collection
```

**Where used**: `LlamaClient`, `ESPHomeClient`, `RemoteNodesClient`

#### 2. Bounded Collections

```python
from collections import deque

self.all_packets = deque(maxlen=5000)  # Auto-evicts old items
self.public_messages = deque(maxlen=2000)
```

**Where used**: `TrafficMonitor`, `ContextManager`

#### 3. Lazy Regex Compilation

```python
class LlamaClient:
    def __init__(self):
        self._clean_patterns = None  # Compiled on first use

    def _get_clean_patterns(self):
        if self._clean_patterns is None:
            self._clean_patterns = [
                re.compile(r'<think>.*?</think>', re.DOTALL),
                ...
            ]
        return self._clean_patterns
```

### Network Optimization

#### 1. Caching

```python
class RemoteNodesClient:
    def get_direct_nodes_with_ttl(self, host, port, days=3):
        cache_key = f"{host}:{port}:{days}"

        # Check cache
        if cached := self._cache_get(cache_key):
            return cached

        # Fetch and cache
        data = self._fetch_from_remote(host, port, days)
        self._cache_set(cache_key, data, ttl=60)  # 60 seconds
        return data
```

**TTL**: 60 seconds
**Where used**: `RemoteNodesClient`

#### 2. Deduplication

```python
class TrafficMonitor:
    def add_packet(self, packet, source='local'):
        # Create unique key
        dedup_key = f"{packet_id}_{from_id}_{to_id}"

        # Check if seen recently (5 seconds)
        if dedup_key in self._recent_packets:
            return  # Skip duplicate

        # Store with timestamp
        self._recent_packets[dedup_key] = current_time
```

**Window**: 5 seconds
**Purpose**: Prevent counting same packet from serial + TCP

#### 3. Throttling

```python
class MessageSender:
    def check_throttling(self, sender_id, sender_info):
        now = time.time()
        window_start = now - COMMAND_WINDOW_SECONDS

        # Clean old timestamps
        self.command_timestamps[sender_id] = [
            ts for ts in self.command_timestamps[sender_id]
            if ts > window_start
        ]

        # Check limit
        if len(self.command_timestamps[sender_id]) >= MAX_COMMANDS_PER_WINDOW:
            wait_time = self._calculate_wait_time(sender_id)
            self.send_message(
                f"⏳ Limite atteinte. Attendre {wait_time}",
                sender_id, sender_info
            )
            return False

        return True
```

**Limits**: 5 commands per 5 minutes (configurable)

### Database Optimization

#### 1. Indexes

```sql
CREATE INDEX idx_packets_timestamp ON packets(timestamp);
CREATE INDEX idx_packets_from_id ON packets(from_id);
CREATE INDEX idx_packets_type ON packets(packet_type);
```

**Purpose**: Fast filtering on time, sender, and type

#### 2. Periodic Cleanup

```python
def cleanup_old_data(self, max_age_hours=48):
    cutoff = time.time() - (max_age_hours * 3600)
    cursor = self.conn.cursor()

    cursor.execute("DELETE FROM packets WHERE timestamp < ?", (cutoff,))
    cursor.execute("DELETE FROM public_messages WHERE timestamp < ?", (cutoff,))

    self.conn.commit()
    cursor.execute("VACUUM")  # Reclaim space
```

**Frequency**: Every 5 minutes (via `MeshBot.periodic_cleanup()`)
**Retention**: 48 hours

#### 3. Batching (Future Improvement)

Currently, packets are saved individually. Consider batching for better performance:

```python
# Current (immediate)
def add_packet(self, packet):
    self.persistence.save_packet(packet)

# Improved (batched)
def add_packet(self, packet):
    self.pending_packets.append(packet)

def flush_pending_packets(self):
    # Called periodically
    self.persistence.save_packets_batch(self.pending_packets)
    self.pending_packets.clear()
```

---

## Security Considerations

### Authentication & Authorization

#### 1. Telegram User Filtering

```python
# config.py
TELEGRAM_AUTHORIZED_USERS = [12345678, 98765432]

# telegram_integration.py
async def command_handler(update: Update, context):
    user_id = update.effective_user.id

    if user_id not in TELEGRAM_AUTHORIZED_USERS:
        await update.message.reply_text("❌ Non autorisé")
        return

    # Process command
```

**Default**: Empty list = all users allowed
**Recommendation**: Always set authorized users in production

#### 2. Reboot Command Protection

```python
# config.py
REBOOT_AUTHORIZED_USERS = [
    123456789,     # Telegram ID
    0x16fad3dc     # Mesh node ID (hex)
]
REBOOT_PASSWORD = "secret_password"

# handlers/command_handlers/system_commands.py
def handle_rebootpi(self, sender_id, sender_info, password):
    # Check authorization
    if sender_id not in REBOOT_AUTHORIZED_USERS:
        return "❌ Non autorisé"

    # Check password
    if password != REBOOT_PASSWORD:
        return "❌ Mot de passe incorrect"

    # Use semaphore-based signaling (survives read-only filesystem)
    from reboot_semaphore import RebootSemaphore
    
    requester_info = {
        'name': sender_info.get('name', 'unknown'),
        'node_id': hex(sender_id),
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    if RebootSemaphore.signal_reboot(requester_info):
        return "✅ Redémarrage Pi5 programmé"
    else:
        return "❌ Erreur lors du signal reboot"
```

**Security features**:
- Double authentication (user ID + password)
- Audit trail (logs requester)
- Privilege separation (bot doesn't have sudo)
- Hidden from public help text

**Technical improvement**:
- Uses `/dev/shm` (tmpfs in RAM) instead of `/tmp` for signaling
- Works even if main filesystem goes read-only
- File locking via `fcntl.flock()` for robust IPC
- See `REBOOT_SEMAPHORE.md` for details

#### 3. Hidden Commands

```python
# Commands not shown in /help
HIDDEN_COMMANDS = [
    '/rebootpi',
    # Add other admin commands
]

def handle_help(self):
    # Only show public commands
    help_text = """
    /bot - Chat AI
    /nodes - Liste nœuds
    # ... public commands only
    """
```

### System Protection

#### 1. Resource Limits

```python
# system_checks.py
class SystemChecks:
    @staticmethod
    def check_llm_conditions():
        # CPU temperature
        cpu_temp = SystemChecks.get_cpu_temp()
        if cpu_temp and cpu_temp > 60:
            return False, f"⚠️ CPU: {cpu_temp:.1f}°C (trop chaud)"

        # Battery voltage
        battery_voltage = SystemChecks.get_battery_voltage()
        if battery_voltage and battery_voltage < 12.0:
            return False, f"🔋 Batterie: {battery_voltage:.1f}V (faible)"

        return True, None
```

**Philosophy**: Fail-open (if check fails, allow request)
**Purpose**: Protect hardware, prevent thermal throttling

#### 2. Timeout Protection

```python
# All HTTP requests have timeouts
response = requests.get(url, timeout=5)

# LLM queries have longer timeouts
MESH_AI_CONFIG = {"timeout": 60}       # 1 minute
TELEGRAM_AI_CONFIG = {"timeout": 120}  # 2 minutes
```

**Purpose**: Prevent hanging on unresponsive services

#### 3. Input Validation

```python
# Always validate user input
def handle_trace(self, sender_id, sender_info, node_name):
    if not node_name or len(node_name) > 20:
        self.sender.send_message("❌ Nom de nœud invalide", sender_id, sender_info)
        return

    # Sanitize for shell (if needed)
    node_name = node_name.replace(";", "").replace("&", "")
```

### Secrets Management

#### Current Approach

```python
# config.py (gitignored)
TELEGRAM_BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
REBOOT_PASSWORD = "secret"
```

#### Recommended Improvement

```python
# Use environment variables
import os

TELEGRAM_BOT_TOKEN = os.getenv("MESHBOT_TELEGRAM_TOKEN")
REBOOT_PASSWORD = os.getenv("MESHBOT_REBOOT_PASSWORD")

# Or use dedicated secrets manager
# - systemd credentials
# - python-dotenv with .env file
# - HashiCorp Vault (for advanced setups)
```

### Audit Logging

```python
# All reboot requests are logged
# /var/log/bot-reboot.log contains:
# - Timestamp
# - Requester name
# - Requester ID (hex)

# Example log entry:
# 2024-11-15 14:23:45: Redémarrage Pi demandé via signal fichier
# Reboot by UserName
# ID: 0x16fad3dc
# Time: 1699999999
```

**Recommendation**: Rotate logs periodically with logrotate

---

## Troubleshooting

### Common Issues

#### Issue 1: Bot Not Responding to Commands

**Symptoms**: Messages sent but no response

**Checklist**:
1. Check if message is from **serial interface** (TCP messages don't trigger commands)
2. Verify throttling not triggered (5 commands per 5 min)
3. Check logs for errors: `journalctl -u meshbot -f`
4. Verify Meshtastic connection: Check serial interface in logs
5. Test with simple command: `/help`

**Debug**:
```python
# In config.py
DEBUG_MODE = True

# Restart bot
sudo systemctl restart meshbot

# Watch logs
journalctl -u meshbot -f
```

#### Issue 2: AI Not Working

**Symptoms**: `/bot` command fails or times out

**Checklist**:
1. Check llama.cpp is running: `curl http://localhost:8080/health`
2. Check CPU temperature: May be blocking if > 60°C
3. Check battery voltage: May be blocking if < threshold
4. Verify llama.cpp logs: `journalctl -u llamacpp -f`
5. Test direct API: `curl -X POST http://localhost:8080/v1/chat/completions ...`

**Common causes**:
- Llama.cpp crashed (restart: `sudo systemctl restart llamacpp`)
- Model not loaded (check llamacpp logs)
- System protection triggered (temp/battery)

#### Issue 3: Duplicate Statistics

**Symptoms**: Packet counts doubled, nodes counted twice

**Cause**: Deduplication not working

**Fix**:
```python
# traffic_monitor.py
# Verify deduplication logic in add_packet()
# Should have 5-second dedup window

# Check if both serial and TCP are adding packets
# Only one should increment stats
```

#### Issue 4: SQLite Database Locked

**Symptoms**: `database is locked` errors

**Cause**: Multiple threads accessing SQLite

**Fix**:
```python
# Ensure connection has check_same_thread=False
sqlite3.connect(db_path, check_same_thread=False)

# Consider using connection pooling or queue for writes
```

#### Issue 5: Memory Growing Unbounded

**Symptoms**: Bot memory usage increases over time

**Checklist**:
1. Check deque maxlen is set: `deque(maxlen=5000)`
2. Verify cleanup runs periodically: `periodic_cleanup()` every 5 min
3. Check for resource leaks: HTTP responses not closed
4. Monitor with: `gc.get_count()`, `gc.collect()`

**Debug**:
```python
# Add to periodic_cleanup()
import gc
gc.collect()
info_print(f"Memory: {gc.get_count()}")
```

#### Issue 6: Telegram Commands Not Working

**Symptoms**: Telegram bot doesn't respond

**Checklist**:
1. Check bot token is correct in `config.py`
2. Verify telegram integration enabled: `TELEGRAM_ENABLED = True`
3. Check user is authorized: `TELEGRAM_AUTHORIZED_USERS`
4. Test bot connection: `curl https://api.telegram.org/bot<TOKEN>/getMe`
5. Check asyncio loop is running

**Debug**:
```python
# telegram_integration.py
# Add debug logging in command handlers
debug_print(f"Telegram command: {update.message.text}")
```

### Debug Tools

#### 1. Interactive Debug Console

```python
# debug_interface.py
# Available commands:
#   test - Test Llama connection
#   mem - Show memory stats
#   context - Show AI conversation context
#   update - Force node DB update
#   quit - Exit debug console
```

#### 2. Traffic Database Viewer

```bash
# Web UI
python browse_traffic_db.py
# Open http://localhost:5000

# CLI viewer
python view_traffic_db.py
```

#### 3. Diagnostic Script

```bash
# Trace packet collection
python diagnostic_traffic.py
```

#### 4. Manual Database Queries

```bash
sqlite3 traffic_history.db

# List all tables
.tables

# Show recent packets
SELECT * FROM packets ORDER BY timestamp DESC LIMIT 10;

# Show node stats
SELECT * FROM node_stats ORDER BY total_packets DESC;

# Count packets by type
SELECT packet_type, COUNT(*) FROM packets GROUP BY packet_type;
```

### Performance Debugging

#### Monitor CPU/Memory

```bash
# System resources
htop

# Bot process specifically
ps aux | grep python | grep main_script

# Monitor over time
watch -n 5 'ps aux | grep main_script'
```

#### Check Database Size

```bash
ls -lh traffic_history.db
sqlite3 traffic_history.db "SELECT COUNT(*) FROM packets;"
```

#### Monitor Network

```bash
# Meshtastic serial traffic
sudo cat /dev/ttyACM0

# TCP connections
netstat -an | grep 4403  # tigrog2 TCP port
```

---

## Platforms Architecture

### Overview

The codebase now features a **pluggable multi-platform architecture** that allows the bot to interact with multiple messaging platforms simultaneously. This abstraction layer separates platform-specific logic from core bot functionality.

### Design Pattern

```
┌─────────────────────────────────────────────┐
│          MeshBot (Core Logic)               │
└──────────────┬──────────────────────────────┘
               │
        ┌──────▼──────┐
        │  Platform   │
        │  Manager    │
        └──────┬──────┘
               │
       ┌───────┴───────┬─────────────┐
       │               │             │
    ┌──▼────┐     ┌───▼───┐    ┌───▼────┐
    │Telegram│     │Discord│    │ Matrix │
    │Platform│     │(future)│   │(future)│
    └────────┘     └───────┘    └────────┘
```

### Platform Interface

All platforms must implement `MessagingPlatform` abstract class:

```python
# platforms/platform_interface.py
class MessagingPlatform(ABC):
    @abstractmethod
    def start(self):
        """Start the platform (connect, authenticate)"""
        pass

    @abstractmethod
    def stop(self):
        """Stop the platform gracefully"""
        pass

    @abstractmethod
    def send_message(self, user_id, message):
        """Send message to user on this platform"""
        pass

    @abstractmethod
    def is_enabled(self):
        """Check if platform is enabled"""
        pass

    @abstractmethod
    def get_user_mapping(self, platform_user_id):
        """Map platform user to Mesh identity"""
        pass
```

### Adding a New Platform

To add Discord, Matrix, or another platform:

```python
# 1. Define configuration in platform_config.py
DISCORD_PLATFORM_CONFIG = PlatformConfig(
    platform_name='discord',
    enabled=True,
    max_message_length=2000,
    chunk_size=1900,
    ai_config={...},
    authorized_users=[...],
    extra_config={'bot_token': '...'}
)

# 2. Create platform implementation
# platforms/discord_platform.py
class DiscordPlatform(MessagingPlatform):
    def __init__(self, config, message_handler, node_manager, context_manager):
        super().__init__(config, message_handler, node_manager, context_manager)
        self.client = discord.Client(...)

    def start(self):
        # Connect to Discord
        self.client.run(self.config.extra_config['bot_token'])

    def send_message(self, user_id, message):
        # Send via Discord API
        pass

# 3. Register in main_bot.py
if DISCORD_ENABLED:
    discord_platform = DiscordPlatform(
        DISCORD_PLATFORM_CONFIG,
        self.message_handler,
        self.node_manager,
        self.context_manager
    )
    self.platform_manager.register_platform(discord_platform)

# 4. Start all platforms
self.platform_manager.start_all()
```

### Platform Configuration

Configuration is centralized in `platform_config.py`:

```python
# Each platform has its own PlatformConfig
TELEGRAM_PLATFORM_CONFIG = PlatformConfig(
    platform_name='telegram',
    enabled=TELEGRAM_ENABLED,
    max_message_length=4096,
    chunk_size=4000,
    ai_config=TELEGRAM_AI_CONFIG,
    authorized_users=TELEGRAM_AUTHORIZED_USERS,
    user_to_mesh_mapping=TELEGRAM_TO_MESH_MAPPING,
    extra_config={
        'bot_token': TELEGRAM_BOT_TOKEN,
        'alert_users': TELEGRAM_ALERT_USERS,
        'polling_interval': 5.0,
    }
)
```

### Telegram Platform Details

The Telegram platform has been refactored into a modular command structure:

```python
# telegram_bot/commands/
# Each command category is a separate module:
├── basic_commands.py      # /help, /start, /status
├── ai_commands.py         # /bot <query>
├── network_commands.py    # /nodes, /my, /signal
├── stats_commands.py      # /top, /histo, /stats, /packets
├── system_commands.py     # /sys, /reboot, /uptime
├── mesh_commands.py       # /echo
├── admin_commands.py      # Admin-only commands
├── trace_commands.py      # /trace <node>
└── utility_commands.py    # /power, /weather, etc.
```

#### Alert Manager

The `AlertManager` allows sending alerts to configured Telegram users:

```python
# telegram_bot/alert_manager.py
class AlertManager:
    def send_alert(self, message):
        """Send alert to all configured users"""
        for user_id in self.alert_users:
            asyncio.run_coroutine_threadsafe(
                self._send_alert_async(user_id, message),
                self.telegram.loop
            )

# Usage in main bot
if critical_condition:
    self.platform_manager.get_platform('telegram').alert_manager.send_alert(
        "⚠️ Critical: Battery voltage below 11V"
    )
```

### Benefits of Platform Architecture

1. **Separation of Concerns**: Core bot logic independent of platform details
2. **Multi-platform Support**: Run Telegram + Discord + Matrix simultaneously
3. **Easy Testing**: Mock platforms for unit tests
4. **Configuration Flexibility**: Each platform has its own config
5. **Graceful Degradation**: If Telegram fails, other platforms continue
6. **Code Reuse**: Common functionality in base class

---

## Map Generation

The `map/` directory contains tools for visualizing the Meshtastic network topology.

### Available Maps

1. **`mesh_map.html`**: Interactive network topology
   - Shows nodes and their connections
   - Color-coded by signal strength
   - Click nodes for details

2. **`map.html`**: Geographic node map
   - Plots nodes on map based on GPS coordinates
   - Shows coverage areas

3. **`meshlink.html`**: Link quality visualization
   - Shows neighbor relationships
   - Link strength indicators

### Generation Scripts

```bash
# Generate network topology map
cd map/
python generate_mesh_map.py

# Export neighbor relationships
python export_neighbors.py

# Clean node info JSON (removes sensitive data)
python info_json_clean.py

# Auto-update all maps
./infoup.sh
```

### Map Data Sources

Maps are generated from:
- **Node database** (SQLite `meshtastic_nodes` table): Node names, GPS, last seen
- **Traffic database** (`traffic_history.db`): Packet history, signal metrics
- **Neighbor data**: Direct node connections from NEIGHBOR_INFO packets

### Use Cases

- **Network planning**: Identify coverage gaps
- **Performance analysis**: Find weak links
- **Node placement**: Optimize antenna locations
- **Community engagement**: Share network status with members

---

## Dependencies

### System Dependencies (apt/dnf/yum)

**Required:**
- `python3-dev` - Python development headers (required for pygeohash compilation)

**Recommended:**
- `git` - Version control for cloning repository
- `python3-pip` - Python package installer
- `python3-venv` - Virtual environment support

**Installation (Debian/Ubuntu/Raspberry Pi OS):**
```bash
sudo apt-get update
sudo apt-get install python3-dev git python3-pip python3-venv
```

**Installation (Fedora/CentOS/RHEL):**
```bash
sudo dnf install python3-devel git python3-pip
```

### Python Dependencies (pip)

All Python dependencies are documented in `requirements.txt`.

**Core dependencies:**
- `meshtastic>=2.2.0` - Meshtastic protocol library
- `pyserial>=3.5` - Serial port communication
- `bleak>=0.22.3,<0.23.0` - Bluetooth Low Energy (for Bluetooth connections)
- `pyyaml>=6.0.1,<7.0.0` - YAML configuration parsing
- `tabulate>=0.9.0,<0.10.0` - Table formatting
- `pypubsub>=4.0.3` - Message pub/sub system
- `requests>=2.31.0` - HTTP requests library

**Platform integrations:**
- `python-telegram-bot>=21.0` - Telegram Bot API

**Weather & Alerts:**
- `beautifulsoup4>=4.12.0` - HTML parsing for weather vigilance scraping
- `lxml>=4.9.0` - XML/HTML parser (used by BeautifulSoup)

**Environmental monitoring:**
- `paho-mqtt>=2.1.0` - MQTT client for real-time lightning data (Blitzortung.org)
- `pygeohash>=3.2.0` - Geohash encoding for geographic filtering (lightning detection)

**Installation:**
```bash
# From requirements.txt (recommended)
pip install -r requirements.txt --break-system-packages

# Manual installation
pip install meshtastic pyserial bleak pyyaml tabulate pypubsub requests \
    python-telegram-bot beautifulsoup4 lxml paho-mqtt pygeohash --break-system-packages
```

**Note on `--break-system-packages`:**
On Raspberry Pi OS and other systems with externally-managed pip, the `--break-system-packages` flag is required. Alternatively, use a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### External Services

**Required:**
- **Llama.cpp server** - Local LLM inference (see `llama.cpp-integration/READMELLAMA.md`)

**Optional:**
- **ESPHome device** - For solar/battery telemetry (`/power` command)
- **Telegram Bot Token** - For Telegram integration
- **Remote Meshtastic node (TCP)** - For extended node database

---

## External Integrations

### Llama.cpp (AI)

**Protocol**: HTTP REST API (OpenAI-compatible)
**Default**: `http://127.0.0.1:8080`
**Systemd**: `llamacpp.service`

#### Endpoints

```bash
# Health check
curl http://localhost:8080/health

# Chat completion
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a helpful assistant"},
      {"role": "user", "content": "Hello"}
    ],
    "max_tokens": 1500,
    "temperature": 0.7
  }'
```

#### Configuration

See `llama.cpp-integration/READMELLAMA.md` for setup

#### Client Code

`llama_client.py::query()`
- Dual configs (Mesh vs Telegram)
- System protection checks
- Response cleaning (removes `<think>` tags)
- Conversation context integration

---

### ESPHome (Telemetry)

**Protocol**: HTTP
**Default**: `http://192.168.1.27:80`

#### Sensors

```bash
# Battery voltage
curl http://192.168.1.27/sensor/battery_voltage
# {"value": 13.2}

# Solar current
curl http://192.168.1.27/sensor/solar_current
# {"value": 1.5}

# Temperature (BME280)
curl http://192.168.1.27/sensor/temperature
# {"value": 22.5}
```

#### Client Code

`esphome_client.py::get_power_report()`
- Fetches all sensors
- Formats for display
- Stores history in `ESPHomeHistory`

---

### Meshtastic Remote Node (tigrog2)

**Protocol**: TCP (Meshtastic API)
**Default**: `192.168.1.38:4403`

#### Purpose

Query extended node list from remote ROUTER node

#### Client Code

`remote_nodes_client.py::get_direct_nodes_with_ttl()`
- TCP connection via `SafeTCPConnection`
- 60-second cache
- Filters: Direct nodes, time-based (3 days default)
- GPS distance calculations

#### Usage

```python
from remote_nodes_client import RemoteNodesClient

client = RemoteNodesClient()
nodes = client.get_direct_nodes_with_ttl(
    host="192.168.1.38",
    port=4403,
    days=3
)
```

---

### Wttr.in (Weather)

**Protocol**: HTTPS
**Endpoint**: `https://wttr.in/<location>`

#### Client Code

`utils_weather.py::get_weather_report()`
- ASCII art weather forecast
- 3-day forecast
- French language (`?lang=fr`)

#### Usage

```python
from utils_weather import get_weather_report

weather = get_weather_report("Paris")
```

---

### Telegram Bot API

**Protocol**: HTTPS (python-telegram-bot library)
**Documentation**: https://python-telegram-bot.org/

#### Configuration

```python
# config.py
TELEGRAM_ENABLED = True
TELEGRAM_BOT_TOKEN = "your_token_here"
TELEGRAM_AUTHORIZED_USERS = [123456789, ...]
```

#### Client Code

`telegram_integration.py::TelegramIntegration`
- Async/await pattern
- User authentication & mapping
- Bidirectional bridge (Telegram ↔ Meshtastic)
- Rich commands (longer AI, full node lists, graphs)

---

### Blitzortung.org (Lightning Detection)

**Protocol**: MQTT (public server)
**Server**: `blitzortung.ha.sed.pl:1883`
**Topic Pattern**: `blitzortung/1.1/{geohash}`

#### Data Format

```json
{
  "lat": 47.123,
  "lon": 6.456,
  "time": 1234567890.123,
  "alt": 0,
  "pol": 1,
  "mds": 5000
}
```

#### Client Code

`blitz_monitor.py::BlitzMonitor`
- MQTT subscription to geohash-based topics
- Real-time lightning strike detection
- Haversine distance calculations
- Automatic position detection from Meshtastic GPS
- Background thread for MQTT loop

#### Usage

```python
from blitz_monitor import BlitzMonitor

# Auto-detect position from interface
monitor = BlitzMonitor(
    interface=meshtastic_interface,
    radius_km=50,
    check_interval=900
)
monitor.start_monitoring()

# Manual position
monitor = BlitzMonitor(
    lat=47.123,
    lon=6.456,
    radius_km=50
)
```

---

### Météo-France Vigilance API

**Protocol**: HTTPS (web scraping via BeautifulSoup4)
**Coverage**: French departments only
**Update Frequency**: Typically every 6 hours

#### Client Code

`vigilance_monitor.py::VigilanceMonitor` + `vigilance_scraper.py::DepartmentWeatherAlert`
- Department-based weather vigilance monitoring
- Web scraping of https://vigilance.meteofrance.fr
- Color-coded alert levels (Vert/Jaune/Orange/Rouge)
- Automatic alert generation for severe weather
- Smart throttling to avoid alert spam

#### Usage

```python
from vigilance_monitor import VigilanceMonitor

monitor = VigilanceMonitor(
    departement='25',  # Doubs
    check_interval=28800,  # 8 hours
    alert_throttle=3600,  # 1 hour minimum between alerts
    alert_levels=['Orange', 'Rouge']
)

# Check vigilance
info = monitor.check_vigilance()
if info and monitor.should_alert(info):
    message = monitor.format_alert_message(info, compact=True)
    monitor.record_alert_sent()
```

---

### Meshtastic MQTT (Neighbor Collection)

**Protocol**: MQTT (paho-mqtt client)
**Server**: Configurable (e.g., serveurperso.com)
**Purpose**: Collect neighbor topology from entire network

#### Topic Structure

```
msh/<region>/<channel>/2/json/<node_id>/NEIGHBORINFO_APP
```

Wildcard subscription: `msh/+/+/2/json/+/NEIGHBORINFO_APP`

#### Message Format (JSON)

```json
{
  "from": 305419896,
  "to": 4294967295,
  "type": "NEIGHBORINFO_APP",
  "sender": "!12345678",
  "payload": {
    "neighborinfo": {
      "nodeId": 305419896,
      "neighbors": [
        {
          "nodeId": 305419897,
          "snr": 8.5,
          "lastRxTime": 1234567890,
          "nodeBroadcastInterval": 900
        }
      ]
    }
  }
}
```

#### Client Code

`mqtt_neighbor_collector.py::MQTTNeighborCollector`
- Connects to Meshtastic MQTT server
- Subscribes to NEIGHBORINFO_APP topics
- Parses JSON neighbor data
- Saves to SQLite `neighbors` table via `TrafficPersistence`
- Background thread with auto-reconnect
- Statistics and status reporting

#### Usage

```python
from mqtt_neighbor_collector import MQTTNeighborCollector

collector = MQTTNeighborCollector(
    mqtt_server="serveurperso.com",
    mqtt_port=1883,
    mqtt_user="meshdev",
    mqtt_password="password",
    mqtt_topic_root="msh",
    persistence=traffic_persistence
)

collector.start_monitoring()

# Get stats
stats = collector.get_stats()
print(f"Nodes discovered: {stats['nodes_discovered']}")

# Get status report
report = collector.get_status_report(compact=False)
```

#### Configuration

```python
# config.py
MQTT_NEIGHBOR_ENABLED = True
MQTT_NEIGHBOR_SERVER = "serveurperso.com"
MQTT_NEIGHBOR_PORT = 1883
MQTT_NEIGHBOR_USER = "meshdev"
MQTT_NEIGHBOR_PASSWORD = "password"
MQTT_NEIGHBOR_TOPIC_ROOT = "msh"
```

#### Benefits

1. **Extended Visibility**: Collect neighbor data from nodes beyond radio range
2. **Network Topology**: Build complete mesh network map
3. **Automatic Collection**: Passive listening to MQTT stream
4. **Database Integration**: Shares same `neighbors` table as radio-based collection
5. **Redundancy**: Complements direct NEIGHBORINFO_APP packet reception

---

## Appendix: Quick Reference

### Key File Locations

| Component | File | Purpose |
|-----------|------|---------|
| Entry point | `main_script.py` | CLI arg parsing, starts bot |
| Orchestrator | `main_bot.py` | MeshBot class, lifecycle |
| Message routing | `handlers/message_router.py` | Command dispatcher (Mesh) |
| Message delivery | `handlers/message_sender.py` | Throttling + chunking |
| Unified stats | `handlers/command_handlers/unified_stats.py` | Unified /stats command |
| DB commands | `handlers/command_handlers/db_commands.py` | Database operations |
| Command handlers | `handlers/command_handlers/*.py` | Domain logic (Mesh) |
| Platform manager | `platforms/platform_manager.py` | Multi-platform orchestrator |
| Platform interface | `platforms/platform_interface.py` | Abstract platform base |
| Telegram platform | `platforms/telegram_platform.py` | Telegram implementation |
| Telegram commands | `telegram_bot/commands/*.py` | Telegram command modules |
| Alert manager | `telegram_bot/alert_manager.py` | Telegram alerts |
| CLI server platform | `platforms/cli_server_platform.py` | TCP CLI server (localhost:9999) |
| CLI client | `cli_client.py` | Interactive CLI client |
| Node database | `node_manager.py` | GPS, names, RX history |
| Packet analytics | `traffic_monitor.py` | Stats, deduplication |
| SQLite layer | `traffic_persistence.py` | Persistence |
| AI client | `llama_client.py` | Llama.cpp integration |
| Lightning monitor | `blitz_monitor.py` | Real-time lightning detection |
| Vigilance monitor | `vigilance_monitor.py` | Weather vigilance alerts |
| Vigilance scraper | `vigilance_scraper.py` | Météo-France web scraper |
| MQTT neighbor collector | `mqtt_neighbor_collector.py` | MQTT-based neighbor collection |
| Map generation | `map/generate_mesh_map.py` | Network topology maps |
| Configuration | `config.py.sample` | Main config template |
| Platform config | `platform_config.py` | Platform-specific configs |
| Systemd service | `meshbot.service` | Service definition |

### Command Reference

| Command | Handler | Purpose |
|---------|---------|---------|
| `/bot <question>` | `ai_commands.py` | Query AI |
| `/nodes [page]` | `network_commands.py` | List nodes |
| `/neighbors [node]` | `network_commands.py` | Mesh neighbors (NEW) |
| `/my` | `network_commands.py` | Your signal |
| `/trace [node]` | `network_commands.py` | Trace sender or specific node |
| `/sys` | `system_commands.py` | System info |
| `/rebootpi` | `system_commands.py` | Reboot Pi (admin) |
| `/stats [sub]` | `unified_stats.py` | Unified statistics (NEW) |
| `/stats global` | `unified_stats.py` | Network overview |
| `/stats top` | `unified_stats.py` | Top talkers |
| `/stats packets` | `unified_stats.py` | Packet distribution |
| `/stats channel` | `unified_stats.py` | Channel utilization |
| `/stats histo` | `unified_stats.py` | Type histogram |
| `/stats traffic` | `unified_stats.py` | Message history (Telegram) |
| `/top [hours]` | `stats_commands.py` | Top talkers (legacy alias) |
| `/histo [type]` | `stats_commands.py` | Packet histogram (legacy) |
| `/packets` | `stats_commands.py` | Packet stats (legacy) |
| `/echo <msg>` | `mesh_commands.py` | Broadcast on mesh |
| `/power` | `utility_commands.py` | ESPHome data |
| `/weather [sub]` | `utility_commands.py` | Weather forecast |
| `/weather rain` | `utility_commands.py` | Rain precipitation graphs |
| `/weather astro` | `utility_commands.py` | Astronomical data |
| `/weather blitz` | `utility_commands.py` | Lightning strikes (NEW) |
| `/weather vigi` | `utility_commands.py` | VIGILANCE alerts (NEW) |
| `/db [sub]` | `db_commands.py` | Database operations (NEW) |
| `/help` | `utility_commands.py` | Help text |
| `/legend` | `utility_commands.py` | Signal legend |

### Configuration Constants

| Constant | Default | Purpose |
|----------|---------|---------|
| `SERIAL_PORT` | `/dev/ttyACM0` | Serial device |
| `REMOTE_NODE_HOST` | `192.168.1.38` | Router IP |
| `MAX_MESSAGE_SIZE` | `180` | LoRa limit (chars) |
| `MAX_COMMANDS_PER_WINDOW` | `5` | Throttle limit |
| `COMMAND_WINDOW_SECONDS` | `300` | Throttle window (5 min) |
| `MAX_CONTEXT_MESSAGES` | `6` | AI context (3 exchanges) |
| `CONTEXT_TIMEOUT` | `1800` | AI context timeout (30 min) |
| `DEBUG_MODE` | `False` | Verbose logging |

### Database Tables

| Table | Purpose |
|-------|---------|
| `packets` | All packets with metadata |
| `public_messages` | Text messages only |
| `node_stats` | Per-node aggregated stats |
| `global_stats` | Overall network stats |
| `network_stats` | Routing & signal metrics |
| `neighbors` | Mesh neighbor relationships (NEW) |
| `weather_cache` | Weather API cache |

### Logging Functions

| Function | When to Use |
|----------|-------------|
| `debug_print()` | Verbose debug (DEBUG_MODE only) |
| `info_print()` | Important events |
| `conversation_print()` | AI conversations |
| `error_print()` | Errors with traceback |

---

## Document Maintenance

This document should be updated when:
- New commands are added
- Architecture changes significantly
- New external integrations are added
- Configuration options change
- Common issues are discovered
- Performance patterns evolve
- New platforms are added

**Last updated**: 2026-01-31
**Updated by**: GitHub Copilot
**Changes in this update (2026-01-31)**:
- **NEW: Configuration Separation** - Sensitive parameters isolated for better security
  - Created `config.priv.py.sample` for sensitive parameters only (tokens, passwords, user IDs)
  - Updated `config.py.sample` to import from config_priv with graceful fallback
  - Removed duplicate CLI_* parameters (were defined twice in old config)
  - Updated `.gitignore` to include `config.priv.py`
  - Created `CONFIG_MIGRATION.md` with migration guide for existing users
  - Created `test_config_separation.py` with comprehensive test suite
  - Benefits: 
    - ✅ Secrets never committed to git
    - ✅ Easier to share public config
    - ✅ Clear separation between public and private params
    - ✅ No duplicate parameters
    - ✅ Fully backward compatible (config.py imports config_priv automatically)
  - Files affected: config.py.sample, config.priv.py.sample, .gitignore, README.md, CLAUDE.md
  - Testing: All 4 tests pass (import without priv, import with priv, no duplicates, isolation verified)

**Previous changes (2026-01-07)**:
- **NEW: TCP Health Monitoring Improvements** - Configurable health checks and packet reception diagnostics
  - Added `TCP_HEALTH_CHECK_INTERVAL` configuration option in config.py
  - Made TCP health check interval user-configurable (default: 30s)
  - Added packet reception rate tracking (packets/minute over 60s window)
  - Implemented session statistics (packets, duration, rate per TCP session)
  - Enhanced health check logging with packet rate information
  - Added `_get_packet_reception_rate()` method for rate calculation
  - Added `_get_session_stats()` method for session metrics
  - Reset session counters on successful TCP reconnection
  - Created comprehensive test suite: `test_tcp_health_improvements.py`
  - Created documentation: `TCP_HEALTH_MONITORING_IMPROVEMENTS.md`
  - Benefits: Better diagnostics for TCP issues, faster problem detection, data-driven troubleshooting
  - Context: Addresses TCP stability issues after Meshtastic 2.7.15 firmware upgrade
  - Users can now adjust check frequency without code changes
  - Logs show actual packet rates to help identify gradual slowdown vs sudden stops

**Previous changes (2025-12-16)**:
- **NEW: DM Decryption for Meshtastic 2.7.15+** - Support for encrypted Direct Messages
  - Added `_decrypt_packet()` method in `traffic_monitor.py` using AES-128-CTR
  - Automatic detection and decryption of DMs addressed to our node
  - Uses default channel 0 PSK (configurable for custom networks)
  - Converts decrypted protobuf to dict format for processing
  - Added comprehensive test suite: `test_dm_decryption.py`
  - Added interactive demo: `demo_dm_decryption.py`
  - Added documentation: `DM_DECRYPTION_2715.md`
  - Benefits: Bot can now process DM commands in Meshtastic 2.7.15+
  - Privacy: Only decrypts DMs to our node, respects other nodes' privacy
  - Backward compatible: Non-encrypted messages work as before

**Previous changes (2025-12-03)**:
- **NEW: MQTT Neighbor Collection** - Enhanced network topology visibility
  - Added `mqtt_neighbor_collector.py` - Collect neighbor data from MQTT server
  - Subscribe to Meshtastic MQTT topics for NEIGHBORINFO_APP packets
  - Extend neighbor visibility beyond direct radio range
  - Configuration: MQTT_NEIGHBOR_ENABLED, MQTT_NEIGHBOR_SERVER, credentials
  - Integration with existing `neighbors` table in SQLite
  - Benefits: Complete network topology, redundant data collection
  - Server: serveurperso.com (user: meshdev, password in config)
  - Topic pattern: `msh/+/+/2/json/+/NEIGHBORINFO_APP`
  - Background thread with auto-reconnect and retry logic
  - Statistics tracking and status reporting

**Previous changes (2025-12-02)**:
- **NEW: Mesh Neighbors Feature** - Display and export mesh network topology
  - Added `neighbors` table to SQLite database with indexes
  - Automatic extraction from NEIGHBORINFO_APP packets
  - New `/neighbors [node]` command for querying topology
  - Database-based JSON export eliminates TCP connection conflicts
  - Created `map/export_neighbors_from_db.py` for database-based export
  - Created `map/infoup_db.sh` to replace TCP-based workflow
  - Added `map/README_NEIGHBORS.md` with migration guide
  - Methods: `save_neighbor_info()`, `load_neighbors()`, `export_neighbors_to_json()`
  - Dual output format: compact (LoRa 180 chars) and detailed (Telegram)
  - Benefits: No TCP conflicts, historical data, user-accessible topology

**Previous changes (2025-11-23)**:
- **BREAKING: Vigilance Module Replacement** - Replaced broken vigilancemeteo package with web scraping
  - Created `vigilance_scraper.py` - BeautifulSoup4-based web scraper for Météo-France
  - Scrapes https://vigilance.meteofrance.fr/fr/{departement} directly
  - Drop-in replacement with same interface as vigilancemeteo
  - Supports all department mappings (75=Paris, 25=Besançon, etc.)
  - Multi-strategy HTML parsing for robustness
  - Updated `vigilance_monitor.py` to use new scraper
  - Replaced `vigilancemeteo>=3.0.0` with `beautifulsoup4>=4.12.0` and `lxml>=4.9.0` in requirements
  - All existing tests updated and passing

**Previous changes (2025-11-17)**:
- **NEW: Real-Time Lightning Detection** - BlitzMonitor for automatic storm warnings
  - Added `blitz_monitor.py` - MQTT-based lightning detection via Blitzortung.org
  - Real-time strike detection with geohash-based geographic filtering
  - Auto-positioning from Meshtastic GPS or manual lat/lon
  - Configurable radius (default: 50km) and check intervals
  - Background MQTT thread for continuous monitoring
  - Haversine distance calculations for accurate proximity
  - Dual output format: compact (LoRa) and detailed (Telegram)
- **NEW: Weather Vigilance Monitoring** - VigilanceMonitor for Météo-France alerts
  - Added `vigilance_monitor.py` - Automatic weather vigilance alerts
  - Department-based monitoring for French regions
  - Color-coded severity levels (Vert/Jaune/Orange/Rouge)
  - Smart alert throttling (default: 1 hour minimum between alerts)
  - Automatic triggering on Orange/Rouge levels only
  - Bulletin tracking to avoid duplicate alerts
- **INTEGRATION: Main Bot Enhancement**
  - Both monitors integrated into `main_bot.py` periodic cleanup cycle
  - Configurable via `config.py.sample` with enable/disable flags
  - Automatic alert generation to mesh network
  - Optional Telegram integration for detailed alerts
- **DEPENDENCIES: New Python Packages**
  - `paho-mqtt>=2.1.0` - MQTT client for Blitzortung.org
  - `pygeohash>=3.2.0` - Geographic filtering for lightning detection
  - `beautifulsoup4>=4.12.0` - HTML parsing for vigilance scraping
  - `lxml>=4.9.0` - XML/HTML parser
- **DOCUMENTATION: Enhanced External Integrations**
  - Added Blitzortung.org MQTT server documentation
  - Added Météo-France Vigilance API documentation
  - Updated directory structure with new monitor files
  - Updated key file locations table

**Previous changes (2025-11-16)**:
- **NEW: Database Management** - Unified `/db` command for database operations
- **ENHANCED: Weather System** - Major weather command improvements with rain graphs and astronomical data
- **IMPROVED: CLI Experience** - Command history and UTF-8 fixes
- **IMPROVED: Statistics** - Better display and usability
- **CLEANUP: Removed obsolete code** - debug_interface.py and packet_history.py

**Previous major changes (2025-11-15)**:
- **NEW: CLI Server Platform** - TCP-based local CLI for development/debug
- **FIX: /trace command** - Now accepts target node argument
- **REMOVED: /g2 command** - Deprecated and removed

**Previous major changes (v2.0)**:
- Added new **Platforms Architecture** section documenting multi-platform support
- Added new **Map Generation** section for network visualization tools
- Updated directory structure to include `platforms/`, `telegram_bot/`, and `map/` directories
- Documented new `AlertManager` for Telegram notifications
- Added `platform_config.py` to configuration documentation

**Last review**: When significant changes occur or new platforms/features are implemented

---

## Recent Updates to This Document

### 2026-02-03: Documentation Cleanup and Consolidation

**Major documentation reorganization:**
- Archived **412 markdown files** (118,516 lines) to `docs/archive/`
- Retained **13 essential docs** in root directory
- Created **DOCS_INDEX.md** for navigation
- Created **docs/archive/README.md** for archive organization
- Created **TEST_CLEANUP_GUIDE.md** for test/demo organization
- Updated **README.md** with documentation section
- Enhanced **CLAUDE.md** with documentation structure information

**Archive Categories:**
- 73 bug fix docs → `docs/archive/fixes/`
- 44 PR summaries → `docs/archive/pull-requests/`
- 27 implementation notes → `docs/archive/implementations/`
- 42 visual guides → `docs/archive/visual-guides/`
- 11 verification docs → `docs/archive/verification/`
- 15 summary docs → `docs/archive/summaries/`
- 163 feature docs → `docs/archive/features/`
- 36 MeshCore docs → `docs/archive/meshcore/`
- 47 network docs → `docs/archive/network/`

**Benefits:**
1. ✅ Clear documentation navigation
2. ✅ Reduced confusion for new contributors
3. ✅ Easier maintenance
4. ✅ Historical docs preserved but not cluttering
5. ✅ CLAUDE.md remains the single source of truth

**Test/Demo Status:**
- 221 test files analyzed (49 fix-specific candidates for archive)
- 55 demo files analyzed (15 fix-specific candidates for archive)
- Created TEST_CLEANUP_GUIDE.md for future organization

---

## Additional Resources

### Documentation Structure

This project maintains a clean, focused documentation structure:

#### Current Documentation (Root Directory)
- **README.md**: User-facing documentation and setup guide
- **CLAUDE.md**: This file - Comprehensive AI assistant guide
- **DOCS_INDEX.md**: Documentation navigation and index
- **CLI_USAGE.md**: CLI client usage guide with command history features
- **BROWSE_TRAFFIC_DB.md**: Web UI for traffic database
- **TRAFFIC_DB_VIEWER.md**: CLI database viewer
- **STATS_CONSOLIDATION_PLAN.md**: Unified statistics system architecture
- **PLATFORMS.md**: Multi-platform architecture documentation
- **TCP_ARCHITECTURE.md**: Network stack architecture (Meshtastic TCP vs HTTP/MQTT services)
- **ENCRYPTED_PACKETS_EXPLAINED.md**: Guide to encrypted vs direct messages
- **MESHCORE_COMPANION.md**: MeshCore companion mode documentation
- **REBOOT_SEMAPHORE.md**: Reboot mechanism and semaphore-based signaling
- **CONFIG_MIGRATION.md**: Configuration migration guide
- **MIGRATION_GUIDE.md**: General migration guide
- **TEST_CLEANUP_GUIDE.md**: Test and demo file organization guide
- **llama.cpp-integration/README.md**: Llama.cpp setup guide
- **map/README.md**: Map generation and network visualization

#### Archived Documentation (docs/archive/)
Over **412 markdown files** have been archived to maintain focus:
- **fixes/**: Bug fix documentation (73 files)
- **pull-requests/**: PR summaries and implementation notes (44 files)
- **implementations/**: Implementation details (27 files)
- **visual-guides/**: Diagrams and visual explanations (42 files)
- **verification/**: Test plans and diagnostics (11 files)
- **summaries/**: Historical summary documents (15 files)
- **features/**: Individual feature documentation (163 files)
- **meshcore/**: MeshCore-specific docs (36 files)
- **network/**: TCP/MQTT connectivity docs (47 files)
- **other/**: Miscellaneous documentation

See **docs/archive/README.md** for detailed archive index.

#### When to Reference Archives
- Understanding bug fix history
- Detailed implementation notes not in current docs
- Design decision rationale
- Troubleshooting similar past issues

**Do NOT reference archives for:**
- Day-to-day development (use CLAUDE.md)
- Current architecture (use CLAUDE.md, PLATFORMS.md, TCP_ARCHITECTURE.md)
- User documentation (use README.md)
- Setup instructions (use README.md)

### External References

- **Meshtastic Python Docs**: https://meshtastic.org/docs/software/python/cli/
- **python-telegram-bot Docs**: https://python-telegram-bot.org/
- **Llama.cpp**: https://github.com/ggerganov/llama.cpp

### Documentation Maintenance Strategy

**As of 2026-02-03**, the documentation has been cleaned up and consolidated:
- **Before**: 465+ markdown files scattered in root directory
- **After**: 13 essential docs in root + organized archives
- **Benefit**: Clear navigation, reduced confusion, easier maintenance

**Maintenance Guidelines:**
1. Keep root documentation focused and up-to-date
2. Update CLAUDE.md with architectural changes
3. Archive old fix/PR documentation immediately after merge
4. Use DOCS_INDEX.md for navigation
5. Document test purposes in TEST_CLEANUP_GUIDE.md

---

**End of CLAUDE.md**
