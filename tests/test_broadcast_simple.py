#!/usr/bin/env python3
"""
Simple test: Verify broadcast logging fix by checking code directly
"""

def check_broadcast_methods():
    """Check that _send_broadcast_via_tigrog2 doesn't call log_conversation"""
    print("=" * 60)
    print("TEST: Vérification du code des méthodes broadcast")
    print("=" * 60)
    
    files_to_check = [
        'handlers/command_handlers/ai_commands.py',
        'handlers/command_handlers/network_commands.py',
        'handlers/command_handlers/utility_commands.py'
    ]
    
    all_good = True
    
    for file_path in files_to_check:
        print(f"\n📄 Vérification: {file_path}")
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find _send_broadcast_via_tigrog2 method
        if '_send_broadcast_via_tigrog2' not in content:
            print(f"  ⚠️ Pas de méthode _send_broadcast_via_tigrog2 trouvée")
            continue
        
        # Extract the method
        start = content.find('def _send_broadcast_via_tigrog2')
        if start == -1:
            print(f"  ❌ Méthode _send_broadcast_via_tigrog2 introuvable")
            all_good = False
            continue
        
        # Find the end of the method (next def or end of class)
        next_def = content.find('\n    def ', start + 1)
        next_class = content.find('\nclass ', start + 1)
        
        end = len(content)
        if next_def != -1:
            end = min(end, next_def)
        if next_class != -1:
            end = min(end, next_class)
        
        method_content = content[start:end]
        
        # Check if log_conversation is called within the method
        if 'log_conversation' in method_content:
            print(f"  ❌ ERREUR: log_conversation appelé dans _send_broadcast_via_tigrog2")
            print(f"     (devrait être appelé uniquement par le handler)")
            all_good = False
        else:
            print(f"  ✅ OK: log_conversation NON appelé dans _send_broadcast_via_tigrog2")
        
        # Check for documentation about not logging
        if 'Ne log PAS la conversation' in method_content or 'Ne log PAS' in method_content:
            print(f"  ✅ OK: Documentation présente sur le non-logging")
        else:
            print(f"  ⚠️ Info: Documentation manquante (recommandé mais pas critique)")
    
    print("\n" + "=" * 60)
    if all_good:
        print("✅ VÉRIFICATION RÉUSSIE")
        print("Les méthodes _send_broadcast_via_tigrog2 ne loggent plus en double")
    else:
        print("❌ VÉRIFICATION ÉCHOUÉE")
        print("Des méthodes _send_broadcast_via_tigrog2 appellent encore log_conversation")
    print("=" * 60)
    
    return all_good


if __name__ == "__main__":
    import sys
    success = check_broadcast_methods()
    sys.exit(0 if success else 1)
