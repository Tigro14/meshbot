#!/usr/bin/env python3
"""
Démonstration des alertes Mesh (DM)
Montre comment les alertes critiques sont envoyées aux nœuds abonnés
"""

import sys
import time

# Mock config pour démo
class MockConfig:
    DEBUG_MODE = False
    MESH_ALERTS_ENABLED = True
    MESH_ALERT_SUBSCRIBED_NODES = [0x16fad3dc, 0x12345678, 0xabcdef01]
    MESH_ALERT_THROTTLE_SECONDS = 1800  # 30 minutes
    BLITZ_MESH_ALERT_THRESHOLD = 5
    MAX_MESSAGE_SIZE = 180

sys.modules['config'] = MockConfig()

from mesh_alert_manager import MeshAlertManager


class DemoMessageSender:
    """Simulateur d'envoi de messages pour la démo"""
    def __init__(self):
        self.sent_count = 0
        
    def send_single(self, message, node_id, node_info):
        """Simuler l'envoi d'un DM"""
        self.sent_count += 1
        print(f"\n  📨 DM → 0x{node_id:08x}")
        print(f"     Message: {message}")


def demo_vigilance_alert():
    """Démonstration d'alerte vigilance météo"""
    print("\n" + "=" * 70)
    print("DÉMONSTRATION: Alerte Vigilance Météo")
    print("=" * 70)
    
    sender = DemoMessageSender()
    manager = MeshAlertManager(
        message_sender=sender,
        subscribed_nodes=[0x16fad3dc, 0x12345678, 0xabcdef01],
        throttle_seconds=1800  # 30 minutes
    )
    
    print("\n📍 Configuration:")
    print(f"  • Nœuds abonnés: 3")
    print(f"  • IDs: 0x16fad3dc, 0x12345678, 0xabcdef01")
    print(f"  • Throttle: 30 minutes")
    
    print("\n🌦️ Scénario: Météo-France détecte vigilance ORANGE")
    print("  → Département 25 (Doubs)")
    print("  → Phénomène: Vent violent")
    
    # Message d'alerte compact (format LoRa)
    alert_message = """🟠 VIGILANCE ORANGE
Dept 25
Vent violent: Orange"""
    
    print(f"\n📝 Message d'alerte (format compact LoRa):")
    print(f"  Taille: {len(alert_message)} caractères (limite: 180)")
    print(f"  Contenu:")
    for line in alert_message.split('\n'):
        print(f"    {line}")
    
    print("\n📤 Envoi aux nœuds abonnés...")
    sent_count = manager.send_alert(
        alert_type='vigilance',
        message=alert_message,
        force=False
    )
    
    print(f"\n✅ Résultat: {sent_count} DM envoyés")
    print(f"   Les 3 nœuds ont été alertés de la vigilance ORANGE")


def demo_blitz_alert():
    """Démonstration d'alerte éclairs"""
    print("\n" + "=" * 70)
    print("DÉMONSTRATION: Alerte Éclairs (Blitzortung)")
    print("=" * 70)
    
    sender = DemoMessageSender()
    manager = MeshAlertManager(
        message_sender=sender,
        subscribed_nodes=[0x16fad3dc, 0x12345678],
        throttle_seconds=1800
    )
    
    print("\n📍 Configuration:")
    print(f"  • Nœuds abonnés: 2")
    print(f"  • IDs: 0x16fad3dc, 0x12345678")
    print(f"  • Seuil d'alerte: 5 éclairs")
    print(f"  • Rayon: 50km")
    print(f"  • Fenêtre: 15 minutes")
    
    print("\n⚡ Scénario: Détection de 8 éclairs à proximité")
    print("  → Plus proche: 12.3 km")
    print("  → Seuil dépassé (8 >= 5)")
    
    # Message d'alerte compact
    alert_message = """⚡ 8 éclairs (15min)
+ proche: 12.3km
il y a 2min"""
    
    print(f"\n📝 Message d'alerte (format compact LoRa):")
    print(f"  Taille: {len(alert_message)} caractères")
    print(f"  Contenu:")
    for line in alert_message.split('\n'):
        print(f"    {line}")
    
    print("\n📤 Envoi aux nœuds abonnés...")
    sent_count = manager.send_alert(
        alert_type='blitz',
        message=alert_message,
        force=False
    )
    
    print(f"\n✅ Résultat: {sent_count} DM envoyés")
    print(f"   Les nœuds ont été alertés de l'orage à proximité")


