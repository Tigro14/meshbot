#!/usr/bin/env python3
"""
Demo des commandes traffic (/trafic, /trafficmt, /trafficmc)
Montre le filtrage par réseau
"""

import sys
import os
from datetime import datetime
import time

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockPublicMessage:
    """Message public simulé pour tests"""
    def __init__(self, timestamp, sender_name, message, source):
        self.data = {
            'timestamp': timestamp,
            'sender_name': sender_name,
            'message': message,
            'source': source
        }


class MockTrafficMonitor:
    """Traffic monitor simulé pour tests"""
    def __init__(self):
        # Créer des messages test avec différentes sources
        current_time = time.time()
        
        self.public_messages = [
            # Messages Meshtastic (local = serial)
            {'timestamp': current_time - 7200, 'sender_name': 'tigro', 'message': 'Test serial 1', 'source': 'local'},
            {'timestamp': current_time - 6000, 'sender_name': 'node1', 'message': 'Hello from serial', 'source': 'local'},
            {'timestamp': current_time - 5000, 'sender_name': 'node2', 'message': 'Test serial 2', 'source': 'local'},
            
            # Messages Meshtastic (tcp)
            {'timestamp': current_time - 4000, 'sender_name': 'router1', 'message': 'Test TCP 1', 'source': 'tcp'},
            {'timestamp': current_time - 3000, 'sender_name': 'router2', 'message': 'Hello from TCP', 'source': 'tcp'},
            {'timestamp': current_time - 2000, 'sender_name': 'tigrog2', 'message': 'Test tigrog2', 'source': 'tigrog2'},
            
            # Messages MeshCore
            {'timestamp': current_time - 1800, 'sender_name': 'mcnode1', 'message': 'Test MeshCore 1', 'source': 'meshcore'},
            {'timestamp': current_time - 1200, 'sender_name': 'mcnode2', 'message': 'Hello from MeshCore', 'source': 'meshcore'},
            {'timestamp': current_time - 600, 'sender_name': 'mcnode3', 'message': 'Test MeshCore 2', 'source': 'meshcore'},
            {'timestamp': current_time - 300, 'sender_name': 'mcnode1', 'message': 'Latest MeshCore msg', 'source': 'meshcore'},
        ]


def demo_get_traffic_report(traffic_monitor, hours=8):
    """Simuler get_traffic_report (tous les messages)"""
    print(f"\n{'='*80}")
    print(f"📊 DEMO: /trafic {hours}h (TOUS LES MESSAGES)")
    print(f"{'='*80}")
    
    current_time = time.time()
    cutoff_time = current_time - (hours * 3600)
    
    # Filtrer les messages de la période
    recent_messages = [
        msg for msg in traffic_monitor.public_messages
        if msg['timestamp'] >= cutoff_time
    ]
    
    if not recent_messages:
        print(f"📭 Aucun message public dans les {hours}h")
        return
    
    # Compter par source
    source_counts = {}
    for msg in recent_messages:
        source = msg.get('source', 'unknown')
        source_counts[source] = source_counts.get(source, 0) + 1
    
    print(f"\n📊 **MESSAGES PUBLICS ({hours}h)**")
    print(f"{'='*40}")
    print(f"Total: {len(recent_messages)} messages")
    print()
    print("Par source:")
    for source, count in sorted(source_counts.items()):
        source_label = {
            'local': '📻 Serial (Meshtastic)',
            'tcp': '📡 TCP (Meshtastic)',
            'tigrog2': '📡 TCP tigrog2 (Meshtastic)',
            'meshcore': '🔗 MeshCore'
        }.get(source, source)
        print(f"  {source_label}: {count}")
    print()
    
    # Trier par timestamp
    recent_messages.sort(key=lambda x: x['timestamp'])
    
    # Afficher les messages
    for msg in recent_messages:
        msg_time = datetime.fromtimestamp(msg['timestamp'])
        time_str = msg_time.strftime("%H:%M:%S")
        sender = msg['sender_name']
        content = msg['message']
        source_icon = {
            'local': '📻',
            'tcp': '📡',
            'tigrog2': '📡',
            'meshcore': '🔗'
        }.get(msg.get('source'), '❓')
        
        print(f"[{time_str}] {source_icon} [{sender}] {content}")


