#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visual demonstration of /mqtt command output
Shows various scenarios and edge cases
"""

def show_scenario(title, output):
    """Print a scenario with formatting"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print('='*70)
    print(output)
    print()


def main():
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█" + "  /mqtt TELEGRAM COMMAND - VISUAL DEMONSTRATION".center(68) + "█")
    print("█" + " "*68 + "█")
    print("█"*70)
    
    # Scenario 1: Normal operation with 5 nodes
    show_scenario(
        "Scenario 1: Normal Operation (5 MQTT nodes heard)",
        """📡 Nœuds MQTT entendus directement (5 nœuds, 48h)

Statut MQTT: Connecté 🟢

1. 🟢 tigrobot (5678) - 2m
2. 🟢 tigrog2 (4321) - 30m
3. 🟡 Paris-Gateway (ef01) - 5h
4. 🟡 Unknown-Node (beef) - 10h
5. 🟠 Lyon-Mesh-001 (d3dc) - 1j"""
    )
    
    # Scenario 2: Filtered to 24h
    show_scenario(
        "Scenario 2: Filtered to Last 24 Hours (/mqtt 24)",
        """📡 Nœuds MQTT entendus directement (4 nœuds, 24h)

Statut MQTT: Connecté 🟢

1. 🟢 tigrobot (5678) - 2m
2. 🟢 tigrog2 (4321) - 30m
3. 🟡 Paris-Gateway (ef01) - 5h
4. 🟡 Unknown-Node (beef) - 10h"""
    )
    
    # Scenario 3: Only very recent nodes
    show_scenario(
        "Scenario 3: Only Very Recent Nodes (/mqtt 1)",
        """📡 Nœuds MQTT entendus directement (2 nœuds, 1h)

Statut MQTT: Connecté 🟢

1. 🟢 tigrobot (5678) - 2m
2. 🟢 tigrog2 (4321) - 30m"""
    )
    
    # Scenario 4: MQTT disconnected
    show_scenario(
        "Scenario 4: MQTT Collector Disconnected",
        """📡 Nœuds MQTT entendus directement (3 nœuds, 48h)

Statut MQTT: Déconnecté 🔴

1. 🟢 tigrobot (5678) - 45m
2. 🟡 Paris-Gateway (ef01) - 12h
3. 🟠 Lyon-Mesh-001 (d3dc) - 2j

⚠️ Note: Le collecteur MQTT est déconnecté mais affiche les dernières données connues."""
    )
    
    # Scenario 5: No nodes heard
    show_scenario(
        "Scenario 5: No Nodes Heard Recently",
        """ℹ️ Aucun nœud MQTT entendu dans les 1 dernières heures.

Le collecteur MQTT est actif mais n'a pas encore reçu de paquets NEIGHBORINFO."""
    )
    
    # Scenario 6: MQTT collector disabled
    show_scenario(
        "Scenario 6: MQTT Collector Not Enabled",
        """❌ Collecteur MQTT de voisins non disponible ou désactivé.

Pour l'activer, configurez dans config.py:
```
MQTT_NEIGHBOR_ENABLED = True
MQTT_NEIGHBOR_SERVER = "serveurperso.com"
MQTT_NEIGHBOR_USER = "meshdev"
MQTT_NEIGHBOR_PASSWORD = "..."
```"""
    )
    
    # Scenario 7: Large network (many nodes)
    show_scenario(
        "Scenario 7: Large Mesh Network (15 nodes)",
        """📡 Nœuds MQTT entendus directement (15 nœuds, 48h)

Statut MQTT: Connecté 🟢

1. 🟢 tigrobot (5678) - 1m
2. 🟢 tigrog2 (4321) - 5m
3. 🟢 Marseille-01 (abc1) - 15m
4. 🟢 Nice-Gateway (def2) - 45m
5. 🟡 Lyon-001 (d3dc) - 2h
6. 🟡 Lyon-002 (d3dd) - 3h
7. 🟡 Toulouse-Hub (cafe) - 6h
8. 🟡 Bordeaux-Mesh (beef) - 12h
9. 🟡 Strasbourg-01 (feed) - 18h
10. 🟡 Lille-Gateway (dead) - 22h
11. 🟠 Nantes-001 (1234) - 1j
12. 🟠 Rennes-Mesh (5678) - 1j
13. 🟠 Montpellier-01 (9abc) - 2j
14. 🟠 Clermont-Hub (def0) - 2j
15. 🟠 Dijon-Gateway (1111) - 2j"""
    )
    
    # Scenario 8: Mixed known/unknown nodes
    show_scenario(
        "Scenario 8: Mix of Named and Unknown Nodes",
        """📡 Nœuds MQTT entendus directement (6 nœuds, 48h)

Statut MQTT: Connecté 🟢

1. 🟢 tigrobot (5678) - 5m
2. 🟢 !87654321 (4321) - 30m  ← Unknown node (no name in DB)
3. 🟡 Paris-Gateway (ef01) - 8h
4. 🟡 !deadbeef (beef) - 10h  ← Unknown node
5. 🟠 Lyon-Mesh-001 (d3dc) - 1j
6. 🟠 !12345678 (5678) - 2j  ← Unknown node"""
    )
    
    # Command usage examples
    print("\n" + "="*70)
    print("  COMMAND USAGE EXAMPLES")
    print("="*70)
    print("""
User sends in Telegram:
  /mqtt              → Show all nodes (default 48h)
  /mqtt 24           → Show nodes from last 24 hours
  /mqtt 1            → Show nodes from last hour
  /mqtt 168          → Show nodes from last week (max: 7 days)
  
Bot responds with formatted list showing:
  • Connection status (🟢 Connected / 🔴 Disconnected)
  • Total node count and time window
  • Each node with:
    - Status icon (🟢 <1h, 🟡 <24h, 🟠 >24h)
    - LongName in bold (or node_id if unknown)
    - Short ID in monospace (last 4 hex chars)
    - Elapsed time since last heard
""")
    
    # Icon legend
    print("\n" + "="*70)
    print("  STATUS ICON LEGEND")
    print("="*70)
    print("""
  🟢 Green   - Node heard within last hour (very active)
  🟡 Yellow  - Node heard within last 24 hours (active)
  🟠 Orange  - Node heard more than 24 hours ago (inactive)
  
  Connection Status:
  Connecté 🟢   - MQTT collector connected to server
  Déconnecté 🔴 - MQTT collector disconnected (shows cached data)
""")
    
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█" + "  END OF DEMONSTRATION".center(68) + "█")
    print("█" + " "*68 + "█")
    print("█"*70 + "\n")


if __name__ == "__main__":
    main()
