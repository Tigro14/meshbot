#!/usr/bin/env python3
"""
Debug de la connexion ESPHome
"""

import asyncio
import aioesphomeapi
import socket
import base64

# Configuration
ESPHOME_HOST = "192.168.1.27"
ESPHOME_PORT = 6053
API_KEY = "9KfuXXxUI+8z26N+dc1X5pFhgnKj6KA1d4matApCVAA="  # Remplacez par votre clé complète

def verify_key_format():
    """Vérifie le format de la clé"""
    print("=" * 60)
    print("VÉRIFICATION FORMAT CLÉ")
    print("=" * 60)
    
    print(f"Clé fournie: {API_KEY[:20]}...")
    print(f"Longueur: {len(API_KEY)} caractères")
    
    # Vérifier si c'est du base64 valide
    try:
        decoded = base64.b64decode(API_KEY)
        print(f"✅ Clé base64 valide ({len(decoded)} bytes)")
        
        # ESPHome utilise des clés de 32 bytes
        if len(decoded) == 32:
            print("✅ Longueur correcte (32 bytes)")
        else:
            print(f"⚠️ Longueur inhabituelle: {len(decoded)} bytes (attendu: 32)")
            
    except Exception as e:
        print(f"❌ Clé base64 invalide: {e}")
        
        # Essayer de nettoyer la clé
        clean_key = API_KEY.strip().replace(' ', '').replace('\n', '')
        print(f"Clé nettoyée: {clean_key[:20]}...")
        
        try:
            decoded = base64.b64decode(clean_key)
            print(f"✅ Clé nettoyée valide ({len(decoded)} bytes)")
        except:
            print("❌ Clé toujours invalide après nettoyage")

def test_raw_connection():
    """Test de connexion socket brute"""
    print("\n" + "=" * 60)
    print("TEST CONNEXION SOCKET")
    print("=" * 60)
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        print(f"Connexion à {ESPHOME_HOST}:{ESPHOME_PORT}")
        sock.connect((ESPHOME_HOST, ESPHOME_PORT))
        print("✅ Socket connecté")
        
        # Envoyer un petit message pour voir la réponse
        sock.send(b"hello")
        
        try:
            response = sock.recv(100)
            print(f"Réponse brute: {response}")
        except socket.timeout:
            print("Pas de réponse du serveur")
            
        sock.close()
        
    except Exception as e:
        print(f"❌ Connexion socket échouée: {e}")

async def test_connection_variants():
    """Test différentes variantes de connexion"""
    print("\n" + "=" * 60)
    print("TEST VARIANTES DE CONNEXION")
    print("=" * 60)
    
    variants = [
        {"password": API_KEY, "encryption_key": None},
        {"password": None, "encryption_key": API_KEY},
        {"password": "", "encryption_key": API_KEY}
    ]
    
    for i, variant in enumerate(variants, 1):
        print(f"\nVariante {i}: {variant}")
        
        try:
            if variant["encryption_key"]:
                api = aioesphomeapi.APIClient(ESPHOME_HOST, ESPHOME_PORT, 
                                            password=variant["password"], 
                                            encryption_key=variant["encryption_key"])
            else:
                api = aioesphomeapi.APIClient(ESPHOME_HOST, ESPHOME_PORT, 
                                            password=variant["password"])
            
            await api.connect(login=True)
            print("✅ Connexion réussie !")
            
            device_info = await api.device_info()
            print(f"Device: {device_info.name}")
            
            await api.disconnect()
            return True
            
        except Exception as e:
            print(f"❌ Échec: {e}")
    
    return False

async def test_without_encryption():
    """Test sans chiffrement (pour vérifier la connectivité)"""
    print("\n" + "=" * 60)
    print("TEST SANS CHIFFREMENT")
    print("=" * 60)
    
    try:
        # Connexion sans clé de chiffrement
        api = aioesphomeapi.APIClient(ESPHOME_HOST, ESPHOME_PORT, password="")
        
        print("Tentative de connexion sans chiffrement...")
        await api.connect(login=False)
        
        print("✅ Connexion de base réussie")
        
        # Essayer d'obtenir des infos basiques
        device_info = await api.device_info()
        print(f"Device accessible: {device_info.name}")
        
        await api.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ Même sans chiffrement: {e}")
        return False

def suggest_solutions():
    """Suggère des solutions"""
    print("\n" + "=" * 60)
    print("SUGGESTIONS DE SOLUTIONS")
    print("=" * 60)
    
    print("1. FORMAT DE CLÉ:")
    print("   - Vérifiez que votre clé n'a pas d'espaces ou de retours à la ligne")
    print("   - Elle doit finir par '=' généralement")
    print("   - Longueur typique: 44 caractères")
    
    print("\n2. VERSION D'ESPHome:")
    print("   - Les versions récentes ont changé le protocole")
    print("   - Essayez: pip install --upgrade aioesphomeapi")
    
    print("\n3. CONFIGURATION ESPHome:")
    print("   - Vérifiez que l'API est bien activée")
    print("   - Port 6053 doit être ouvert")
    print("   - Pas de firewall qui bloque")
    
    print("\n4. ALTERNATIVE SIMPLE:")
    print("   - Utilisez Home Assistant comme intermédiaire")
    print("   - Ou créez un endpoint HTTP simple dans ESPHome")

async def main():
    print("DEBUG CONNEXION ESPHome")
    print(f"Host: {ESPHOME_HOST}:{ESPHOME_PORT}")
    
    # Vérifications de base
    verify_key_format()
    test_raw_connection()
    
    # Tests de connexion API
    success = await test_connection_variants()
    
    if not success:
        # Test sans chiffrement
        basic_success = await test_without_encryption()
        
        if basic_success:
            print("\n💡 L'ESPHome est accessible mais la clé de chiffrement pose problème")
        else:
            print("\n💡 Problème de connectivité de base")
    
    # Suggestions
    suggest_solutions()

if __name__ == "__main__":
    asyncio.run(main())
