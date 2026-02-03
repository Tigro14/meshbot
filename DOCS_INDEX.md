# Documentation Index

## Core Documentation

### User Guides
- **[README.md](README.md)** - Main user guide, setup instructions, and project overview
- **[CLI_USAGE.md](CLI_USAGE.md)** - Command-line interface client usage and features
- **[ENCRYPTED_PACKETS_EXPLAINED.md](ENCRYPTED_PACKETS_EXPLAINED.md)** - Understanding DM encryption in Meshtastic

### Developer Guides
- **[CLAUDE.md](CLAUDE.md)** - Comprehensive AI assistant guide for development (2,968 lines)
  - Project architecture
  - Development workflows
  - Common tasks and patterns
  - Testing strategies
  - Troubleshooting guide

### Architecture Documentation
- **[PLATFORMS.md](PLATFORMS.md)** - Multi-platform architecture (Telegram, Discord, Matrix)
- **[TCP_ARCHITECTURE.md](TCP_ARCHITECTURE.md)** - Network stack architecture and HTTP/MQTT separation
- **[STATS_CONSOLIDATION_PLAN.md](STATS_CONSOLIDATION_PLAN.md)** - Unified statistics system design

### Feature-Specific Guides
- **[MESHCORE_COMPANION.md](MESHCORE_COMPANION.md)** - MeshCore companion mode documentation
- **[REBOOT_SEMAPHORE.md](REBOOT_SEMAPHORE.md)** - Reboot mechanism and semaphore-based signaling

### Migration & Configuration
- **[CONFIG_MIGRATION.md](CONFIG_MIGRATION.md)** - Configuration file migration guide
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - General migration guide

### Database Tools
- **[BROWSE_TRAFFIC_DB.md](BROWSE_TRAFFIC_DB.md)** - Web UI for browsing traffic database
- **[TRAFFIC_DB_VIEWER.md](TRAFFIC_DB_VIEWER.md)** - CLI tool for viewing traffic database

## Directory Structure

```
meshbot/
├── README.md                          # Main user guide
├── CLAUDE.md                          # Developer guide (PRIMARY)
├── DOCS_INDEX.md                      # This file
│
├── handlers/                          # Message processing
│   ├── message_router.py              # Command dispatcher
│   ├── message_sender.py              # Delivery + throttling
│   └── command_handlers/              # Domain-specific handlers
│
├── platforms/                         # Multi-platform support
│   ├── telegram_platform.py           # Telegram integration
│   └── cli_server_platform.py         # CLI server
│
├── telegram_bot/                      # Telegram-specific code
│   └── commands/                      # Telegram command modules
│
├── map/                               # Network visualization
│   └── README.md                      # Map generation guide
│
├── llama.cpp-integration/             # AI integration
│   └── READMELLAMA.md                 # Llama.cpp setup
│
└── docs/                              # Additional documentation
    └── archive/                       # Historical documentation
        └── README.md                  # Archive index
```

## Quick Navigation

### For New Contributors
1. Start with [README.md](README.md) for project overview
2. Read [CLAUDE.md](CLAUDE.md) for comprehensive development guide
3. Check [PLATFORMS.md](PLATFORMS.md) for architecture understanding

### For Users
1. [README.md](README.md) - Setup and installation
2. [CLI_USAGE.md](CLI_USAGE.md) - Using the CLI client
3. [ENCRYPTED_PACKETS_EXPLAINED.md](ENCRYPTED_PACKETS_EXPLAINED.md) - Understanding encryption

### For Developers
1. [CLAUDE.md](CLAUDE.md) - Your primary resource (READ THIS FIRST)
2. [TCP_ARCHITECTURE.md](TCP_ARCHITECTURE.md) - Network architecture
3. [PLATFORMS.md](PLATFORMS.md) - Platform abstraction
4. [STATS_CONSOLIDATION_PLAN.md](STATS_CONSOLIDATION_PLAN.md) - Statistics design

### For Operations
1. [CONFIG_MIGRATION.md](CONFIG_MIGRATION.md) - Configuration updates
2. [REBOOT_SEMAPHORE.md](REBOOT_SEMAPHORE.md) - Remote reboot mechanism
3. [BROWSE_TRAFFIC_DB.md](BROWSE_TRAFFIC_DB.md) - Database monitoring

## Historical Documentation

All historical documentation (bug fixes, PRs, implementations) has been moved to `docs/archive/`.

See [docs/archive/README.md](docs/archive/README.md) for:
- 412 archived markdown files
- Bug fix documentation
- Pull request summaries
- Implementation notes
- Visual guides
- Verification documents

## External Resources

- **Meshtastic Python API**: https://meshtastic.org/docs/software/python/cli/
- **python-telegram-bot**: https://python-telegram-bot.org/
- **Llama.cpp**: https://github.com/ggerganov/llama.cpp

## Document Maintenance

**Primary Documentation (keep updated):**
- CLAUDE.md - Update with architectural changes
- README.md - Update with new features
- PLATFORMS.md - Update when adding platforms

**Last Updated:** 2026-02-03
**Maintained By:** Project contributors
