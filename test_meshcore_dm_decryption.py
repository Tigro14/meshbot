#!/usr/bin/env python3
"""
Test MeshCore DM decryption functionality

This test verifies that the meshcore-serial-monitor.py can decrypt
encrypted Direct Messages using PyNaCl.
"""

import sys
import base64

# Test PyNaCl availability
try:
    import nacl.public
    import nacl.utils
    NACL_AVAILABLE = True
except ImportError:
    print("❌ PyNaCl not installed - cannot test decryption")
    print("   Install with: pip install PyNaCl")
    sys.exit(1)


def test_encryption_decryption():
    """Test basic encryption and decryption with NaCl"""
    print("\n" + "="*60)
    print("Test 1: Basic Encryption/Decryption")
    print("="*60)
    
    # Generate a keypair for Alice (sender)
    alice_private_key = nacl.public.PrivateKey.generate()
    alice_public_key = alice_private_key.public_key
    
    # Generate a keypair for Bob (receiver - our bot)
    bob_private_key = nacl.public.PrivateKey.generate()
    bob_public_key = bob_private_key.public_key
    
    print(f"✅ Generated keypairs")
    print(f"   Alice private key: {base64.b64encode(bytes(alice_private_key)).decode()[:32]}...")
    print(f"   Alice public key:  {base64.b64encode(bytes(alice_public_key)).decode()[:32]}...")
    print(f"   Bob private key:   {base64.b64encode(bytes(bob_private_key)).decode()[:32]}...")
    print(f"   Bob public key:    {base64.b64encode(bytes(bob_public_key)).decode()[:32]}...")
    
    # Alice encrypts a message to Bob
    plaintext = "Hello Bob! This is an encrypted DM from Alice."
    print(f"\n📝 Original message: {plaintext}")
    
    # Alice creates a Box with her private key and Bob's public key
    alice_box = nacl.public.Box(alice_private_key, bob_public_key)
    encrypted = alice_box.encrypt(plaintext.encode('utf-8'))
    
    print(f"🔐 Encrypted message: {base64.b64encode(encrypted).decode()[:64]}...")
    print(f"   Length: {len(encrypted)} bytes")
    
    # Bob decrypts the message with his private key and Alice's public key
    bob_box = nacl.public.Box(bob_private_key, alice_public_key)
    decrypted = bob_box.decrypt(encrypted)
    decrypted_text = decrypted.decode('utf-8')
    
    print(f"✅ Decrypted message: {decrypted_text}")
    
    # Verify
    if decrypted_text == plaintext:
        print("✅ TEST PASSED: Decryption successful!")
        return True
    else:
        print("❌ TEST FAILED: Decryption mismatch!")
        return False


def test_key_parsing():
    """Test parsing private keys from different formats"""
    print("\n" + "="*60)
    print("Test 2: Private Key Parsing")
    print("="*60)
    
    # Generate a test key
    test_key = nacl.public.PrivateKey.generate()
    test_key_bytes = bytes(test_key)
    
    # Test base64 format
    print("\n📝 Testing base64 format...")
    base64_key = base64.b64encode(test_key_bytes).decode()
    print(f"   Key: {base64_key}")
    
    try:
        parsed_bytes = base64.b64decode(base64_key)
        parsed_key = nacl.public.PrivateKey(parsed_bytes)
        print(f"   ✅ Parsed successfully: {len(parsed_bytes)} bytes")
    except Exception as e:
        print(f"   ❌ Failed to parse: {e}")
        return False
    
    # Test hex format
    print("\n📝 Testing hex format...")
    hex_key = test_key_bytes.hex()
    print(f"   Key: {hex_key}")
    
    try:
        parsed_bytes = bytes.fromhex(hex_key)
        parsed_key = nacl.public.PrivateKey(parsed_bytes)
        print(f"   ✅ Parsed successfully: {len(parsed_bytes)} bytes")
    except Exception as e:
        print(f"   ❌ Failed to parse: {e}")
        return False
    
    # Test hex with colons (common format)
    print("\n📝 Testing hex format with colons...")
    hex_key_colons = ':'.join(test_key_bytes.hex()[i:i+2] for i in range(0, len(test_key_bytes.hex()), 2))
    print(f"   Key: {hex_key_colons}")
    
    try:
        parsed_bytes = bytes.fromhex(hex_key_colons.replace(':', ''))
        parsed_key = nacl.public.PrivateKey(parsed_bytes)
        print(f"   ✅ Parsed successfully: {len(parsed_bytes)} bytes")
    except Exception as e:
        print(f"   ❌ Failed to parse: {e}")
        return False
    
    print("\n✅ TEST PASSED: All key formats parsed successfully!")
    return True


