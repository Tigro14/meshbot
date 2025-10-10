#!/usr/bin/env python3
"""
Diagnostic complet Telegram
Identifie si le bot est blacklisté, rate-limité ou a un problème réseau
"""

import sys
import time
import socket
import subprocess

# Ajouter le chemin du bot
sys.path.insert(0, '/home/dietpi/bot')

from config import TELEGRAM_BOT_TOKEN
from utils import info_print, error_print

def test_dns_resolution():
    """Test 1 : Résolution DNS"""
    info_print("=" * 80)
    info_print("🧪 TEST 1 : RÉSOLUTION DNS")
    info_print("=" * 80)
    
    try:
        info_print("Résolution de api.telegram.org...")
        start = time.time()
        ips = socket.getaddrinfo('api.telegram.org', 443, socket.AF_INET)
        elapsed = time.time() - start
        
        resolved_ips = [ip[4][0] for ip in ips]
        info_print(f"✅ DNS OK ({elapsed:.3f}s)")
        info_print(f"   IPs résolues: {', '.join(set(resolved_ips))}")
        return True, resolved_ips[0] if resolved_ips else None
        
    except Exception as e:
        error_print(f"❌ DNS échoué: {e}")
        return False, None

def test_tcp_connection(ip_address):
    """Test 2 : Connexion TCP brute"""
    info_print("\n" + "=" * 80)
    info_print("🧪 TEST 2 : CONNEXION TCP")
    info_print("=" * 80)
    
    try:
        info_print(f"Connexion TCP vers {ip_address}:443...")
        start = time.time()
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        
        result = sock.connect_ex((ip_address, 443))
        elapsed = time.time() - start
        sock.close()
        
        if result == 0:
            info_print(f"✅ TCP OK ({elapsed:.3f}s)")
            return True
        else:
            error_print(f"❌ TCP échoué (code {result})")
            return False
            
    except Exception as e:
        error_print(f"❌ Erreur TCP: {e}")
        return False

