#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify the Telegram integration fix
Tests that the Application builder accepts the timeout parameters
and that start_polling doesn't receive invalid parameters
"""

import sys
import traceback

def test_application_builder_timeouts():
    """Test that Application.builder() accepts timeout parameters"""
    try:
        from telegram.ext import Application
        
        print("Testing Application.builder() with timeout parameters...")
        
        # This should work without errors
        app_builder = (
            Application.builder()
            .token("test_token_123:ABCdefGHI")  # Dummy token
            .read_timeout(180)
            .write_timeout(180)
            .connect_timeout(180)
            .pool_timeout(180)
        )
        
        print("✅ Application.builder() accepts all timeout parameters")
        return True
        
    except AttributeError as e:
        print(f"❌ Application.builder() doesn't support timeout methods: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        traceback.print_exc()
        return False

def test_start_polling_signature():
    """Test that start_polling doesn't accept deprecated parameters"""
    try:
        from telegram.ext import Updater
        import inspect
        
        print("\nChecking start_polling signature...")
        
        # Get the signature of start_polling
        sig = inspect.signature(Updater.start_polling)
        params = list(sig.parameters.keys())
        
        print(f"start_polling parameters: {params}")
        
        # Check that deprecated parameters are NOT in the signature
        deprecated = ['read_timeout', 'write_timeout', 'connect_timeout', 'pool_timeout']
        found_deprecated = [p for p in deprecated if p in params]
        
        if found_deprecated:
            print(f"⚠️ Found deprecated parameters in signature: {found_deprecated}")
            print("   This suggests an older version of python-telegram-bot")
            return False
        else:
            print("✅ No deprecated timeout parameters in start_polling signature")
            return True
            
    except ImportError as e:
        print(f"⚠️ Cannot import Updater: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Telegram Integration Fix")
    print("=" * 60)
    
    try:
        import telegram
        print(f"python-telegram-bot version: {telegram.__version__}")
    except ImportError:
        print("⚠️ python-telegram-bot is not installed")
        print("   This test requires python-telegram-bot>=21.0")
        return False
    except AttributeError:
        print("⚠️ Cannot determine python-telegram-bot version")
    
    print()
    
    # Run tests
    test1 = test_application_builder_timeouts()
    test2 = test_start_polling_signature()
    
    print("\n" + "=" * 60)
    if test1 and test2:
        print("✅ All tests passed!")
        print("   The fix should work correctly with this version of python-telegram-bot")
        return True
    else:
        print("⚠️ Some tests failed")
        print("   Please check the python-telegram-bot version (should be >=21.0)")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
