#!/usr/bin/env python3
"""
Démonstration du nouvel alias /hop
Montre comment utiliser la commande /hop comme alias de /stats hop
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 70)
print("DÉMONSTRATION: Nouvel alias /hop")
print("=" * 70)

print("\n📋 DESCRIPTION:")
print("  La commande /hop est un nouvel alias pour /stats hop")
print("  Elle permet d'analyser la portée maximale des nœuds mesh")
print("  en affichant les top 20 nœuds triés par hop_start.")

print("\n💡 UTILISATION:")
print("  1. /hop          → Top 20 nœuds (24h par défaut)")
print("  2. /hop 48       → Top 20 nœuds (48 dernières heures)")
print("  3. /hop 168      → Top 20 nœuds (7 derniers jours)")

print("\n📊 EXEMPLES DE SORTIE:")

print("\n1️⃣  FORMAT MESH (LoRa - compact):")
print("-" * 70)
print("""🔄 Hop(24h) Top5
tigrog2:7
tigrobot:7
relay-nord:6
relay-sud:6
mobile-1:5""")
print("-" * 70)

print("\n2️⃣  FORMAT TELEGRAM (détaillé):")
print("-" * 70)
print("""🔄 **TOP 20 NŒUDS PAR HOP_START (24h)**
==================================================

12 nœuds actifs, top 20 affichés

1. 🔴 tigrog2
   Hop start max: **7** (45 paquets)

2. 🔴 tigrobot
   Hop start max: **7** (38 paquets)

3. 🟡 relay-nord
   Hop start max: **6** (22 paquets)

4. 🟡 relay-sud
   Hop start max: **6** (19 paquets)

5. 🟡 mobile-1
   Hop start max: **5** (15 paquets)

• Moyenne hop_start (top 20): 5.8
• Max hop_start observé: 7""")
print("-" * 70)

print("\n🎯 UTILITÉ:")
print("  • Identifier les meilleurs relais du réseau")
print("  • Optimiser le placement des nœuds")
print("  • Analyser la couverture réseau")
print("  • Comprendre la topologie mesh")

print("\n🔄 ÉQUIVALENCES:")
print("  /hop       ←→  /stats hop")
print("  /hop 48    ←→  /stats hop 48")
print("  /hop 168   ←→  /stats hop 168")

print("\n📌 ICÔNES DE PORTÉE:")
print("  🔴 hop_start ≥ 7  → Très grande portée (Router/Relais)")
print("  🟡 hop_start 5-6  → Grande portée (Mobile/Fixe)")
print("  🟢 hop_start 3-4  → Portée moyenne (Standard)")
print("  ⚪ hop_start ≤ 2  → Faible portée (Indoor/Test)")

print("\n✨ AVANTAGES:")
print("  ✅ Plus court et rapide à taper: /hop vs /stats hop")
print("  ✅ Même comportement que les autres alias (/top, /histo, /packets)")
print("  ✅ Compatible Mesh et Telegram")
print("  ✅ Supporte tous les paramètres (heures)")

print("\n" + "=" * 70)
print("✅ DÉMONSTRATION TERMINÉE")
print("=" * 70)
