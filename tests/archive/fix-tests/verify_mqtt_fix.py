#!/usr/bin/env python3
"""
Script de vérification rapide du fix MQTT disconnect callback

Ce script vérifie que le fix est correctement appliqué et que
l'erreur "takes from 4 to 5 positional arguments but 6 were given"
ne peut plus se produire.
"""

import sys
import inspect

print("=" * 70)
print("VÉRIFICATION DU FIX MQTT DISCONNECT CALLBACK")
print("=" * 70)

# Vérifier paho-mqtt
try:
    import paho.mqtt.client as mqtt
    import paho.mqtt
    print(f"✅ paho-mqtt disponible (version {paho.mqtt.__version__})")
except ImportError:
    print("❌ paho-mqtt non disponible")
    sys.exit(1)

# Vérifier pygeohash
try:
    import pygeohash
    print("✅ pygeohash disponible")
except ImportError:
    print("⚠️  pygeohash non disponible (tests BlitzMonitor seront limités)")
    # Mock pour permettre l'import
    from unittest.mock import Mock
    sys.modules['pygeohash'] = Mock()

# Importer les modules
try:
    from blitz_monitor import BlitzMonitor
    print("✅ blitz_monitor importé")
except Exception as e:
    print(f"❌ Erreur import blitz_monitor: {e}")
    sys.exit(1)

try:
    from mqtt_neighbor_collector import MQTTNeighborCollector
    print("✅ mqtt_neighbor_collector importé")
except Exception as e:
    print(f"❌ Erreur import mqtt_neighbor_collector: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("VÉRIFICATION DES SIGNATURES")
print("=" * 70)

# Vérifier BlitzMonitor
print("\n1. BlitzMonitor._on_mqtt_disconnect")
print("-" * 40)
monitor = BlitzMonitor(lat=47.0, lon=6.0, radius_km=50)
sig = inspect.signature(monitor._on_mqtt_disconnect)
params = list(sig.parameters.keys())
expected = ['client', 'userdata', 'disconnect_flags', 'reason_code', 'properties']

print(f"Paramètres trouvés: {params}")
print(f"Paramètres attendus: {expected}")

if params == expected:
    print("✅ Signature correcte pour VERSION2")
else:
    print("❌ Signature incorrecte!")
    print(f"   Différence: {set(expected) - set(params)}")
    sys.exit(1)

# Vérifier MQTTNeighborCollector
print("\n2. MQTTNeighborCollector._on_mqtt_disconnect")
print("-" * 40)
from unittest.mock import Mock
mock_persistence = Mock()
collector = MQTTNeighborCollector(
    mqtt_server="test",
    persistence=mock_persistence
)

sig = inspect.signature(collector._on_mqtt_disconnect)
params = list(sig.parameters.keys())

print(f"Paramètres trouvés: {params}")
print(f"Paramètres attendus: {expected}")

if params == expected:
    print("✅ Signature correcte pour VERSION2")
else:
    print("❌ Signature incorrecte!")
    print(f"   Différence: {set(expected) - set(params)}")
    sys.exit(1)

print("\n" + "=" * 70)
print("VÉRIFICATION DE LA COMPATIBILITÉ MQTT")
print("=" * 70)

# Créer un client MQTT VERSION2 et assigner les callbacks
print("\n3. Test assignation callbacks MQTT VERSION2")
print("-" * 40)

try:
    # BlitzMonitor
    monitor = BlitzMonitor(lat=47.0, lon=6.0, radius_km=50)
    monitor.mqtt_client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    monitor.mqtt_client.on_disconnect = monitor._on_mqtt_disconnect
    print("✅ BlitzMonitor: callback assigné sans erreur")
    
    # MQTTNeighborCollector
    if collector.enabled:
        collector.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        collector.mqtt_client.on_disconnect = collector._on_mqtt_disconnect
        print("✅ MQTTNeighborCollector: callback assigné sans erreur")
    else:
        print("⚠️  MQTTNeighborCollector désactivé (dépendances manquantes)")
    
except Exception as e:
    print(f"❌ Erreur lors de l'assignation: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("TEST D'INVOCATION")
print("=" * 70)

# Tester l'invocation du callback avec les bons arguments
print("\n4. Test invocation callback avec arguments VERSION2")
print("-" * 40)

try:
    mock_client = Mock()
    mock_userdata = None
    mock_disconnect_flags = Mock()
    mock_reason_code = 0
    mock_properties = None
    
    # Invoquer BlitzMonitor callback
    monitor._on_mqtt_disconnect(
        mock_client,
        mock_userdata,
        mock_disconnect_flags,
        mock_reason_code,
        mock_properties
    )
    print("✅ BlitzMonitor: callback invoqué sans TypeError")
    
    # Invoquer MQTTNeighborCollector callback
    collector._on_mqtt_disconnect(
        mock_client,
        mock_userdata,
        mock_disconnect_flags,
        mock_reason_code,
        mock_properties
    )
    print("✅ MQTTNeighborCollector: callback invoqué sans TypeError")
    
except TypeError as e:
    print(f"❌ TypeError lors de l'invocation: {e}")
    print("   Le fix n'est PAS appliqué correctement!")
    sys.exit(1)

print("\n" + "=" * 70)
print("RÉSULTAT FINAL")
print("=" * 70)
print("\n✅ TOUS LES TESTS PASSENT")
print("\nLe fix est correctement appliqué:")
print("  - Les signatures sont correctes pour paho-mqtt VERSION2")
print("  - Les callbacks peuvent être assignés sans erreur")
print("  - Les callbacks peuvent être invoqués avec 5 paramètres")
print("\nL'erreur 'takes from 4 to 5 positional arguments but 6 were given'")
print("ne peut plus se produire.")
print("\n" + "=" * 70)
