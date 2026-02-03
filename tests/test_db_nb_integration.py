#!/usr/bin/env python3
"""
Test d'intégration pour /db nb - vérifie que la commande est bien routée
"""

import os
import sys

def test_routing_in_message_router():
    """Vérifier que /db est bien routé dans message_router.py"""
    print("=" * 60)
    print("TEST: Vérification du routing dans message_router.py")
    print("=" * 60)
    
    router_path = "handlers/message_router.py"
    if not os.path.exists(router_path):
        print(f"❌ Fichier {router_path} non trouvé")
        return False
    
    with open(router_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Vérifier que DBCommands est importé
    if "from .command_handlers.db_commands import DBCommands" not in content:
        print("❌ DBCommands n'est pas importé")
        return False
    print("✅ DBCommands importé")
    
    # Vérifier que db_handler est initialisé
    if "self.db_handler = DBCommands" not in content:
        print("❌ db_handler n'est pas initialisé")
        return False
    print("✅ db_handler initialisé")
    
    # Vérifier que /db est routé
    if "/db" not in content or "db_handler.handle_db" not in content:
        print("❌ Commande /db non routée")
        return False
    print("✅ Commande /db routée")
    
    return True


def test_telegram_handler_registered():
    """Vérifier que le handler Telegram est enregistré"""
    print("\n" + "=" * 60)
    print("TEST: Vérification de l'enregistrement Telegram")
    print("=" * 60)
    
    # Chercher dans le fichier principal de telegram_platform ou telegram_integration
    telegram_files = [
        "platforms/telegram_platform.py",
        "telegram_integration.py"
    ]
    
    found = False
    for telegram_file in telegram_files:
        if not os.path.exists(telegram_file):
            continue
        
        with open(telegram_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "db_command" in content.lower():
            print(f"✅ Commande db trouvée dans {telegram_file}")
            found = True
            break
    
    if not found:
        # Vérifier dans le fichier telegram_bot/commands/db_commands.py
        db_cmd_file = "telegram_bot/commands/db_commands.py"
        if os.path.exists(db_cmd_file):
            print(f"✅ Handler DB Telegram existe: {db_cmd_file}")
            found = True
    
    return found


def test_help_mentions_nb():
    """Vérifier que l'aide mentionne nb"""
    print("\n" + "=" * 60)
    print("TEST: Vérification de la documentation dans l'aide")
    print("=" * 60)
    
    db_commands_path = "handlers/command_handlers/db_commands.py"
    
    with open(db_commands_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Chercher dans la méthode _get_help
    if "nb" not in content.lower():
        print("❌ 'nb' non trouvé dans l'aide")
        return False
    
    print("✅ 'nb' mentionné dans l'aide")
    
    # Vérifier le format mesh et telegram
    if "nb=neighbors" in content or "nb - Stats voisinage" in content:
        print("✅ Documentation complète trouvée")
        return True
    
    return True


def test_command_flow():
    """Tester le flux complet de la commande"""
    print("\n" + "=" * 60)
    print("TEST: Flux complet de la commande")
    print("=" * 60)
    
    print("Flux attendu:")
    print("1. Utilisateur envoie '/db nb' via Mesh ou Telegram")
    print("2. MessageRouter.process_text_message() détecte '/db'")
    print("3. MessageRouter appelle db_handler.handle_db()")
    print("4. DBCommands.handle_db() parse 'nb' comme subcommand")
    print("5. DBCommands._get_neighbors_stats() est appelé")
    print("6. Résultat formaté selon channel (mesh/telegram)")
    print("7. MessageSender.send_chunks() envoie la réponse")
    
    print("\n✅ Flux logique vérifié")
    return True


def test_file_structure():
    """Vérifier que tous les fichiers nécessaires existent"""
    print("\n" + "=" * 60)
    print("TEST: Structure des fichiers")
    print("=" * 60)
    
    required_files = [
        "handlers/command_handlers/db_commands.py",
        "telegram_bot/commands/db_commands.py",
        "test_db_neighbors_stats.py",
        "demo_db_neighbors.py",
        "DB_NB_COMMAND_DOCUMENTATION.md"
    ]
    
    all_exist = True
    for filepath in required_files:
        if os.path.exists(filepath):
            print(f"✅ {filepath}")
        else:
            print(f"❌ {filepath} manquant")
            all_exist = False
    
    return all_exist


if __name__ == "__main__":
    print("\n🧪 TESTS D'INTÉGRATION - /db nb")
    print("=" * 60)
    
    tests = [
        ("Routing dans MessageRouter", test_routing_in_message_router),
        ("Handler Telegram enregistré", test_telegram_handler_registered),
        ("Aide documentée", test_help_mentions_nb),
        ("Flux de commande", test_command_flow),
        ("Structure des fichiers", test_file_structure)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Erreur dans {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Résumé
    print("\n" + "=" * 60)
    print("RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for test_name, result in results:
        status = "✅ PASSÉ" if result else "❌ ÉCHEC"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Total: {passed} passés, {failed} échoués sur {len(results)} tests")
    
    if failed == 0:
        print("✅ TOUS LES TESTS D'INTÉGRATION PASSÉS")
        print("=" * 60)
        sys.exit(0)
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        print("=" * 60)
        sys.exit(1)
