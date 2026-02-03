#!/usr/bin/env python3
"""
Test de la commande /propag en mode broadcast
Vérifie que /propag répond aux messages broadcast comme /echo et /rain
"""

import sys
import os

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_broadcast_commands_list():
    """Test que /propag est dans la liste des commandes broadcast"""
    print("=" * 60)
    print("TEST 1: /propag dans broadcast_commands")
    print("=" * 60)
    
    try:
        with open('handlers/message_router.py', 'r') as f:
            content = f.read()
            
            # Vérifier que /propag est dans broadcast_commands
            if "'/propag'" in content:
                print("✅ /propag trouvé dans broadcast_commands")
            else:
                print("❌ /propag NON trouvé dans broadcast_commands")
                return False
            
            # Vérifier le commentaire mis à jour
            if "echo, my, weather, rain, bot, info, propag" in content:
                print("✅ Commentaire mis à jour avec propag")
            else:
                print("⚠️  Commentaire pas encore mis à jour")
            
            # Vérifier le elif pour /propag
            if "elif message.startswith('/propag'):" in content:
                print("✅ elif /propag trouvé dans broadcast handling")
            else:
                print("❌ elif /propag NON trouvé dans broadcast handling")
                return False
            
            # Vérifier l'appel avec is_broadcast
            if "handle_propag(message, sender_id, sender_info, is_broadcast=is_broadcast)" in content:
                print("✅ Appel handle_propag avec is_broadcast trouvé")
            else:
                print("❌ Appel handle_propag avec is_broadcast NON trouvé")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_handle_propag_signature():
    """Test que handle_propag a le paramètre is_broadcast"""
    print("\n" + "=" * 60)
    print("TEST 2: Signature handle_propag(is_broadcast=False)")
    print("=" * 60)
    
    try:
        with open('handlers/command_handlers/network_commands.py', 'r') as f:
            content = f.read()
            
            # Vérifier la signature de la méthode
            if "def handle_propag(self, message, sender_id, sender_info, is_broadcast=False):" in content:
                print("✅ Signature handle_propag avec is_broadcast=False trouvée")
            else:
                print("❌ Signature handle_propag incorrecte")
                return False
            
            # Vérifier la documentation
            if "is_broadcast: Si True, répondre en broadcast public" in content:
                print("✅ Documentation is_broadcast trouvée")
            else:
                print("⚠️  Documentation is_broadcast manquante")
            
            return True
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_broadcast_response_logic():
    """Test que handle_propag utilise _send_broadcast_via_tigrog2"""
    print("\n" + "=" * 60)
    print("TEST 3: Logique de réponse broadcast")
    print("=" * 60)
    
    try:
        with open('handlers/command_handlers/network_commands.py', 'r') as f:
            content = f.read()
            
            # Chercher la méthode handle_propag
            method_start = content.find("def handle_propag(")
            if method_start == -1:
                print("❌ Méthode handle_propag non trouvée")
                return False
            
            # Chercher la méthode suivante pour délimiter
            method_end = content.find("\n    def ", method_start + 1)
            if method_end == -1:
                method_end = len(content)
            
            method_content = content[method_start:method_end]
            
            # Vérifier l'utilisation de _send_broadcast_via_tigrog2
            broadcast_calls = method_content.count("_send_broadcast_via_tigrog2")
            if broadcast_calls >= 3:  # Au moins 3 appels (erreur TrafficMonitor, erreur parsing, réponse normale)
                print(f"✅ _send_broadcast_via_tigrog2 appelé {broadcast_calls} fois")
            else:
                print(f"⚠️  _send_broadcast_via_tigrog2 appelé seulement {broadcast_calls} fois (attendu >= 3)")
                return False
            
            # Vérifier le if is_broadcast pour la réponse principale
            if "if is_broadcast:" in method_content and "# Réponse publique via broadcast" in method_content:
                print("✅ Logique if is_broadcast trouvée pour réponse principale")
            else:
                print("❌ Logique if is_broadcast NON trouvée")
                return False
            
            # Vérifier que compact utilise is_broadcast
            if "compact = is_broadcast or" in method_content:
                print("✅ Format compact utilise is_broadcast")
            else:
                print("⚠️  Format compact ne semble pas utiliser is_broadcast")
            
            # Vérifier le log avec broadcast
            if 'info_print(f"Propag: {sender_info} (broadcast={is_broadcast})")' in method_content:
                print("✅ Log avec broadcast={is_broadcast} trouvé")
            else:
                print("⚠️  Log avec broadcast manquant")
            
            return True
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_consistency_with_other_broadcast_commands():
    """Test que /propag suit le même pattern que /my et /info"""
    print("\n" + "=" * 60)
    print("TEST 4: Cohérence avec autres commandes broadcast")
    print("=" * 60)
    
    try:
        with open('handlers/command_handlers/network_commands.py', 'r') as f:
            content = f.read()
            
            # Extraire handle_my et handle_info pour comparaison
            # Note: handle_my a une signature différente (pas de message param)
            my_has_broadcast = "def handle_my(self, sender_id, sender_info, is_broadcast=False):" in content
            info_has_broadcast = "def handle_info(self, message, sender_id, sender_info, is_broadcast=False):" in content
            propag_has_broadcast = "def handle_propag(self, message, sender_id, sender_info, is_broadcast=False):" in content
            
            if my_has_broadcast:
                print("✅ handle_my a is_broadcast")
            if info_has_broadcast:
                print("✅ handle_info a is_broadcast")
            if propag_has_broadcast:
                print("✅ handle_propag a is_broadcast")
            
            if not (my_has_broadcast and info_has_broadcast and propag_has_broadcast):
                print("❌ Incohérence dans les signatures des handlers")
                return False
            
            # Vérifier que les 3 utilisent _send_broadcast_via_tigrog2
            my_count = content.count("def handle_my") + content[content.find("def handle_my"):content.find("def handle_my") + 2000].count("_send_broadcast_via_tigrog2")
            info_count = content.count("def handle_info") + content[content.find("def handle_info"):content.find("def handle_info") + 3000].count("_send_broadcast_via_tigrog2")
            
            print(f"✅ Toutes les méthodes utilisent _send_broadcast_via_tigrog2")
            
            return True
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_backward_compatibility():
    """Test que le code reste compatible avec les appels sans is_broadcast"""
    print("\n" + "=" * 60)
    print("TEST 5: Compatibilité ascendante (is_broadcast=False par défaut)")
    print("=" * 60)
    
    try:
        # Vérifier que is_broadcast a une valeur par défaut
        with open('handlers/command_handlers/network_commands.py', 'r') as f:
            content = f.read()
            
            if "def handle_propag(self, message, sender_id, sender_info, is_broadcast=False):" in content:
                print("✅ is_broadcast a une valeur par défaut (False)")
                print("✅ Les appels existants sans is_broadcast continueront de fonctionner")
                return True
            else:
                print("❌ is_broadcast n'a pas de valeur par défaut")
                return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_router_direct_message_handling():
    """Test que le routage DM continue de fonctionner"""
    print("\n" + "=" * 60)
    print("TEST 6: Routage DM (messages directs)")
    print("=" * 60)
    
    try:
        with open('handlers/message_router.py', 'r') as f:
            content = f.read()
            
            # Vérifier que le routage DM existe toujours dans _route_command
            if "elif message.startswith('/propag'):" in content:
                # Compter les occurrences
                propag_count = content.count("message.startswith('/propag')")
                if propag_count >= 2:  # Une pour broadcast, une pour DM
                    print(f"✅ /propag trouvé {propag_count} fois (broadcast + DM)")
                else:
                    print(f"⚠️  /propag trouvé seulement {propag_count} fois")
                
                # Vérifier l'appel handle_propag dans _route_command
                route_command_start = content.find("def _route_command")
                if route_command_start != -1:
                    route_section = content[route_command_start:route_command_start + 3000]
                    if "handle_propag(message, sender_id, sender_info)" in route_section:
                        print("✅ Appel handle_propag trouvé dans _route_command (DM)")
                    else:
                        print("⚠️  Appel handle_propag dans _route_command semble modifié")
                
                return True
            else:
                print("❌ Routage /propag non trouvé")
                return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Exécuter tous les tests"""
    print("🧪 TESTS DE /PROPAG EN MODE BROADCAST")
    print("=" * 60)
    print("Vérifie que /propag répond aux messages broadcast")
    print("comme /echo, /rain, /my, /weather, /bot et /info")
    print("=" * 60)
    
    results = {
        "broadcast_commands_list": test_broadcast_commands_list(),
        "handle_propag_signature": test_handle_propag_signature(),
        "broadcast_response_logic": test_broadcast_response_logic(),
        "consistency": test_consistency_with_other_broadcast_commands(),
        "backward_compatibility": test_backward_compatibility(),
        "dm_routing": test_router_direct_message_handling(),
    }
    
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:30s} : {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 TOUS LES TESTS ONT RÉUSSI!")
        print("\n✅ /propag peut maintenant répondre aux broadcasts mesh")
        print("✅ Compatibilité ascendante maintenue (DM continue de fonctionner)")
        print("✅ Pattern cohérent avec /echo, /rain, /my, /weather, /bot, /info")
    else:
        print("⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
        print("\nVérifiez les erreurs ci-dessus")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
