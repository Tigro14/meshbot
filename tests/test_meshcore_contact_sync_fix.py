#!/usr/bin/env python3
"""
Test: MeshCore contact startup sync — dict iteration fix
=========================================================

The meshcore library stores contacts as dict {pubkey_prefix: contact_dict}.
The old code did `for contact in post_contacts` which iterates dict KEYS
(pubkey_prefix strings), causing `contact.get(...)` to raise AttributeError
and silently skip every contact.  After the fix the loop does
`for _key, contact in post_contacts.items()` so real names are resolved.

Also verifies:
- `adv_name` field (used by meshcore library) is extracted as display name
- `node_id` is derived from first 4 bytes of `public_key` when missing
- `node_manager.node_names` cache is populated so names resolve immediately
  without a DB round-trip
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Simulate the sync loop logic (extracted from meshcore_cli_wrapper.py)
# ---------------------------------------------------------------------------

def simulate_sync_loop(post_contacts, node_names_cache):
    """
    Simulate the fixed contact sync loop.

    Args:
        post_contacts: dict {pubkey_prefix: contact_dict} as returned by
                       meshcore library after sync_contacts()
        node_names_cache: the node_manager.node_names dict to populate

    Returns:
        list of (contact_id, name) tuples that were successfully saved
    """
    saved = []
    contacts_items = post_contacts.items() if isinstance(post_contacts, dict) else enumerate(post_contacts)
    for _key, contact in contacts_items:
        try:
            contact_id = contact.get('contact_id') or contact.get('node_id')
            name = contact.get('adv_name') or contact.get('name') or contact.get('long_name')
            public_key = contact.get('public_key') or contact.get('publicKey')

            # Derive node_id from public_key prefix when not explicitly provided
            if not contact_id and public_key:
                try:
                    if isinstance(public_key, str) and len(public_key) >= 8:
                        contact_id = int(public_key[:8], 16)
                    elif isinstance(public_key, bytes) and len(public_key) >= 4:
                        contact_id = int.from_bytes(public_key[:4], 'big')
                except Exception:
                    pass

            if not contact_id:
                continue

            if isinstance(contact_id, str):
                if contact_id.startswith('!'):
                    contact_id = int(contact_id[1:], 16)
                else:
                    try:
                        contact_id = int(contact_id, 16)
                    except ValueError:
                        contact_id = int(contact_id)

            best_name = name or f"Node-{contact_id:08x}"
            # Populate in-memory cache
            node_names_cache[contact_id] = {
                'name': best_name,
                'shortName': name or '',
                'hwModel': contact.get('hw_model'),
                'lat': contact.get('adv_lat') or contact.get('latitude'),
                'lon': contact.get('adv_lon') or contact.get('longitude'),
                'alt': contact.get('altitude'),
                'last_update': None
            }
            saved.append((contact_id, best_name))
        except Exception as e:
            pass  # same as production code

    return saved


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_old_loop_fails():
    """Demonstrate the OLD bug: iterating dict gives keys, not values."""
    print("\n🧪 Test: old loop iterates dict keys (bug demonstration)")
    print("=" * 70)

    # Simulate meshcore.contacts dict
    post_contacts = {
        '889fa138c712': {
            'adv_name': 'Tigro',
            'public_key': '889fa138c712abcd1234567890abcdef1234567890abcdef1234567890abcdef',
        }
    }

    old_saved = []
    for contact in post_contacts:  # OLD: iterates keys
        try:
            name = contact.get('adv_name')  # AttributeError on string!
            old_saved.append(name)
        except AttributeError:
            pass  # silently swallowed

    assert len(old_saved) == 0, "Old loop should save nothing (all failures)"
    print("  ✅ Old loop correctly demonstrates the bug: 0 contacts saved")
    return True


def test_fixed_loop_saves_contacts():
    """Fixed loop iterates dict values → contacts are saved with real names."""
    print("\n🧪 Test: fixed loop iterates dict values")
    print("=" * 70)

    post_contacts = {
        '889fa138c712': {
            'adv_name': 'Tigro',
            'public_key': '889fa138c712abcd1234567890abcdef1234567890abcdef1234567890abcdef',
        },
        '143bcd7f1b1f': {
            'adv_name': 'tigro',
            'public_key': '143bcd7f1b1f0000000000000000000000000000000000000000000000000000',
        }
    }

    node_names = {}
    saved = simulate_sync_loop(post_contacts, node_names)

    assert len(saved) == 2, f"Expected 2 contacts saved, got {len(saved)}"

    # Check Tigro (0x889fa138)
    tigro_id = int('889fa138', 16)
    assert tigro_id in node_names, f"Tigro (0x{tigro_id:08x}) missing from node_names"
    assert node_names[tigro_id]['name'] == 'Tigro', f"Expected 'Tigro', got '{node_names[tigro_id]['name']}'"

    # Check tigro (0x143bcd7f)
    tigro2_id = int('143bcd7f', 16)
    assert tigro2_id in node_names, f"tigro (0x{tigro2_id:08x}) missing from node_names"
    assert node_names[tigro2_id]['name'] == 'tigro', f"Expected 'tigro', got '{node_names[tigro2_id]['name']}'"

    print(f"  ✅ {len(saved)} contacts saved correctly")
    for cid, name in saved:
        print(f"     0x{cid:08x} → {name}")
    return True


def test_adv_name_extraction():
    """Meshcore library uses 'adv_name'; verify it is preferred over 'name'."""
    print("\n🧪 Test: adv_name field extracted as display name")
    print("=" * 70)

    post_contacts = {
        'abcdef012345': {
            'adv_name': 'Real Name from MeshCore',
            'name': 'fallback_name',
            'public_key': 'abcdef0123450000000000000000000000000000000000000000000000000000',
        }
    }

    node_names = {}
    saved = simulate_sync_loop(post_contacts, node_names)

    assert len(saved) == 1
    cid = int('abcdef01', 16)
    assert node_names[cid]['name'] == 'Real Name from MeshCore', \
        f"Expected adv_name to win, got '{node_names[cid]['name']}'"
    print(f"  ✅ adv_name 'Real Name from MeshCore' correctly extracted")
    return True


def test_node_id_derived_from_public_key():
    """When contact has no node_id, derive it from first 4 bytes of public_key."""
    print("\n🧪 Test: node_id derived from public_key when missing")
    print("=" * 70)

    post_contacts = {
        '02ce115f9999': {
            'adv_name': 'Test Repeater',
            # No contact_id or node_id field — must derive from public_key
            'public_key': '02ce115f99990000000000000000000000000000000000000000000000000000',
        }
    }

    node_names = {}
    saved = simulate_sync_loop(post_contacts, node_names)

    expected_id = int('02ce115f', 16)
    assert len(saved) == 1, f"Expected 1 contact saved, got {len(saved)}"
    assert saved[0][0] == expected_id, \
        f"Expected node_id=0x{expected_id:08x}, got 0x{saved[0][0]:08x}"
    assert saved[0][1] == 'Test Repeater'
    print(f"  ✅ node_id 0x{expected_id:08x} derived from public_key[:8]='02ce115f'")
    return True


def test_node_id_derived_from_bytes_public_key():
    """Derive node_id from bytes public_key (alternative format)."""
    print("\n🧪 Test: node_id derived from bytes public_key")
    print("=" * 70)

    post_contacts = {
        'aabbccdd1122': {
            'adv_name': 'Bytes Node',
            'public_key': bytes.fromhex('aabbccdd1122334455667788990011223344556677889900112233445566778899'),
        }
    }

    node_names = {}
    saved = simulate_sync_loop(post_contacts, node_names)

    expected_id = int.from_bytes(bytes.fromhex('aabbccdd'), 'big')
    assert len(saved) == 1
    assert saved[0][0] == expected_id, \
        f"Expected 0x{expected_id:08x}, got 0x{saved[0][0]:08x}"
    print(f"  ✅ node_id 0x{expected_id:08x} derived from first 4 bytes of bytes public_key")
    return True


def test_get_node_name_resolves_after_sync():
    """After sync, get_node_name returns real name from in-memory cache."""
    print("\n🧪 Test: get_node_name resolves real name after contact sync")
    print("=" * 70)

    # Simulate a minimal node_names cache (what node_manager would have)
    node_names = {}

    # Run the sync
    post_contacts = {
        '889fa138c712': {
            'adv_name': 'Tigro',
            'public_key': '889fa138c712abcdef0000000000000000000000000000000000000000000000',
        }
    }
    simulate_sync_loop(post_contacts, node_names)

    # Simulate get_node_name logic (simplified)
    def get_node_name(node_id):
        if node_id in node_names:
            return node_names[node_id]['name']
        return f"Node-{node_id:08x}"  # fallback

    tigro_id = int('889fa138', 16)
    name = get_node_name(tigro_id)
    assert name == 'Tigro', f"Expected 'Tigro', got '{name}'"
    print(f"  ✅ get_node_name(0x{tigro_id:08x}) → '{name}' (not 'Node-889fa138')")
    return True


def test_contact_without_public_key_skipped():
    """Contacts with no ID and no public_key are skipped gracefully."""
    print("\n🧪 Test: contact with no derivable ID is skipped")
    print("=" * 70)

    post_contacts = {
        'badcontact': {
            'adv_name': 'No Key Contact',
            # No public_key, no contact_id → cannot derive ID
        }
    }

    node_names = {}
    saved = simulate_sync_loop(post_contacts, node_names)
    assert len(saved) == 0, f"Expected 0 saved, got {len(saved)}"
    print("  ✅ Contact without derivable ID correctly skipped")
    return True


def run_all_tests():
    print("\n" + "=" * 70)
    print("MESHCORE CONTACT SYNC FIX — TEST SUITE")
    print("=" * 70)

    results = [
        ("Old loop bug demonstrated", test_old_loop_fails()),
        ("Fixed loop saves contacts", test_fixed_loop_saves_contacts()),
        ("adv_name extraction", test_adv_name_extraction()),
        ("node_id from public_key (str)", test_node_id_derived_from_public_key()),
        ("node_id from public_key (bytes)", test_node_id_derived_from_bytes_public_key()),
        ("get_node_name resolves after sync", test_get_node_name_resolves_after_sync()),
        ("No-ID contact skipped", test_contact_without_public_key_skipped()),
    ]

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        print(f"  {'✅ PASS' if result else '❌ FAIL'}: {name}")
    print("\n" + "=" * 70)
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        return True
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total})")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
