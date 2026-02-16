#!/usr/bin/env python3
"""
Démonstration de la sortie attendue pour les logs MQTT avec longname
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def show_examples():
    """Afficher des exemples avant/après"""
    
    print("\n" + "="*70)
    print("DÉMONSTRATION: Logs MQTT avec longname")
    print("="*70)
    
    print("\n📋 AVANT (sans longname):")
    print("-" * 70)
    print("Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet POSITION de 2867b4fa")
    print("Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet NODEINFO de ae613834")
    print("Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet NODEINFO de d4b288a9")
    
    print("\n✨ APRÈS (avec longname quand disponible):")
    print("-" * 70)
    print("Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet POSITION de 2867b4fa (TigroRouter)")
    print("Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet NODEINFO de ae613834 (NodeAlpha)")
    print("Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet NODEINFO de d4b288a9 (MeshNode-West)")
    
    print("\n📝 COMPORTEMENT:")
    print("-" * 70)
    print("✅ Si node_manager est disponible ET a un longname pour le nœud:")
    print("   → Affiche: Paquet TYPE de HEXID (LongName)")
    print("")
    print("✅ Si node_manager n'est pas disponible OU n'a pas de longname:")
    print("   → Affiche: Paquet TYPE de HEXID")
    print("")
    print("✅ Si longname est 'Unknown' ou commence par '!' (ID hex):")
    print("   → Affiche: Paquet TYPE de HEXID (sans le longname)")
    print("")
    
    print("\n💡 AVANTAGES:")
    print("-" * 70)
    print("• Identification rapide des nœuds dans les logs")
    print("• Facilite le debugging et le monitoring")
    print("• Pas de surcharge si le nom n'est pas disponible")
    print("• Compatible avec l'existant (fallback sur hex ID)")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    show_examples()
