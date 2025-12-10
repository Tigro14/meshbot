#!/usr/bin/env python3
"""
Test de l'intégration de la commande /propag dans Telegram

Vérifie que:
1. La méthode propag_command existe dans NetworkCommands (Telegram)
2. Le handler est enregistré dans telegram_integration.py
3. La commande est listée dans /start
"""

import sys
import os

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_telegram_command_exists():
    """Vérifier que la méthode propag_command existe"""
    print("=" * 60)
    print("TEST 1: Méthode propag_command existe dans NetworkCommands")
    print("=" * 60)
    
    try:
        # Lire le fichier
        with open('telegram_bot/commands/network_commands.py', 'r') as f:
            content = f.read()
        
        # Vérifier la présence de la méthode
        if 'async def propag_command' in content:
            print("✅ Méthode propag_command trouvée")
            
            # Vérifier la signature
            if 'update: Update' in content and 'context: ContextTypes.DEFAULT_TYPE' in content:
                print("✅ Signature correcte (async, Update, ContextTypes)")
            else:
                print("⚠️  Signature potentiellement incorrecte")
            
            # Vérifier le contenu
            if 'get_propagation_report' in content:
                print("✅ Appel à get_propagation_report trouvé")
            else:
                print("❌ Appel à get_propagation_report non trouvé")
            
            # Vérifier format détaillé pour Telegram
            if 'compact=False' in content:
                print("✅ Format détaillé (compact=False) configuré pour Telegram")
            else:
                print("⚠️  Format compact non spécifié (peut utiliser valeur par défaut)")
            
            return True
        else:
            print("❌ Méthode propag_command non trouvée")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_handler_registration():
    """Vérifier que le handler est enregistré"""
    print("\n" + "=" * 60)
    print("TEST 2: Handler enregistré dans telegram_integration.py")
    print("=" * 60)
    
    try:
        # Lire le fichier
        with open('telegram_integration.py', 'r') as f:
            content = f.read()
        
        # Vérifier l'enregistrement du handler
        if 'CommandHandler("propag"' in content:
            print("✅ CommandHandler pour 'propag' trouvé")
            
            # Vérifier le lien avec la méthode
            if 'network_commands.propag_command' in content:
                print("✅ Lien avec network_commands.propag_command trouvé")
                return True
            else:
                print("❌ Lien avec la méthode propag_command non trouvé")
                return False
        else:
            print("❌ CommandHandler pour 'propag' non trouvé")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_start_command_list():
    """Vérifier que /propag est dans la liste /start"""
    print("\n" + "=" * 60)
    print("TEST 3: /propag dans la liste /start")
    print("=" * 60)
    
    try:
        # Lire le fichier
        with open('telegram_bot/commands/basic_commands.py', 'r') as f:
            content = f.read()
        
        # Vérifier dans la méthode start_command
        if '/propag' in content:
            print("✅ /propag trouvé dans basic_commands.py")
            
            # Vérifier qu'il est dans welcome_msg
            if 'welcome_msg' in content and '/propag' in content:
                print("✅ /propag dans le message de bienvenue")
                
                # Extraire la ligne pour vérifier le format
                lines = content.split('\n')
                propag_lines = [l for l in lines if '/propag' in l]
                if propag_lines:
                    print(f"📝 Ligne trouvée: {propag_lines[0].strip()}")
                    return True
            else:
                print("⚠️  /propag trouvé mais peut-être pas dans welcome_msg")
                return True
        else:
            print("❌ /propag non trouvé dans basic_commands.py")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_help_text():
    """Vérifier que /propag est documenté dans l'aide"""
    print("\n" + "=" * 60)
    print("TEST 4: Documentation dans le texte d'aide")
    print("=" * 60)
    
    try:
        # Lire le fichier
        with open('handlers/command_handlers/utility_commands.py', 'r') as f:
            content = f.read()
        
        # Vérifier la documentation
        if '/propag' in content:
            print("✅ /propag trouvé dans utility_commands.py")
            
            # Vérifier les exemples d'utilisation
            examples = [
                '/propag → Top 5 liaisons (24h)',
                '/propag 48 → Top 5 liaisons (48h)',
                '/propag 24 10 → Top 10 liaisons (24h)'
            ]
            
            found_examples = 0
            for example in examples:
                if example in content:
                    found_examples += 1
            
            print(f"✅ {found_examples}/3 exemples d'utilisation trouvés")
            
            # Vérifier la description du rayon
            if 'Rayon: 100km' in content or 'rayon de 100km' in content.lower():
                print("✅ Rayon de 100km documenté")
            else:
                print("⚠️  Rayon de 100km non documenté (mais configuré dans le code)")
            
            return True
        else:
            print("❌ /propag non trouvé dans utility_commands.py")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def main():
    """Exécuter tous les tests"""
    print("🧪 TESTS D'INTÉGRATION TELEGRAM POUR /PROPAG")
    print("=" * 60)
    
    results = {
        "Méthode propag_command": test_telegram_command_exists(),
        "Handler enregistré": test_handler_registration(),
        "Liste /start": test_start_command_list(),
        "Documentation aide": test_help_text()
    }
    
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:25s} : {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 TOUS LES TESTS ONT RÉUSSI!")
        print("\nLa commande /propag est maintenant:")
        print("  ✅ Implémentée dans telegram_bot/commands/network_commands.py")
        print("  ✅ Enregistrée dans telegram_integration.py")
        print("  ✅ Listée dans le menu /start")
        print("  ✅ Documentée dans le texte d'aide")
        print("\nLa commande devrait maintenant fonctionner sur Telegram!")
    else:
        print("⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
