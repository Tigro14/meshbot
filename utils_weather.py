#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module météo partagé entre Meshtastic et Telegram

Ce module centralise la logique de récupération de la météo avec cache
pour éviter la duplication de code entre utility_commands.py et telegram_integration.py

Version améliorée avec prévisions à 3 jours au format JSON.

Utilisation:
    from utils.weather import get_weather_data
    
    weather = get_weather_data()
    print(weather)

Cache:
    - Fichier: /tmp/weather_cache.json
    - Durée: 5 minutes (300 secondes)
    - Partagé entre toutes les sources (Meshtastic, Telegram, etc.)
"""

import subprocess
import os
import json
import time
from utils import info_print, error_print, debug_print

# Configuration
CACHE_DIR = "/tmp"
CACHE_DURATION = 300  # 5 minutes en secondes (fresh cache)
CACHE_STALE_DURATION = 3600  # 1 heure (stale-while-revalidate window)
CACHE_MAX_AGE = 86400  # 24 heures = durée max pour servir cache périmé en cas d'erreur

# Cache spécifique pour le graphe de pluie (durée plus longue car wttr.in ne répond pas correctement)
RAIN_CACHE_DURATION = 3600  # 1 heure (fresh cache)
RAIN_CACHE_STALE_DURATION = 3600  # 1 heure - servir le cache dans cette fenêtre sans refresh
WTTR_BASE_URL = "https://wttr.in"
DEFAULT_LOCATION = ""  # Vide = géolocalisation par IP
CURL_TIMEOUT = 25  # secondes (increased from 10s for better reliability on slow networks)
CURL_MAX_RETRIES = 3  # Number of retry attempts for failed curl requests
CURL_RETRY_DELAY = 2  # Initial delay between retries in seconds (exponential backoff)

# Mapping codes météo wttr.in → émojis
WEATHER_EMOJI = {
    '113': '☀️',   # Sunny/Clear
    '116': '⛅',   # Partly cloudy
    '119': '☁️',   # Cloudy
    '122': '☁️',   # Overcast
    '143': '🌫️',  # Mist
    '176': '🌦️',  # Patchy rain possible
    '179': '🌨️',  # Patchy snow possible
    '182': '🌧️',  # Patchy sleet possible
    '185': '🌧️',  # Patchy freezing drizzle
    '200': '⛈️',  # Thundery outbreaks
    '227': '🌨️',  # Blowing snow
    '230': '❄️',   # Blizzard
    '248': '🌫️',  # Fog
    '260': '🌫️',  # Freezing fog
    '263': '🌧️',  # Patchy light drizzle
    '266': '🌧️',  # Light drizzle
    '281': '🌧️',  # Freezing drizzle
    '284': '🌧️',  # Heavy freezing drizzle
    '293': '🌦️',  # Patchy light rain
    '296': '🌧️',  # Light rain
    '299': '🌧️',  # Moderate rain at times
    '302': '🌧️',  # Moderate rain
    '305': '🌧️',  # Heavy rain at times
    '308': '🌧️',  # Heavy rain
    '311': '🌧️',  # Light freezing rain
    '314': '🌧️',  # Moderate or heavy freezing rain
    '317': '🌨️',  # Light sleet
    '320': '🌨️',  # Moderate or heavy sleet
    '323': '🌨️',  # Patchy light snow
    '326': '🌨️',  # Light snow
    '329': '🌨️',  # Patchy moderate snow
    '332': '❄️',   # Moderate snow
    '335': '❄️',   # Patchy heavy snow
    '338': '❄️',   # Heavy snow
    '350': '🌧️',  # Ice pellets
    '353': '🌦️',  # Light rain shower
    '356': '🌧️',  # Moderate or heavy rain shower
    '359': '🌧️',  # Torrential rain shower
    '362': '🌨️',  # Light sleet showers
    '365': '🌨️',  # Moderate or heavy sleet showers
    '368': '🌨️',  # Light snow showers
    '371': '❄️',   # Moderate or heavy snow showers
    '374': '🌧️',  # Light showers of ice pellets
    '377': '🌧️',  # Moderate or heavy showers of ice pellets
    '386': '⛈️',  # Patchy light rain with thunder
    '389': '⛈️',  # Moderate or heavy rain with thunder
    '392': '⛈️',  # Patchy light snow with thunder
    '395': '⛈️',  # Moderate or heavy snow with thunder
}


def _curl_with_retry(url, timeout=CURL_TIMEOUT, max_retries=CURL_MAX_RETRIES):
    """
    Execute curl with retry logic and exponential backoff
    
    Args:
        url: URL to fetch
        timeout: Timeout in seconds for each attempt
        max_retries: Maximum number of retry attempts
    
    Returns:
        subprocess.CompletedProcess: Result of successful curl command
    
    Raises:
        subprocess.TimeoutExpired: If all retries timeout
        Exception: If all retries fail with errors
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            info_print(f"🌐 Curl attempt {attempt + 1}/{max_retries}: {url[:80]}...")
            result = subprocess.run(
                ['curl', '-s', url],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            # Success
            if result.returncode == 0 and result.stdout:
                if attempt > 0:
                    info_print(f"✅ Curl succeeded on attempt {attempt + 1}")
                return result
            
            # Non-timeout failure - might be worth retrying
            error_print(f"⚠️ Curl attempt {attempt + 1} failed (returncode: {result.returncode})")
            last_exception = Exception(f"Curl failed with returncode {result.returncode}")
            
        except subprocess.TimeoutExpired as e:
            error_print(f"⏱️ Curl attempt {attempt + 1} timeout (>{timeout}s)")
            last_exception = e
            
        except Exception as e:
            error_print(f"❌ Curl attempt {attempt + 1} error: {e}")
            last_exception = e
        
        # Wait before retry (exponential backoff)
        if attempt < max_retries - 1:
            delay = CURL_RETRY_DELAY * (2 ** attempt)  # 2s, 4s, 8s...
            info_print(f"⏳ Waiting {delay}s before retry...")
            time.sleep(delay)
    
    # All retries failed
    if isinstance(last_exception, subprocess.TimeoutExpired):
        raise last_exception
    else:
        raise Exception(f"All {max_retries} curl attempts failed") from last_exception


def get_weather_openmeteo(lat=None, lon=None, persistence=None):
    """
    Récupérer les données météo depuis Open-Meteo API (modèle France HD)
    
    Args:
        lat: Latitude (float). Si None, utilise WEATHER_LATITUDE de config.py
        lon: Longitude (float). Si None, utilise WEATHER_LONGITUDE de config.py
        persistence: Instance TrafficPersistence pour le cache SQLite (optionnel)
    
    Returns:
        str: Données météo formatées ou message d'erreur
    
    Exemple:
        >>> weather = get_weather_openmeteo(48.8566, 2.3522)  # Paris
        >>> print(weather)
        Now: ☀️ 12°C 15km/h 0mm
    """
    import requests
    import json
    from config import WEATHER_LATITUDE, WEATHER_LONGITUDE, WEATHER_MODEL, WEATHER_FORECAST_HOURS
    
    try:
        # Utiliser les coordonnées fournies ou celles de config
        if lat is None or lon is None:
            lat = WEATHER_LATITUDE
            lon = WEATHER_LONGITUDE
        
        # Clé de cache
        cache_key = f"openmeteo_{lat}_{lon}"
        
        # Vérifier le cache SQLite si disponible
        if persistence:
            try:
                cached_data, age_hours = persistence.get_weather_cache_with_age(
                    cache_key, 'weather', max_age_seconds=CACHE_MAX_AGE
                )
                if cached_data:
                    cache_age_seconds = age_hours * 3600
                    
                    # Fresh cache (<5 min)
                    if cache_age_seconds < CACHE_DURATION:
                        info_print(f"✅ Cache OpenMeteo FRESH (age: {cache_age_seconds}s)")
                        return cached_data
                    
                    # Stale but valid (<1h)
                    elif cache_age_seconds < CACHE_STALE_DURATION:
                        info_print(f"⚡ Cache OpenMeteo STALE mais valide (age: {cache_age_seconds}s)")
                        return cached_data
                    
                    else:
                        info_print(f"⏰ Cache OpenMeteo expiré (age: {age_hours}h)")
            except Exception as e:
                error_print(f"⚠️ Erreur lecture cache: {e}")
        
        # Construire l'URL Open-Meteo
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join([
                "temperature_2m",
                "precipitation",
                "precipitation_probability",
                "wind_speed_10m",
                "weather_code",
            ]),
            "timezone": "Europe/Paris",
            "forecast_hours": WEATHER_FORECAST_HOURS,
            "models": WEATHER_MODEL,  # meteofrance_arome_france_hd
        }
        
        info_print(f"🌤️ Récupération météo Open-Meteo ({WEATHER_MODEL})...")
        
        # Requête HTTP avec timeout
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extraire les données actuelles (première heure)
        if 'hourly' in data:
            hourly = data['hourly']
            
            # Température actuelle (°C)
            temp = hourly.get('temperature_2m', [0])[0]
            
            # Vent (km/h)
            wind = hourly.get('wind_speed_10m', [0])[0]
            
            # Précipitation (mm)
            precip = hourly.get('precipitation', [0])[0]
            
            # Code météo
            weather_code = hourly.get('weather_code', [0])[0]
            
            # Emoji basé sur le code météo
            emoji = get_weather_icon(str(weather_code))
            
            # Formater la sortie
            result = f"Now: {emoji} {temp:.0f}°C {wind:.0f}km/h {precip:.1f}mm"
            
            # Sauvegarder en cache si persistence disponible
            if persistence:
                try:
                    persistence.set_weather_cache(cache_key, 'weather', result)
                    info_print(f"💾 Cache OpenMeteo sauvegardé")
                except Exception as e:
                    error_print(f"⚠️ Erreur sauvegarde cache: {e}")
            
            return result
        else:
            error_print("❌ Format de réponse Open-Meteo inattendu")
            return "❌ Erreur format réponse météo"
    
    except requests.exceptions.Timeout:
        error_print("❌ Timeout Open-Meteo")
        return "❌ Timeout météo"
    
    except requests.exceptions.RequestException as e:
        error_print(f"❌ Erreur requête Open-Meteo: {e}")
        return "❌ Erreur récupération météo"
    
    except Exception as e:
        error_print(f"❌ Erreur Open-Meteo: {e}")
        import traceback
        error_print(traceback.format_exc())
        return "❌ Erreur météo"


