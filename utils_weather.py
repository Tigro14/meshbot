#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module météo partagé entre Meshtastic et Telegram

Ce module centralise la logique de récupération de la météo avec cache
pour éviter la duplication de code entre utility_commands.py et telegram_integration.py

Utilisation:
    from utils.weather import get_weather_data
    
    weather = get_weather_data()
    print(weather)  # "Paris: ☁️  +12°C"

Cache:
    - Fichier: /tmp/weather_cache.json
    - Durée: 5 minutes (300 secondes)
    - Partagé entre toutes les sources (Meshtastic, Telegram, etc.)
"""

import subprocess
import os
import json
import time
from utils import info_print, error_print

# Configuration
CACHE_FILE = "/tmp/weather_cache.json"
CACHE_DURATION = 300  # 5 minutes en secondes
WTTR_URL = "https://wttr.in/Paris?format=4"
CURL_TIMEOUT = 10  # secondes


def get_weather_data():
    """
    Récupérer les données météo avec système de cache
    
    Le cache est vérifié en premier. S'il est valide (< 5 minutes),
    les données sont retournées immédiatement sans appel réseau.
    
    Sinon, un appel curl est fait vers wttr.in et le cache est mis à jour.
    
    Returns:
        str: Données météo formatées (ex: "Paris: ☁️  +12°C")
             ou message d'erreur si échec
    
    Exemples:
        >>> weather = get_weather_data()
        >>> print(weather)
        "Paris: ☁️  +12°C"
        
        >>> # Appel immédiat suivant (< 5 min)
        >>> weather = get_weather_data()  # Utilise le cache
        >>> print(weather)
        "Paris: ☁️  +12°C"
    """
    try:
        # ----------------------------------------------------------------
        # Phase 1: Vérifier le cache
        # ----------------------------------------------------------------
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                cache_time = cache_data.get('timestamp', 0)
                current_time = time.time()
                age_seconds = int(current_time - cache_time)
                
                # Cache encore valide ?
                if age_seconds < CACHE_DURATION:
                    weather_data = cache_data.get('data', '')
                    info_print(f"✅ Cache météo utilisé (age: {age_seconds}s / {CACHE_DURATION}s)")
                    return weather_data
                else:
                    info_print(f"⏰ Cache expiré (age: {age_seconds}s > {CACHE_DURATION}s)")
            
            except (json.JSONDecodeError, IOError) as e:
                error_print(f"⚠️ Erreur lecture cache: {e}")
                # Continuer vers l'appel curl
        
        # ----------------------------------------------------------------
        # Phase 2: Appel curl vers wttr.in
        # ----------------------------------------------------------------
        info_print(f"🌤️ Récupération météo depuis {WTTR_URL}...")
        
        result = subprocess.run(
            ['curl', '-s', WTTR_URL],
            capture_output=True,
            text=True,
            timeout=CURL_TIMEOUT
        )
        
        # ----------------------------------------------------------------
        # Phase 3: Traiter la réponse
        # ----------------------------------------------------------------
        if result.returncode == 0 and result.stdout:
            weather_data = result.stdout.strip()
            
            # Validation basique de la réponse
            if not weather_data or len(weather_data) > 200:
                error_print(f"⚠️ Réponse wttr.in invalide (longueur: {len(weather_data)})")
                return "❌ Réponse météo invalide"
            
            # Sauvegarder en cache
            cache_data = {
                'timestamp': time.time(),
                'data': weather_data,
                'source': 'wttr.in',
                'url': WTTR_URL
            }
            
            try:
                with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, indent=2)
                info_print(f"✅ Cache météo créé/mis à jour")
            except IOError as e:
                error_print(f"⚠️ Impossible d'écrire le cache: {e}")
                # Pas grave, on retourne quand même les données
            
            info_print(f"✅ Météo récupérée: {weather_data}")
            return weather_data
        
        else:
            error_msg = "❌ Erreur récupération météo"
            error_print(f"{error_msg} (curl returncode: {result.returncode})")
            
            if result.stderr:
                error_print(f"   stderr: {result.stderr[:200]}")
            
            return error_msg
    
    except subprocess.TimeoutExpired:
        error_msg = f"❌ Timeout météo (> {CURL_TIMEOUT}s)"
        error_print(error_msg)
        return error_msg
    
    except FileNotFoundError:
        error_msg = "❌ Commande curl non trouvée"
        error_print(error_msg)
        return error_msg
    
    except Exception as e:
        error_print(f"❌ Erreur inattendue dans get_weather_data: {e}")
        import traceback
        error_print(traceback.format_exc())
        return f"❌ Erreur: {str(e)[:50]}"


def get_cache_info():
    """
    Obtenir des informations sur l'état du cache
    
    Returns:
        dict: Informations sur le cache ou None si pas de cache
        {
            'exists': bool,
            'age_seconds': int,
            'is_valid': bool,
            'data': str,
            'timestamp': float
        }
    
    Exemple:
        >>> info = get_cache_info()
        >>> if info and info['is_valid']:
        ...     print(f"Cache valide depuis {info['age_seconds']}s")
    """
    try:
        if not os.path.exists(CACHE_FILE):
            return {
                'exists': False,
                'age_seconds': None,
                'is_valid': False,
                'data': None,
                'timestamp': None
            }
        
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        cache_time = cache_data.get('timestamp', 0)
        current_time = time.time()
        age_seconds = int(current_time - cache_time)
        is_valid = age_seconds < CACHE_DURATION
        
        return {
            'exists': True,
            'age_seconds': age_seconds,
            'is_valid': is_valid,
            'data': cache_data.get('data', ''),
            'timestamp': cache_time,
            'max_age': CACHE_DURATION
        }
    
    except Exception as e:
        error_print(f"Erreur get_cache_info: {e}")
        return None


def clear_cache():
    """
    Effacer le cache météo
    
    Utile pour forcer une nouvelle récupération ou pour le nettoyage.
    
    Returns:
        bool: True si le cache a été effacé, False sinon
    
    Exemple:
        >>> clear_cache()
        >>> weather = get_weather_data()  # Forcera un appel curl
    """
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            info_print(f"🗑️ Cache météo effacé: {CACHE_FILE}")
            return True
        else:
            info_print(f"ℹ️ Pas de cache à effacer")
            return False
    except Exception as e:
        error_print(f"Erreur clear_cache: {e}")
        return False


def get_weather_for_city(city="Paris"):
    """
    Récupérer la météo pour une ville spécifique
    
    Note: Cette fonction ne supporte pas le cache pour l'instant.
    Chaque appel fait une requête à wttr.in.
    
    Args:
        city (str): Nom de la ville
    
    Returns:
        str: Données météo formatées ou message d'erreur
    
    Exemple:
        >>> weather = get_weather_for_city("Lyon")
        >>> print(weather)
        "Lyon: ☀️  +15°C"
    """
    try:
        url = f"https://wttr.in/{city}?format=4"
        info_print(f"🌤️ Récupération météo pour {city}...")
        
        result = subprocess.run(
            ['curl', '-s', url],
            capture_output=True,
            text=True,
            timeout=CURL_TIMEOUT
        )
        
        if result.returncode == 0 and result.stdout:
            weather_data = result.stdout.strip()
            info_print(f"✅ Météo {city}: {weather_data}")
            return weather_data
        else:
            return f"❌ Erreur météo {city}"
    
    except subprocess.TimeoutExpired:
        return f"❌ Timeout météo {city}"
    
    except Exception as e:
        error_print(f"Erreur get_weather_for_city({city}): {e}")
        return f"❌ Erreur: {str(e)[:50]}"


# ============================================================================
# TESTS (si exécuté directement)
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Tests du module weather")
    print("=" * 60)
    
    # Test 1: Récupération simple
    print("\nTest 1: Récupération météo")
    weather = get_weather_data()
    print(f"Résultat: {weather}")
    
    # Test 2: Info cache
    print("\nTest 2: Info cache")
    cache_info = get_cache_info()
    if cache_info:
        print(f"Cache existe: {cache_info['exists']}")
        print(f"Cache valide: {cache_info['is_valid']}")
        if cache_info['exists']:
            print(f"Âge: {cache_info['age_seconds']}s")
            print(f"Données: {cache_info['data']}")
    
    # Test 3: Utilisation cache
    print("\nTest 3: Deuxième appel (devrait utiliser cache)")
    weather2 = get_weather_data()
    print(f"Résultat: {weather2}")
    
    # Test 4: Ville spécifique
    print("\nTest 4: Météo Lyon (sans cache)")
    lyon_weather = get_weather_for_city("Lyon")
    print(f"Résultat: {lyon_weather}")
    
    # Test 5: Nettoyage
    print("\nTest 5: Nettoyage cache")
    cleared = clear_cache()
    print(f"Cache effacé: {cleared}")
    
    print("\n" + "=" * 60)
    print("✅ Tests terminés")
    print("=" * 60)
