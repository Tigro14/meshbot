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
from utils import info_print, error_print

# Configuration
CACHE_DIR = "/tmp"
CACHE_DURATION = 300  # 5 minutes en secondes
WTTR_BASE_URL = "https://wttr.in"
DEFAULT_LOCATION = ""  # Vide = géolocalisation par IP
CURL_TIMEOUT = 10  # secondes

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
    Formater une ligne de météo avec séparations visuelles pour meilleure lisibilité

    Args:
        label (str): Label de la ligne (🌡️ Maintenant/📅 Aujourd'hui/📆 Demain/📋 J+2)
        emoji (str): Émoji météo
        temp (str): Température (ex: "12")
        wind (str): Vitesse vent en km/h (ex: "15")
        precip (str): Précipitations en mm (ex: "0.5")
        humidity (str): Humidité en % (ex: "65")

    Returns:
        str: Ligne formatée avec séparations (ex: "🌡️ Maintenant: ☀️ 12°C | 💨 15km/h | 💧 0mm | 💦 65%")
    """
    # Convertir précipitations en format propre (pas de .0 inutiles)
    try:
        precip_float = float(precip)
        precip_str = f"{precip_float:.1f}mm" if precip_float % 1 != 0 else f"{int(precip_float)}mm"
    except (ValueError, TypeError):
        precip_str = f"{precip}mm"

    # Format avec séparations | et émojis pour meilleure lisibilité
    return f"{label}: {emoji} {temp}°C | 💨 {wind}km/h | 💧 {precip_str} | 💦 {humidity}%"


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

        lines.append(format_weather_line('🌡️ Maintenant', emoji, temp, wind, precip, humidity))

        # ----------------------------------------------------------------
        # Lines 3-5: TODAY, TOMORROW, DAY+2 (weather array)
        # ----------------------------------------------------------------
        weather = json_data.get('weather', [])
        day_labels = ['📅 Aujourd\'hui', '📆 Demain', '📋 J+2']
        
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


def get_weather_data(location=None):
    """
    Récupérer les données météo avec système de cache

    Args:
        location: Ville/lieu pour la météo (ex: "Paris", "London", "New York")
                 Si None ou vide, utilise la géolocalisation par IP

    Le cache est vérifié en premier. S'il est valide (< 5 minutes),
    les données sont retournées immédiatement sans appel réseau.

    Sinon, un appel curl est fait vers wttr.in et le cache est mis à jour.

    Returns:
        str: Données météo formatées sur 4 lignes ou message d'erreur

    Exemples:
        >>> weather = get_weather_data()  # Géolocalisation
        >>> print(weather)
        Now: ☀️ 12°C 15km/h 0mm 65%

        >>> weather = get_weather_data("London")  # Ville spécifique
        >>> print(weather)
        Now: 🌧️ 8°C 20km/h 2mm 80%
    """
    try:
        # Normaliser la location
        if not location:
            location = DEFAULT_LOCATION

        # Construire l'URL et le nom du cache
        if location:
            # Encoder la ville pour l'URL (espaces → +)
            location_encoded = location.replace(' ', '+')
            wttr_url = f"{WTTR_BASE_URL}/{location_encoded}?format=j1"
            # Nom de cache safe (espaces → _)
            location_safe = location.replace(' ', '_').replace('/', '_')
            cache_file = f"{CACHE_DIR}/weather_cache_{location_safe}.json"
        else:
            wttr_url = f"{WTTR_BASE_URL}/?format=j1"
            cache_file = f"{CACHE_DIR}/weather_cache_default.json"

        # ----------------------------------------------------------------
        # Phase 1: Vérifier le cache
        # ----------------------------------------------------------------
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
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
        info_print(f"🌤️ Récupération météo depuis {wttr_url}...")

        result = subprocess.run(
            ['curl', '-s', wttr_url],
            capture_output=True,
            text=True,
            timeout=CURL_TIMEOUT
        )
        
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
                return "❌ Réponse météo invalide"
            
            # Validation basique de la réponse formatée
            if not weather_data or 'Erreur' in weather_data:
                error_print(f"⚠️ Données météo invalides")
                return "❌ Données météo invalides"
            
            # Sauvegarder en cache
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
                info_print(f"✅ Cache météo créé/mis à jour")
            except IOError as e:
                error_print(f"⚠️ Impossible d'écrire le cache: {e}")
                # Pas grave, on retourne quand même les données
            
            info_print(f"✅ Météo récupérée:\n{weather_data}")
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


def get_rain_graph(location=None, days=1):
    """
    Récupérer le graphe ASCII des précipitations (compact sparkline)

    Args:
        location: Ville/lieu pour la météo (ex: "Paris", "London")
                 Si None ou vide, utilise la géolocalisation par IP
        days: Nombre de jours à afficher (1 ou 3)
              1 = aujourd'hui seulement (défaut)
              3 = aujourd'hui + demain + J+2

    Returns:
        str: Graphe sparkline compact des précipitations

    Exemples:
        >>> rain = get_rain_graph("Paris")  # Seulement aujourd'hui
        >>> print(rain)
        🌧️ Paris Auj (max:1.2mm)
        ▁▂▃█▇▄▂▁▁▁▃▄▆▇▅▃▁▁▁▁▂▃▄▃▂▁
        0  3  6  9  12 15 18 21

        >>> rain = get_rain_graph("Paris", days=3)  # 3 jours
    """
    try:
        # Normaliser la location
        if not location:
            location = DEFAULT_LOCATION

        # Construire l'URL v2n (narrow format avec graphes ASCII)
        if location:
            location_encoded = location.replace(' ', '+')
            wttr_url = f"https://v2n.wttr.in/{location_encoded}"
        else:
            wttr_url = "https://v2n.wttr.in"

        info_print(f"🌧️ Récupération graphe pluie depuis {wttr_url}...")

        # Appel curl vers wttr.in v2n
        result = subprocess.run(
            ['curl', '-s', wttr_url],
            capture_output=True,
            text=True,
            timeout=CURL_TIMEOUT
        )

        if result.returncode != 0 or not result.stdout:
            error_msg = "❌ Erreur récupération graphe pluie"
            error_print(f"{error_msg} (curl returncode: {result.returncode})")
            return error_msg

        output = result.stdout.strip()

        if not output:
            return "❌ Graphe pluie vide"

        # Parser la sortie pour extraire les précipitations
        lines = output.split('\n')

        # Chercher la section avec les barres de précipitations (contient █▇▄▃▂▁_)
        rain_chars = []
        max_precip = 0.0

        for line in lines:
            # Ligne avec la valeur max (ex: "1.25mm|95%")
            if 'mm' in line and '|' in line and '%' in line:
                try:
                    # Extraire la valeur max (ex: "1.25mm")
                    mm_part = line.split('mm')[0].strip()
                    max_precip = float(mm_part.split()[-1])
                except:
                    pass

            # Ligne avec les caractères de graphe ASCII
            if any(c in line for c in '█▇▆▅▄▃▂▁_'):
                # Extraire juste les caractères du graphe
                for char in line:
                    if char in '█▇▆▅▄▃▂▁_ ':
                        if char == '_':
                            rain_chars.append('▁')
                        elif char == ' ':
                            rain_chars.append('▁')
                        else:
                            rain_chars.append(char)

        if not rain_chars:
            return "❌ Graphe pluie non trouvé"

        # Convertir les caractères en valeurs numériques (0-7)
        char_to_value = {
            '▁': 0, '_': 0, ' ': 0,
            '▂': 1,
            '▃': 2,
            '▄': 3,
            '▅': 4,
            '▆': 5,
            '▇': 6,
            '█': 7
        }

        # Convertir en valeurs et compacter
        values = []
        for char in rain_chars:
            if char in char_to_value:
                values.append(char_to_value[char])

        if not values:
            return "❌ Aucune donnée pluie"

        # Échantillonner pour avoir 48 points par jour (résolution 30 min)
        # IMPORTANT: Prendre le MAX de chaque fenêtre pour préserver les pics
        # days=1 → 48 points, days=3 → 144 points
        target_points = 48 * days
        if len(values) > target_points:
            window_size = len(values) // target_points
            if window_size < 1:
                window_size = 1

            sampled = []
            for i in range(0, len(values), window_size):
                window = values[i:i+window_size]
                if window:
                    # Prendre le MAX de chaque fenêtre pour préserver les fronts raides
                    sampled.append(max(window))
            values = sampled[:target_points]

        # Créer un graphe multi-lignes (3 niveaux de hauteur)
        width = len(values)
        line_high = []  # Valeurs >= 5 (▅▆▇█)
        line_mid = []   # Valeurs 3-4 (▃▄)
        line_low = []   # Valeurs 0-2 (▁▂)

        for v in values:
            # Ligne haute (>= 5)
            if v >= 6:
                line_high.append('█')
            elif v == 5:
                line_high.append('▄')
            else:
                line_high.append(' ')

            # Ligne moyenne (3-4)
            if v >= 4:
                line_mid.append('█')
            elif v == 3:
                line_mid.append('▄')
            else:
                line_mid.append(' ')

            # Ligne basse (toutes les valeurs > 0)
            if v >= 2:
                line_low.append('█')
            elif v == 1:
                line_low.append('▄')
            else:
                line_low.append('▁')

        # Formater la sortie
        location_name = location if location else "local"
        max_str = f"{max_precip:.1f}mm"  # Toujours avec 1 décimale

        # Créer une échelle horaire lisible (marqueurs toutes les 3h)
        # 48 points par jour = 2 points/heure
        # Marqueurs à 0h, 3h, 6h, 9h, 12h, 15h, 18h, 21h pour chaque jour
        hour_scale = []
        for i in range(width):
            # 48 points / 24h = 2 points/heure
            hour = (i // 2) % 24
            point_in_hour = i % 2

            # Afficher seulement sur le premier point de l'heure
            if point_in_hour == 0 and hour % 3 == 0:
                hour_scale.append(str(hour))
            else:
                hour_scale.append(' ')

        # Découper jour par jour (48 points par jour) pour rester sous 220 chars/message
        messages = []
        day_names = ['Auj', 'Dem', 'J+2']

        for day in range(days):
            start_idx = day * 48
            end_idx = start_idx + 48

            day_lines = []
            # Titre avec jour et max pour ce jour
            day_lines.append(f"🌧️ {location_name} {day_names[day]} (max:{max_str})")

            # Extraire les segments pour ce jour
            high_day = ''.join(line_high[start_idx:end_idx]).rstrip()
            mid_day = ''.join(line_mid[start_idx:end_idx]).rstrip()
            low_day = ''.join(line_low[start_idx:end_idx])
            scale_day = ''.join(hour_scale[start_idx:end_idx])

            # Ajouter les lignes qui ont des données
            if high_day.strip():
                day_lines.append(high_day)
            if mid_day.strip():
                day_lines.append(mid_day)
            day_lines.append(low_day)
            day_lines.append(scale_day)

            messages.append("\n".join(day_lines))

        # Retourner les 3 messages séparés par un délimiteur
        return "\n\n".join(messages)

    except subprocess.TimeoutExpired:
        error_msg = f"❌ Timeout graphe pluie (> {CURL_TIMEOUT}s)"
        error_print(error_msg)
        return error_msg

    except FileNotFoundError:
        error_msg = "❌ Commande curl non trouvée"
        error_print(error_msg)
        return error_msg

    except Exception as e:
        error_print(f"❌ Erreur inattendue dans get_rain_graph: {e}")
        import traceback
        error_print(traceback.format_exc())
        return f"❌ Erreur: {str(e)[:50]}"


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


def get_weather_astro(location=None):
    """
    Récupérer les informations astronomiques et météo actuelles

    Args:
        location: Ville/lieu pour la météo (ex: "Paris", "London")
                 Si None ou vide, utilise la géolocalisation par IP

    Returns:
        str: Infos astronomiques formatées (3 lignes)

    Exemples:
        >>> astro = get_weather_astro("Paris")
        >>> print(astro)
        Weather: Mist, +12°C, 94%, 5km/h, 1008hPa
        Now: 00:53:40 | Sunrise: 08:01 | Sunset: 17:08
        🌔 Moonrise: 10:23 | Moonset: 18:45 (67%)
    """
    try:
        # Normaliser la location
        if not location:
            location = DEFAULT_LOCATION

        # Construire l'URL et le nom du cache
        if location:
            location_encoded = location.replace(' ', '+')
            wttr_url = f"{WTTR_BASE_URL}/{location_encoded}?format=j1"
            location_safe = location.replace(' ', '_').replace('/', '_')
            cache_file = f"{CACHE_DIR}/weather_cache_{location_safe}.json"
        else:
            wttr_url = f"{WTTR_BASE_URL}/?format=j1"
            cache_file = f"{CACHE_DIR}/weather_cache_default.json"

        # Essayer de lire depuis le cache d'abord
        weather_json = None
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                cache_time = cache_data.get('timestamp', 0)
                current_time = time.time()
                age_seconds = int(current_time - cache_time)

                # Si cache valide (< 5 min), l'utiliser
                if age_seconds < CACHE_DURATION:
                    # Refaire l'appel pour avoir le JSON complet (pas juste le texte formaté)
                    info_print(f"📊 Récupération données géo depuis {wttr_url}...")
                    result = subprocess.run(
                        ['curl', '-s', wttr_url],
                        capture_output=True,
                        text=True,
                        timeout=CURL_TIMEOUT
                    )
                    if result.returncode == 0 and result.stdout:
                        weather_json = json.loads(result.stdout.strip())
            except:
                pass

        # Si pas de cache ou expiré, faire l'appel
        if not weather_json:
            info_print(f"📊 Récupération données géo depuis {wttr_url}...")
            result = subprocess.run(
                ['curl', '-s', wttr_url],
                capture_output=True,
                text=True,
                timeout=CURL_TIMEOUT
            )

            if result.returncode != 0 or not result.stdout:
                return "❌ Erreur récupération données géo"

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

        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        error_msg = f"❌ Timeout données astro (> {CURL_TIMEOUT}s)"
        error_print(error_msg)
        return error_msg

    except FileNotFoundError:
        error_msg = "❌ Commande curl non trouvée"
        error_print(error_msg)
        return error_msg

    except Exception as e:
        error_print(f"❌ Erreur inattendue dans get_weather_astro: {e}")
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
        Now: ☀️ 15°C 10km/h 0mm 60%
        Today: ⛅ 16°C 12km/h 0mm 58%
        ...
    """
    try:
        url = f"https://wttr.in/{city}?format=j1"
        info_print(f"🌤️ Récupération météo pour {city}...")
        
        result = subprocess.run(
            ['curl', '-s', url],
            capture_output=True,
            text=True,
            timeout=CURL_TIMEOUT
        )
        
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
