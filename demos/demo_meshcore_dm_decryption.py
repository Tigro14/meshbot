#!/usr/bin/env python3
"""
Demo: MeshCore DM Decryption

This script demonstrates how the meshcore-serial-monitor.py decrypts
encrypted Direct Messages using PyNaCl.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import base64

try:
    import nacl.public
    import nacl.utils
except ImportError:
    print("❌ PyNaCl not installed")
    print("   Install with: pip install PyNaCl")
    sys.exit(1)


def demo_basic_flow():
    """Demonstrate the complete encryption/decryption flow"""
    print("\n" + "="*70)
    print("DEMO: MeshCore DM Encryption/Decryption Flow")
    print("="*70)
    
    # Step 1: Setup
    print("\n📋 STEP 1: Device Setup")
    print("-" * 70)
    
    # Bob = Our bot/device (receiver)
    bob_private_key = nacl.public.PrivateKey.generate()
    bob_public_key = bob_private_key.public_key
    
    print("🤖 Our Device (Bob):")
    print(f"   Private Key: {base64.b64encode(bytes(bob_private_key)).decode()}")
    print(f"   Public Key:  {base64.b64encode(bytes(bob_public_key)).decode()}")
    print("   ℹ️  Private key is secret, never shared")
    print("   ℹ️  Public key is broadcasted to network via NODEINFO")
    
    # Alice = Sender
    alice_private_key = nacl.public.PrivateKey.generate()
    alice_public_key = alice_private_key.public_key
    
    print("\n👤 Sender Device (Alice):")
    print(f"   Private Key: {base64.b64encode(bytes(alice_private_key)).decode()}")
    print(f"   Public Key:  {base64.b64encode(bytes(alice_public_key)).decode()}")
    print("   ℹ️  Alice's public key stored in Bob's contact list")
    
    # Step 2: Encryption (Alice's side)
    print("\n📤 STEP 2: Sender Encrypts Message")
    print("-" * 70)
    
    plaintext = "/help"
    print(f"📝 Alice wants to send DM: \"{plaintext}\"")
    
    # Alice creates a Box using her private key and Bob's public key
    alice_box = nacl.public.Box(alice_private_key, bob_public_key)
    
    # Encrypt the message
    encrypted = alice_box.encrypt(plaintext.encode('utf-8'))
    encrypted_base64 = base64.b64encode(encrypted).decode()
    
    print(f"\n🔐 Alice encrypts using:")
    print(f"   • Her private key (signing)")
    print(f"   • Bob's public key (encryption)")
    print(f"   • NaCl crypto_box algorithm")
    
    print(f"\n📦 Encrypted message:")
    print(f"   Raw bytes: {len(encrypted)} bytes")
    print(f"   Base64:    {encrypted_base64[:64]}...")
    print(f"              {encrypted_base64[64:] if len(encrypted_base64) > 64 else ''}")
    
    print(f"\n📡 Message structure:")
    print(f"   [Nonce: 24 bytes][Ciphertext: {len(encrypted) - 40} bytes][MAC: 16 bytes]")
    
    # Step 3: Transmission
    print("\n📡 STEP 3: Message Transmission")
    print("-" * 70)
    
    print("🌐 Message sent via MeshCore radio:")
    print("   • Over LoRa frequency")
    print("   • Addressed to Bob (contact_id)")
    print("   • Encrypted end-to-end")
    print("   • No intermediate nodes can decrypt")
    
    # Step 4: Reception
    print("\n📥 STEP 4: Our Device Receives Message")
    print("-" * 70)
    
    print("📬 meshcore-serial-monitor.py receives CONTACT_MSG_RECV event:")
    print(f"   Event: ContactMessageEvent")
    print(f"   From:  0x{int.from_bytes(bytes(alice_public_key)[:4], 'big'):08x}")
    print(f"   Text:  {encrypted_base64[:50]}...")
    print(f"   ℹ️  Text appears encrypted (non-printable/base64 pattern)")
    
    # Step 5: Decryption detection
    print("\n🔍 STEP 5: Encrypted Message Detection")
    print("-" * 70)
    
    print("✅ Monitor detects encrypted message:")
    print("   • Text contains non-printable characters")
    print("   • OR text matches base64 pattern")
    print("   • Private key is configured (--private-key)")
    
    print("\n🔑 Monitor retrieves decryption keys:")
    print("   • Our private key: From CLI argument")
    print("   • Sender's public key: From MeshCore contacts")
    
    # Step 6: Decryption (Bob's side)
    print("\n🔓 STEP 6: Message Decryption")
    print("-" * 70)
    
    print("🔐 Monitor decrypts using:")
    print(f"   • Our private key (decryption)")
    print(f"   • Alice's public key (verification)")
    print(f"   • NaCl crypto_box_open")
    
    # Bob creates a Box using his private key and Alice's public key
    bob_box = nacl.public.Box(bob_private_key, alice_public_key)
    
    # Decrypt the message
    decrypted_bytes = bob_box.decrypt(encrypted)
    decrypted_text = decrypted_bytes.decode('utf-8')
    
    print(f"\n✅ Decryption successful!")
    print(f"   Original:  \"{plaintext}\"")
    print(f"   Decrypted: \"{decrypted_text}\"")
    print(f"   Match:     {'✅ YES' if plaintext == decrypted_text else '❌ NO'}")
    
    # Step 7: Result
    print("\n✨ STEP 7: Result Display")
    print("-" * 70)
    
    print("📊 Monitor output:")
    print(f"   ============================================================")
    print(f"   [14:23:45] 📬 Message #1 received!")
    print(f"   ============================================================")
    print(f"   Event type: ContactMessageEvent")
    print(f"     From: 0x{int.from_bytes(bytes(alice_public_key)[:4], 'big'):08x}")
    print(f"     Text: {encrypted_base64[:50]}...")
    print(f"   ")
    print(f"   🔐 Text appears encrypted, attempting decryption...")
    print(f"     ✅ Found sender's public key (32 bytes)")
    print(f"     ✅ Decryption successful!")
    print(f"     📨 Decrypted text: {decrypted_text}")
    print(f"   ============================================================")
    
    # Summary
    print("\n📋 SUMMARY")
    print("-" * 70)
    print("✅ End-to-end encryption preserved")
    print("✅ Only Bob can decrypt (has private key)")
    print("✅ Alice's identity verified (public key signature)")
    print("✅ No intermediate nodes can read message")
    print("✅ Monitor provides diagnostic visibility")


def demo_security():
    """Demonstrate security properties"""
    print("\n" + "="*70)
    print("DEMO: Security Properties")
    print("="*70)
    
    # Setup keys
    bob_private_key = nacl.public.PrivateKey.generate()
    bob_public_key = bob_private_key.public_key
    
    alice_private_key = nacl.public.PrivateKey.generate()
    alice_public_key = alice_private_key.public_key
    
    eve_private_key = nacl.public.PrivateKey.generate()  # Attacker
    eve_public_key = eve_private_key.public_key
    
    print("\n👥 Participants:")
    print("   🤖 Bob (our device) - Legitimate receiver")
    print("   👤 Alice - Legitimate sender")
    print("   👿 Eve - Attacker trying to read message")
    
    # Alice encrypts message to Bob
    plaintext = "Secret message!"
    alice_box = nacl.public.Box(alice_private_key, bob_public_key)
    encrypted = alice_box.encrypt(plaintext.encode('utf-8'))
    
    print(f"\n📤 Alice sends encrypted DM to Bob: \"{plaintext}\"")
    
    # Test 1: Bob can decrypt
    print("\n✅ TEST 1: Legitimate Receiver (Bob)")
    print("-" * 70)
    try:
        bob_box = nacl.public.Box(bob_private_key, alice_public_key)
        decrypted = bob_box.decrypt(encrypted)
        print(f"   ✅ Bob decrypts: \"{decrypted.decode('utf-8')}\"")
        print(f"   ℹ️  Bob has his private key + Alice's public key")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Test 2: Eve cannot decrypt (no Bob's private key)
    print("\n❌ TEST 2: Attacker Without Receiver's Private Key (Eve)")
    print("-" * 70)
    try:
        eve_box = nacl.public.Box(eve_private_key, alice_public_key)
        decrypted = eve_box.decrypt(encrypted)
        print(f"   ❌ Eve decrypts: \"{decrypted.decode('utf-8')}\"")
        print(f"   ⚠️  SECURITY BREACH!")
    except Exception as e:
        print(f"   ✅ Eve cannot decrypt: {type(e).__name__}")
        print(f"   ℹ️  Eve doesn't have Bob's private key")
    
    # Test 3: Eve cannot decrypt (wrong sender key)
    print("\n❌ TEST 3: Attacker With Wrong Sender Key")
    print("-" * 70)
    try:
        # Eve tries to decrypt using Bob's private key but wrong sender key
        bob_box_wrong = nacl.public.Box(bob_private_key, eve_public_key)
        decrypted = bob_box_wrong.decrypt(encrypted)
        print(f"   ❌ Decrypts: \"{decrypted.decode('utf-8')}\"")
        print(f"   ⚠️  SECURITY BREACH!")
    except Exception as e:
        print(f"   ✅ Cannot decrypt: {type(e).__name__}")
        print(f"   ℹ️  Message was encrypted with Alice's key, not Eve's")
    
    # Test 4: Message tampering detection
    print("\n❌ TEST 4: Message Tampering Detection")
    print("-" * 70)
    try:
        # Corrupt the encrypted message
        tampered = encrypted[:-5] + b'XXXXX'
        bob_box = nacl.public.Box(bob_private_key, alice_public_key)
        decrypted = bob_box.decrypt(tampered)
        print(f"   ❌ Tampered message accepted: \"{decrypted.decode('utf-8')}\"")
        print(f"   ⚠️  SECURITY BREACH!")
    except Exception as e:
        print(f"   ✅ Tampering detected: {type(e).__name__}")
        print(f"   ℹ️  Poly1305 MAC verification failed")
    
    # Summary
    print("\n📋 SECURITY SUMMARY")
    print("-" * 70)
    print("✅ Only receiver with private key can decrypt")
    print("✅ Sender identity verified via public key")
    print("✅ Message tampering detected via MAC")
    print("✅ Forward secrecy (ephemeral keys in full implementation)")
    print("✅ Resistant to replay attacks (with proper nonce management)")


def demo_key_formats():
    """Demonstrate different key format support"""
    print("\n" + "="*70)
    print("DEMO: Supported Key Formats")
    print("="*70)
    
    # Generate a test key
    test_key = nacl.public.PrivateKey.generate()
    test_key_bytes = bytes(test_key)
    
    print("\n🔑 Private Key (32 bytes):")
    print(f"   Raw bytes: {test_key_bytes[:16].hex()}... ({len(test_key_bytes)} bytes)")
    
    # Format 1: Base64
    print("\n📝 Format 1: Base64 (Recommended)")
    print("-" * 70)
    base64_key = base64.b64encode(test_key_bytes).decode()
    print(f"   {base64_key}")
    print(f"   Length: {len(base64_key)} characters")
    print(f"   Usage:  --private-key \"{base64_key}\"")
    
    # Format 2: Hex
    print("\n📝 Format 2: Hex")
    print("-" * 70)
    hex_key = test_key_bytes.hex()
    print(f"   {hex_key}")
    print(f"   Length: {len(hex_key)} characters")
    print(f"   Usage:  --private-key \"{hex_key}\"")
    
    # Format 3: Hex with colons
    print("\n📝 Format 3: Hex with Colons (Hardware Style)")
    print("-" * 70)
    hex_key_colons = ':'.join(test_key_bytes.hex()[i:i+2] for i in range(0, len(test_key_bytes.hex()), 2))
    print(f"   {hex_key_colons}")
    print(f"   Length: {len(hex_key_colons)} characters")
    print(f"   Usage:  --private-key \"{hex_key_colons}\"")
    
    # Format 4: File
    print("\n📝 Format 4: Key File")
    print("-" * 70)
    print(f"   File: my_private_key.txt")
    print(f"   Content: {base64_key}")
    print(f"   Usage: --private-key-file my_private_key.txt")
    print(f"   ")
    print(f"   Create file:")
    print(f"   echo \"{base64_key}\" > my_private_key.txt")
    print(f"   chmod 600 my_private_key.txt")


def main():
    """Run all demos"""
    print("\n" + "="*70)
    print("MeshCore DM Decryption - Interactive Demo")
    print("="*70)
    print("\nThis demo shows how the meshcore-serial-monitor.py decrypts")
    print("encrypted Direct Messages using PyNaCl (Curve25519 + XSalsa20-Poly1305)")
    
    demos = [
        ("Complete Encryption/Decryption Flow", demo_basic_flow),
        ("Security Properties", demo_security),
        ("Supported Key Formats", demo_key_formats),
    ]
    
    for i, (name, demo_func) in enumerate(demos, 1):
        input(f"\nPress Enter to see Demo {i}/{len(demos)}: {name}...")
        demo_func()
    
    print("\n" + "="*70)
    print("Demo Complete!")
    print("="*70)
    print("\n📚 Next Steps:")
    print("   1. Install PyNaCl: pip install PyNaCl")
    print("   2. Get your private key from MeshCore device")
    print("   3. Run monitor with decryption:")
    print("      python3 meshcore-serial-monitor.py /dev/ttyACM0 \\")
    print("        --private-key-file my_private_key.txt \\")
    print("        --debug")
    print("\n📖 Documentation: MESHCORE_DM_DECRYPTION.md")
    print("🧪 Test Suite: python3 test_meshcore_dm_decryption.py")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✅ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