def get_weather_icon(weather_code):
    """
    Convertir un code météo wttr.in en émoji
    
    Args:
        weather_code (str): Code météo (ex: "113", "296")
    
    Returns:
        str: Émoji correspondant ou ❓ si inconnu
    """
    return WEATHER_EMOJI.get(str(weather_code), '❓')


def format_weather_line(label, emoji, temp, wind, precip, humidity):
    """
    Formater une ligne de météo de manière compacte

    Args:
        label (str): Label de la ligne (Now/Today/Tomorrow/Day+2)
        emoji (str): Émoji météo
        temp (str): Température (ex: "12")
        wind (str): Vitesse vent en km/h (ex: "15")
        precip (str): Précipitations en mm (ex: "0.5")
        humidity (str): Humidité en % (ex: "65")

    Returns:
        str: Ligne formatée compacte (ex: "Now: ☀️ 12°C 15km/h 0mm 65%")
    """
    # Convertir précipitations en format propre (pas de .0 inutiles)
    try:
        precip_float = float(precip)
        precip_str = f"{precip_float:.1f}mm" if precip_float % 1 != 0 else f"{int(precip_float)}mm"
    except (ValueError, TypeError):
        precip_str = f"{precip}mm"

    # Format compact pour /weather normal
    return f"{label}: {emoji} {temp}°C {wind}km/h {precip_str} {humidity}%"


def parse_weather_json(json_data):
    """
    Parser le JSON de wttr.in et formater avec header location + 4 lignes

    Format:
        📍 [City], [Country]
        Now: [emoji] [temp]°C [wind]km/h [precip]mm [humidity]%
        Today: [emoji] [temp]°C [wind]km/h [precip]mm [humidity]%
        Tomorrow: [emoji] [temp]°C [wind]km/h [precip]mm [humidity]%
        Day+2: [emoji] [temp]°C [wind]km/h [precip]mm [humidity]%

    Args:
        json_data (dict): Données JSON de wttr.in

    Returns:
        str: Météo formatée avec location + 4 lignes
    """
    try:
        lines = []

        # ----------------------------------------------------------------
        # Header: Location from nearest_area
        # ----------------------------------------------------------------
        nearest_area = json_data.get('nearest_area', [{}])[0]
        area_name = nearest_area.get('areaName', [{}])[0].get('value', 'Unknown')
        country = nearest_area.get('country', [{}])[0].get('value', '')

        if country and country != area_name:
            location_str = f"📍 {area_name}, {country}"
        else:
            location_str = f"📍 {area_name}"

        lines.append(location_str)

        # ----------------------------------------------------------------
        # Line 2: NOW (current_condition)
        # ----------------------------------------------------------------
        current = json_data.get('current_condition', [{}])[0]
        weather_code = current.get('weatherCode', '113')
        emoji = get_weather_icon(weather_code)
        temp = current.get('temp_C', '?')
        wind = current.get('windspeedKmph', '?')
        precip = current.get('precipMM', '0')
        humidity = current.get('humidity', '?')

        lines.append(format_weather_line('Now', emoji, temp, wind, precip, humidity))

        # ----------------------------------------------------------------
        # Lines 3-5: TODAY, TOMORROW, DAY+2 (weather array)
        # ----------------------------------------------------------------
        weather = json_data.get('weather', [])
        day_labels = ['Today', 'Tomorrow', 'Day+2']
        
        for i, label in enumerate(day_labels):
            if i < len(weather):
                day_data = weather[i]
                hourly = day_data.get('hourly', [{}])[0]  # Premier slot horaire
                
                weather_code = hourly.get('weatherCode', '113')
                emoji = get_weather_icon(weather_code)
                
                # Pour les prévisions, utiliser maxtempC et les données du premier slot horaire
                temp = day_data.get('maxtempC', hourly.get('tempC', '?'))
                wind = hourly.get('windspeedKmph', '?')
                precip = hourly.get('precipMM', '0')
                humidity = hourly.get('humidity', '?')
                
                lines.append(format_weather_line(label, emoji, temp, wind, precip, humidity))
            else:
                lines.append(f"{label}: ❌ Données indisponibles")
        
        return '\n'.join(lines)
    
    except Exception as e:
        error_print(f"Erreur parsing JSON météo: {e}")
        import traceback
        error_print(traceback.format_exc())
        return "❌ Erreur format météo"


def _load_stale_cache(cache_file):
    """
    Charger le cache périmé depuis fichier JSON en cas de défaillance wttr.in

    Args:
        cache_file: Chemin du fichier de cache

    Returns:
        tuple: (data, age_hours) ou (None, 0) si pas de cache
    """
    if not os.path.exists(cache_file):
        return (None, 0)

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)

        cache_time = cache_data.get('timestamp', 0)
        current_time = time.time()
        age_seconds = int(current_time - cache_time)
        age_hours = int(age_seconds / 3600)

        # Ne pas servir un cache trop vieux (> 24h)
        if age_seconds > CACHE_MAX_AGE:
            debug_print(f"⏰ Cache trop vieux ({age_hours}h > 24h), ignoré")
            return (None, 0)

        weather_data = cache_data.get('data', '')
        if weather_data:
            return (weather_data, age_hours)

    except Exception as e:
        error_print(f"⚠️ Erreur lecture cache périmé: {e}")

    return (None, 0)


