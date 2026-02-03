# Archived Documentation

This directory contains historical documentation from bug fixes, pull requests, and feature implementations.

## Archive Structure

### `/fixes/` - Bug Fix Documentation (73 files)
Documentation for specific bug fixes and issues resolved. Most of these are historical and superseded by current codebase functionality.

**Topics covered:**
- Broadcast loop fixes
- Echo command fixes
- TCP connection fixes
- Serial port fixes
- CPU usage fixes
- Key synchronization fixes
- And many more...

### `/pull-requests/` - PR Documentation (44 files)
Pull request summaries and implementation details. These document the development history but are not needed for current development.

**Topics covered:**
- PR summaries for major features
- PR feedback and implementation notes
- Visual comparisons of changes

### `/implementations/` - Implementation Summaries (27 files)
Detailed implementation notes for completed features. While historical, some may contain useful technical details.

**Topics covered:**
- Node metrics implementation
- TCP health monitoring
- Telemetry storage
- DM decryption implementation
- MeshCore integration

### `/visual-guides/` - Visual Documentation (42 files)
Diagrams, flowcharts, and visual explanations of features and fixes. Many are superseded by current documentation.

### `/verification/` - Verification & Diagnostic Docs (11 files)
Test plans, verification checklists, and diagnostic guides used during development.

### `/summaries/` - Summary Documents (15 files)
"Final summaries" of multiple fixes bundled together. Historical reference only.

### `/features/` - Feature Documentation (163 files)
Individual feature documentation that has been superseded by core documentation:
- DB commands
- DM encryption
- Dual network mode
- ESPHome integration
- MeshCore features
- MQTT features
- Neighbor tracking
- Node management
- PKI/public key features
- Propag command
- Telemetry features
- And many more...

### `/meshcore/` - MeshCore-Specific Docs (36 files)
MeshCore integration documentation. Core concepts are now in `CLAUDE.md` and `MESHCORE_COMPANION.md`.

### `/network/` - Network & Connectivity (47 files)
TCP and MQTT connectivity documentation. Core architecture is in `TCP_ARCHITECTURE.md`.

### `/other/` - Miscellaneous (Various files)
Answers to questions, migration guides, firmware notes, and other miscellaneous documentation.

## When to Reference Archived Docs

**You should reference these archives when:**
1. Understanding the history of a specific bug or feature
2. Looking for detailed implementation notes not in current docs
3. Understanding why certain design decisions were made
4. Troubleshooting similar issues that occurred in the past

**You should NOT need these for:**
1. Day-to-day development
2. Understanding current architecture (see `CLAUDE.md`)
3. User documentation (see `README.md`)
4. Setting up the bot (see current docs)

## Current Documentation

All current, relevant documentation is maintained in the repository root:
- **README.md** - User guide and setup instructions
- **CLAUDE.md** - Comprehensive AI assistant guide for development
- **PLATFORMS.md** - Multi-platform architecture
- **TCP_ARCHITECTURE.md** - Network stack architecture
- **CLI_USAGE.md** - CLI client reference
- **STATS_CONSOLIDATION_PLAN.md** - Statistics system architecture
- **ENCRYPTED_PACKETS_EXPLAINED.md** - DM encryption guide
- **MESHCORE_COMPANION.md** - MeshCore mode documentation
- **REBOOT_SEMAPHORE.md** - Reboot mechanism documentation
- **CONFIG_MIGRATION.md** - Configuration migration guide
- **MIGRATION_GUIDE.md** - General migration guide
- **BROWSE_TRAFFIC_DB.md** - Traffic database web UI
- **TRAFFIC_DB_VIEWER.md** - Traffic database CLI viewer

## Statistics

- **Total archived files:** 412 markdown files
- **Total archived content:** ~110,000+ lines
- **Archive date:** 2026-02-03
- **Reason:** Documentation consolidation and cleanup
