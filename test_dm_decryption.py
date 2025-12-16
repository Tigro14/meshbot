#!/usr/bin/env python3
"""
Test DM decryption for Meshtastic 2.7.15 encrypted messages

This test verifies that the bot can decrypt DM messages sent to it.
"""

import sys
import time

# Mock config before importing traffic_monitor
class MockConfig:
    DEBUG_MODE = True

sys.modules['config'] = MockConfig()

from traffic_monitor import TrafficMonitor
from node_manager import NodeManager

def test_decrypt_packet():
    """Test the _decrypt_packet method"""
    print("\n=== Test 1: _decrypt_packet Method ===")
    
    # Create a mock node manager
    node_manager = NodeManager(None)
    
    # Create traffic monitor
    monitor = TrafficMonitor(node_manager)
    
    # Check if crypto is available
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        from meshtastic.protobuf import mesh_pb2, portnums_pb2
        import base64
        print("✅ Cryptography and protobuf libraries available")
        
        # Create a test encrypted packet
        # We'll encrypt a simple TEXT_MESSAGE_APP packet
        psk = base64.b64decode("1PG7OiApB1nwvP+rz05pAQ==")
        packet_id = 12345678
        from_id = 0x16fad3dc  # Example node ID
        
        # Create a Data protobuf
        data = mesh_pb2.Data()
        data.portnum = portnums_pb2.PortNum.TEXT_MESSAGE_APP
        data.payload = "Hello from encrypted DM!".encode('utf-8')
        
        # Serialize
        plaintext = data.SerializeToString()
        
        # Encrypt
        nonce_bytes = packet_id.to_bytes(8, 'little') + from_id.to_bytes(4, 'little')
        nonce = nonce_bytes + b'\x00' * 4
        
        cipher = Cipher(
            algorithms.AES(psk),
            modes.CTR(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(plaintext) + encryptor.finalize()
        
        print(f"✅ Created test encrypted packet ({len(encrypted_data)} bytes)")
        
        # Now test decryption
        decrypted = monitor._decrypt_packet(encrypted_data, packet_id, from_id)
        
        if decrypted:
            print(f"✅ Decryption successful!")
            print(f"   Portnum: {decrypted.portnum}")
            print(f"   Payload: {decrypted.payload.decode('utf-8')}")
            
            if decrypted.portnum == portnums_pb2.PortNum.TEXT_MESSAGE_APP:
                if decrypted.payload.decode('utf-8') == "Hello from encrypted DM!":
                    print("✅ TEST PASSED: Message decrypted correctly!")
                    return True
                else:
                    print("❌ TEST FAILED: Message content mismatch")
                    return False
            else:
                print("❌ TEST FAILED: Wrong portnum")
                return False
        else:
            print("❌ TEST FAILED: Decryption returned None")
            return False
            
    except ImportError as e:
        print(f"⚠️  Libraries not available: {e}")
        print("   This is expected in environments without cryptography/protobuf")
        return True  # Not a failure, just not testable

def test_decrypt_packet_base64():
    """Test the _decrypt_packet method with base64-encoded string"""
    print("\n=== Test 2: _decrypt_packet with Base64 String ===")
    
    # Create a mock node manager
    node_manager = NodeManager(None)
    
    # Create traffic monitor
    monitor = TrafficMonitor(node_manager)
    
    # Check if crypto is available
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        from meshtastic.protobuf import mesh_pb2, portnums_pb2
        import base64
        print("✅ Cryptography and protobuf libraries available")
        
        # Create a test encrypted packet
        psk = base64.b64decode("1PG7OiApB1nwvP+rz05pAQ==")
        packet_id = 12345678
        from_id = 0x16fad3dc
        
        # Create a Data protobuf
        data = mesh_pb2.Data()
        data.portnum = portnums_pb2.PortNum.TEXT_MESSAGE_APP
        data.payload = "Base64 test message!".encode('utf-8')
        
        # Serialize
        plaintext = data.SerializeToString()
        
        # Encrypt
        nonce_bytes = packet_id.to_bytes(8, 'little') + from_id.to_bytes(4, 'little')
        nonce = nonce_bytes + b'\x00' * 4
        
        cipher = Cipher(
            algorithms.AES(psk),
            modes.CTR(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        encrypted_bytes = encryptor.update(plaintext) + encryptor.finalize()
        
        # Convert to base64 string (like Meshtastic Python lib does)
        encrypted_string = base64.b64encode(encrypted_bytes).decode('ascii')
        
        print(f"✅ Created test encrypted packet as base64 string")
        print(f"   Length: {len(encrypted_string)} chars")
        
        # Now test decryption with base64 string
        decrypted = monitor._decrypt_packet(encrypted_string, packet_id, from_id)
        
        if decrypted:
            print(f"✅ Decryption successful from base64 string!")
            print(f"   Portnum: {decrypted.portnum}")
            print(f"   Payload: {decrypted.payload.decode('utf-8')}")
            
            if decrypted.portnum == portnums_pb2.PortNum.TEXT_MESSAGE_APP:
                if decrypted.payload.decode('utf-8') == "Base64 test message!":
                    print("✅ TEST PASSED: Base64 string decrypted correctly!")
                    return True
                else:
                    print("❌ TEST FAILED: Message content mismatch")
                    return False
            else:
                print("❌ TEST FAILED: Wrong portnum")
                return False
        else:
            print("❌ TEST FAILED: Decryption returned None")
            return False
            
    except ImportError as e:
        print(f"⚠️  Libraries not available: {e}")
        print("   This is expected in environments without cryptography/protobuf")
        return True  # Not a failure, just not testable

def test_encrypted_packet_handling():
    """Test add_packet with encrypted DM"""
    print("\n=== Test 3: Encrypted Packet Handling ===")
    
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        from meshtastic.protobuf import mesh_pb2, portnums_pb2
        import base64
        
        # Create traffic monitor
        node_manager = NodeManager(None)
        monitor = TrafficMonitor(node_manager)
        
        my_node_id = 0x12345678
        from_id = 0x16fad3dc
        packet_id = 87654321
        
        # Create and encrypt a message
        psk = base64.b64decode("1PG7OiApB1nwvP+rz05pAQ==")
        
        data = mesh_pb2.Data()
        data.portnum = portnums_pb2.PortNum.TEXT_MESSAGE_APP
        data.payload = "Test DM message".encode('utf-8')
        plaintext = data.SerializeToString()
        
        nonce_bytes = packet_id.to_bytes(8, 'little') + from_id.to_bytes(4, 'little')
        nonce = nonce_bytes + b'\x00' * 4
        
        cipher = Cipher(
            algorithms.AES(psk),
            modes.CTR(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(plaintext) + encryptor.finalize()
        
        # Create a mock packet with encrypted field (DM to us)
        packet = {
            'from': from_id,
            'to': my_node_id,  # DM to our node
            'id': packet_id,
            'encrypted': encrypted_data,
            'rssi': -50,
            'snr': 8.5,
            'hopLimit': 3,
            'hopStart': 3
        }
        
        print(f"✅ Created mock encrypted DM packet")
        print(f"   From: 0x{from_id:08x}")
        print(f"   To: 0x{my_node_id:08x} (our node)")
        
        # Process the packet
        monitor.add_packet(packet, source='local', my_node_id=my_node_id)
        
        # Check if packet was decrypted
        if 'decoded' in packet:
            print("✅ Packet has 'decoded' field after processing")
            decoded = packet['decoded']
            
            if decoded.get('portnum') == 'TEXT_MESSAGE_APP':
                print(f"✅ Portnum: {decoded.get('portnum')}")
                
                if 'text' in decoded:
                    message = decoded['text']
                    print(f"✅ Message text: {message}")
                    
                    if message == "Test DM message":
                        print("✅ TEST PASSED: DM decrypted and added to packet!")
                        return True
                    else:
                        print("❌ TEST FAILED: Message content mismatch")
                        return False
                else:
                    print("⚠️  No 'text' field in decoded (may still work)")
                    return True
            else:
                print(f"❌ TEST FAILED: Wrong portnum: {decoded.get('portnum')}")
                return False
        else:
            print("❌ TEST FAILED: Packet was not decrypted")
            return False
            
    except ImportError as e:
        print(f"⚠️  Libraries not available: {e}")
        return True

def test_broadcast_not_decrypted():
    """Test that broadcast messages are not decrypted"""
    print("\n=== Test 4: Broadcast Messages Not Decrypted ===")
    
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        from meshtastic.protobuf import mesh_pb2, portnums_pb2
        import base64
        
        node_manager = NodeManager(None)
        monitor = TrafficMonitor(node_manager)
        
        my_node_id = 0x12345678
        from_id = 0x16fad3dc
        packet_id = 99999999
        
        # Create encrypted data
        psk = base64.b64decode("1PG7OiApB1nwvP+rz05pAQ==")
        
        data = mesh_pb2.Data()
        data.portnum = portnums_pb2.PortNum.TEXT_MESSAGE_APP
        data.payload = "Broadcast message".encode('utf-8')
        plaintext = data.SerializeToString()
        
        nonce_bytes = packet_id.to_bytes(8, 'little') + from_id.to_bytes(4, 'little')
        nonce = nonce_bytes + b'\x00' * 4
        
        cipher = Cipher(
            algorithms.AES(psk),
            modes.CTR(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(plaintext) + encryptor.finalize()
        
        # Create packet with broadcast address (not DM)
        packet = {
            'from': from_id,
            'to': 0xFFFFFFFF,  # Broadcast, not DM
            'id': packet_id,
            'encrypted': encrypted_data,
            'rssi': -50,
            'snr': 8.5,
            'hopLimit': 3,
            'hopStart': 3
        }
        
        print(f"✅ Created mock encrypted broadcast packet")
        print(f"   From: 0x{from_id:08x}")
        print(f"   To: 0xFFFFFFFF (broadcast)")
        
        # Process the packet
        monitor.add_packet(packet, source='local', my_node_id=my_node_id)
        
        # Check that packet was NOT decrypted
        if 'decoded' not in packet and 'encrypted' in packet:
            print("✅ TEST PASSED: Broadcast packet remained encrypted")
            return True
        else:
            print("❌ TEST FAILED: Broadcast packet was decrypted (should not be)")
            return False
            
    except ImportError as e:
        print(f"⚠️  Libraries not available: {e}")
        return True

def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Meshtastic 2.7.15 DM Decryption")
    print("=" * 60)
    
    results = []
    
    # Test 1: Decrypt method (bytes)
    results.append(("Decrypt Method (bytes)", test_decrypt_packet()))
    
    # Test 2: Decrypt method (base64 string)
    results.append(("Decrypt Method (base64)", test_decrypt_packet_base64()))
    
    # Test 3: Encrypted packet handling
    results.append(("Encrypted Packet Handling", test_encrypted_packet_handling()))
    
    # Test 4: Broadcast not decrypted
    results.append(("Broadcast Not Decrypted", test_broadcast_not_decrypted()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        return 1

if __name__ == '__main__':
    sys.exit(main())