def _load_stale_cache_sqlite(persistence, cache_key, cache_type):
    """
    Charger le cache périmé depuis SQLite en cas de défaillance wttr.in

    Args:
        persistence: Instance TrafficPersistence
        cache_key: Clé de cache
        cache_type: Type de cache ('rain', 'astro', 'weather')

    Returns:
        tuple: (data, age_hours) ou (None, 0) si pas de cache
    """
    if not persistence:
        return (None, 0)

    try:
        # Utiliser la nouvelle méthode qui retourne l'âge exact
        return persistence.get_weather_cache_with_age(cache_key, cache_type, max_age_seconds=CACHE_MAX_AGE)

    except Exception as e:
        error_print(f"⚠️ Erreur lecture cache SQLite périmé: {e}")

    return (None, 0)


def get_weather_data(location=None, persistence=None):
    """
    Récupérer les données météo avec système de cache (SQLite ou fichier)

    Args:
        location: Ville/lieu pour la météo (ex: "Paris", "London", "New York")
                 Si None ou vide, utilise la géolocalisation par IP
        persistence: Instance TrafficPersistence pour le cache SQLite (optionnel)
                    Si fourni, utilise SQLite; sinon, cache fichier /tmp

    Le cache est vérifié en premier. S'il existe (même périmé), les données
    sont retournées immédiatement ("serve first"). Une tentative de
    rafraîchissement est faite uniquement si le cache est périmé.

    Pattern "serve first, refresh later":
    - Cache < 5 min (FRESH): retourne immédiatement
    - Cache < 1h (STALE): retourne immédiatement (skip refresh pour performance)
    - Cache > 1h: tente de rafraîchir, fallback sur cache périmé si échec
    - Pas de cache: tente de récupérer depuis wttr.in

    Returns:
        str: Données météo formatées sur 4 lignes ou message d'erreur

    Exemples:
        >>> weather = get_weather_data()  # Géolocalisation
        >>> print(weather)
        Now: ☀️ 12°C 15km/h 0mm 65%

        >>> weather = get_weather_data("London", persistence)  # Avec SQLite
        >>> print(weather)
        Now: 🌧️ 8°C 20km/h 2mm 80%
    """
    # Vérifier si on doit utiliser Open-Meteo
    try:
        from config import WEATHER_USE_OPENMETEO
        if WEATHER_USE_OPENMETEO and not location:
            # Pour la géolocalisation (pas de ville spécifiée), utiliser Open-Meteo
            info_print("🌍 Utilisation de Open-Meteo API (France HD)")
            return get_weather_openmeteo(persistence=persistence)
    except ImportError:
        # WEATHER_USE_OPENMETEO non défini, continuer avec wttr.in
        pass
    
    # Variables pour fallback dans les exceptions
    cache_key = None
    cache_file = None

    try:
        # Normaliser la location
        if not location:
            location = DEFAULT_LOCATION

        # Clé de cache pour SQLite
        cache_key = location or 'default'

        # Construire l'URL
        if location:
            # Encoder la ville pour l'URL (espaces → +)
            location_encoded = location.replace(' ', '+')
            wttr_url = f"{WTTR_BASE_URL}/{location_encoded}?format=j1"
            # Nom de cache safe pour fichier (espaces → _)
            location_safe = location.replace(' ', '_').replace('/', '_')
            cache_file = f"{CACHE_DIR}/weather_cache_{location_safe}.json"
        else:
            wttr_url = f"{WTTR_BASE_URL}/?format=j1"
            cache_file = f"{CACHE_DIR}/weather_cache_default.json"

        # ----------------------------------------------------------------
        # Phase 1: Vérifier le cache SQLite ou fichier ("serve first")
        # ----------------------------------------------------------------
        cache_needs_refresh = False
        cached_data = None
        cache_age_seconds = 0

        if persistence:
            # Utiliser le cache SQLite
            try:
                stale_data, age_hours = persistence.get_weather_cache_with_age(
                    cache_key, 'weather', max_age_seconds=CACHE_MAX_AGE
                )
                if stale_data:
                    cached_data = stale_data
                    cache_age_seconds = age_hours * 3600

                    if cache_age_seconds < CACHE_DURATION:
                        info_print(f"✅ Cache SQLite FRESH utilisé (age: {cache_age_seconds}s / {CACHE_DURATION}s)")
                        return cached_data
                    elif cache_age_seconds < CACHE_STALE_DURATION:
                        info_print(f"⚡ Cache SQLite STALE mais valide (age: {cache_age_seconds}s / {CACHE_STALE_DURATION}s)")
                        # Serve first: return immediately
                        return cached_data
                    else:
                        info_print(f"⏰ Cache SQLite expiré (age: {age_hours}h), tentative de rafraîchissement")
                        cache_needs_refresh = True
                else:
                    cache_needs_refresh = True
            except Exception as e:
                error_print(f"⚠️ Erreur lecture cache SQLite: {e}")
                cache_needs_refresh = True
        else:
            # Utiliser le cache fichier (comportement original)
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)

                    cache_time = cache_data.get('timestamp', 0)
                    current_time = time.time()
                    cache_age_seconds = int(current_time - cache_time)
                    cached_data = cache_data.get('data', '')

                    # Fresh cache (<5 min): serve immediately
                    if cache_age_seconds < CACHE_DURATION:
                        info_print(f"✅ Cache fichier FRESH utilisé (age: {cache_age_seconds}s / {CACHE_DURATION}s)")
                        return cached_data

                    # Stale but valid (<1 hour): serve immediately (skip refresh)
                    elif cache_age_seconds < CACHE_STALE_DURATION:
                        info_print(f"⚡ Cache fichier STALE mais valide (age: {cache_age_seconds}s / {CACHE_STALE_DURATION}s)")
                        return cached_data

                    else:
                        info_print(f"⏰ Cache fichier expiré (age: {cache_age_seconds}s > {CACHE_STALE_DURATION}s)")
                        cache_needs_refresh = True

                except (json.JSONDecodeError, IOError) as e:
                    error_print(f"⚠️ Erreur lecture cache fichier: {e}")
                    cache_needs_refresh = True
            else:
                cache_needs_refresh = True

        # ----------------------------------------------------------------
        # Phase 2: Rafraîchissement depuis wttr.in (si nécessaire)
        # ----------------------------------------------------------------
        if not cache_needs_refresh:
            # Fresh cache already returned above
            pass

        info_print(f"🌤️ Récupération météo depuis {wttr_url}...")

        # Appel curl avec retry logic
        try:
            result = _curl_with_retry(wttr_url, timeout=CURL_TIMEOUT)
        except subprocess.TimeoutExpired:
            error_print(f"❌ Timeout météo après {CURL_MAX_RETRIES} tentatives (>{CURL_TIMEOUT}s chacune)")
            # Fallback vers cache périmé si disponible
            if cached_data:
                age_hours = int(cache_age_seconds / 3600)
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache {age_hours}h)\n{cached_data}"
            # Essayer le cache SQLite/fichier périmé
            if persistence:
                stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'weather')
            else:
                stale_data, age_hours = _load_stale_cache(cache_file)
            if stale_data:
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache {age_hours}h)\n{stale_data}"
            return f"❌ Timeout récupération météo ({CURL_MAX_RETRIES} tentatives)"
        except Exception as e:
            error_print(f"❌ Erreur curl après {CURL_MAX_RETRIES} tentatives: {e}")
            # Fallback vers cache périmé
            if cached_data:
                age_hours = int(cache_age_seconds / 3600)
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache {age_hours}h)\n{cached_data}"
            if persistence:
                stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'weather')
            else:
                stale_data, age_hours = _load_stale_cache(cache_file)
            if stale_data:
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache {age_hours}h)\n{stale_data}"
            return "❌ Erreur récupération météo"

        # ----------------------------------------------------------------
        # Phase 3: Traiter la réponse
        # ----------------------------------------------------------------
        if result.returncode == 0 and result.stdout:
            json_response = result.stdout.strip()

            # Parser le JSON
            try:
                weather_json = json.loads(json_response)
                weather_data = parse_weather_json(weather_json)
            except json.JSONDecodeError as e:
                error_print(f"⚠️ JSON invalide: {e}")
                # Fallback sur cache si disponible
                if cached_data:
                    age_hours = int(cache_age_seconds / 3600)
                    return f"⚠️ (cache {age_hours}h)\n{cached_data}"
                return "❌ Réponse météo invalide"

            # Validation basique de la réponse formatée
            if not weather_data or 'Erreur' in weather_data:
                error_print(f"⚠️ Données météo invalides")
                if cached_data:
                    age_hours = int(cache_age_seconds / 3600)
                    return f"⚠️ (cache {age_hours}h)\n{cached_data}"
                return "❌ Données météo invalides"

            # Sauvegarder en cache SQLite ou fichier
            if persistence:
                persistence.set_weather_cache(cache_key, 'weather', weather_data)
            else:
                # Cache fichier (comportement original)
                cache_data = {
                    'timestamp': time.time(),
                    'data': weather_data,
                    'source': 'wttr.in',
                    'url': wttr_url,
                    'location': location or 'auto'
                }

                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(cache_data, f, indent=2)
                    info_print(f"✅ Cache fichier météo créé/mis à jour")
                except IOError as e:
                    error_print(f"⚠️ Impossible d'écrire le cache fichier: {e}")
                    # Pas grave, on retourne quand même les données

            info_print(f"✅ Météo récupérée:\n{weather_data}")
            return weather_data

        else:
            error_msg = "❌ Erreur récupération météo"
            error_print(f"{error_msg} (curl returncode: {result.returncode})")

            if result.stderr:
                error_print(f"   stderr: {result.stderr[:200]}")

            # Fallback: essayer de servir le cache périmé
            if cached_data:
                age_hours = int(cache_age_seconds / 3600)
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache {age_hours}h)\n{cached_data}"

            if persistence:
                stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'weather')
            else:
                stale_data, age_hours = _load_stale_cache(cache_file)
            if stale_data:
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache {age_hours}h)\n{stale_data}"

            return error_msg

    except FileNotFoundError:
        error_msg = "❌ Commande curl non trouvée"
        error_print(error_msg)

        # Fallback: cache périmé
        if persistence:
            stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'weather')
        elif cache_file:
            stale_data, age_hours = _load_stale_cache(cache_file)
        else:
            stale_data, age_hours = None, 0
        if stale_data:
            error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
            return f"⚠️ (cache {age_hours}h)\n{stale_data}"

        return error_msg

    except Exception as e:
        error_print(f"❌ Erreur inattendue dans get_weather_data: {e}")
        import traceback
        error_print(traceback.format_exc())

        # Fallback: cache périmé
        if persistence:
            stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'weather')
        elif cache_file:
            stale_data, age_hours = _load_stale_cache(cache_file)
        else:
            stale_data, age_hours = None, 0
        if stale_data:
            error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
            return f"⚠️ (cache {age_hours}h)\n{stale_data}"

        return f"❌ Erreur: {str(e)[:50]}"