def demo_throttling():
    """Démonstration du throttling"""
    print("\n" + "=" * 70)
    print("DÉMONSTRATION: Throttling des Alertes")
    print("=" * 70)
    
    sender = DemoMessageSender()
    manager = MeshAlertManager(
        message_sender=sender,
        subscribed_nodes=[0x16fad3dc],
        throttle_seconds=10  # 10 secondes pour la démo
    )
    
    print("\n📍 Configuration:")
    print(f"  • Nœud: 0x16fad3dc")
    print(f"  • Throttle: 10 secondes")
    
    print("\n📤 Test 1: Premier envoi d'alerte blitz")
    sent1 = manager.send_alert('blitz', '⚡ 5 éclairs détectés')
    print(f"  → {sent1} DM envoyé")
    
    print("\n📤 Test 2: Deuxième envoi immédiat (même type)")
    sent2 = manager.send_alert('blitz', '⚡ 7 éclairs détectés')
    print(f"  → {sent2} DM envoyé (throttlé car < 10s)")
    
    print("\n📤 Test 3: Envoi type différent (vigilance)")
    sent3 = manager.send_alert('vigilance', '🟠 VIGILANCE ORANGE')
    print(f"  → {sent3} DM envoyé (type différent = OK)")
    
    print("\n⏳ Attente 11 secondes...")
    time.sleep(11)
    
    print("\n📤 Test 4: Nouvel envoi blitz après throttle")
    sent4 = manager.send_alert('blitz', '⚡ 10 éclairs détectés')
    print(f"  → {sent4} DM envoyé (throttle expiré)")
    
    stats = manager.get_stats()
    print(f"\n📊 Statistiques finales:")
    print(f"  • Total envoyé: {stats['total_alerts_sent']}")
    print(f"  • Throttlé: {stats['alerts_throttled']}")


def demo_configuration():
    """Démonstration de la configuration"""
    print("\n" + "=" * 70)
    print("CONFIGURATION: Comment configurer les alertes Mesh")
    print("=" * 70)
    
    config_example = """
# Dans config.py:

# ========================================
# CONFIGURATION ALERTES MESH (DM)
# ========================================

# Activer les alertes Mesh
MESH_ALERTS_ENABLED = True

# Nœuds à alerter (liste d'IDs en hex ou decimal)
MESH_ALERT_SUBSCRIBED_NODES = [
    0x16fad3dc,  # Node 1
    0x12345678,  # Node 2
    305419896,   # Node 3 (format decimal)
]

# Seuil d'éclairs pour alerter (nombre minimum)
BLITZ_MESH_ALERT_THRESHOLD = 5  # 5 éclairs ou plus

# Throttling (temps minimum entre 2 alertes identiques)
MESH_ALERT_THROTTLE_SECONDS = 1800  # 30 minutes
"""
    
    print(config_example)
    
    print("\n📋 Alertes automatiques:")
    print("  ✅ Vigilance: Orange ou Rouge")
    print("  ✅ Éclairs: >= BLITZ_MESH_ALERT_THRESHOLD")
    
    print("\n🔔 Comportement:")
    print("  • Envoi automatique aux nœuds abonnés")
    print("  • Format compact adapté au LoRa (< 180 chars)")
    print("  • Throttling pour éviter le spam")
    print("  • Logs complets pour debug")


def main():
    """Programme principal de démonstration"""
    print("\n" + "=" * 70)
    print("SYSTÈME D'ALERTES MESH VIA DM MESHTASTIC")
    print("=" * 70)
    print("\nCe système permet d'envoyer automatiquement des alertes critiques")
    print("(vigilance météo, éclairs) aux nœuds Meshtastic abonnés via DM.")
    
    try:
        demo_configuration()
        input("\n⏸️  Appuyez sur Entrée pour continuer...")
        
        demo_vigilance_alert()
        input("\n⏸️  Appuyez sur Entrée pour continuer...")
        
        demo_blitz_alert()
        input("\n⏸️  Appuyez sur Entrée pour continuer...")
        
        demo_throttling()
        
        print("\n" + "=" * 70)
        print("✅ DÉMONSTRATION TERMINÉE")
        print("=" * 70)
        print("\n💡 Points clés:")
        print("  • Les alertes sont envoyées via DM Meshtastic")
        print("  • Format compact optimisé pour LoRa (< 180 chars)")
        print("  • Throttling évite le spam (30 min par défaut)")
        print("  • Alertes par type (vigilance, blitz)")
        print("  • Configuration simple dans config.py")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Démonstration interrompue")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
