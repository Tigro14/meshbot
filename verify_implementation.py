#!/usr/bin/env python3
"""
Final verification script - Comprehensive check of all changes
"""

import os
import sys

print("=" * 70)
print("FINAL VERIFICATION: /db Password Protection Implementation")
print("=" * 70)

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description} NOT FOUND: {filepath}")
        return False

def check_file_content(filepath, search_strings, description):
    """Check if file contains expected content"""
    if not os.path.exists(filepath):
        print(f"❌ {description}: File not found")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    missing = []
    for search_str in search_strings:
        if search_str not in content:
            missing.append(search_str)
    
    if missing:
        print(f"❌ {description}: Missing content")
        for m in missing:
            print(f"   - {m}")
        return False
    else:
        print(f"✅ {description}")
        return True

print("\n=== Checking Production Files ===\n")

success = True

# Check core implementation
success &= check_file_content(
    "/home/runner/work/meshbot/meshbot/handlers/command_handlers/db_commands.py",
    [
        "from config import REBOOT_PASSWORD",
        "if provided_password != REBOOT_PASSWORD:",
        "def _cleanup_db(self, args, channel='mesh'):",
        "def _vacuum_db(self, args, channel='mesh'):",
        "clean <password>",
        "vacuum <password>",
    ],
    "Core db_commands.py implementation"
)

# Check Telegram integration
success &= check_file_content(
    "/home/runner/work/meshbot/meshbot/telegram_bot/commands/db_commands.py",
    [
        "result = db_handler._vacuum_db(args, 'telegram')",
        "result = db_handler._cleanup_db(args, 'telegram')",
    ],
    "Telegram integration"
)

print("\n=== Checking Test Files ===\n")

# Check test files exist
success &= check_file_exists(
    "/home/runner/work/meshbot/meshbot/test_db_password.py",
    "Unit test file"
)

success &= check_file_exists(
    "/home/runner/work/meshbot/meshbot/test_db_password_integration.py",
    "Integration test file"
)

success &= check_file_exists(
    "/home/runner/work/meshbot/meshbot/demo_db_password.py",
    "Demo script"
)

print("\n=== Checking Documentation ===\n")

# Check documentation files
success &= check_file_exists(
    "/home/runner/work/meshbot/meshbot/DB_PASSWORD_PROTECTION.md",
    "Implementation guide"
)

success &= check_file_exists(
    "/home/runner/work/meshbot/meshbot/IMPLEMENTATION_SUMMARY_DB_PASSWORD.md",
    "Implementation summary"
)

success &= check_file_exists(
    "/home/runner/work/meshbot/meshbot/DB_PASSWORD_FLOW_DIAGRAM.md",
    "Flow diagrams"
)

print("\n=== Running Tests ===\n")

# Run unit tests
print("Running unit tests...")
result = os.system("cd /home/runner/work/meshbot/meshbot && python test_db_password.py > /tmp/test_output.txt 2>&1")
if result == 0:
    print("✅ Unit tests passed")
else:
    print("❌ Unit tests failed")
    success = False

# Run integration tests
print("Running integration tests...")
result = os.system("cd /home/runner/work/meshbot/meshbot && python test_db_password_integration.py > /tmp/integration_output.txt 2>&1")
if result == 0:
    print("✅ Integration tests passed")
else:
    print("❌ Integration tests failed")
    success = False

print("\n=== Syntax Validation ===\n")

# Check Python syntax
import py_compile

files_to_check = [
    "handlers/command_handlers/db_commands.py",
    "telegram_bot/commands/db_commands.py",
]

for f in files_to_check:
    filepath = f"/home/runner/work/meshbot/meshbot/{f}"
    try:
        py_compile.compile(filepath, doraise=True)
        print(f"✅ {f} - Valid Python syntax")
    except Exception as e:
        print(f"❌ {f} - Syntax error: {e}")
        success = False

print("\n=== Git Status ===\n")

# Check git status
result = os.system("cd /home/runner/work/meshbot/meshbot && git status --short")
print()

print("\n=== Summary ===\n")

if success:
    print("✅ ALL VERIFICATIONS PASSED")
    print("\nImplementation is complete and ready for review!")
    print("\nChanges summary:")
    print("  • 2 production files modified")
    print("  • 3 test files created")
    print("  • 3 documentation files created")
    print("  • All tests passing")
    print("  • Valid Python syntax")
    print("\nNext steps:")
    print("  1. Review the pull request")
    print("  2. Test in development environment")
    print("  3. Merge to main branch")
    print("  4. Update user documentation")
    exit(0)
else:
    print("❌ SOME VERIFICATIONS FAILED")
    print("\nPlease review the errors above and fix them.")
    exit(1)

print("=" * 70)