def demo_get_traffic_report_mt(traffic_monitor, hours=8):
    """Simuler get_traffic_report_mt (seulement Meshtastic)"""
    print(f"\n{'='*80}")
    print(f"📡 DEMO: /trafficmt {hours}h (MESHTASTIC SEULEMENT)")
    print(f"{'='*80}")
    
    current_time = time.time()
    cutoff_time = current_time - (hours * 3600)
    
    # Filtrer les messages Meshtastic de la période
    meshtastic_sources = {'local', 'tcp', 'tigrog2'}
    recent_messages = [
        msg for msg in traffic_monitor.public_messages
        if msg['timestamp'] >= cutoff_time and msg.get('source') in meshtastic_sources
    ]
    
    if not recent_messages:
        print(f"📭 Aucun message public Meshtastic dans les {hours}h")
        return
    
    # Compter par source
    source_counts = {}
    for msg in recent_messages:
        source = msg.get('source', 'unknown')
        source_counts[source] = source_counts.get(source, 0) + 1
    
    print(f"\n📡 **MESSAGES PUBLICS MESHTASTIC ({hours}h)**")
    print(f"{'='*40}")
    print(f"Total: {len(recent_messages)} messages")
    print()
    for source, count in sorted(source_counts.items()):
        source_label = {
            'local': '📻 Serial',
            'tcp': '📡 TCP',
            'tigrog2': '📡 TCP (tigrog2)'
        }.get(source, source)
        print(f"  {source_label}: {count}")
    print()
    
    # Trier par timestamp
    recent_messages.sort(key=lambda x: x['timestamp'])
    
    # Afficher les messages
    for msg in recent_messages:
        msg_time = datetime.fromtimestamp(msg['timestamp'])
        time_str = msg_time.strftime("%H:%M:%S")
        sender = msg['sender_name']
        content = msg['message']
        source_icon = {
            'local': '📻',
            'tcp': '📡',
            'tigrog2': '📡'
        }.get(msg.get('source'), '❓')
        
        print(f"[{time_str}] {source_icon} [{sender}] {content}")


def demo_get_traffic_report_mc(traffic_monitor, hours=8):
    """Simuler get_traffic_report_mc (seulement MeshCore)"""
    print(f"\n{'='*80}")
    print(f"🔗 DEMO: /trafficmc {hours}h (MESHCORE SEULEMENT)")
    print(f"{'='*80}")
    
    current_time = time.time()
    cutoff_time = current_time - (hours * 3600)
    
    # Filtrer les messages MeshCore de la période
    recent_messages = [
        msg for msg in traffic_monitor.public_messages
        if msg['timestamp'] >= cutoff_time and msg.get('source') == 'meshcore'
    ]
    
    if not recent_messages:
        print(f"📭 Aucun message public MeshCore dans les {hours}h")
        return
    
    print(f"\n🔗 **MESSAGES PUBLICS MESHCORE ({hours}h)**")
    print(f"{'='*40}")
    print(f"Total: {len(recent_messages)} messages")
    print()
    
    # Trier par timestamp
    recent_messages.sort(key=lambda x: x['timestamp'])
    
    # Afficher les messages
    for msg in recent_messages:
        msg_time = datetime.fromtimestamp(msg['timestamp'])
        time_str = msg_time.strftime("%H:%M:%S")
        sender = msg['sender_name']
        content = msg['message']
        
        print(f"[{time_str}] [{sender}] {content}")


def main():
    """Fonction principale de demo"""
    print("=" * 80)
    print("🧪 DEMO: Commandes traffic (/trafic, /trafficmt, /trafficmc)")
    print("=" * 80)
    print()
    print("Cette demo montre le filtrage par réseau des messages publics")
    print()
    
    # Créer un traffic monitor avec des données test
    traffic_monitor = MockTrafficMonitor()
    
    print(f"📦 Données test créées:")
    print(f"   • {sum(1 for m in traffic_monitor.public_messages if m['source'] == 'local')} messages Serial (Meshtastic)")
    print(f"   • {sum(1 for m in traffic_monitor.public_messages if m['source'] in ['tcp', 'tigrog2'])} messages TCP (Meshtastic)")
    print(f"   • {sum(1 for m in traffic_monitor.public_messages if m['source'] == 'meshcore')} messages MeshCore")
    print(f"   • {len(traffic_monitor.public_messages)} messages total")
    
    # ========================================
    # SCÉNARIO 1: /trafic (tous les messages)
    # ========================================
    demo_get_traffic_report(traffic_monitor, hours=8)
    
    # ========================================
    # SCÉNARIO 2: /trafficmt (Meshtastic seulement)
    # ========================================
    demo_get_traffic_report_mt(traffic_monitor, hours=8)
    
    # ========================================
    # SCÉNARIO 3: /trafficmc (MeshCore seulement)
    # ========================================
    demo_get_traffic_report_mc(traffic_monitor, hours=8)
    
    # ========================================
    # RÉSUMÉ
    # ========================================
    print("\n" + "=" * 80)
    print("✅ RÉSUMÉ DE LA DEMO")
    print("=" * 80)
    print()
    print("1. ✅ /trafic - Affiche TOUS les messages (Meshtastic + MeshCore)")
    print("2. ✅ /trafficmt - Affiche UNIQUEMENT les messages Meshtastic")
    print("3. ✅ /trafficmc - Affiche UNIQUEMENT les messages MeshCore")
    print()
    print("🎯 AVANTAGES:")
    print("   • Filtrage par réseau pour analyses ciblées")
    print("   • Compatible avec mode dual (Meshtastic + MeshCore)")
    print("   • Compteurs par source pour visibilité détaillée")
    print("   • Icônes visuelles pour identifier rapidement les sources")
    print()
    print("📋 UTILISATION:")
    print("   /trafic [heures]     → Tous messages (défaut: 8h)")
    print("   /trafficmt [heures]  → Messages Meshtastic uniquement")
    print("   /trafficmc [heures]  → Messages MeshCore uniquement")
    print()


if __name__ == "__main__":
    main()
