# Quick Reference: Diagnostic Logging for /my Command

## 🚀 Quick Start

### 1. Deploy Updated Bot
```bash
cd /home/dietpi/bot
git pull
sudo systemctl restart meshtastic-bot
```

### 2. Monitor Logs in Real-Time
```bash
journalctl -u meshtastic-bot -f | grep -E "(RX_HISTORY|RX_LOG|CONVERSATION)"
```

### 3. Test the /my Command
Send `/my` from your MeshCore device

### 4. What You'll See

#### ✅ Working Correctly:
```
📊 [RX_LOG] Extracted signal data: snr=11.2dB, rssi=-71dBm
🔍 [RX_HISTORY] Node 0x889fa138 | snr=11.2 | DM=False | RX_LOG=True | hops=3
✅ [RX_HISTORY] UPDATED 0x889fa138 (Node-889fa138) | old_snr=10.0→new_snr=10.6dB | count=6

[CONVERSATION] RESPONSE: ⚫ ~-71dBm SNR:11.2dB | 📈 Excellente (2m) | 📶 Signal local
```

#### ❌ Problem: No RX_LOG Events
```
(no 📊 logs appear)

[CONVERSATION] RESPONSE: 📶 Signal: n/a | 📈 Inconnue (7j) | 📶 Signal local
```
**Cause:** RX_LOG events not arriving

#### ❌ Problem: RX_LOG Has No Signal Data
```
📊 [RX_LOG] Extracted signal data: snr=0.0dB, rssi=0dBm
🔍 [RX_HISTORY] Node 0x889fa138 | snr=0.0 | DM=False | RX_LOG=True | hops=0

[CONVERSATION] RESPONSE: 📶 Signal: n/a | 📈 Inconnue (7j) | 📶 Signal local
```
**Cause:** RX_LOG events don't contain SNR/RSSI

## 📊 Useful Commands

### Count RX_LOG Events (Last Hour)
```bash
journalctl -u meshtastic-bot --since "1 hour ago" | grep -c "📊 \[RX_LOG\]"
```

### See Last 5 Updates
```bash
journalctl -u meshtastic-bot --since "1 hour ago" | grep "✅ \[RX_HISTORY\]" | tail -5
```

### Find Your Node's Updates
```bash
# Replace 889fa138 with your node ID
journalctl -u meshtastic-bot --since "10 minutes ago" | grep "0x889fa138"
```

### Check for Skipped Updates
```bash
journalctl -u meshtastic-bot --since "1 hour ago" | grep "⏭️"
```

## 📝 What to Share

Copy and share this output:

```bash
# 1. RX_LOG events count
echo "=== RX_LOG Events ==="
journalctl -u meshtastic-bot --since "10 minutes ago" | grep "📊 \[RX_LOG\]"

# 2. rx_history updates
echo "=== RX_HISTORY Updates ==="
journalctl -u meshtastic-bot --since "10 minutes ago" | grep "🔍 \[RX_HISTORY\]"

# 3. Successful updates
echo "=== Successful Updates ==="
journalctl -u meshtastic-bot --since "10 minutes ago" | grep "✅ \[RX_HISTORY\]"

# 4. Your /my response
echo "=== /my Response ==="
journalctl -u meshtastic-bot --since "5 minutes ago" | grep "QUERY: /my" -A 2
```

## 🔧 Troubleshooting

### If No 📊 Logs Appear
- MeshCore not sending RX_LOG events
- Check MeshCore connection: `journalctl -u meshtastic-bot | grep "meshcore" | tail -20`

### If SNR Always 0.0
- RX_LOG events don't contain signal data
- May need different extraction method

### If Wrong Node Updated
- Node ID routing issue
- Share logs with node IDs

## 📚 Full Documentation
- `docs/DEBUG_RX_HISTORY_LOGGING.md` - Complete guide
- `docs/DIAGNOSTIC_SESSION_2026-02-18.md` - Session summary

## ✉️ Report Format

When reporting, please include:
1. Node ID (hex): `0x________`
2. Time of test: `HH:MM:SS`
3. All four command outputs above
4. What you expected vs what you saw

## 🎯 Goal

We want to see this sequence when you send `/my`:
```
📊 [RX_LOG] Extracted signal data: snr=X.XdB, rssi=XdBm
🔍 [RX_HISTORY] Node 0xYOURNODE | snr=X.X | DM=False | RX_LOG=True | hops=N
✅ [RX_HISTORY] UPDATED 0xYOURNODE (...) | old_snr=X.X→new_snr=X.XdB | count=N

[CONVERSATION] RESPONSE: ⚫ ~XdBm SNR:X.XdB | 📈 Excellente | 📶 Signal local
```

If any step is missing, that's where the problem is!

---

**Ready to test!** Deploy, monitor, and share what you see.
