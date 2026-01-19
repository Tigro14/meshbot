# MeshCore Message Decryption Troubleshooting Guide

## Overview

This guide addresses issues with decrypting Direct Messages (DMs) when using the MeshCore library. The monitor tool (`meshcore-serial-monitor.py`) is designed as a diagnostic tool that relies on the meshcore library to handle message decryption.

## Why Not Add Decryption to the Monitor?

### Problem Statement

A suggestion was made to install `meshcoredecoder` package and add decryption logic directly to the monitor. However, this approach has several issues:

1. **Package Verification**: Cannot verify that `meshcoredecoder` exists as a PyPI package
2. **Scope Creep**: Adding decryption is beyond the current PR's scope (debug mode and heartbeat)
3. **Duplicate Functionality**: This would duplicate what the meshcore library should already provide
4. **Complexity**: Would require:
   - Private key access and secure storage
   - Implementing MeshCore protocol decryption
   - Comprehensive error handling
   - Extensive testing

### Recommended Approach

**The monitor is working as designed** - it's a diagnostic tool that relies on the meshcore library for decryption. If messages aren't being decrypted, the issue is with the meshcore library configuration, not the monitor code.

## Common Issues and Solutions

### Issue 1: CONTACT_MSG_RECV Events Not Received

**Symptoms:**
- Monitor runs but no messages are received
- Event subscription appears successful but callback never fires

**Root Causes:**
1. Auto message fetching not started
2. Contacts not synced
3. Event dispatcher not properly initialized

**Solutions:**

```python
# Ensure contacts are synced first
if hasattr(meshcore, 'sync_contacts'):
    await meshcore.sync_contacts()
else:
    print("ERROR: sync_contacts() not available")

# Start auto message fetching
if hasattr(meshcore, 'start_auto_message_fetching'):
    await meshcore.start_auto_message_fetching()
else:
    print("ERROR: start_auto_message_fetching() not available")
```

**Verification:**
Run the enhanced monitor with diagnostics:
```bash
python3 meshcore-serial-monitor.py /dev/ttyACM0
```

Look for these lines in the output:
```
✅ Contacts synced successfully
✅ Auto message fetching started
```

### Issue 2: Messages Received but Encrypted

**Symptoms:**
- CONTACT_MSG_RECV events are received
- Message payload is encrypted/garbled
- Cannot read message text