def _format_single_day_graph(truncated_lines, location_name, date_label, max_str, start_offset, truncate_width, compact_mode, ultra_compact=False, split_mode=False):
    """
    Formater le graphe pour un seul jour

    Args:
        truncated_lines: Lignes du graphe déjà tronquées
        location_name: Nom de la ville
        date_label: Label de date (ex: "aujourd'hui 17/11")
        max_str: Valeur max de précipitations (ex: "1.7mm")
        start_offset: Offset de départ dans le graphe source
        truncate_width: Largeur du graphe tronqué
        compact_mode: Si True, seulement 3 lignes
        ultra_compact: Si True, format minimal pour LoRa (<180 chars)
                      - Seulement 2 lignes de graphe
                      - Header court
                      - Échelle horaire minimale
        split_mode: Si True, retourne tuple (part1_sparkline, part2_info)
                   Sinon retourne string unique (backward compat)

    Returns:
        str ou tuple: 
            - Si split_mode=False: String unique (backward compat)
            - Si split_mode=True: (part1_graph, part2_header)
                * part1_graph: 2 lignes sparkline + échelle horaire (graphe complet)
                * part2_header: Info locale seulement (location/date/max)
    """
    # Sélection des lignes de graphe
    # En mode split: toujours 2 lignes (top + bottom) pour économiser de l'espace
    # En mode non-split: utiliser la logique originale
    if split_mode:
        # Mode split: 2 lignes sparkline (top + bottom) pour économiser espace
        sparkline_lines = []
        if len(truncated_lines) >= 5:
            sparkline_lines.append(truncated_lines[0].rstrip())  # Top
            sparkline_lines.append(truncated_lines[4].rstrip())  # Bottom
        sparkline_str = "\n".join(sparkline_lines)
        
        # Créer l'échelle horaire (toujours standard en mode split)
        hour_scale = []
        for i in range(truncate_width):
            actual_position = start_offset + i
            hour = (actual_position // 2) % 24
            point_in_hour = actual_position % 2
            if point_in_hour == 0 and hour % 3 == 0:
                hour_scale.append(str(hour))
            else:
                hour_scale.append(' ')
        hour_scale_str = ''.join(hour_scale).rstrip()
        
        # Partie 1: Graphe complet (sparkline + échelle)
        part1_graph = f"{sparkline_str}\n{hour_scale_str}"
        
        # Partie 2: Header seulement (location/date/max)
        part2_header = f"🌧️ {location_name} {date_label} (max:{max_str})"
        
        return (part1_graph, part2_header)
    
    else:
        # Mode non-split: logique originale pour backward compat
        sparkline_lines = []
        
        if ultra_compact and len(truncated_lines) >= 5:
            # Ultra compact: seulement 2 lignes (top + bottom)
            sparkline_lines.append(truncated_lines[0].rstrip())  # Top
            sparkline_lines.append(truncated_lines[4].rstrip())  # Bottom
        elif compact_mode and len(truncated_lines) >= 5:
            # Mode compact: 3 lignes (top, middle, bottom)
            sparkline_lines.append(truncated_lines[0].rstrip())  # Top
            sparkline_lines.append(truncated_lines[2].rstrip())  # Middle
            sparkline_lines.append(truncated_lines[4].rstrip())  # Bottom
        else:
            # Mode normal: toutes les 5 lignes
            for line in truncated_lines:
                sparkline_lines.append(line)

        part1_sparkline = "\n".join(sparkline_lines)

        # Échelle horaire + header info
        info_lines = []
        
        if ultra_compact:
            # Ultra compact: échelle simplifiée toutes les 6h
            hour_scale = []
            for i in range(truncate_width):
                actual_position = start_offset + i
                hour = (actual_position // 2) % 24
                point_in_hour = actual_position % 2
                if point_in_hour == 0 and hour % 6 == 0:
                    hour_scale.append(str(hour))
                else:
                    hour_scale.append(' ')
            info_lines.append(''.join(hour_scale).rstrip())
        else:
            # Standard: marqueurs toutes les 3h
            hour_scale = []
            for i in range(truncate_width):
                actual_position = start_offset + i
                hour = (actual_position // 2) % 24
                point_in_hour = actual_position % 2
                if point_in_hour == 0 and hour % 3 == 0:
                    hour_scale.append(str(hour))
                else:
                    hour_scale.append(' ')
            info_lines.append(''.join(hour_scale).rstrip())

        # Header
        if ultra_compact:
            date_only = date_label.split()[-1] if date_label else ""
            info_lines.append(f"🌧 {location_name} {date_only} (max:{max_str})")
        else:
            info_lines.append(f"🌧️ {location_name} {date_label} (max:{max_str})")

        part2_info = "\n".join(info_lines)
        
        return f"{part1_sparkline}\n{part2_info}"


def get_rain_graph(location=None, days=1, max_hours=38, compact_mode=False, persistence=None, start_at_current_time=False, ultra_compact=False, split_messages=False):
    """
    Récupérer le graphe ASCII des précipitations (compact sparkline)

    Args:
        location: Ville/lieu pour la météo (ex: "Paris", "London")
                 Si None ou vide, utilise la géolocalisation par IP
        days: Nombre de jours à afficher (1, 2 ou 3)
              1 = aujourd'hui seulement (défaut) - depuis l'heure actuelle
              2 = aujourd'hui + demain - 2 graphes séparés
              3 = aujourd'hui + demain + J+2 - 3 graphes séparés
        max_hours: Nombre d'heures maximum à afficher par jour (défaut 38)
                   15 = Ultra compact for LoRa (<180 chars with ultra_compact=True)
                   22 = Mesh compact (44 chars, 3 lines, ~207 chars total)
                   38 = Telegram/CLI (76 chars, 5 lines, ~450 chars total)
        compact_mode: Si True, affiche 3 lignes au lieu de 5 (Mesh LoRa limit)
        persistence: Instance TrafficPersistence pour le cache SQLite (optionnel)
        start_at_current_time: Si True, démarre le graphe à l'heure actuelle au lieu de minuit
                              (utile pour Mesh: affiche les prochaines heures au lieu du passé)
        ultra_compact: Si True, format minimal pour LoRa (<180 chars)
                      - Seulement 2 lignes de graphe au lieu de 3
                      - Header court sans nom de ville
                      - Échelle horaire simplifiée (toutes les 6h)
                      Recommandé: max_hours=15 avec ultra_compact=True
        split_messages: Si True, retourne tuple (sparkline, info) pour envoi en 2 messages
                       Si False, retourne string unique (backward compat)

    Returns:
        str ou tuple: 
            - Si split_messages=False: Graphe sparkline compact (str)
            - Si split_messages=True et days=1: tuple (sparkline_str, info_str)
            - Si split_messages=True et days>1: tuple ([sparklines], [infos])
              Pour days > 1: plusieurs graphes séparés

    Exemples:
        >>> rain = get_rain_graph("Paris")  # Aujourd'hui depuis maintenant
        >>> rain = get_rain_graph("Paris", days=2)  # Aujourd'hui + demain (2 graphes)
        >>> rain = get_rain_graph("Paris", days=3)  # Aujourd'hui + demain + J+2 (3 graphes)
        >>> rain = get_rain_graph("Paris", max_hours=22, compact_mode=True)  # Mesh compact
        >>> rain = get_rain_graph("Paris", max_hours=15, ultra_compact=True)  # LoRa ultra compact
        >>> sparkline, info = get_rain_graph("Paris", split_messages=True)  # 2 messages séparés
    """
    # Initialize cache variables at function level for exception handlers
    cache_key = None
    cached_data = None
    cache_age_seconds = 0

    try:
        # Normaliser la location
        if not location:
            location = DEFAULT_LOCATION

        # Clé de cache (inclut tous les paramètres qui affectent le résultat)
        # Note: split_messages n'affecte que le format de sortie, pas le contenu des données,
        #       donc exclu de la clé de cache (le cache stocke toujours le format standard)
        # Note: Inclure l'heure arrondie pour créer des buckets de cache horaires
        #       Ex: requêtes à 7:15, 7:30, 7:45 → cache "hour7"
        #           requête à 8:00 → nouveau cache "hour8"
        #       Cela aligne le cache avec start_at_current_time tout en permettant
        #       la réutilisation durant la même heure
        if start_at_current_time:
            from datetime import datetime
            current_hour = datetime.now().hour
            cache_key = f"{location or 'default'}_{days}_{max_hours}_{compact_mode}_{ultra_compact}_hour{current_hour}"
        else:
            cache_key = f"{location or 'default'}_{days}_{max_hours}_{compact_mode}_{ultra_compact}"

        # ----------------------------------------------------------------
        # "Serve first" pattern: always return cached data if available
        # ----------------------------------------------------------------
        if persistence:
            # Check for any cached data (even stale)
            stale_data, age_hours = persistence.get_weather_cache_with_age(cache_key, 'rain', max_age_seconds=CACHE_MAX_AGE)
            if stale_data:
                cached_data = stale_data
                cache_age_seconds = age_hours * 3600

                # Fresh cache (<5 min): return immediately
                if cache_age_seconds < RAIN_CACHE_DURATION:
                    info_print(f"✅ Cache SQLite rain FRESH (age: {cache_age_seconds}s)")
                    return cached_data

                # Stale but valid (<1 hour): return immediately
                elif cache_age_seconds < RAIN_CACHE_STALE_DURATION:
                    info_print(f"⚡ Cache SQLite rain STALE mais valide (age: {cache_age_seconds}s)")
                    return cached_data

                # Very stale (>1h): try to refresh, fallback to cached
                else:
                    info_print(f"⏰ Cache SQLite rain expiré (age: {age_hours}h), tentative de rafraîchissement")

        # Construire l'URL v2n (narrow format avec graphes ASCII)
        # Ajouter ?T pour désactiver les codes ANSI (couleurs)
        if location:
            location_encoded = location.replace(' ', '+')
            wttr_url = f"https://v2n.wttr.in/{location_encoded}?T"
        else:
            wttr_url = "https://v2n.wttr.in?T"

        info_print(f"🌧️ Récupération graphe pluie depuis {wttr_url}...")

        # Appel curl vers wttr.in v2n avec retry logic
        try:
            result = _curl_with_retry(wttr_url, timeout=CURL_TIMEOUT)

            if result.returncode != 0 or not result.stdout:
                error_msg = "❌ Erreur récupération graphe pluie"
                error_print(f"{error_msg} (curl returncode: {result.returncode})")

                # Fallback: use cached data if available with STALLED indicator
                if cached_data:
                    age_hours = cache_age_seconds / 3600
                    error_print(f"⚠️ Servir cache périmé ({age_hours:.1f}h)")
                    return _add_stale_indicator_to_rain_graph(cached_data, age_hours, split_messages)

                # Fallback: cache SQLite périmé
                stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'rain')
                if stale_data:
                    error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                    return _add_stale_indicator_to_rain_graph(stale_data, age_hours, split_messages)

                return error_msg

        except subprocess.TimeoutExpired:
            error_msg = f"❌ Timeout graphe pluie après {CURL_MAX_RETRIES} tentatives (>{CURL_TIMEOUT}s chacune)"
            error_print(error_msg)

            # Fallback: use cached data if available
            if cached_data:
                age_hours = int(cache_age_seconds / 3600)
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache ~{age_hours}h)\n{cached_data}"

            # Fallback: cache SQLite périmé
            stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'rain')
            if stale_data:
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache ~{age_hours}h)\n{stale_data}"

            return error_msg
        except Exception as e:
            error_msg = f"❌ Erreur curl: {e}"
            error_print(error_msg)

            # Fallback: use cached data if available
            if cached_data:
                age_hours = int(cache_age_seconds / 3600)
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache ~{age_hours}h)\n{cached_data}"

            # Fallback: cache SQLite périmé
            stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'rain')
            if stale_data:
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache ~{age_hours}h)\n{stale_data}"

            return error_msg

        output = result.stdout.strip()

        if not output:
            error_msg = "❌ Graphe pluie vide"
            error_print(error_msg)

            # Fallback: use cached data if available
            if cached_data:
                age_hours = int(cache_age_seconds / 3600)
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache ~{age_hours}h)\n{cached_data}"

            # Fallback: cache SQLite périmé
            stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'rain')
            if stale_data:
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache ~{age_hours}h)\n{stale_data}"

            return error_msg

        # Parser la sortie pour extraire les précipitations
        lines = output.split('\n')

        # DEBUG: Afficher les premières lignes pour voir le format
        debug_print(f"[RAIN DEBUG] Total lines: {len(lines)}")
        for i, line in enumerate(lines[:50]):  # Première 50 lignes
            if 'mm' in line or any(c in line for c in '█▇▆▅▄▃▂▁'):
                debug_print(f"[RAIN DEBUG] Line {i}: {line[:100]}")

        # Chercher la section avec les barres de précipitations (contient █▇▄▃▂▁_)
        rain_chars = []
        max_precip = 0.0
        rain_lines = []

        # Trouver la ligne mm|% et extraire TOUTES les lignes du graphe multi-lignes
        for i, line in enumerate(lines):
            # Ligne avec la valeur max (ex: "0.42mm|100%")
            if 'mm' in line and '|' in line and '%' in line:
                try:
                    # Extraire la valeur max (ex: "0.42mm")
                    mm_part = line.split('mm')[0].strip()
                    max_precip = float(mm_part.split()[-1])
                    debug_print(f"[RAIN DEBUG] Found mm|% at line {i}: {line[:80]}")

                    # Extraire TOUTES les lignes suivantes avec des sparklines
                    # Le graphe wttr.in est multi-lignes (empilé verticalement)
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j]
                        # Si la ligne contient des sparklines et n'est pas vide
                        if any(c in next_line for c in '█▇▆▅▄▃▂▁_'):
                            rain_lines.append(next_line)
                            debug_print(f"[RAIN DEBUG] Rain line {j}: {next_line[:80]}")
                            j += 1
                        # Si ligne vide ou sans sparklines, on arrête
                        elif next_line.strip() in ['', '│']:
                            break
                        else:
                            j += 1
                            # On continue un peu pour voir s'il y a d'autres lignes
                            if j - i > 10:  # Max 10 lignes après mm|%
                                break

                    break
                except Exception as e:
                    debug_print(f"[RAIN DEBUG] Error parsing mm line: {e}")
                    pass

        # Garder directement les 5 lignes originales de wttr.in (meilleur rendu)
        # On prend toutes les lignes du graphe multi-lignes vertical
        if not rain_lines or len(rain_lines) < 5:
            return "❌ Graphe pluie incomplet"

        debug_print(f"[RAIN DEBUG] Found {len(rain_lines)} rain graph lines")

        # Nettoyer les lignes (enlever bordures │ mais GARDER l'indentation)
        cleaned_lines = []
        for line in rain_lines:
            # Enlever les caractères de bordure │ mais GARDER les espaces de début (indentation)
            cleaned = line.replace('│', '').rstrip()  # rstrip() enlève seulement espaces de FIN
            cleaned_lines.append(cleaned)

        # Calculer la largeur selon max_hours (2 points par heure)
        # max_hours=22 → 44 chars (Mesh, compact, "today")
        # max_hours=38 → 76 chars (Telegram/CLI, optimal sans line wrap)
        truncate_width = max_hours * 2

        # Importer datetime pour les calculs de temps
        from datetime import datetime, timedelta
        current_hour = datetime.now().hour
        current_minute = datetime.now().minute
        today = datetime.now()

        # Obtenir le vrai nom de la ville via l'API JSON (une seule fois pour tous les jours)
        location_name = location if location else "local"
        try:
            # Faire un appel pour obtenir le nom de la ville (avec retry logic)
            if location:
                location_encoded = location.replace(' ', '+')
                json_url = f"{WTTR_BASE_URL}/{location_encoded}?format=j1"
            else:
                json_url = f"{WTTR_BASE_URL}/?format=j1"

            # Use retry wrapper with shorter timeout for location name fetch
            json_result = _curl_with_retry(json_url, timeout=10, max_retries=2)

            if json_result.returncode == 0 and json_result.stdout:
                weather_json = json.loads(json_result.stdout.strip())
                nearest_area = weather_json.get('nearest_area', [{}])[0]
                area_name = nearest_area.get('areaName', [{}])[0].get('value', '')
                if area_name:
                    location_name = area_name
        except Exception as e:
            debug_print(f"[RAIN DEBUG] Could not fetch location name: {e}")
            # Garder le nom par défaut

        max_str = f"{max_precip:.1f}mm"

        # Si days > 1, on va générer plusieurs graphes séparés
        if days > 1:
            result_parts = []

            for day_index in range(days):
                # Calculer les paramètres pour chaque jour
                if day_index == 0:
                    # Aujourd'hui: de l'heure actuelle jusqu'à minuit
                    start_offset = current_hour * 2
                    if current_minute >= 30:
                        start_offset += 1
                    # Heures restantes aujourd'hui
                    hours_today = 24 - current_hour
                    day_truncate_width = min(truncate_width, hours_today * 2)
                    date_label = today.strftime("aujourd'hui %d/%m")
                elif day_index == 1:
                    # Demain: 0h-24h (ou moins selon max_hours)
                    start_offset = 24 * 2  # Début de demain
                    day_truncate_width = min(truncate_width, 24 * 2)
                    tomorrow = today + timedelta(days=1)
                    date_label = tomorrow.strftime("demain %d/%m")
                else:  # day_index == 2
                    # J+2: 0h-24h (ou moins selon max_hours)
                    start_offset = 48 * 2  # Début de J+2
                    day_truncate_width = min(truncate_width, 24 * 2)
                    day_after = today + timedelta(days=2)
                    date_label = day_after.strftime("J+2 %d/%m")

                # Extraire les lignes pour ce jour
                day_truncated_lines = []
                for line in cleaned_lines:
                    truncated = line[start_offset:start_offset + day_truncate_width]
                    day_truncated_lines.append(truncated)

                # Générer le graphe pour ce jour
                day_result = _format_single_day_graph(
                    day_truncated_lines,
                    location,
                    date_label,
                    max_str,
                    start_offset,
                    day_truncate_width,
                    compact_mode,
                    ultra_compact,
                    split_mode=split_messages
                )
                
                result_parts.append(day_result)

            # Construire le résultat selon le mode
            if split_messages:
                # Séparer sparklines et infos
                sparklines = [part[0] for part in result_parts]
                infos = [part[1] for part in result_parts]
                
                # Joindre chaque partie
                combined_sparklines = "\n\n".join(sparklines)
                combined_infos = "\n\n".join(infos)
                
                # Construire le format standard pour le cache (combiner chaque tuple en string)
                standard_parts = [f"{sparkline}\n{info}" for sparkline, info in result_parts]
                result = "\n\n".join(standard_parts)
                
                # Sauvegarder en cache SQLite (format standard)
                if persistence:
                    persistence.set_weather_cache(cache_key, 'rain', result)
                
                # Retourner les parties séparées
                return (combined_sparklines, combined_infos)
            else:
                # Joindre les graphes avec double saut de ligne
                result = "\n\n".join(result_parts)

                # Sauvegarder en cache SQLite
                if persistence:
                    persistence.set_weather_cache(cache_key, 'rain', result)

                return result

        # Cas simple: un seul jour (days=1)
        start_offset = 0
        if days == 1 or start_at_current_time:
            # Démarrer à l'heure actuelle au lieu de minuit
            start_offset = current_hour * 2
            if current_minute >= 30:
                start_offset += 1
            debug_print(f"[RAIN DEBUG] Starting at current time: offset={start_offset} (hour={current_hour}, min={current_minute})")

        truncated_lines = []
        for line in cleaned_lines:
            # Extraire la portion à afficher (depuis start_offset)
            truncated = line[start_offset:start_offset + truncate_width]
            truncated_lines.append(truncated)

        debug_print(f"[RAIN DEBUG] Truncated to {truncate_width} chars ({max_hours}h) starting at offset {start_offset}")

        # Calculer le label de date pour days=1
        date_label = today.strftime("aujourd'hui %d/%m")

        # Utiliser la fonction helper pour formater le graphe
        result = _format_single_day_graph(
            truncated_lines,
            location_name,
            date_label,
            max_str,
            start_offset,
            truncate_width,
            compact_mode,
            ultra_compact,
            split_mode=split_messages
        )

        if split_messages:
            # En mode split, result est tuple (sparkline, info)
            sparkline, info = result
            
            # Construire le format standard pour le cache
            combined = f"{sparkline}\n{info}"
            
            # Sauvegarder en cache SQLite (format standard)
            if persistence:
                persistence.set_weather_cache(cache_key, 'rain', combined)
            
            # Retourner les parties séparées
            return result
        else:
            # En mode normal, result est une string
            # Sauvegarder en cache SQLite
            if persistence:
                persistence.set_weather_cache(cache_key, 'rain', result)

            return result

    except FileNotFoundError:
        error_msg = "❌ Commande curl non trouvée"
        error_print(error_msg)

        # Fallback: use cached data if available with STALLED indicator
        if cached_data:
            age_hours = cache_age_seconds / 3600
            error_print(f"⚠️ Servir cache périmé ({age_hours:.1f}h)")
            return _add_stale_indicator_to_rain_graph(cached_data, age_hours, split_messages)

        # Fallback: cache SQLite périmé
        if cache_key is not None:
            stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'rain')
            if stale_data:
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return _add_stale_indicator_to_rain_graph(stale_data, age_hours, split_messages)

        return error_msg

    except Exception as e:
        error_print(f"❌ Erreur inattendue dans get_rain_graph: {e}")
        import traceback
        error_print(traceback.format_exc())

        # Fallback: use cached data if available with STALLED indicator
        if cached_data:
            age_hours = cache_age_seconds / 3600
            error_print(f"⚠️ Servir cache périmé ({age_hours:.1f}h)")
            return _add_stale_indicator_to_rain_graph(cached_data, age_hours, split_messages)

        # Fallback: cache SQLite périmé
        if cache_key is not None:
            stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'rain')
            if stale_data:
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return _add_stale_indicator_to_rain_graph(stale_data, age_hours, split_messages)

        return f"❌ Erreur: {str(e)[:50]}"


