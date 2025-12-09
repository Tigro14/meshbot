#!/usr/bin/env python3
"""
Test de la sanitisation des noms de nœuds.
Vérifie que la fonction clean_node_name() filtre correctement
les tentatives d'injection SQL et les balises HTML/XSS tout en
préservant les émojis.
"""

import sys
import os

# Create minimal config for testing if it doesn't exist
if not os.path.exists('config.py'):
    # Create temporary config
    config_module = type(sys)('config')
    config_module.DEBUG_MODE = False
    sys.modules['config'] = config_module

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import clean_node_name

def test_sanitization():
    """Test various attack scenarios and edge cases"""
    
    test_cases = [
        # (input, expected_output, description)
        
        # ✅ VALID CASES - Should preserve
        ("TigroBot 🐅", "TigroBot 🐅", "Normal name with emoji"),
        ("🏠 HomeBase", "🏠 HomeBase", "Emoji at start"),
        ("Node 🚀🔥⚡", "Node 🚀🔥⚡", "Multiple emojis"),
        ("Normal_Node-123", "Normal_Node-123", "Alphanumeric with hyphen and underscore"),
        ("Test Node", "Test Node", "Simple name with space"),
        ("ABC123", "ABC123", "Alphanumeric only"),
        ("Node-1", "Node-1", "Name with hyphen"),
        ("my_node", "my_node", "Name with underscore"),
        ("  Spaces  ", "Spaces", "Leading/trailing spaces removed"),
        ("Multi  Spaces", "Multi Spaces", "Multiple spaces collapsed"),
        
        # ❌ SQL INJECTION - Should filter
        ("Node'; DROP TABLE nodes;--", "Node DROP TABLE nodes--", "SQL injection with DROP TABLE"),
        ("' OR '1'='1", "OR 11", "SQL injection with OR condition"),
        ("admin'--", "admin--", "SQL injection with comment"),
        ("'; DELETE FROM users;--", "DELETE FROM users--", "SQL injection DELETE"),
        ("1' UNION SELECT * FROM passwords--", "1 UNION SELECT FROM passwords--", "SQL injection UNION"),
        
        # ❌ XSS/HTML - Should filter
        ("<script>alert('XSS')</script>", "scriptalertXSSscript", "Script tag injection"),
        ("Node<img src=x onerror=alert(1)>", "Nodeimg srcx onerroralert1", "IMG tag with onerror"),
        ("<iframe src='evil.com'>", "iframe srcevilcom", "Iframe tag"),
        ("Test<br/>Line", "TestbrLine", "BR tag"),
        ("<!-- comment -->Hack", "-- comment --Hack", "HTML comment"),
        ("<a href='javascript:alert(1)'>Click</a>", "a hrefjavascriptalert1Clicka", "Link with javascript"),
        ("Test&lt;script&gt;", "Testltscriptgt", "HTML encoded script"),
        ("<svg onload=alert(1)>", "svg onloadalert1", "SVG with onload"),
        ("<body onload=alert(1)>", "body onloadalert1", "Body with onload"),
        
        # ❌ SPECIAL CHARACTERS - Should filter
        ("Node@123", "Node123", "At symbol"),
        ("Test#Hash", "TestHash", "Hash symbol"),
        ("Price$100", "Price100", "Dollar sign"),
        ("Test%20Name", "Test20Name", "Percent encoding"),
        ("Node&Name", "NodeName", "Ampersand"),
        ("Test*Star", "TestStar", "Asterisk"),
        ("Node(Paren)", "NodeParen", "Parentheses"),
        ("Test{Brace}", "TestBrace", "Braces"),
        ("Node[Bracket]", "NodeBracket", "Brackets"),
        ("Test\\Backslash", "TestBackslash", "Backslash"),
        ("Node|Pipe", "NodePipe", "Pipe"),
        ("Test:Colon", "TestColon", "Colon"),
        ("Node;Semi", "NodeSemi", "Semicolon"),
        ("Test,Comma", "TestComma", "Comma"),
        ("Node.Dot", "NodeDot", "Dot"),
        ("Test?Question", "TestQuestion", "Question mark"),
        ("Node/Slash", "NodeSlash", "Forward slash"),
        
        # ✅ EDGE CASES
        ("", "", "Empty string"),
        ("   ", "", "Only spaces"),
        ("123", "123", "Only numbers"),
        ("_-_", "_-_", "Only allowed special chars"),
        ("🎉🎊🎈", "🎉🎊🎈", "Only emojis"),
    ]
    
    print("=" * 80)
    print("TEST DE SANITISATION DES NOMS DE NŒUDS")
    print("=" * 80)
    print()
    
    passed = 0
    failed = 0
    
    for input_name, expected, description in test_cases:
        result = clean_node_name(input_name)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status}: {description}")
        print(f"  Input:    {input_name!r}")
        print(f"  Expected: {expected!r}")
        print(f"  Got:      {result!r}")
        
        if result != expected:
            print(f"  ⚠️  MISMATCH!")
        
        print()
    
    print("=" * 80)
    print(f"RÉSULTATS: {passed} passés, {failed} échoués sur {passed + failed} tests")
    print("=" * 80)
    
    return failed == 0


def test_real_world_names():
    """Test with real-world Meshtastic node names"""
    
    print()
    print("=" * 80)
    print("TEST AVEC DES NOMS RÉELS DE NŒUDS MESHTASTIC")
    print("=" * 80)
    print()
    
    real_names = [
        "TigroBot 🐅",
        "🏠 Maison",
        "Repeater 📡",
        "Bike Tracker 🚲",
        "Outdoor ⛰️",
        "Base Station",
        "Mobile-01",
        "Node_Alpha",
        "Tigro's Node",  # Apostrophe should be filtered
        "Test&Debug",    # Ampersand should be filtered
    ]
    
    for name in real_names:
        cleaned = clean_node_name(name)
        print(f"Original: {name!r}")
        print(f"Cleaned:  {cleaned!r}")
        print()


if __name__ == "__main__":
    # Run sanitization tests
    success = test_sanitization()
    
    # Run real-world name tests
    test_real_world_names()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
