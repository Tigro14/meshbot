# Post-Fix Verification Guide

Quick verification steps to ensure all fixes are working correctly.

---

## ✅ Quick Tests (5 minutes)

### 1. Config Import Test
```bash
python3 test_config_import_graceful.py
```
**Expected:** All tests PASSED ✅

### 2. Serial Config Test
Create minimal config:
```python
# config.py
MESHTASTIC_ENABLED = True
CONNECTION_MODE = 'serial'
SERIAL_PORT = '/dev/ttyACM0'
```

Run diagnostic:
```bash
python3 test_message_polling_diagnostic.py
```
**Expected:** No import errors, test runs ✅

---

## 🧪 Full Verification (30 minutes)

### Hardware Tests

#### Meshtastic Serial
1. Configure serial mode in config.py
2. Start bot
3. Send test DM via Meshtastic
4. Verify response received

**Log Check:**
```
✅ Abonné aux messages Meshtastic (receive)
🔔 on_message CALLED
```

#### MeshCore Serial
1. Enable MESHCORE_ENABLED in config.py
2. Start bot
3. Check polling logs every 5 seconds
4. Send test DM via MeshCore
5. Verify response received

**Log Check:**
```
✅ [MESHCORE] Thread de polling démarré
📤 [MESHCORE-POLL] Demande de messages en attente
📬 [MESHCORE-DM] De: 0x...
```

---

## 📊 Test Results Summary

| Test | Expected | Status |
|------|----------|--------|
| Config import unit test | PASS | [ ] |
| Serial-only diagnostic | No errors | [ ] |
| TCP diagnostic | No errors | [ ] |
| Meshtastic message RX | Message processed | [ ] |
| MeshCore message RX | Message processed | [ ] |
| MeshCore polling | Every 5s | [ ] |

---

## 🐛 Troubleshooting

### Issue: Import Error
**Symptom:** Still getting import errors
**Solution:** Verify using `getattr()` pattern in test file

### Issue: No Polling Logs
**Symptom:** Missing [MESHCORE-POLL] logs
**Solution:** Enable DEBUG_MODE = True in config.py

### Issue: Messages Not Received
**Symptom:** Logs show callback but no response
**Check:** Review main bot message handling code

---

## 📚 Documentation Quick Links

- **Configuration Guide:** DIAGNOSTIC_TEST_CONFIG_GUIDE.md
- **Visual Comparison:** DIAGNOSTIC_TEST_FIX_VISUAL.md
- **Technical Details:** MESSAGE_POLLING_FIX_SUMMARY.md
- **Complete Overview:** COMPLETE_FIX_SUMMARY.md

---

**Status:** Ready for production deployment ✅