**Root Causes:**
1. Device private key not configured
2. Contacts not properly synced (missing sender's public key)
3. Encryption keys not loaded by meshcore library

**Solutions:**

1. **Check Private Key Configuration:**
   ```python
   # The monitor now checks for these attributes
   key_attrs = ['private_key', 'key', 'node_key', 'device_key', 'crypto']
   ```

2. **Verify Contact List:**
   ```python
   # After sync_contacts(), check:
   if hasattr(meshcore, 'contacts'):
       print(f"Contacts: {len(meshcore.contacts)}")
   ```

3. **Ensure Keys Are Loaded:**
   The meshcore library should automatically load keys during initialization. If not:
   - Check device configuration
   - Verify firmware supports key storage
   - Consult meshcore library documentation

### Issue 3: Configuration Diagnostic Failures

**Symptoms:**
- Monitor reports configuration issues
- Multiple warnings about missing capabilities

**Root Causes:**
1. Incompatible meshcore library version
2. Device doesn't support required features
3. Library not properly configured

**Solutions:**

1. **Update meshcore library:**
   ```bash
   pip install --upgrade meshcore
   ```

2. **Check library version:**
   ```python
   import meshcore
   print(meshcore.__version__)
   ```

3. **Verify device compatibility:**
   - Ensure device firmware supports companion mode
   - Check that device has crypto capabilities
   - Consult device documentation

## Diagnostic Tools

### Enhanced Monitor (meshcore-serial-monitor.py)

The monitor now includes comprehensive diagnostics that check:

1. **Private Key Access** - Verifies key attributes exist and are set
2. **Contact Sync Capability** - Checks if sync_contacts() is available
3. **Auto Message Fetching** - Verifies start_auto_message_fetching() exists
4. **Event Dispatcher** - Ensures event system is present
5. **Contact List** - Verifies contacts were actually synced

**Usage:**
```bash
python3 meshcore-serial-monitor.py /dev/ttyACM0
```

**Expected Output:**
```
🔍 Configuration Diagnostics
==============================================================

1️⃣  Checking private key access...
   ✅ Found key-related attributes: private_key, crypto
   ✅ private_key is set

2️⃣  Checking contact sync capability...
   ✅ sync_contacts() method available
   ✅ Found 5 contacts

3️⃣  Checking auto message fetching...
   ✅ start_auto_message_fetching() available

4️⃣  Checking event dispatcher...
   ✅ Event dispatcher (events) available

5️⃣  Checking debug mode...
   ℹ️  Debug mode is disabled (enable for more verbose logging)

==============================================================
✅ No configuration issues detected
==============================================================
```

### MeshCore CLI Wrapper (meshcore_cli_wrapper.py)

The wrapper now includes:
- Configuration diagnostics on startup
- Contact verification after sync
- Enhanced error messages with troubleshooting tips
- Detailed logging of configuration issues

## Debugging Steps

### Step 1: Run Monitor with Diagnostics

```bash
python3 meshcore-serial-monitor.py /dev/ttyACM0
```

Review the diagnostic output and note any warnings or errors.

### Step 2: Check Configuration Issues

If diagnostics report issues:

1. **Private key missing:**
   - Configure device private key
   - Check device storage/EEPROM
   - Consult device firmware documentation

2. **sync_contacts() not available:**
   - Update meshcore library
   - Check library version compatibility
   - Verify device firmware version

3. **start_auto_message_fetching() not available:**
   - Update meshcore library
   - Check if manual message fetching is required
   - Review library changelog

4. **No event dispatcher:**
   - Update meshcore library
   - Check library version (dispatcher added in recent versions)
   - Consider manual polling if events not supported

### Step 3: Test Message Reception

1. Send a test DM to the device
2. Monitor the console output
3. Look for CONTACT_MSG_RECV events

**Expected:**
```
📬 Message #1 received!
==============================================================
Event type: ContactMessageReceived
  From: 0x12345678
  Text: Hello from another node
==============================================================
```

**If encrypted:**
```
📬 Message #1 received!
==============================================================
Event type: ContactMessageReceived
  From: 0x12345678
  Text: <encrypted data>  ← Problem: not decrypted
==============================================================
```

### Step 4: Enable Debug Mode

For more detailed logging:

```python
# Modify meshcore-serial-monitor.py
self.meshcore = await MeshCore.create_serial(
    self.port,
    baudrate=self.baudrate,
    debug=True  # Enable debug mode
)
```

## Architecture Notes

### Why Decryption is Library's Responsibility

```
┌─────────────────────────────────────┐
│     Monitor (Diagnostic Tool)       │
│  - Event subscription               │
│  - Display received messages        │
│  - Configuration diagnostics        │
└────────────┬────────────────────────┘
             │
             │ Relies on
             ▼
┌─────────────────────────────────────┐
│   MeshCore Library (meshcore-cli)   │
│  - Event dispatcher                 │
│  - Message decryption ← HERE        │
│  - Contact management               │
│  - Key management                   │
└─────────────────────────────────────┘
```

**Design Principles:**
1. Monitor = diagnostic tool (should be simple)
2. Library = handles complexity (crypto, protocol, keys)
3. Separation of concerns = easier maintenance
4. Don't duplicate library functionality

### Event Flow

```
1. Device receives encrypted DM
2. MeshCore library:
   a. Fetches message from device
   b. Looks up sender's public key (from contacts)
   c. Uses device private key to decrypt
   d. Dispatches CONTACT_MSG_RECV event with decrypted text
3. Monitor callback receives decrypted message
4. Monitor displays message
```

If step 2b or 2c fails, the event may not be dispatched or may contain encrypted data.

## Reference Configuration

### Working Setup

```python
# Connect
meshcore = await MeshCore.create_serial('/dev/ttyACM0', baudrate=115200)

# Subscribe to events
meshcore.events.subscribe(EventType.CONTACT_MSG_RECV, callback)

# Sync contacts (CRITICAL)
await meshcore.sync_contacts()

# Start auto message fetching (CRITICAL)
await meshcore.start_auto_message_fetching()

# Keep event loop running
while True:
    await asyncio.sleep(0.1)
```

### Required Device Configuration

- Device must have private key configured
- Device must support companion mode
- Firmware must support crypto operations
- Device must have contact list storage

## Further Investigation

If issues persist after following this guide:

1. **Check MeshCore Library Issues:**
   - GitHub: https://github.com/meshcore-dev/meshcore_py
   - File an issue with diagnostic output

2. **Check Device Firmware:**
   - Consult device documentation
   - Update firmware if available
   - Verify crypto support

3. **Review Library Documentation:**
   - API reference
   - Examples and tutorials
   - Known limitations

4. **Community Support:**
   - MeshCore Discord/forums
   - Device manufacturer support
   - Stack Overflow

## Conclusion

**Do not add decryption to the monitor.** The correct approach is:

1. ✅ Use the enhanced diagnostic tools
2. ✅ Fix meshcore library configuration
3. ✅ Ensure device has proper key configuration
4. ✅ Verify contacts are synced
5. ✅ Confirm auto message fetching is running

The monitor's role is to help diagnose configuration issues, not to replace the library's functionality.