def test_https_handshake():
    """Test 3 : Handshake HTTPS/TLS"""
    info_print("\n" + "=" * 80)
    info_print("🧪 TEST 3 : HANDSHAKE HTTPS/TLS")
    info_print("=" * 80)
    
    try:
        import ssl
        
        info_print("Handshake TLS avec api.telegram.org:443...")
        start = time.time()
        
        context = ssl.create_default_context()
        with socket.create_connection(("api.telegram.org", 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname="api.telegram.org") as ssock:
                elapsed = time.time() - start
                cert = ssock.getpeercert()
                
                info_print(f"✅ TLS OK ({elapsed:.3f}s)")
                info_print(f"   Subject: {dict(x[0] for x in cert['subject'])}")
                info_print(f"   Issuer: {dict(x[0] for x in cert['issuer'])['commonName']}")
                return True
                
    except Exception as e:
        error_print(f"❌ TLS échoué: {e}")
        return False

def test_telegram_api_simple():
    """Test 4 : API Telegram simple (getMe)"""
    info_print("\n" + "=" * 80)
    info_print("🧪 TEST 4 : API TELEGRAM (getMe)")
    info_print("=" * 80)
    
    try:
        import httpx
        
        info_print("Appel API getMe...")
        start = time.time()
        
        client = httpx.Client(timeout=30.0)
        try:
            response = client.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
            )
            elapsed = time.time() - start
            
            info_print(f"⏱️  Temps de réponse: {elapsed:.3f}s")
            info_print(f"📊 Status HTTP: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    bot = data['result']
                    info_print(f"✅ API OK")
                    info_print(f"   Bot: @{bot.get('username')}")
                    info_print(f"   ID: {bot.get('id')}")
                    info_print(f"   Nom: {bot.get('first_name')}")
                    return True, None
                else:
                    error_print(f"❌ API retourne ok=false: {data.get('description')}")
                    return False, data.get('description')
            
            elif response.status_code == 401:
                error_print("❌ TOKEN INVALIDE (401 Unauthorized)")
                return False, "Token invalide"
            
            elif response.status_code == 403:
                error_print("❌ BOT BANNI (403 Forbidden)")
                return False, "Bot banni"
            
            elif response.status_code == 429:
                error_print("❌ RATE LIMITED (429 Too Many Requests)")
                retry_after = response.headers.get('Retry-After', 'inconnu')
                error_print(f"   Réessayer dans: {retry_after}s")
                return False, f"Rate limited ({retry_after}s)"
            
            else:
                error_print(f"❌ HTTP {response.status_code}")
                error_print(f"   Body: {response.text[:200]}")
                return False, f"HTTP {response.status_code}"
                
        finally:
            client.close()
            
    except httpx.TimeoutException as e:
        error_print(f"❌ TIMEOUT après 30s")
        return False, "Timeout"
    except Exception as e:
        error_print(f"❌ Erreur: {e}")
        return False, str(e)

def test_telegram_api_updates():
    """Test 5 : API getUpdates (utilisée par polling)"""
    info_print("\n" + "=" * 80)
    info_print("🧪 TEST 5 : API TELEGRAM (getUpdates)")
    info_print("=" * 80)
    
    try:
        import httpx
        
        info_print("Appel API getUpdates...")
        start = time.time()
        
        client = httpx.Client(timeout=35.0)
        try:
            response = client.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                params={'timeout': 30, 'limit': 1}
            )
            elapsed = time.time() - start
            
            info_print(f"⏱️  Temps de réponse: {elapsed:.3f}s")
            info_print(f"📊 Status HTTP: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    updates = data.get('result', [])
                    info_print(f"✅ getUpdates OK")
                    info_print(f"   Updates: {len(updates)}")
                    return True, None
                else:
                    error_print(f"❌ ok=false: {data.get('description')}")
                    return False, data.get('description')
            
            elif response.status_code == 429:
                error_print("❌ RATE LIMITED sur getUpdates")
                retry_after = response.headers.get('Retry-After', 'inconnu')
                return False, f"Rate limited ({retry_after}s)"
            
            else:
                error_print(f"❌ HTTP {response.status_code}")
                return False, f"HTTP {response.status_code}"
                
        finally:
            client.close()
            
    except httpx.TimeoutException:
        error_print(f"❌ TIMEOUT après 35s")
        return False, "Timeout"
    except Exception as e:
        error_print(f"❌ Erreur: {e}")
        return False, str(e)

def test_network_quality():
    """Test 6 : Qualité réseau"""
    info_print("\n" + "=" * 80)
    info_print("🧪 TEST 6 : QUALITÉ RÉSEAU")
    info_print("=" * 80)
    
    try:
        info_print("Ping vers api.telegram.org (10 paquets)...")
        result = subprocess.run(
            ['ping', '-c', '10', 'api.telegram.org'],
            capture_output=True, text=True, timeout=15
        )
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            
            # Extraire stats
            for line in lines:
                if 'packet loss' in line:
                    info_print(f"📊 {line.strip()}")
                if 'rtt min/avg/max' in line or 'round-trip' in line:
                    info_print(f"📊 {line.strip()}")
            
            # Analyser
            if '0% packet loss' in result.stdout:
                info_print("✅ Réseau stable")
                return True
            elif '100% packet loss' in result.stdout:
                error_print("❌ Réseau complètement bloqué")
                return False
            else:
                error_print("⚠️  Perte de paquets détectée")
                return False
        else:
            error_print("❌ Ping échoué")
            return False
            
    except Exception as e:
        error_print(f"❌ Erreur ping: {e}")
        return False

def check_firewall():
    """Test 7 : Vérifier firewall local"""
    info_print("\n" + "=" * 80)
    info_print("🧪 TEST 7 : FIREWALL LOCAL")
    info_print("=" * 80)
    
    try:
        # Vérifier iptables
        result = subprocess.run(['iptables', '-L', '-n'], 
                              capture_output=True, text=True, timeout=5)
        
        if 'DROP' in result.stdout or 'REJECT' in result.stdout:
            error_print("⚠️  Règles de firewall détectées")
            info_print("   Vérifier avec: sudo iptables -L -n -v")
        else:
            info_print("✅ Pas de règles DROP/REJECT évidentes")
        
        return True
        
    except Exception as e:
        info_print(f"ℹ️  Impossible de vérifier iptables: {e}")
        return True

def main():
    """Diagnostic complet"""
    info_print("🔬 DIAGNOSTIC COMPLET TELEGRAM")
    info_print("=" * 80)
    
    results = {}
    
    # Test 1 : DNS
    dns_ok, ip_address = test_dns_resolution()
    results['dns'] = dns_ok
    
    if not dns_ok:
        error_print("\n🔴 ARRÊT : DNS échoué")
        return 1
    
    # Test 2 : TCP
    results['tcp'] = test_tcp_connection(ip_address)
    
    # Test 3 : TLS
    results['tls'] = test_https_handshake()
    
    # Test 4 : API simple
    api_ok, api_error = test_telegram_api_simple()
    results['api_simple'] = api_ok
    
    if not api_ok and api_error:
        if 'banni' in api_error.lower() or '403' in api_error:
            error_print("\n🔴 CONFIRMATION : BOT BANNI PAR TELEGRAM")
            info_print("\n💡 Actions à faire:")
            info_print("   1. Contacter @BotSupport sur Telegram")
            info_print("   2. Vérifier les logs du bot pour abus")
            info_print("   3. Créer un nouveau bot si nécessaire")
            return 1
        
        if 'rate limit' in api_error.lower() or '429' in api_error:
            error_print("\n⚠️  CONFIRMATION : RATE LIMITED")
            info_print("\n💡 Actions à faire:")
            info_print("   1. Attendre quelques heures")
            info_print("   2. Réduire poll_interval à 60s")
            info_print("   3. Vérifier les logs pour boucles infinies")
            return 1
    
    # Test 5 : getUpdates
    if api_ok:
        results['api_updates'] = test_telegram_api_updates()[0]
    
    # Test 6 : Réseau
    results['network'] = test_network_quality()
    
    # Test 7 : Firewall
    results['firewall'] = check_firewall()
    
    # Résumé
    info_print("\n" + "=" * 80)
    info_print("📊 RÉSUMÉ DIAGNOSTIC")
    info_print("=" * 80)
    
    for test, success in results.items():
        status = "✅" if success else "❌"
        info_print(f"{status} {test.upper()}")
    
    # Verdict
    info_print("\n" + "=" * 80)
    info_print("🎯 VERDICT")
    info_print("=" * 80)
    
    if all(results.values()):
        info_print("✅ Tous les tests passent")
        info_print("   Le problème vient probablement de:")
        info_print("   - Timeouts trop courts dans le code")
        info_print("   - Connexion lente (augmenter à 120s)")
    
    elif results.get('dns') and results.get('tcp') and results.get('tls'):
        if not results.get('api_simple'):
            error_print("🔴 Problème API Telegram")
            info_print("   → Bot banni, token invalide ou rate limited")
        elif not results.get('api_updates'):
            error_print("🔴 Problème getUpdates spécifiquement")
            info_print("   → Polling trop agressif détecté par Telegram")
    
    elif not results.get('network'):
        error_print("🔴 Problème réseau")
        info_print("   → Perte de paquets, latence élevée")
        info_print("   → Vérifier routeur/FAI")
    
    else:
        error_print("🔴 Problème réseau de base")
        info_print("   → DNS, TCP ou TLS échoue")
        info_print("   → Firewall ou configuration réseau")
    
    return 0 if all(results.values()) else 1

if __name__ == "__main__":
    sys.exit(main())
