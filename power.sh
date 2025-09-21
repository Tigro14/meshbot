#!/bin/bash
echo "=== Pi 5 Power Estimation ==="
echo "CPU Temp: $(vcgencmd measure_temp)"
echo "Voltage: $(vcgencmd measure_volts)"
echo "CPU Freq: $(vcgencmd measure_clock arm)"
echo "Throttling: $(vcgencmd get_throttled)"
echo "CPU Usage: $(cat /proc/loadavg)"
