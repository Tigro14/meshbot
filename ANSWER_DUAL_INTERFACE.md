# Answer: Why Can't I Use Both Meshtastic and MeshCore Together?

## Direct Answer

**You cannot use both interfaces simultaneously because the bot is designed with a single-interface architecture.** Only ONE radio connection can be active at a time.

## Quick Facts

- ✅ **Meshtastic**: Full mesh network (broadcasts + DMs + topology)
- ⚠️ **MeshCore**: DM-only companion mode
- ❌ **Both Together**: Not supported (architectural limitation)
- 📝 **Recommendation**: Use Meshtastic if you have it

## What You Should Do

### Choose Based on Your Hardware

```
Have Meshtastic radio? → Set MESHTASTIC_ENABLED = True
                          Set MESHCORE_ENABLED = False

Have MeshCore radio? → Set MESHTASTIC_ENABLED = False
                       Set MESHCORE_ENABLED = True

Have BOTH radios? → Still choose Meshtastic!
                    (It does everything MeshCore does + more)
```

### Configuration

```python
# config.py - Recommended for most users
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False
SERIAL_PORT = "/dev/ttyACM2"
```

## What Happens If You Enable Both?

The bot will:
1. ⚠️ Show a warning message
2. ✅ Connect to Meshtastic (priority)
3. ❌ Ignore MeshCore
4. 📝 Tell you how to fix the config

This is **intentional behavior** to prevent confusion!

## Why This Design?

**Technical Reasons:**
1. Single `self.interface` variable (can only hold one connection)
2. Message deduplication complexity
3. Response routing ambiguity
4. Statistics tracking challenges
5. Command context conflicts

**Practical Reasons:**
1. Meshtastic already provides everything MeshCore does
2. Most users only have one type of radio
3. Dual mode adds complexity with little benefit
4. Single interface is simpler and more reliable

## Documentation Files

For more details, see:

1. **DUAL_INTERFACE_FAQ.md** - User-friendly FAQ (3.4 KB)
   - Quick answers to common questions
   - Configuration examples
   - Comparison table

2. **DUAL_INTERFACE_VISUAL_GUIDE.md** - Visual diagrams (10 KB)
   - Architecture diagrams
   - Message flow comparisons
   - Scenario illustrations
   - Decision tree

3. **WHY_NOT_BOTH_INTERFACES.md** - Technical deep-dive (10.2 KB)
   - Complete architecture analysis
   - Capability comparison
   - Future possibility discussion
   - Use case analysis

## Summary Table

| Feature | Meshtastic | MeshCore | Both |
|---------|-----------|----------|------|
| Broadcasts | ✅ | ❌ | ❌ Not supported |
| DMs | ✅ | ✅ | ❌ Not supported |
| Network topology | ✅ | ❌ | ❌ Not supported |
| All commands | ✅ | ⚠️ Limited | ❌ Not supported |
| Configuration | Simple | Simple | Unnecessary |

## Your Next Steps

1. **Decide which interface to use** based on your hardware
2. **Update config.py** with ONE interface enabled
3. **Restart the bot**: `sudo systemctl restart meshbot`
4. **Verify logs** show correct connection
5. **Test with commands** like `/echo` or `/nodes`

## Still Have Questions?

Read the detailed documentation files or check the configuration examples in `config.py.sample`.

**Bottom line:** Pick the interface that matches your radio. If you have Meshtastic, use it!
