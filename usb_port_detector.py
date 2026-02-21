#!/usr/bin/env python3
"""
USB Port Auto-Detection Module

Automatically detects USB serial devices based on:
- Product name
- Manufacturer
- Serial number
- Vendor ID / Product ID

This allows configuration like SERIAL_PORT = "auto:HT-n5262"
instead of hardcoded /dev/ttyACM0 that may change.
"""

import os
import glob
import re
from typing import Optional, Dict, List
from utils import debug_print, info_print, error_print


class USBPortDetector:
    """
    Detects USB serial devices by their attributes.
    
    Uses /sys/class/tty/*/device/.. to read USB device information
    without requiring external dependencies like pyudev.
    """
    
    @staticmethod
    def list_usb_serial_devices() -> List[Dict[str, str]]:
        """
        List all USB serial devices with their attributes.
        
        Returns:
            List of dicts with keys: port, product, manufacturer, serial, 
                                    idVendor, idProduct
        """
        devices = []
        
        # Find all tty devices
        for tty_path in glob.glob('/sys/class/tty/tty*'):
            device_path = os.path.join(tty_path, 'device')
            
            # Check if it's a USB device (has ../ that leads to usb device)
            if not os.path.exists(device_path):
                continue
                
            # Navigate to USB device directory
            # Structure: /sys/class/tty/ttyACM0/device -> ../../3-1:1.0
            # We need to go up to find idVendor, idProduct, etc.
            usb_device_path = None
            current = device_path
            
            # Try to find the USB device directory (contains idVendor)
            for _ in range(5):  # Max 5 levels up
                current = os.path.dirname(os.path.realpath(current))
                if os.path.exists(os.path.join(current, 'idVendor')):
                    usb_device_path = current
                    break
            
            if not usb_device_path:
                continue
            
            # Read device attributes
            try:
                port_name = os.path.basename(tty_path)
                port_path = f"/dev/{port_name}"
                
                # Check if device actually exists
                if not os.path.exists(port_path):
                    continue
                
                device_info = {
                    'port': port_path,
                    'tty_name': port_name,
                    'product': USBPortDetector._read_sysfs(usb_device_path, 'product'),
                    'manufacturer': USBPortDetector._read_sysfs(usb_device_path, 'manufacturer'),
                    'serial': USBPortDetector._read_sysfs(usb_device_path, 'serial'),
                    'idVendor': USBPortDetector._read_sysfs(usb_device_path, 'idVendor'),
                    'idProduct': USBPortDetector._read_sysfs(usb_device_path, 'idProduct'),
                }
                
                # Only add if we got at least some info
                if device_info['product'] or device_info['manufacturer']:
                    devices.append(device_info)
                    
            except Exception as e:
                debug_print(f"Error reading device {tty_path}: {e}")
                continue
        
        return devices
    
    @staticmethod
    def _read_sysfs(base_path: str, filename: str) -> Optional[str]:
        """
        Read a sysfs file and return its content.
        
        Args:
            base_path: Base directory path
            filename: File to read
            
        Returns:
            Content as string, or None if file doesn't exist
        """
        file_path = os.path.join(base_path, filename)
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return f.read().strip()
        except Exception:
            pass
        return None
    
    @staticmethod
    def find_device_by_criteria(
        product: Optional[str] = None,
        manufacturer: Optional[str] = None,
        serial: Optional[str] = None,
        vendor_id: Optional[str] = None,
        product_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Find a USB serial device matching the given criteria.
        
        Args:
            product: Product name to match (partial match, case-insensitive)
            manufacturer: Manufacturer name to match (partial match, case-insensitive)
            serial: Serial number to match (exact match)
            vendor_id: USB Vendor ID in hex (e.g., "239a")
            product_id: USB Product ID in hex (e.g., "4405")
            
        Returns:
            Device path (e.g., "/dev/ttyACM0") or None if not found
        """
        devices = USBPortDetector.list_usb_serial_devices()
        
        for device in devices:
            matches = True
            
            # Check product name
            if product and device['product']:
                if product.lower() not in device['product'].lower():
                    matches = False
            elif product:
                matches = False
            
            # Check manufacturer
            if matches and manufacturer and device['manufacturer']:
                if manufacturer.lower() not in device['manufacturer'].lower():
                    matches = False
            elif matches and manufacturer:
                matches = False
            
            # Check serial number (exact match)
            if matches and serial:
                if device['serial'] != serial:
                    matches = False
            
            # Check vendor ID
            if matches and vendor_id:
                if device['idVendor'] != vendor_id.lower():
                    matches = False
            
            # Check product ID
            if matches and product_id:
                if device['idProduct'] != product_id.lower():
                    matches = False
            
            if matches:
                return device['port']
        
        return None
    
    @staticmethod
    def detect_port(port_config: str) -> Optional[str]:
        """
        Detect port from configuration string.
        
        Supports formats:
        - "auto" - First USB serial device found
        - "auto:Product Name" - Match by product name
        - "auto:product=HT-n5262" - Explicit product match
        - "auto:serial=B5A131E366B43F18" - Match by serial number
        - "auto:product=HT-n5262,serial=B5A1..." - Multiple criteria
        - "/dev/ttyACM0" - Direct path (returned as-is)
        
        Args:
            port_config: Port configuration string
            
        Returns:
            Detected device path, or None if not found
        """
        # If not auto-detection, return as-is
        if not port_config or not port_config.startswith('auto'):
            return port_config
        
        # Parse auto-detection criteria
        if port_config == 'auto':
            # Just return first USB serial device
            devices = USBPortDetector.list_usb_serial_devices()
            if devices:
                return devices[0]['port']
            return None
        
        # Parse criteria from config string
        criteria_str = port_config[5:]  # Remove "auto:" prefix
        
        # Check if it's simple format (just product name)
        if '=' not in criteria_str and ',' not in criteria_str:
            # Simple format: "auto:HT-n5262"
            return USBPortDetector.find_device_by_criteria(product=criteria_str)
        
        # Parse key=value format
        criteria = {}
        for part in criteria_str.split(','):
            if '=' in part:
                key, value = part.split('=', 1)
                criteria[key.strip().lower()] = value.strip()
        
        # Map criteria to function parameters
        return USBPortDetector.find_device_by_criteria(
            product=criteria.get('product'),
            manufacturer=criteria.get('manufacturer'),
            serial=criteria.get('serial'),
            vendor_id=criteria.get('vendor'),
            product_id=criteria.get('productid')
        )
    
    @staticmethod
    def resolve_port(port_config: str, device_name: str = "device") -> str:
        """
        Resolve port configuration to actual device path.
        
        This is the main function to use in bot code.
        Logs detection process and falls back gracefully.
        
        Args:
            port_config: Port configuration (auto:... or /dev/tty...)
            device_name: Human-readable device name for logging
            
        Returns:
            Resolved port path, or original config if detection fails
        """
        # If not auto-detection, return as-is
        if not port_config or not str(port_config).startswith('auto'):
            return port_config
        
        info_print(f"🔍 Auto-detecting USB port for {device_name}...")
        debug_print(f"   Configuration: {port_config}")
        
        # List all devices for debugging
        devices = USBPortDetector.list_usb_serial_devices()
        if devices:
            debug_print(f"   Found {len(devices)} USB serial device(s):")
            for dev in devices:
                debug_print(f"     - {dev['port']}: {dev.get('manufacturer', 'N/A')} {dev.get('product', 'N/A')} (SN: {dev.get('serial', 'N/A')})")
        else:
            error_print(f"   ⚠️ No USB serial devices found!")
        
        # Attempt detection
        detected_port = USBPortDetector.detect_port(port_config)
        
        if detected_port:
            info_print(f"✅ Auto-detected port: {detected_port}")
            
            # Show which device was detected
            for dev in devices:
                if dev['port'] == detected_port:
                    info_print(f"   Device: {dev.get('manufacturer', 'N/A')} {dev.get('product', 'N/A')}")
                    if dev.get('serial'):
                        debug_print(f"   Serial: {dev['serial']}")
                    break
            
            return detected_port
        else:
            error_print(f"❌ Auto-detection failed for {device_name}")
            error_print(f"   Configuration: {port_config}")
            error_print(f"   No matching device found")
            error_print(f"   ")
            error_print(f"   💡 Possible solutions:")
            error_print(f"   1. Check device is connected: ls -la /dev/ttyACM* /dev/ttyUSB*")
            error_print(f"   2. Verify product name matches: lsusb")
            error_print(f"   3. Use manual port: SERIAL_PORT = '/dev/ttyACM0'")
            error_print(f"   ")
            
            # Return original config as fallback
            return port_config


def test_detection():
    """
    Test function to show all detected devices.
    Run: python3 usb_port_detector.py
    """
    print("=" * 80)
    print("USB Serial Device Detection Test")
    print("=" * 80)
    
    devices = USBPortDetector.list_usb_serial_devices()
    
    if not devices:
        print("❌ No USB serial devices found")
        print("")
        print("Check:")
        print("  - ls -la /dev/ttyACM* /dev/ttyUSB*")
        print("  - lsusb")
        return
    
    print(f"\n✅ Found {len(devices)} USB serial device(s):\n")
    
    for i, dev in enumerate(devices, 1):
        print(f"{i}. {dev['port']}")
        print(f"   Product:      {dev.get('product', 'N/A')}")
        print(f"   Manufacturer: {dev.get('manufacturer', 'N/A')}")
        print(f"   Serial:       {dev.get('serial', 'N/A')}")
        print(f"   Vendor ID:    {dev.get('idVendor', 'N/A')}")
        print(f"   Product ID:   {dev.get('idProduct', 'N/A')}")
        print("")
    
    # Test some example detections
    print("=" * 80)
    print("Example Auto-Detection Tests")
    print("=" * 80)
    print("")
    
    # Test cases based on provided dmesg
    test_cases = [
        ("auto", "First device"),
        ("auto:HT-n5262", "Heltec device by product name"),
        ("auto:XIAO", "XIAO device by partial product name"),
        ("auto:product=HT-n5262", "Heltec by explicit product"),
        ("auto:serial=B5A131E366B43F18", "Heltec by serial number"),
        ("auto:serial=7CEF06581293BD9C", "XIAO by serial number"),
        ("auto:manufacturer=Heltec", "By manufacturer"),
        ("auto:manufacturer=Seeed", "By manufacturer (partial)"),
    ]
    
    for config, description in test_cases:
        result = USBPortDetector.detect_port(config)
        status = "✅" if result else "❌"
        print(f"{status} {description}")
        print(f"   Config: {config}")
        print(f"   Result: {result or 'Not found'}")
        print("")


if __name__ == '__main__':
    test_detection()
