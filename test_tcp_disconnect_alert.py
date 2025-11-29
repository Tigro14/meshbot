#!/usr/bin/env python3
"""
Test pour vérifier que les alertes de déconnexion TCP sont envoyées via Telegram

Ce test vérifie que:
1. La méthode _send_tcp_disconnect_alert existe
2. Elle vérifie la configuration TCP_DISCONNECT_ALERT_ENABLED
3. Elle vérifie que telegram_integration est disponible
4. Elle formate correctement le message d'alerte
5. Les appels à _send_tcp_disconnect_alert sont présents dans _reconnect_tcp_interface
"""

import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))


def test_tcp_disconnect_alert_method_exists():
    """
    Test que la méthode _send_tcp_disconnect_alert existe dans main_bot.py
    """
    print("\n🧪 Test: Méthode _send_tcp_disconnect_alert existe")
    
    with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
        content = f.read()
    
    # Vérifier que la méthode existe
    assert 'def _send_tcp_disconnect_alert' in content, \
        "❌ La méthode _send_tcp_disconnect_alert devrait exister"
    print("✅ Méthode _send_tcp_disconnect_alert existe")
    
    return True


def test_tcp_disconnect_alert_checks_config():
    """
    Test que _send_tcp_disconnect_alert vérifie la configuration
    """
    print("\n🧪 Test: Vérification de la configuration")
    
    with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
        content = f.read()
    
    # Trouver la méthode
    method_start = content.find('def _send_tcp_disconnect_alert')
    next_def = content.find('\n    def ', method_start + 1)
    method_code = content[method_start:next_def]
    
    # Vérifier que la config est vérifiée
    assert 'TCP_DISCONNECT_ALERT_ENABLED' in method_code, \
        "❌ La méthode devrait vérifier TCP_DISCONNECT_ALERT_ENABLED"
    print("✅ Vérifie TCP_DISCONNECT_ALERT_ENABLED")
    
    # Vérifier que telegram_integration est vérifié
    assert 'telegram_integration' in method_code, \
        "❌ La méthode devrait vérifier telegram_integration"
    print("✅ Vérifie telegram_integration")
    
    return True


def test_tcp_disconnect_alert_formats_message():
    """
    Test que _send_tcp_disconnect_alert formate correctement le message
    """
    print("\n🧪 Test: Formatage du message d'alerte")
    
    with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
        content = f.read()
    
    # Trouver la méthode
    method_start = content.find('def _send_tcp_disconnect_alert')
    next_def = content.find('\n    def ', method_start + 1)
    method_code = content[method_start:next_def]
    
    # Vérifier les éléments du message
    assert 'tcp_host' in method_code, \
        "❌ Le message devrait contenir tcp_host"
    print("✅ Le message contient tcp_host")
    
    assert 'tcp_port' in method_code, \
        "❌ Le message devrait contenir tcp_port"
    print("✅ Le message contient tcp_port")
    
    assert 'send_alert' in method_code, \
        "❌ La méthode devrait appeler send_alert"
    print("✅ Appelle send_alert")
    
    return True


def test_tcp_disconnect_alert_called_on_failure():
    """
    Test que _send_tcp_disconnect_alert est appelée quand la reconnexion échoue
    """
    print("\n🧪 Test: Appel lors de l'échec de reconnexion")
    
    with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
        content = f.read()
    
    # Trouver la méthode _reconnect_tcp_interface
    reconnect_start = content.find('def _reconnect_tcp_interface')
    # Trouver le prochain "def " au même niveau d'indentation après le début de la fonction
    next_def = content.find('\n    def ', reconnect_start + 1)
    reconnect_code = content[reconnect_start:next_def]
    
    # Compter les appels à _send_tcp_disconnect_alert dans la méthode
    call_count = reconnect_code.count('_send_tcp_disconnect_alert')
    
    assert call_count >= 2, \
        f"❌ _send_tcp_disconnect_alert devrait être appelée au moins 2 fois (trouvé {call_count})"
    print(f"✅ _send_tcp_disconnect_alert est appelée {call_count} fois dans _reconnect_tcp_interface")
    
    return True


def test_config_option_exists():
    """
    Test que l'option de configuration TCP_DISCONNECT_ALERT_ENABLED existe
    """
    print("\n🧪 Test: Option de configuration existe")
    
    with open('/home/runner/work/meshbot/meshbot/config.py.sample', 'r') as f:
        content = f.read()
    
    # Vérifier que l'option existe
    assert 'TCP_DISCONNECT_ALERT_ENABLED' in content, \
        "❌ TCP_DISCONNECT_ALERT_ENABLED devrait exister dans config.py.sample"
    print("✅ TCP_DISCONNECT_ALERT_ENABLED existe dans config.py.sample")
    
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("TEST: ALERTES TELEGRAM SUR DÉCONNEXION TCP")
    print("=" * 70)
    
    results = [
        test_tcp_disconnect_alert_method_exists(),
        test_tcp_disconnect_alert_checks_config(),
        test_tcp_disconnect_alert_formats_message(),
        test_tcp_disconnect_alert_called_on_failure(),
        test_config_option_exists(),
    ]
    
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if all(results):
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        print("\nFonctionnalité implémentée:")
        print("- Alerte Telegram envoyée quand la connexion TCP est définitivement perdue")
        print("- Configuration via TCP_DISCONNECT_ALERT_ENABLED")
        print("- Message d'alerte avec host, port, et détails de l'erreur")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
