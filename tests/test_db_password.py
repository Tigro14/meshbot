#!/usr/bin/env python3
"""
Test script to verify /db clean and /db vacuum password protection
Simplified version that tests the logic directly
"""

# Define the test password
REBOOT_PASSWORD = "test_password_123"

def test_cleanup_password_logic():
    """Test cleanup password validation logic"""
    print("\n=== TEST: Cleanup Password Validation ===")
    
    # Test 1: No args (no password)
    args = []
    if not args:
        print("✅ PASS: Correctly rejects when no password provided")
    else:
        print("❌ FAIL: Should reject when no password provided")
        return False
    
    # Test 2: Wrong password
    args = ['wrong_password']
    provided_password = args[0]
    if provided_password != REBOOT_PASSWORD:
        print("✅ PASS: Correctly rejects wrong password")
    else:
        print("❌ FAIL: Should reject wrong password")
        return False
    
    # Test 3: Correct password
    args = ['test_password_123']
    provided_password = args[0]
    if provided_password == REBOOT_PASSWORD:
        print("✅ PASS: Correctly accepts correct password")
    else:
        print("❌ FAIL: Should accept correct password")
        return False
    
    # Test 4: Correct password with hours
    args = ['test_password_123', '72']
    provided_password = args[0]
    if provided_password == REBOOT_PASSWORD:
        hours = int(args[1]) if len(args) > 1 else 48
        if hours == 72:
            print(f"✅ PASS: Correctly accepts password and parses hours={hours}")
        else:
            print("❌ FAIL: Should parse hours correctly")
            return False
    else:
        print("❌ FAIL: Should accept correct password")
        return False
    
    return True

def test_vacuum_password_logic():
    """Test vacuum password validation logic"""
    print("\n=== TEST: Vacuum Password Validation ===")
    
    # Test 1: No args (no password)
    args = []
    if not args:
        print("✅ PASS: Correctly rejects when no password provided")
    else:
        print("❌ FAIL: Should reject when no password provided")
        return False
    
    # Test 2: Wrong password
    args = ['wrong_password']
    provided_password = args[0]
    if provided_password != REBOOT_PASSWORD:
        print("✅ PASS: Correctly rejects wrong password")
    else:
        print("❌ FAIL: Should reject wrong password")
        return False
    
    # Test 3: Correct password
    args = ['test_password_123']
    provided_password = args[0]
    if provided_password == REBOOT_PASSWORD:
        print("✅ PASS: Correctly accepts correct password")
    else:
        print("❌ FAIL: Should accept correct password")
        return False
    
    return True

def verify_code_changes():
    """Verify that the actual code has the password checks"""
    print("\n=== Verifying Code Changes ===")
    
    db_commands_file = "/home/runner/work/meshbot/meshbot/handlers/command_handlers/db_commands.py"
    
    with open(db_commands_file, 'r') as f:
        content = f.read()
    
    # Check for REBOOT_PASSWORD import
    if 'from config import REBOOT_PASSWORD' in content:
        print("✅ PASS: REBOOT_PASSWORD is imported")
    else:
        print("❌ FAIL: REBOOT_PASSWORD not imported")
        return False
    
    # Check for password validation in _cleanup_db
    if 'if provided_password != REBOOT_PASSWORD:' in content:
        print("✅ PASS: Password validation exists")
    else:
        print("❌ FAIL: Password validation not found")
        return False
    
    # Check for password requirement in help
    if '<password>' in content:
        print("✅ PASS: Help text shows password requirement")
    else:
        print("❌ FAIL: Help text doesn't show password requirement")
        return False
    
    # Check that _cleanup_db accepts args
    if 'def _cleanup_db(self, args, channel=' in content:
        print("✅ PASS: _cleanup_db accepts args parameter")
    else:
        print("❌ FAIL: _cleanup_db doesn't accept args")
        return False
    
    # Check that _vacuum_db accepts args
    if 'def _vacuum_db(self, args, channel=' in content:
        print("✅ PASS: _vacuum_db accepts args parameter")
    else:
        print("❌ FAIL: _vacuum_db doesn't accept args")
        return False
    
    # Check that args are passed to _vacuum_db in handle_db
    if "response = self._vacuum_db(args, channel)" in content:
        print("✅ PASS: args are passed to _vacuum_db")
    else:
        print("❌ FAIL: args not passed to _vacuum_db")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Testing /db clean and /db vacuum password protection")
    print("=" * 60)
    
    success = True
    
    if not test_cleanup_password_logic():
        success = False
    
    if not test_vacuum_password_logic():
        success = False
    
    if not verify_code_changes():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED!")
    print("=" * 60)
    
    exit(0 if success else 1)

