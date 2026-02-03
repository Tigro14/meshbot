# Can I Use Both Meshtastic and MeshCore Together?

## Short Answer

**No, you cannot use both at the same time.** The bot can only connect to ONE radio interface at a time.

## Why Choose One?

### Meshtastic = Full Mesh Network 🌐
- ✅ Receive **all** mesh messages (broadcasts + DMs)
- ✅ See **all** nodes in the network
- ✅ Get network statistics
- ✅ Full bot functionality

**Use this if:** You have a Meshtastic-compatible radio

### MeshCore = DMs Only 📩
- ⚠️ Receive **only** DMs sent directly to the bot
- ⚠️ Can't see broadcasts or network
- ⚠️ Limited commands
- ✅ Lightweight companion mode

**Use this if:** You only have a MeshCore-compatible radio

## What Should You Do?

### If You Have a Meshtastic Radio
```python
# config.py
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False  # ← Set to False
```
**Recommendation:** Always choose Meshtastic. It does everything MeshCore does PLUS full mesh.

### If You Only Have MeshCore
```python
# config.py
MESHTASTIC_ENABLED = False  # ← Set to False
MESHCORE_ENABLED = True
```

### If You Have BOTH Radios

Still choose Meshtastic! Here's why:

| Feature | Meshtastic | MeshCore |
|---------|-----------|----------|
| Receive broadcasts | ✅ | ❌ |
| Receive DMs | ✅ | ✅ |
| Send broadcasts | ✅ | ❌ |
| See network nodes | ✅ | ❌ |
| Network statistics | ✅ | ❌ |
| Signal analysis | ✅ | ❌ |
| AI chat (`/bot`) | ✅ | ✅ |
| Weather (`/weather`) | ✅ | ✅ |
| Full commands | ✅ | ⚠️ Limited |

**Verdict:** Meshtastic does everything and more!

## What Happens If I Enable Both?

The bot will automatically choose Meshtastic and show you this warning:

```
⚠️ AVERTISSEMENT: MESHTASTIC_ENABLED et MESHCORE_ENABLED sont tous deux activés
   → Priorité donnée à Meshtastic (capacités mesh complètes)
   → MeshCore sera ignoré. Pour utiliser MeshCore:
   →   Définir MESHTASTIC_ENABLED = False dans config.py
```

**This is intentional!** It prevents connecting to the wrong interface.

## Technical Reason

The bot has a single `self.interface` variable that can only hold ONE connection:

```python
# This works:
self.interface = Meshtastic  # Full mesh

# OR this works:
self.interface = MeshCore    # DMs only

# But NOT both simultaneously:
self.interface = Meshtastic AND MeshCore  # ❌ Not possible
```

Supporting both simultaneously would require:
- Duplicate message handling
- Complex routing logic
- Which interface to reply on?
- How to merge statistics?

It's technically possible but adds significant complexity for little benefit.

## Common Questions

### "I want broadcasts on Meshtastic and DMs on MeshCore"
**Answer:** Just use Meshtastic - it receives both broadcasts AND DMs.

### "Can I switch between them?"
**Answer:** Yes! Just change config and restart:
```bash
# Edit config.py
sudo systemctl restart meshbot
```

### "Why not support both?"
**Answer:** 
1. Adds complexity (deduplication, routing, statistics)
2. No real benefit (Meshtastic already does everything)
3. Most users have only one radio anyway

### "Will this ever change?"
**Answer:** Maybe, if there's a compelling use case. But for now, single interface is simpler and works great.

## Summary

✅ **DO:** Choose the interface that matches your hardware  
✅ **DO:** Use Meshtastic if you have it (full features)  
✅ **DO:** Use MeshCore if that's all you have (DMs only)  
❌ **DON'T:** Enable both (only one will work anyway)  

**Remember:** Meshtastic is almost always the right choice!
