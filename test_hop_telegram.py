#!/usr/bin/env python3
"""
Test du /hop command pour Telegram
Vérifie que la commande /hop est disponible pour Telegram
"""

import sys
import os

# Ajouter le répertoire du projet au path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

def test_hop_telegram_command_exists():
    """Vérifier que le handler /hop existe dans stats_commands"""
    print("TEST: Vérification du handler /hop pour Telegram\n")
    
    try:
        from telegram_bot.commands.stats_commands import StatsCommands
        
        # Vérifier que la méthode hop_command existe
        assert hasattr(StatsCommands, 'hop_command'), "❌ Méthode hop_command manquante"
        print("✅ Méthode hop_command trouvée dans StatsCommands")
        
        # Vérifier que c'est une méthode async
        import inspect
        method = getattr(StatsCommands, 'hop_command')
        assert inspect.iscoroutinefunction(method), "❌ hop_command n'est pas async"
        print("✅ hop_command est une méthode async")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_hop_telegram_registration():
    """Vérifier que /hop est enregistré dans telegram_integration"""
    print("\nTEST: Vérification de l'enregistrement de /hop\n")
    
    try:
        # Lire le fichier telegram_integration.py
        integration_file = os.path.join(script_dir, 'telegram_integration.py')
        with open(integration_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier que /hop est enregistré
        if 'CommandHandler("hop"' in content:
            print('✅ Handler "hop" trouvé dans telegram_integration.py')
            
            # Vérifier qu'il pointe vers stats_commands.hop_command
            if 'stats_commands.hop_command' in content:
                print('✅ Handler "hop" pointe vers stats_commands.hop_command')
                return True
            else:
                print('❌ Handler "hop" ne pointe pas vers stats_commands.hop_command')
                return False
        else:
            print('❌ Handler "hop" non trouvé dans telegram_integration.py')
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_hop_command_signature():
    """Vérifier la signature de la méthode hop_command"""
    print("\nTEST: Vérification de la signature de hop_command\n")
    
    try:
        from telegram_bot.commands.stats_commands import StatsCommands
        import inspect
        
        method = getattr(StatsCommands, 'hop_command')
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        
        print(f"Paramètres: {params}")
        
        # Vérifier les paramètres attendus
        expected_params = ['self', 'update', 'context']
        if params == expected_params:
            print(f"✅ Signature correcte: {expected_params}")
            return True
        else:
            print(f"❌ Signature incorrecte")
            print(f"   Attendu: {expected_params}")
            print(f"   Trouvé: {params}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_hop_command_docstring():
    """Vérifier que la méthode a une documentation"""
    print("\nTEST: Vérification de la documentation\n")
    
    try:
        from telegram_bot.commands.stats_commands import StatsCommands
        
        method = getattr(StatsCommands, 'hop_command')
        docstring = method.__doc__
        
        if docstring and len(docstring.strip()) > 0:
            print("✅ Documentation présente")
            print(f"\nDocstring:\n{docstring[:200]}...")
            return True
        else:
            print("❌ Pas de documentation")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=" * 70)
    print("TEST: /hop Telegram Command Implementation")
    print("=" * 70)
    print()
    
    results = []
    
    # Test 1: Vérifier l'existence du handler
    results.append(test_hop_telegram_command_exists())
    
    # Test 2: Vérifier l'enregistrement
    results.append(test_hop_telegram_registration())
    
    # Test 3: Vérifier la signature
    results.append(test_hop_command_signature())
    
    # Test 4: Vérifier la documentation
    results.append(test_hop_command_docstring())
    
    # Résumé
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    
    total = len(results)
    passed = sum(results)
    
    print(f"\nTests réussis: {passed}/{total}")
    
    if passed == total:
        print("\n✅ TOUS LES TESTS PASSENT")
        print("\nLa commande /hop est correctement implémentée pour Telegram:")
        print("  1. ✅ Handler hop_command existe dans StatsCommands")
        print("  2. ✅ Handler est enregistré dans telegram_integration.py")
        print("  3. ✅ Signature correcte (async avec update, context)")
        print("  4. ✅ Documentation présente")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