def _add_stale_indicator_to_rain_graph(cached_data, age_hours, split_messages=False):
    """
    Ajouter un indicateur STALLED au graphe de pluie en cache
    
    Args:
        cached_data: Données en cache (string ou tuple si split_messages)
        age_hours: Age du cache en heures
        split_messages: Si True, cached_data est un tuple (sparkline, info)
    
    Returns:
        Données avec indicateur STALLED ajouté au header
    """
    stale_text = f"STALLED for {int(age_hours)}h"
    
    if isinstance(cached_data, tuple):
        # Mode split: modifier seulement la partie info (sparkline, info)
        sparkline, info = cached_data
        # Chercher la ligne avec le header (contient 🌧 ou 🌧️)
        info_lines = info.split('\n')
        for i, line in enumerate(info_lines):
            if '🌧' in line:
                # Ajouter STALLED après la date
                info_lines[i] = line + f" - {stale_text}"
                break
        modified_info = '\n'.join(info_lines)
        return (sparkline, modified_info)
    else:
        # Mode string: modifier la ligne avec le header
        lines = cached_data.split('\n')
        for i, line in enumerate(lines):
            if '🌧' in line:
                # Ajouter STALLED après la date
                lines[i] = line + f" - {stale_text}"
                break
        return '\n'.join(lines)


