#!/usr/bin/env python3
"""
Test: Private/Public Key Pair Validation

This test validates the key pair validation functionality added to
meshcore_cli_wrapper.py to detect mismatched private/public keys.

Issue: User suspects private key on connected node doesn't match public key
Solution: Add validation to check if private key can derive expected public key
"""

import sys
import os
import unittest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Check if PyNaCl is available
try:
    import nacl.public
    import nacl.encoding
    NACL_AVAILABLE = True
    print("✅ PyNaCl disponible - tests complets possibles")
except ImportError:
    NACL_AVAILABLE = False
    print("⚠️  PyNaCl non disponible - tests limités")
    print("   Installation: pip install PyNaCl")


class TestKeyPairValidation(unittest.TestCase):
    """Test key pair validation"""
    
    @unittest.skipIf(not NACL_AVAILABLE, "PyNaCl not available")
    def test_valid_key_pair(self):
        """Test validation with a valid key pair"""
        # Generate a valid key pair
        private_key = nacl.public.PrivateKey.generate()
        public_key = private_key.public_key
        
        # Get bytes
        private_key_bytes = bytes(private_key)
        public_key_bytes = bytes(public_key)
        
        # Mock meshcore wrapper's validation method
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create a dummy wrapper (won't actually connect)
        # We'll just test the validation method
        wrapper = object.__new__(MeshCoreCLIWrapper)
        
        # Test validation
        is_valid, derived_public_key, error_msg = wrapper._validate_key_pair(
            private_key_bytes,
            public_key_bytes
        )
        
        self.assertTrue(is_valid, f"Valid key pair should validate: {error_msg}")
        self.assertIsNone(error_msg)
        self.assertEqual(derived_public_key, public_key_bytes)
        
        print(f"✅ Valid key pair validated successfully")
        print(f"   Private key (hex): {private_key_bytes.hex()[:16]}...")
        print(f"   Public key (hex):  {public_key_bytes.hex()[:16]}...")
    
    @unittest.skipIf(not NACL_AVAILABLE, "PyNaCl not available")
    def test_mismatched_key_pair(self):
        """Test validation with mismatched keys"""
        # Generate two different key pairs
        private_key1 = nacl.public.PrivateKey.generate()
        private_key2 = nacl.public.PrivateKey.generate()
        
        # Use private key from pair 1, public key from pair 2 (mismatch!)
        private_key_bytes = bytes(private_key1)
        wrong_public_key_bytes = bytes(private_key2.public_key)
        
        # Mock meshcore wrapper's validation method
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        wrapper = object.__new__(MeshCoreCLIWrapper)
        
        # Test validation - should detect mismatch
        is_valid, derived_public_key, error_msg = wrapper._validate_key_pair(
            private_key_bytes,
            wrong_public_key_bytes
        )
        
        self.assertFalse(is_valid, "Mismatched key pair should fail validation")
        self.assertIsNotNone(error_msg)
        self.assertIn("ne correspond pas", error_msg.lower())
        
        print(f"✅ Mismatched key pair detected successfully")
        print(f"   Error: {error_msg}")
    
    @unittest.skipIf(not NACL_AVAILABLE, "PyNaCl not available")
    def test_key_hex_format(self):
        """Test validation with hex-encoded keys"""
        # Generate a key pair
        private_key = nacl.public.PrivateKey.generate()
        public_key = private_key.public_key
        
        # Convert to hex
        private_key_hex = bytes(private_key).hex()
        public_key_hex = bytes(public_key).hex()
        
        # Mock meshcore wrapper's validation method
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        wrapper = object.__new__(MeshCoreCLIWrapper)
        
        # Test validation with hex strings
        is_valid, derived_public_key, error_msg = wrapper._validate_key_pair(
            private_key_hex,
            public_key_hex
        )
        
        self.assertTrue(is_valid, f"Hex-encoded key pair should validate: {error_msg}")
        self.assertIsNone(error_msg)
        
        print(f"✅ Hex-encoded keys validated successfully")
    
    @unittest.skipIf(not NACL_AVAILABLE, "PyNaCl not available")
    def test_key_base64_format(self):
        """Test validation with base64-encoded keys"""
        import base64
        
        # Generate a key pair
        private_key = nacl.public.PrivateKey.generate()
        public_key = private_key.public_key
        
        # Convert to base64
        private_key_b64 = base64.b64encode(bytes(private_key)).decode()
        public_key_b64 = base64.b64encode(bytes(public_key)).decode()
        
        # Mock meshcore wrapper's validation method
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        wrapper = object.__new__(MeshCoreCLIWrapper)
        
        # Test validation with base64 strings
        is_valid, derived_public_key, error_msg = wrapper._validate_key_pair(
            private_key_b64,
            public_key_b64
        )
        
        self.assertTrue(is_valid, f"Base64-encoded key pair should validate: {error_msg}")
        self.assertIsNone(error_msg)
        
        print(f"✅ Base64-encoded keys validated successfully")
    
    @unittest.skipIf(not NACL_AVAILABLE, "PyNaCl not available")
    def test_node_id_derivation(self):
        """Test that node_id can be derived from public key"""
        # Generate a key pair
        private_key = nacl.public.PrivateKey.generate()
        public_key = private_key.public_key
        public_key_bytes = bytes(public_key)
        
        # Derive node_id (first 4 bytes of public key)
        node_id = int.from_bytes(public_key_bytes[:4], 'big')
        
        print(f"✅ Node ID derivation test")
        print(f"   Public key: {public_key_bytes.hex()[:16]}...")
        print(f"   Node ID: 0x{node_id:08x}")
        
        # Verify it's a valid 32-bit value
        self.assertGreaterEqual(node_id, 0)
        self.assertLess(node_id, 2**32)
    
    @unittest.skipIf(not NACL_AVAILABLE, "PyNaCl not available")
    def test_invalid_key_size(self):
        """Test validation with invalid key size"""
        # Invalid private key (wrong size)
        invalid_key = b'too_short'
        
        # Mock meshcore wrapper's validation method
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        wrapper = object.__new__(MeshCoreCLIWrapper)
        
        # Test validation - should fail
        is_valid, derived_public_key, error_msg = wrapper._validate_key_pair(
            invalid_key
        )
        
        self.assertFalse(is_valid, "Invalid key size should fail validation")
        self.assertIsNotNone(error_msg)
        self.assertIn("32 octets", error_msg.lower())
        
        print(f"✅ Invalid key size detected: {error_msg}")
    
    def test_nacl_not_available_graceful_fallback(self):
        """Test graceful fallback when PyNaCl not available"""
        # This test runs even without PyNaCl
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        wrapper = object.__new__(MeshCoreCLIWrapper)
        
        # If NACL_AVAILABLE is False in the module, validation should return None
        # We'll test the actual behavior
        result = wrapper._validate_key_pair(b'dummy_key')
        
        if NACL_AVAILABLE:
            # Should get validation result (likely False for dummy key)
            self.assertIsInstance(result, tuple)
            print("✅ PyNaCl available - validation performed")
        else:
            # Should get None with error message about PyNaCl
            is_valid, _, error_msg = result
            self.assertIsNone(is_valid)
            self.assertIn("PyNaCl", error_msg)
            print(f"✅ Graceful fallback when PyNaCl not available: {error_msg}")


def run_tests():
    """Run the test suite"""
    print("\n" + "="*70)
    print("  Testing Private/Public Key Pair Validation")
    print("="*70 + "\n")
    
    if not NACL_AVAILABLE:
        print("⚠️  PyNaCl non disponible - seuls les tests de fallback seront exécutés")
        print("   Installation: pip install PyNaCl")
        print()
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestKeyPairValidation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("  ✅ ALL TESTS PASSED!")
        print(f"     {result.testsRun} tests run successfully")
        if NACL_AVAILABLE:
            print("\n  Key pair validation functionality verified:")
            print("  - Valid key pairs validate successfully")
            print("  - Mismatched keys are detected")
            print("  - Multiple key formats supported (bytes/hex/base64)")
            print("  - Node ID can be derived from public key")
            print("  - Invalid keys are rejected")
        else:
            print("\n  Graceful fallback verified when PyNaCl not available")
    else:
        print("  ❌ SOME TESTS FAILED")
        print(f"     Failures: {len(result.failures)}")
        print(f"     Errors: {len(result.errors)}")
    print("="*70 + "\n")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
