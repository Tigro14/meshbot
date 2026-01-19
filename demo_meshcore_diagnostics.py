#!/usr/bin/env python3
"""
Demo script showing the MeshCore configuration diagnostics in action

This demonstrates the enhanced diagnostic capabilities without requiring
actual MeshCore hardware.
"""

import asyncio
from unittest.mock import Mock


class DemoMeshCore:
    """Demo MeshCore object with configurable issues"""
    
    def __init__(self, scenario="perfect"):
        self.scenario = scenario
        
        if scenario == "perfect":
            # Perfect configuration
            self.private_key = b'mock_key_12345'
            self.contacts = ['contact_1', 'contact_2', 'contact_3']
            self.events = Mock()
        elif scenario == "no_key":
            # Missing private key
            self.contacts = ['contact_1', 'contact_2']
            self.events = Mock()
        elif scenario == "no_contacts":
            # Private key but no contacts
            self.private_key = b'mock_key_12345'
            self.contacts = []
            self.events = Mock()
        elif scenario == "minimal":
            # Minimal configuration - many issues
            pass
    
    async def sync_contacts(self):
        """Mock sync_contacts"""
        if self.scenario == "minimal":
            raise AttributeError("sync_contacts not available")
        await asyncio.sleep(0)
    
    async def start_auto_message_fetching(self):
        """Mock start_auto_message_fetching"""
        if self.scenario == "minimal":
            raise AttributeError("start_auto_message_fetching not available")
        await asyncio.sleep(0)


async def run_diagnostics(meshcore, scenario_name):
    """Run configuration diagnostics on a MeshCore object"""
    print("\n" + "="*70)
    print(f"🔍 Configuration Diagnostics - Scenario: {scenario_name}")
    print("="*70)
    
    issues_found = []
    
    # Check 1: Private key access
    print("\n1️⃣  Checking private key access...")
    key_attrs = ['private_key', 'key', 'node_key', 'device_key', 'crypto']
    found_key_attrs = [attr for attr in key_attrs if hasattr(meshcore, attr)]
    
    if found_key_attrs:
        print(f"   ✅ Found key-related attributes: {', '.join(found_key_attrs)}")
        
        for attr in found_key_attrs:
            value = getattr(meshcore, attr)
            if value is None:
                print(f"   ⚠️  {attr} is None")
                issues_found.append(f"{attr} is None - decryption may fail")
            else:
                print(f"   ✅ {attr} is set")
    else:
        print("   ⚠️  No private key attributes found")
        issues_found.append("No private key found - encrypted messages cannot be decrypted")
    
    # Check 2: Contact sync capability
    print("\n2️⃣  Checking contact sync capability...")
    if hasattr(meshcore, 'sync_contacts'):
        print("   ✅ sync_contacts() method available")
        
        if hasattr(meshcore, 'contacts'):
            contacts = meshcore.contacts
            if contacts:
                print(f"   ✅ Found {len(contacts)} contacts")
            else:
                print("   ⚠️  Contact list is empty")
                issues_found.append("No contacts found - DM decryption may fail")
        else:
            print("   ⚠️  No contact list accessor found")
    else:
        print("   ❌ sync_contacts() method NOT available")
        issues_found.append("sync_contacts() not available - contact sync cannot be performed")
    
    # Check 3: Auto message fetching
    print("\n3️⃣  Checking auto message fetching...")
    if hasattr(meshcore, 'start_auto_message_fetching'):
        print("   ✅ start_auto_message_fetching() available")
    else:
        print("   ❌ start_auto_message_fetching() NOT available")
        issues_found.append("start_auto_message_fetching() not available - messages must be fetched manually")
    
    # Check 4: Event dispatcher
    print("\n4️⃣  Checking event dispatcher...")
    if hasattr(meshcore, 'events'):
        print("   ✅ Event dispatcher (events) available")
    elif hasattr(meshcore, 'dispatcher'):
        print("   ✅ Event dispatcher (dispatcher) available")
    else:
        print("   ❌ No event dispatcher found")
        issues_found.append("No event dispatcher - events cannot be received")
    
    # Summary
    print("\n" + "="*70)
    if issues_found:
        print("⚠️  Configuration Issues Found:")
        for i, issue in enumerate(issues_found, 1):
            print(f"   {i}. {issue}")
        print("\n💡 Troubleshooting Tips:")
        print("   • Ensure the MeshCore device has a private key configured")
        print("   • Check that contacts are properly synced")
        print("   • Verify auto message fetching is started")
        print("   • Try enabling debug mode for more detailed logs")
    else:
        print("✅ No configuration issues detected")
        print("\n🎉 Ready to receive and decrypt messages!")
    print("="*70 + "\n")


async def main():
    """Run demo with different scenarios"""
    print("\n" + "="*70)
    print("🎭 MeshCore Configuration Diagnostics - Demo")
    print("="*70)
    print("\nThis demo shows how the enhanced diagnostics detect configuration")
    print("issues and provide troubleshooting guidance.")
    
    # Scenario 1: Perfect configuration
    print("\n\n" + "🟢 SCENARIO 1: Perfect Configuration")
    print("-" * 70)
    print("All features present and configured correctly.")
    meshcore_perfect = DemoMeshCore(scenario="perfect")
    await run_diagnostics(meshcore_perfect, "Perfect Configuration")
    
    # Scenario 2: Missing private key
    print("\n\n" + "🟡 SCENARIO 2: Missing Private Key")
    print("-" * 70)
    print("Device has contacts and events, but no private key.")
    meshcore_no_key = DemoMeshCore(scenario="no_key")
    await run_diagnostics(meshcore_no_key, "Missing Private Key")
    
    # Scenario 3: Empty contact list
    print("\n\n" + "🟡 SCENARIO 3: Empty Contact List")
    print("-" * 70)
    print("Device has private key but no contacts synced.")
    meshcore_no_contacts = DemoMeshCore(scenario="no_contacts")
    await run_diagnostics(meshcore_no_contacts, "Empty Contact List")
    
    # Scenario 4: Minimal/broken configuration
    print("\n\n" + "🔴 SCENARIO 4: Minimal Configuration (Multiple Issues)")
    print("-" * 70)
    print("Device missing most required features.")
    meshcore_minimal = DemoMeshCore(scenario="minimal")
    await run_diagnostics(meshcore_minimal, "Minimal Configuration")
    
    # Summary
    print("\n\n" + "="*70)
    print("📊 DEMO SUMMARY")
    print("="*70)
    print("\nThe diagnostics help identify:")
    print("  ✅ Perfect configuration (Scenario 1)")
    print("  ⚠️  Missing private key (Scenario 2)")
    print("  ⚠️  Empty contact list (Scenario 3)")
    print("  ❌ Multiple configuration issues (Scenario 4)")
    print("\nEach scenario provides:")
    print("  • Clear issue identification")
    print("  • Specific error messages")
    print("  • Actionable troubleshooting tips")
    print("\n💡 Instead of adding decryption to the monitor, we help users")
    print("   fix their meshcore library configuration!")
    print("="*70 + "\n")


if __name__ == '__main__':
    asyncio.run(main())
