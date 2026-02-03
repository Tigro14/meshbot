# CPU Fix Verification Steps

## For Production Deployment

After deploying this fix to your Raspberry Pi, follow these steps to verify the CPU usage improvement.

### Step 1: Deploy the Fix

```bash
cd /home/dietpi/bot  # Or your bot directory
git pull origin copilot/fix-cpu-usage-issue
sudo systemctl restart meshtastic-bot
```

### Step 2: Verify Bot is Running

```bash
sudo systemctl status meshtastic-bot
```

Expected output: `active (running)`

### Step 3: Monitor CPU Usage with py-spy

Install py-spy if not already installed:
```bash
pip install py-spy --break-system-packages
```

Run the profiler (requires sudo):
```bash
sudo py-spy top --pid $(systemctl show --property MainPID --value meshtastic-bot)
```

### Step 4: Interpret Results

#### Before Fix (EXPECTED - If you see this, fix not deployed)
```
  %Own   %Total  OwnTime  TotalTime  Function (filename)
 92.00%  92.00%    7.15s     7.15s   _readBytes (tcp_interface_patch.py)  ❌
```

#### After Fix (EXPECTED - Success!)
```
  %Own   %Total  OwnTime  TotalTime  Function (filename)
  <1.0%   <1.0%   <0.10s    <0.10s   _readBytes (tcp_interface_patch.py)  ✅
```

### Step 5: Verify Message Reception Still Works

Send a test message via Meshtastic to verify the bot still responds:
```
/help
```

Expected: Bot responds with help text (proves no regression in functionality)

### Step 6: Monitor System CPU Usage

```bash
htop
# Look for python3 process running main_script.py
# CPU% should be very low when idle (<5%)
```

Or use top:
```bash
top -p $(systemctl show --property MainPID --value meshtastic-bot)
```

## Troubleshooting

### If CPU is still high

1. **Check which version is deployed:**
   ```bash
   cd /home/dietpi/bot
   git log --oneline -1
   # Should show: "Fix CPU 100% issue by increasing select() timeout from 1s to 30s"
   ```

2. **Verify the timeout value in code:**
   ```bash
   grep "read_timeout" tcp_interface_patch.py
   # Should show: self.read_timeout = kwargs.pop('read_timeout', 30.0)
   ```

3. **Check logs for errors:**
   ```bash
   sudo journalctl -u meshtastic-bot -n 50
   ```

### If messages aren't received

1. **Check network connectivity:**
   ```bash
   ping <mesh_node_ip>  # e.g., ping 192.168.1.38
   ```

2. **Verify TCP connection:**
   ```bash
   sudo netstat -an | grep 4403
   # Should show ESTABLISHED connection
   ```

3. **Check bot logs:**
   ```bash
   sudo journalctl -u meshtastic-bot -f
   # Should show "📨 MESSAGE REÇU" when messages arrive
   ```

## Expected Outcomes

### ✅ Success Indicators
- CPU usage in py-spy shows <1% for _readBytes
- System CPU for python3 process is <5% when idle
- Messages are still received and processed normally
- No errors in journalctl logs
- Bot responds to commands as before

### ❌ Failure Indicators
- CPU still at 92% in py-spy (fix not deployed)
- Messages not received (network issue, not CPU fix related)
- Errors in logs (check journalctl)

## Performance Metrics

### Expected Improvements
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| _readBytes CPU | 92% | <1% | ~99% reduction |
| select() calls/sec | 1.0 | 0.033 | 30x reduction |
| System idle CPU | ~95% | <5% | ~90% reduction |
| Message latency | <1ms | <1ms | No change ✅ |

## Rollback Plan (if needed)

If you encounter any issues, you can rollback:

```bash
cd /home/dietpi/bot
git checkout main  # Or previous working branch
sudo systemctl restart meshtastic-bot
```

However, this is **not expected** as:
- All tests pass
- No protocol changes
- No breaking changes
- Only performance improvement

## Questions?

If you see unexpected behavior or have questions about the fix, please report:
1. Output of `py-spy top`
2. Any error messages from `journalctl`
3. Whether messages are being received
4. Git commit hash: `git log --oneline -1`
