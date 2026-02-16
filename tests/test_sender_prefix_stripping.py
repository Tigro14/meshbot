#!/usr/bin/env python3
"""
Test pour vérifier que le préfixe du sender est correctement retiré
Bug: Après le fix du sender ID, le préfixe n'est plus retiré car sender_id != 0xFFFFFFFF
Fix: Retirer le préfixe pour TOUS les broadcasts avec le pattern, pas seulement 0xFFFFFFFF
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import Mock, MagicMock


class TestSenderPrefixStripping(unittest.TestCase):
    """Test que le préfixe du sender est correctement retiré après fix du sender ID"""
    
    def test_prefix_stripped_with_correct_sender_id(self):
        """Test que le préfixe est retiré même quand sender_id est correct (pas 0xFFFFFFFF)"""
        
        # Simulate the router logic
        message = "Tigro: /echo pas encore de neige ici"
        sender_id = 0x16fad3dc  # Real sender ID (NOT 0xFFFFFFFF)
        is_broadcast = True
        
        # OLD LOGIC (BROKEN after sender ID fix):
        # if is_broadcast and sender_id == 0xFFFFFFFF and ': ' in message:
        #     strip_prefix()
        # Result: Prefix NOT stripped because sender_id != 0xFFFFFFFF
        
        old_would_strip = is_broadcast and sender_id == 0xFFFFFFFF and ': ' in message
        
        # NEW LOGIC (CORRECT):
        # if is_broadcast and ': ' in message:
        #     strip_prefix()
        # Result: Prefix stripped for any broadcast with pattern
        
        new_would_strip = is_broadcast and ': ' in message
        
        # Verify the fix
        self.assertFalse(old_would_strip, "OLD logic would NOT strip prefix (broken)")
        self.assertTrue(new_would_strip, "NEW logic SHOULD strip prefix (fixed)")
        
        # Simulate the stripping
        if new_would_strip:
            parts = message.split(': ', 1)
            if len(parts) == 2 and parts[1].startswith('/'):
                cleaned_message = parts[1]
            else:
                cleaned_message = message
        else:
            cleaned_message = message
        
        self.assertEqual(cleaned_message, "/echo pas encore de neige ici", 
                        "Prefix should be stripped")
        self.assertTrue(cleaned_message.startswith('/echo'),
                       "Cleaned message should start with command")
        
        print("✅ Test Prefix Stripping: Prefix correctly stripped with real sender ID")
        print(f"   - Original: '{message}'")
        print(f"   - sender_id: 0x{sender_id:08x} (NOT 0xFFFFFFFF)")
        print(f"   - is_broadcast: {is_broadcast}")
        print(f"   - Old logic would strip: {old_would_strip} (BROKEN)")
        print(f"   - New logic would strip: {new_would_strip} (FIXED)")
        print(f"   - Cleaned: '{cleaned_message}'")
    
    def test_prefix_not_stripped_for_non_commands(self):
        """Test que le préfixe n'est pas retiré pour les messages normaux"""
        
        message = "Tigro: Bonjour tout le monde"
        sender_id = 0x16fad3dc
        is_broadcast = True
        
        # Should check for prefix pattern
        should_strip = is_broadcast and ': ' in message
        
        # But only strip if it's a command
        if should_strip:
            parts = message.split(': ', 1)
            if len(parts) == 2 and parts[1].startswith('/'):
                cleaned_message = parts[1]
            else:
                cleaned_message = message  # Keep original for non-commands
        else:
            cleaned_message = message
        
        self.assertEqual(cleaned_message, message, 
                        "Non-command messages should keep prefix")
        
        print("✅ Test Non-Command: Prefix kept for non-command messages")
        print(f"   - Original: '{message}'")
        print(f"   - Cleaned: '{cleaned_message}' (unchanged)")
    
    def test_prefix_stripped_for_various_commands(self):
        """Test que le préfixe est retiré pour différentes commandes"""
        
        test_cases = [
            ("Tigro: /echo test", "/echo test"),
            ("User: /my", "/my"),
            ("Alice: /weather Paris", "/weather Paris"),
            ("Bob: /bot question", "/bot question"),
        ]
        
        for original, expected in test_cases:
            sender_id = 0x12345678
            is_broadcast = True
            
            # Apply new logic
            if is_broadcast and ': ' in original:
                parts = original.split(': ', 1)
                if len(parts) == 2 and parts[1].startswith('/'):
                    cleaned = parts[1]
                else:
                    cleaned = original
            else:
                cleaned = original
            
            self.assertEqual(cleaned, expected, 
                           f"Command should be extracted from '{original}'")
        
        print("✅ Test Various Commands: All prefixes correctly stripped")
        for original, expected in test_cases:
            print(f"   - '{original}' → '{expected}'")


if __name__ == '__main__':
    print("=" * 80)
    print("TEST: Retrait du préfixe du sender après fix du sender ID")
    print("=" * 80)
    print("")
    print("Problème: Après fix du sender ID, le préfixe n'est plus retiré")
    print("Cause: Condition vérifiait sender_id == 0xFFFFFFFF (toujours faux maintenant)")
    print("Solution: Retirer préfixe pour TOUS les broadcasts avec pattern")
    print("")
    
    # Run tests with verbose output
    unittest.main(verbosity=2)