def get_moon_emoji(moon_illumination):
    """
    Convertir le pourcentage d'illumination de la lune en émoji

    Args:
        moon_illumination: Pourcentage d'illumination (0-100)

    Returns:
        str: Émoji de phase lunaire
    """
    try:
        illum = int(moon_illumination)
        if illum < 6:
            return '🌑'  # Nouvelle lune
        elif illum < 19:
            return '🌒'  # Premier croissant
        elif illum < 31:
            return '🌓'  # Premier quartier
        elif illum < 44:
            return '🌔'  # Gibbeuse croissante
        elif illum < 56:
            return '🌕'  # Pleine lune
        elif illum < 69:
            return '🌖'  # Gibbeuse décroissante
        elif illum < 81:
            return '🌗'  # Dernier quartier
        elif illum < 94:
            return '🌘'  # Dernier croissant
        else:
            return '🌑'  # Nouvelle lune
    except:
        return '🌙'  # Fallback


def get_weather_astro(location=None, persistence=None):
    """
    Récupérer les informations astronomiques et météo actuelles

    Args:
        location: Ville/lieu pour la météo (ex: "Paris", "London")
                 Si None ou vide, utilise la géolocalisation par IP
        persistence: Instance TrafficPersistence pour le cache SQLite (optionnel)

    Returns:
        str: Infos astronomiques formatées (4 lignes)

    Exemples:
        >>> astro = get_weather_astro("Paris")
        >>> print(astro)
        📍 Paris, France
        Weather: Mist, +12°C, 94%, 5km/h, 1008hPa
        Now: 00:53:40 | Sunrise: 08:01 | Sunset: 17:08
        🌔 Moonrise: 10:23 | Moonset: 18:45 (67%)
    """
    # Initialize cache variables at function level for exception handlers
    cache_key = None
    cached_data = None
    cache_age_seconds = 0

    try:
        # Normaliser la location
        if not location:
            location = DEFAULT_LOCATION

        # Clé de cache
        cache_key = location or 'default'

        # ----------------------------------------------------------------
        # "Serve first" pattern: always return cached data if available
        # ----------------------------------------------------------------
        if persistence:
            # Check for any cached data (even stale)
            stale_data, age_hours = persistence.get_weather_cache_with_age(cache_key, 'astro', max_age_seconds=CACHE_MAX_AGE)
            if stale_data:
                cached_data = stale_data
                cache_age_seconds = age_hours * 3600

                # Fresh cache (<5 min): return immediately
                if cache_age_seconds < CACHE_DURATION:
                    info_print(f"✅ Cache SQLite astro FRESH (age: {cache_age_seconds}s)")
                    return cached_data

                # Stale but valid (<1 hour): return immediately
                elif cache_age_seconds < CACHE_STALE_DURATION:
                    info_print(f"⚡ Cache SQLite astro STALE mais valide (age: {cache_age_seconds}s)")
                    return cached_data

                # Very stale (>1h): try to refresh, fallback to cached
                else:
                    info_print(f"⏰ Cache SQLite astro expiré (age: {age_hours}h), tentative de rafraîchissement")

        # Construire l'URL
        if location:
            location_encoded = location.replace(' ', '+')
            wttr_url = f"{WTTR_BASE_URL}/{location_encoded}?format=j1"
        else:
            wttr_url = f"{WTTR_BASE_URL}/?format=j1"

        # Faire l'appel API avec retry logic
        info_print(f"📊 Récupération données astro depuis {wttr_url}...")
        try:
            result = _curl_with_retry(wttr_url, timeout=CURL_TIMEOUT)

            if result.returncode != 0 or not result.stdout:
                error_msg = "❌ Erreur récupération données astro"
                error_print(f"{error_msg} (curl returncode: {result.returncode})")

                # Fallback: use cached data if available
                if cached_data:
                    age_hours = int(cache_age_seconds / 3600)
                    error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                    return f"⚠️ (cache ~{age_hours}h)\n{cached_data}"

                # Fallback: cache SQLite périmé
                stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'astro')
                if stale_data:
                    error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                    return f"⚠️ (cache ~{age_hours}h)\n{stale_data}"

                return error_msg

        except subprocess.TimeoutExpired:
            error_msg = f"❌ Timeout données astro après {CURL_MAX_RETRIES} tentatives (>{CURL_TIMEOUT}s chacune)"
            error_print(error_msg)

            # Fallback: use cached data if available
            if cached_data:
                age_hours = int(cache_age_seconds / 3600)
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache ~{age_hours}h)\n{cached_data}"

            # Fallback: cache SQLite périmé
            stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'astro')
            if stale_data:
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache ~{age_hours}h)\n{stale_data}"

            return error_msg
        except Exception as e:
            error_msg = f"❌ Erreur curl: {e}"
            error_print(error_msg)

            # Fallback: use cached data if available
            if cached_data:
                age_hours = int(cache_age_seconds / 3600)
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache ~{age_hours}h)\n{cached_data}"

            # Fallback: cache SQLite périmé
            stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'astro')
            if stale_data:
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache ~{age_hours}h)\n{stale_data}"

            return error_msg

        weather_json = json.loads(result.stdout.strip())

        # Parser les données
        lines = []

        # Ligne 1: Location header
        nearest_area = weather_json.get('nearest_area', [{}])[0]
        area_name = nearest_area.get('areaName', [{}])[0].get('value', 'Unknown')
        country = nearest_area.get('country', [{}])[0].get('value', '')

        if country and country != area_name:
            location_str = f"📍 {area_name}, {country}"
        else:
            location_str = f"📍 {area_name}"

        lines.append(location_str)

        # Ligne 2: Weather actuel
        current = weather_json.get('current_condition', [{}])[0]
        weather_desc = current.get('weatherDesc', [{}])[0].get('value', 'Unknown')
        temp = current.get('temp_C', '?')
        humidity = current.get('humidity', '?')
        wind = current.get('windspeedKmph', '?')
        pressure = current.get('pressure', '?')

        lines.append(f"Weather: {weather_desc}, +{temp}°C, {humidity}%, {wind}km/h, {pressure}hPa")

        # Ligne 3 & 4: Infos astronomiques
        astronomy = weather_json.get('weather', [{}])[0].get('astronomy', [{}])[0]

        # Heure locale
        local_time = time.strftime("%H:%M:%S%z")

        # Données astronomiques (format HH:MM:SS, on garde juste HH:MM)
        sunrise = astronomy.get('sunrise', '??:??:??')[:5]
        sunset = astronomy.get('sunset', '??:??:??')[:5]
        moonrise = astronomy.get('moonrise', '??:??:??')[:5]
        moonset = astronomy.get('moonset', '??:??:??')[:5]
        moon_illumination = astronomy.get('moon_illumination', '50')

        # Émoji de phase lunaire
        moon_emoji = get_moon_emoji(moon_illumination)

        # Ligne 3: Now, Sunrise, Sunset
        lines.append(f"Now: {local_time[:8]} | Sunrise: {sunrise} | Sunset: {sunset}")

        # Ligne 4: Moonrise, Moonset avec émoji de phase
        lines.append(f"{moon_emoji} Moonrise: {moonrise} | Moonset: {moonset} ({moon_illumination}%)")

        # Formater le résultat
        result = "\n".join(lines)

        # Sauvegarder en cache SQLite
        if persistence:
            persistence.set_weather_cache(cache_key, 'astro', result)

        return result

    except FileNotFoundError:
        error_msg = "❌ Commande curl non trouvée"
        error_print(error_msg)

        # Fallback: use cached data if available
        if cached_data:
            age_hours = int(cache_age_seconds / 3600)
            error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
            return f"⚠️ (cache ~{age_hours}h)\n{cached_data}"

        # Fallback: cache SQLite périmé
        if cache_key is not None:
            stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'astro')
            if stale_data:
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache ~{age_hours}h)\n{stale_data}"

        return error_msg

    except Exception as e:
        error_print(f"❌ Erreur inattendue dans get_weather_astro: {e}")
        import traceback
        error_print(traceback.format_exc())

        # Fallback: use cached data if available
        if cached_data:
            age_hours = int(cache_age_seconds / 3600)
            error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
            return f"⚠️ (cache ~{age_hours}h)\n{cached_data}"

        # Fallback: cache SQLite périmé
        if cache_key is not None:
            stale_data, age_hours = _load_stale_cache_sqlite(persistence, cache_key, 'astro')
            if stale_data:
                error_print(f"⚠️ Servir cache périmé ({age_hours}h)")
                return f"⚠️ (cache ~{age_hours}h)\n{stale_data}"

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
        Now: ☀️ 15°C 10km/h 0mm 60%
        Today: ⛅ 16°C 12km/h 0mm 58%
        ...
    """
    try:
        url = f"https://wttr.in/{city}?format=j1"
        info_print(f"🌤️ Récupération météo pour {city}...")

        try:
            result = _curl_with_retry(url, timeout=CURL_TIMEOUT)
        except subprocess.TimeoutExpired:
            error_print(f"❌ Timeout météo {city} après {CURL_MAX_RETRIES} tentatives (>{CURL_TIMEOUT}s chacune)")
            return f"❌ Timeout récupération météo pour {city}"
        except Exception as e:
            error_print(f"❌ Erreur curl {city}: {e}")
            return f"❌ Erreur récupération météo pour {city}"

        if result.returncode == 0 and result.stdout:
            json_response = result.stdout.strip()
            
            try:
                weather_json = json.loads(json_response)
                weather_data = parse_weather_json(weather_json)
                info_print(f"✅ Météo {city}:\n{weather_data}")
                return weather_data
            except json.JSONDecodeError as e:
                error_print(f"⚠️ JSON invalide pour {city}: {e}")
                return f"❌ Erreur météo {city}"
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
    print(f"Résultat:\n{weather}")
    
    # Test 2: Info cache
    print("\nTest 2: Info cache")
    cache_info = get_cache_info()
    if cache_info:
        print(f"Cache existe: {cache_info['exists']}")
        print(f"Cache valide: {cache_info['is_valid']}")
        if cache_info['exists']:
            print(f"Âge: {cache_info['age_seconds']}s")
            print(f"Données:\n{cache_info['data']}")
    
    # Test 3: Utilisation cache
    print("\nTest 3: Deuxième appel (devrait utiliser cache)")
    weather2 = get_weather_data()
    print(f"Résultat:\n{weather2}")
    
    # Test 4: Ville spécifique
    print("\nTest 4: Météo Lyon (sans cache)")
    lyon_weather = get_weather_for_city("Lyon")
    print(f"Résultat:\n{lyon_weather}")
    
    # Test 5: Nettoyage
    print("\nTest 5: Nettoyage cache")
    cleared = clear_cache()
    print(f"Cache effacé: {cleared}")
    
    print("\n" + "=" * 60)
    print("✅ Tests terminés")
    print("=" * 60)
