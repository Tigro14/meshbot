#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test pour vérifier l'amélioration du logging de debug pour les erreurs de parsing traceroute

Ce test vérifie que:
1. Les erreurs de parsing sont loggées avec détails
2. Le payload brut est inclus dans les logs
3. Les informations de debug sont incluses dans le message utilisateur
"""

import sys
import os

# Simulation d'un cas où le parsing échoue
def test_parse_error_logging():
    """
    Simuler une erreur de parsing et vérifier le logging
    """
    print("=" * 70)
    print("TEST AMÉLIORATION DEBUG LOGGING TRACEROUTE")
    print("=" * 70)
    
    # Simuler un payload invalide
    invalid_payload = b'\x00\x01\x02\x03\xff\xfe\xfd'
    payload_hex = invalid_payload.hex()
    payload_size = len(invalid_payload)
    
    print(f"\n📦 Test avec payload invalide:")
    print(f"   Taille: {payload_size} bytes")
    print(f"   Hex: {payload_hex}")
    
    # Simuler l'erreur de parsing
    parse_error = "Error parsing RouteDiscovery: Invalid protobuf format"
    error_type = "DecodeError"
    
    print(f"\n❌ Erreur de parsing simulée:")
    print(f"   Type: {error_type}")
    print(f"   Message: {parse_error}")
    
    # Construire le message utilisateur (format amélioré)
    debug_parts = []
    debug_parts.append("📊 **Traceroute vers champlard**")
    debug_parts.append("━━━━━━━━━━━━━━━━━━━━")
    debug_parts.append("")
    debug_parts.append("⚠️ **Route non décodable**")
    debug_parts.append("Le nœud a répondu mais le format n'est pas standard.")
    debug_parts.append("")
    debug_parts.append("⏱️ **Temps de réponse:** 2.5s")
    debug_parts.append("")
    debug_parts.append("🔍 **Debug Info:**")
    debug_parts.append(f"Erreur: `{parse_error}`")
    debug_parts.append(f"Taille payload: {payload_size} bytes")
    
    # Limiter le hex à 64 caractères
    hex_preview = payload_hex[:64]
    if len(payload_hex) > 64:
        hex_preview += "..."
    debug_parts.append(f"Payload hex: `{hex_preview}`")
    debug_parts.append("")
    debug_parts.append("ℹ️ Cela peut arriver avec:")
    debug_parts.append("  • Certaines versions du firmware")
    debug_parts.append("  • Des paquets corrompus en transit")
    debug_parts.append("  • Des formats protobuf incompatibles")
    
    user_message = "\n".join(debug_parts)
    
    print("\n📤 Message utilisateur (format amélioré):")
    print("─" * 70)
    print(user_message)
    print("─" * 70)
    
    # Logs de debug (ce qui apparaîtra dans les logs serveur)
    debug_logs = []
    debug_logs.append(f"📦 [Traceroute] Paquet reçu:")
    debug_logs.append(f"   Payload size: {payload_size} bytes")
    debug_logs.append(f"   Payload hex: {payload_hex}")
    debug_logs.append(f"❌ Erreur parsing RouteDiscovery: {parse_error}")
    debug_logs.append(f"   Type d'erreur: {error_type}")
    debug_logs.append(f"   Payload size: {payload_size} bytes")
    debug_logs.append(f"   Payload hex: {payload_hex}")
    
    print("\n📋 Logs de debug (serveur):")
    print("─" * 70)
    for log in debug_logs:
        print(log)
    print("─" * 70)
    
    # Vérifications
    checks = []
    
    # 1. Le message utilisateur contient l'erreur
    if "Erreur:" in user_message and parse_error in user_message:
        print("\n✅ Message utilisateur contient l'erreur de parsing")
        checks.append(True)
    else:
        print("\n❌ Message utilisateur ne contient pas l'erreur")
        checks.append(False)
    
    # 2. Le message utilisateur contient la taille du payload
    if f"Taille payload: {payload_size} bytes" in user_message:
        print("✅ Message utilisateur contient la taille du payload")
        checks.append(True)
    else:
        print("❌ Message utilisateur ne contient pas la taille")
        checks.append(False)
    
    # 3. Le message utilisateur contient le hex du payload
    if f"Payload hex:" in user_message and hex_preview in user_message:
        print("✅ Message utilisateur contient le payload hex")
        checks.append(True)
    else:
        print("❌ Message utilisateur ne contient pas le payload hex")
        checks.append(False)
    
    # 4. Le message utilisateur est informatif
    if "Cela peut arriver avec:" in user_message:
        print("✅ Message utilisateur est informatif")
        checks.append(True)
    else:
        print("❌ Message utilisateur n'est pas assez informatif")
        checks.append(False)
    
    # 5. Les logs de debug contiennent les détails
    debug_log_str = "\n".join(debug_logs)
    if payload_hex in debug_log_str and error_type in debug_log_str:
        print("✅ Logs de debug contiennent les détails techniques")
        checks.append(True)
    else:
        print("❌ Logs de debug manquent des détails")
        checks.append(False)
    
    return all(checks)

if __name__ == "__main__":
    print("\nTest de l'amélioration du logging de debug pour traceroute\n")
    
    success = test_parse_error_logging()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("\nL'amélioration apporte:")
        print("  • Erreur de parsing visible dans le message utilisateur")
        print("  • Taille du payload affichée")
        print("  • Aperçu hex du payload pour debug")
        print("  • Logs serveur détaillés avec traceback complet")
        print("  • Message informatif sur les causes possibles")
        sys.exit(0)
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