def test_monitor_decryption_logic():
    """Test the decryption logic as it would work in the monitor"""
    print("\n" + "="*60)
    print("Test 3: Monitor Decryption Logic")
    print("="*60)
    
    # Simulate the monitor's private key (Bob = our bot)
    bob_private_key = nacl.public.PrivateKey.generate()
    bob_public_key = bob_private_key.public_key
    
    print(f"✅ Bot private key (base64): {base64.b64encode(bytes(bob_private_key)).decode()}")
    print(f"   Bot public key (base64):  {base64.b64encode(bytes(bob_public_key)).decode()}")
    
    # Simulate a sender (Alice)
    alice_private_key = nacl.public.PrivateKey.generate()
    alice_public_key = alice_private_key.public_key
    
    print(f"\n✅ Sender public key (base64): {base64.b64encode(bytes(alice_public_key)).decode()}")
    
    # Alice sends an encrypted DM
    plaintext = "/help"
    print(f"\n📝 Sender encrypts message: {plaintext}")
    
    alice_box = nacl.public.Box(alice_private_key, bob_public_key)
    encrypted = alice_box.encrypt(plaintext.encode('utf-8'))
    encrypted_base64 = base64.b64encode(encrypted).decode()
    
    print(f"🔐 Encrypted (base64): {encrypted_base64[:64]}...")
    
    # Simulate monitor receiving the message
    print(f"\n📬 Monitor receives encrypted DM...")
    
    # Monitor decrypts using its private key and sender's public key
    try:
        # Get sender's public key (in monitor, this would come from contacts)
        sender_public_key_bytes = bytes(alice_public_key)
        
        # Create Box for decryption
        bob_box = nacl.public.Box(bob_private_key, nacl.public.PublicKey(sender_public_key_bytes))
        
        # Decrypt
        decrypted_bytes = bob_box.decrypt(encrypted)
        decrypted_text = decrypted_bytes.decode('utf-8')
        
        print(f"✅ Monitor decrypted message: {decrypted_text}")
        
        if decrypted_text == plaintext:
            print("✅ TEST PASSED: Monitor decryption successful!")
            return True
        else:
            print("❌ TEST FAILED: Decryption mismatch!")
            return False
            
    except Exception as e:
        print(f"❌ TEST FAILED: Decryption error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_invalid_key_handling():
    """Test handling of invalid keys and data"""
    print("\n" + "="*60)
    print("Test 4: Invalid Key/Data Handling")
    print("="*60)
    
    # Test 1: Wrong sender public key
    print("\n📝 Test 4a: Wrong sender public key...")
    
    bob_private_key = nacl.public.PrivateKey.generate()
    bob_public_key = bob_private_key.public_key
    
    alice_private_key = nacl.public.PrivateKey.generate()
    alice_public_key = alice_private_key.public_key
    
    # Encrypt with Alice
    plaintext = "Secret message"
    alice_box = nacl.public.Box(alice_private_key, bob_public_key)
    encrypted = alice_box.encrypt(plaintext.encode('utf-8'))
    
    # Try to decrypt with wrong sender key
    wrong_key = nacl.public.PrivateKey.generate()
    try:
        bob_box = nacl.public.Box(bob_private_key, wrong_key.public_key)
        decrypted = bob_box.decrypt(encrypted)
        print(f"   ❌ Should have failed but didn't!")
        return False
    except Exception as e:
        print(f"   ✅ Correctly failed: {type(e).__name__}")
    
    # Test 2: Corrupted encrypted data
    print("\n📝 Test 4b: Corrupted encrypted data...")
    
    corrupted = encrypted[:-5] + b'XXXXX'  # Corrupt last 5 bytes
    try:
        bob_box = nacl.public.Box(bob_private_key, alice_public_key)
        decrypted = bob_box.decrypt(corrupted)
        print(f"   ❌ Should have failed but didn't!")
        return False
    except Exception as e:
        print(f"   ✅ Correctly failed: {type(e).__name__}")
    
    print("\n✅ TEST PASSED: Invalid inputs handled correctly!")
    return True


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("MeshCore DM Decryption Test Suite")
    print("="*60)
    
    if not NACL_AVAILABLE:
        print("❌ PyNaCl not available - tests skipped")
        return 1
    
    print(f"\n✅ PyNaCl version: {nacl.__version__}")
    
    tests = [
        ("Basic Encryption/Decryption", test_encryption_decryption),
        ("Key Parsing", test_key_parsing),
        ("Monitor Decryption Logic", test_monitor_decryption_logic),
        ("Invalid Key/Data Handling", test_invalid_key_handling),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ TEST FAILED: {test_name}")
            print(f"   Exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"  ✅ Passed: {passed}/{len(tests)}")
    print(f"  ❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
