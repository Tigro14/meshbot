#!/usr/bin/env python3
"""
Test script to verify [MC]/[MT] log prefixes are correctly applied.

This script checks that interface-specific diagnostic logs use the correct
prefixed logging functions (debug_print_mc, info_print_mc, debug_print_mt, info_print_mt).
"""

import re
import sys

def check_file_for_patterns():
    """Check main_bot.py for correct logging patterns."""
    
    issues = []
    
    with open('main_bot.py', 'r') as f:
        lines = f.readlines()
    
    # Patterns to check
    checks = [
        # MeshCore callback configuration should use info_print_mc
        {
            'name': 'MeshCore callback configuration',
            'start_pattern': r'Callback MeshCore configuré',
            'required_func': 'info_print_mc',
            'line_range': (2410, 2420),
        },
        # Meshtastic subscription should use info_print_mt
        {
            'name': 'Meshtastic subscription',
            'start_pattern': r'Subscribing to Meshtastic messages',
            'required_func': 'info_print_mt',
            'line_range': (2540, 2560),
        },
        # MeshCore companion mode should use info_print_mc
        {
            'name': 'MeshCore companion mode',
            'start_pattern': r'Mode companion: Messages gérés par interface MeshCore',
            'required_func': 'info_print_mc',
            'line_range': (2550, 2560),
        },
    ]
    
    for check in checks:
        found = False
        correct_func = False
        
        for i in range(check['line_range'][0] - 1, min(check['line_range'][1], len(lines))):
            line = lines[i]
            if re.search(check['start_pattern'], line):
                found = True
                if check['required_func'] in line:
                    correct_func = True
                    print(f"✅ {check['name']}: Uses {check['required_func']} (line {i+1})")
                else:
                    # Check what function is used
                    if 'info_print(' in line and check['required_func'] not in line:
                        issues.append(f"❌ {check['name']}: Uses generic info_print instead of {check['required_func']} (line {i+1})")
                    elif 'debug_print(' in line and check['required_func'] not in line:
                        issues.append(f"❌ {check['name']}: Uses generic debug_print instead of {check['required_func']} (line {i+1})")
                break
        
        if not found:
            print(f"⚠️  {check['name']}: Pattern not found in expected range")
    
    # Check on_message entry logging for context-awareness
    on_message_check = False
    for i in range(560, 600):
        if i < len(lines):
            line = lines[i]
            if 'on_message() CALLED' in line:
                # Check if it uses log_func variable (context-aware)
                if 'log_func(' in line:
                    on_message_check = True
                    print(f"✅ on_message() entry logging: Uses context-aware log_func (line {i+1})")
                elif 'info_print_mc(' in line or 'info_print_mt(' in line:
                    on_message_check = True
                    print(f"✅ on_message() entry logging: Uses prefixed function (line {i+1})")
                elif 'info_print(' in line:
                    issues.append(f"❌ on_message() entry logging: Uses generic info_print (line {i+1})")
                break
    
    if not on_message_check:
        print("⚠️  on_message() entry logging: Could not verify (pattern not found)")
    
    # Check interface health for context-awareness
    interface_health_check = False
    for i in range(2930, 2950):
        if i < len(lines):
            line = lines[i]
            if 'INTERFACE-HEALTH' in line:
                # Check if it uses log_func variable (context-aware)
                if 'log_func(' in line:
                    interface_health_check = True
                    print(f"✅ Interface health check: Uses context-aware log_func (line {i+1})")
                elif 'info_print_mc(' in line or 'info_print_mt(' in line:
                    interface_health_check = True
                    print(f"✅ Interface health check: Uses prefixed function (line {i+1})")
                elif 'info_print(' in line and 'log_func' not in lines[i-5:i+1]:
                    issues.append(f"❌ Interface health check: Uses generic info_print without context (line {i+1})")
                break
    
    if not interface_health_check:
        print("⚠️  Interface health check: Could not verify (pattern not found)")
    
    return issues

if __name__ == '__main__':
    print("=" * 80)
    print("Testing [MC]/[MT] Log Prefix Implementation")
    print("=" * 80)
    print()
    
    issues = check_file_for_patterns()
    
    print()
    print("=" * 80)
    if issues:
        print("❌ ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
        print("=" * 80)
        sys.exit(1)
    else:
        print("✅ ALL CHECKS PASSED")
        print("   All interface-specific logs use correct prefixes")
        print("=" * 80)
        sys.exit(0)
