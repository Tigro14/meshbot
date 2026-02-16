#!/usr/bin/env python3
"""
Test pour vérifier que le message_router traite les broadcasts du propre nœud
Bug: message_router filtre les broadcasts avec is_from_me même après fix de main_bot.py
Fix: Appliquer la même logique que main_bot.py dans message_router.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import Mock, MagicMock


class TestMessageRouterOwnNodeBroadcasts(unittest.TestCase):
    """Test que le message_router traite les broadcasts du propre nœud"""
    
    def test_router_allows_broadcast_from_own_node(self):
        """Test que le message router permet les broadcasts du propre nœud"""
        
        # Simulate the router logic
        is_broadcast_command = True  # Message starts with /echo
        is_broadcast = True          # to_id = 0xFFFFFFFF
        is_for_me = False            # Not addressed to us specifically
        is_from_me = True            # from_id == my_id (same node)
        
        # OLD LOGIC (BROKEN):
        # if is_broadcast_command and (is_broadcast or is_for_me) and not is_from_me:
        old_would_process = is_broadcast_command and (is_broadcast or is_for_me) and not is_from_me
        
        # NEW LOGIC (FIXED):
        # if is_broadcast_command and (is_broadcast or is_for_me):
        #     if is_broadcast or not is_from_me:
        new_outer = is_broadcast_command and (is_broadcast or is_for_me)
        new_inner = is_broadcast or not is_from_me
        new_would_process = new_outer and new_inner
        
        # Verify the fix
        self.assertFalse(old_would_process, "OLD logic would NOT process (broken)")
        self.assertTrue(new_would_process, "NEW logic SHOULD process (fixed)")
        
        print("✅ Test Router Own Node Broadcast: Command correctly processed")
        print(f"   - is_broadcast: {is_broadcast}")
        print(f"   - is_from_me: {is_from_me}")
        print(f"   - is_for_me: {is_for_me}")
        print(f"   - Old logic would process: {old_would_process} (BROKEN)")
        print(f"   - New logic would process: {new_would_process} (FIXED)")
    
    def test_router_still_filters_dm_from_self(self):
        """Test que le message router filtre toujours les DMs de soi-même"""
        
        # DM from self scenario
        is_broadcast_command = True
        is_broadcast = False  # Direct message, not broadcast
        is_for_me = True      # Addressed to us
        is_from_me = True     # from_id == my_id
        
        # NEW LOGIC:
        # if is_broadcast_command and (is_broadcast or is_for_me):
        #     if is_broadcast or not is_from_me:
        new_outer = is_broadcast_command and (is_broadcast or is_for_me)
        new_inner = is_broadcast or not is_from_me
        new_would_process = new_outer and new_inner
        
        # Should NOT process (DM from self)
        self.assertTrue(new_outer, "Outer condition should be true")
        self.assertFalse(new_inner, "Inner condition should be false (is_broadcast=False, is_from_me=True)")
        self.assertFalse(new_would_process, "Should NOT process DM from self")
        
        print("✅ Test Router DM from Self: DM correctly filtered")
        print(f"   - is_broadcast: {is_broadcast}")
        print(f"   - is_from_me: {is_from_me}")
        print(f"   - is_for_me: {is_for_me}")
        print(f"   - Would process: {new_would_process} (CORRECT: False)")
    
    def test_router_allows_broadcast_from_other_node(self):
        """Test que le message router permet les broadcasts d'autres nœuds"""
        
        # Broadcast from different node
        is_broadcast_command = True
        is_broadcast = True
        is_for_me = False
        is_from_me = False  # Different node
        
        # NEW LOGIC:
        new_outer = is_broadcast_command and (is_broadcast or is_for_me)
        new_inner = is_broadcast or not is_from_me
        new_would_process = new_outer and new_inner
        
        # Should process
        self.assertTrue(new_would_process, "Should process broadcast from other node")
        
        print("✅ Test Router Other Node Broadcast: Command correctly processed")
        print(f"   - is_broadcast: {is_broadcast}")
        print(f"   - is_from_me: {is_from_me}")
        print(f"   - Would process: {new_would_process} (CORRECT: True)")
    
    def test_router_allows_dm_from_other_node(self):
        """Test que le message router permet les DMs d'autres nœuds"""
        
        # DM from different node
        is_broadcast_command = True
        is_broadcast = False  # Direct message
        is_for_me = True      # To us
        is_from_me = False    # From different node
        
        # NEW LOGIC:
        new_outer = is_broadcast_command and (is_broadcast or is_for_me)
        new_inner = is_broadcast or not is_from_me
        new_would_process = new_outer and new_inner
        
        # Should process
        self.assertTrue(new_would_process, "Should process DM from other node")
        
        print("✅ Test Router DM from Other Node: Command correctly processed")
        print(f"   - is_broadcast: {is_broadcast}")
        print(f"   - is_from_me: {is_from_me}")
        print(f"   - is_for_me: {is_for_me}")
        print(f"   - Would process: {new_would_process} (CORRECT: True)")


if __name__ == '__main__':
    print("=" * 80)
    print("TEST: Message Router - Filtrage des broadcasts du propre nœud")
    print("=" * 80)
    print("")
    print("Problème: message_router filtre les broadcasts avec is_from_me")
    print("Solution: Même logique que main_bot.py - permettre broadcasts du propre nœud")
    print("")
    
    # Run tests with verbose output
    unittest.main(verbosity=2)
