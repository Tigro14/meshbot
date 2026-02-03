#!/usr/bin/env python3
"""
Test to understand why /keys with argument fails silently
"""

# Simulate the issue: what if _check_node_keys returns empty string?
response = ""

print(f"Response: '{response}'")
print(f"Response length: {len(response)}")
print(f"Response is truthy: {bool(response)}")

# What happens when we try to send it?
if response:
    print("✅ Would send response")
else:
    print("❌ Response is empty/falsy - might not send!")

# What if it returns None?
response2 = None
print(f"\nResponse2: '{response2}'")
print(f"Response2 is None: {response2 is None}")

try:
    print(f"Response2 length: {len(response2)}")
except TypeError as e:
    print(f"❌ Can't get length of None: {e}")
