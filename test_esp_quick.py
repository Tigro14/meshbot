#!/usr/bin/env python3
# Test rapide ESPHome
import requests
import socket
import time

ESPHOME_HOST = "192.168.1.27"
ESPHOME_PORT = 80

def test_esphome_quick():
    try:
        # Test web
        response = requests.get(f"http://{ESPHOME_HOST}:{ESPHOME_PORT}/", timeout=8)
        web_status = "Web-OK" if response.status_code == 200 else f"Web-{response.status_code}"
    except:
        web_status = "Web-KO"
    
    try:
        # Test API
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((ESPHOME_HOST, 6053))
        sock.close()
        api_status = "API-OK" if result == 0 else "API-KO"
    except:
        api_status = "API-Error"
    
    return f"{web_status} | {api_status} | {time.strftime('%H:%M')}"

if __name__ == "__main__":
    print("Test ESPHome:", test_esphome_quick())
