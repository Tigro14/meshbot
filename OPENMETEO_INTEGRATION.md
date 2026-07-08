# Open-Meteo API Integration

## Overview

The bot now supports **Open-Meteo API** as an alternative to wttr.in for weather data, with specific support for **France's high-definition weather model** (`meteofrance_arome_france_hd`).

## Features

- ✅ **France-specific weather model**: Uses Météo-France AROME HD model for accurate French weather
- ✅ **Configurable coordinates**: Auto-detect from GPS or manual configuration
- ✅ **Cache integration**: Full SQLite cache support (5min fresh, 1h stale)
- ✅ **Backward compatible**: Falls back to wttr.in for city-specific queries
- ✅ **Error handling**: Graceful degradation with detailed error messages

## Configuration

### config.py

```python
# ========================================
# CONFIGURATION MÉTÉO OPEN-METEO
# ========================================

# Configuration pour Open-Meteo API (météo France haute définition)
WEATHER_LATITUDE = 48.8566   # Latitude Paris par défaut (0.0 = auto-détection depuis GPS)
WEATHER_LONGITUDE = 2.3522   # Longitude Paris par défaut (0.0 = auto-détection depuis GPS)
WEATHER_USE_OPENMETEO = True  # Utiliser Open-Meteo au lieu de wttr.in
WEATHER_MODEL = "meteofrance_arome_france_hd"  # Modèle météo France haute définition
WEATHER_FORECAST_HOURS = 48  # Nombre d'heures de prévision (défaut: 48h)
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `WEATHER_LATITUDE` | `48.8566` (Paris) | Latitude for weather location |
| `WEATHER_LONGITUDE` | `2.3522` (Paris) | Longitude for weather location |
| `WEATHER_USE_OPENMETEO` | `True` | Enable Open-Meteo API |
| `WEATHER_MODEL` | `meteofrance_arome_france_hd` | Weather model to use |
| `WEATHER_FORECAST_HOURS` | `48` | Hours of forecast data |

### Model Options

For France, use the high-definition model:
- **`meteofrance_arome_france_hd`** - Météo-France AROME HD (France only, best quality)

For other regions:
- **`best_match`** - Auto-select best model for location
- **`gfs_seamless`** - Global model (worldwide)
- **`icon_seamless`** - DWD ICON model (Europe)
- **`ecmwf_ifs04`** - ECMWF IFS model (global)

See [Open-Meteo Models](https://open-meteo.com/en/docs) for complete list.

## Usage

### Automatic (via /weather command)

When `WEATHER_USE_OPENMETEO = True`, the `/weather` command automatically uses Open-Meteo for geolocation queries:

```bash
# On Meshtastic or Telegram
/weather
```

**Output:**
```
Now: ☀️ 12°C 15km/h 0.0mm
```

### Programmatic (Python)

```python
from utils_weather import get_weather_openmeteo

# Use default config (Paris)
weather = get_weather_openmeteo()
print(weather)

# Custom coordinates (Lyon)
weather = get_weather_openmeteo(lat=45.75, lon=4.85)
print(weather)

# With SQLite cache
weather = get_weather_openmeteo(lat=45.75, lon=4.85, persistence=traffic_persistence)
print(weather)
```

### Integration with get_weather_data()

The main `get_weather_data()` function automatically routes to Open-Meteo when:
1. `WEATHER_USE_OPENMETEO = True` in config
2. No specific location is provided (geolocation mode)

```python
from utils_weather import get_weather_data

# Automatically uses Open-Meteo if enabled
weather = get_weather_data()

# For specific cities, still uses wttr.in
weather = get_weather_data("London")  # Falls back to wttr.in
```

## API Details

### Endpoint

```
GET https://api.open-meteo.com/v1/forecast
```

### Parameters

```python
params = {
    "latitude": 48.8566,
    "longitude": 2.3522,
    "hourly": ",".join([
        "temperature_2m",
        "precipitation",
        "precipitation_probability",
        "wind_speed_10m",
        "weather_code",
    ]),
    "timezone": "Europe/Paris",
    "forecast_hours": 48,
    "models": "meteofrance_arome_france_hd",
}
```

### Response Format

The function extracts current conditions from the first hourly slot:
- **Temperature**: `temperature_2m[0]` (°C)
- **Wind speed**: `wind_speed_10m[0]` (km/h)
- **Precipitation**: `precipitation[0]` (mm)
- **Weather code**: Mapped to emoji via `get_weather_icon()`

## Cache Behavior

Same caching strategy as wttr.in:

| Cache Age | Behavior |
|-----------|----------|
| < 5 min (FRESH) | Return immediately |
| < 1 hour (STALE) | Return immediately (skip refresh) |
| > 1 hour | Attempt refresh, fallback to stale cache if API fails |
| None | Fetch from API |

## Testing

Run the test suite to verify integration:

```bash
python3 test_openmeteo.py
```

**Note**: Requires internet access to `api.open-meteo.com`

## Error Handling

The function handles various error cases:
- **DNS failure**: Returns "❌ Erreur récupération météo"
- **HTTP timeout**: Returns "❌ Timeout météo"
- **Invalid response**: Returns "❌ Erreur format réponse météo"
- **General exceptions**: Returns "❌ Erreur météo" with traceback

All errors are logged with `error_print()` for debugging.

## Advantages vs wttr.in

| Feature | Open-Meteo | wttr.in |
|---------|-----------|---------|
| France HD model | ✅ `meteofrance_arome_france_hd` | ❌ Generic |
| API stability | ✅ Reliable | ⚠️ Sometimes slow |
| Data freshness | ✅ Real-time | ⚠️ Variable |
| JSON format | ✅ Clean JSON | ⚠️ Complex JSON |
| Rate limiting | ✅ Generous (10k/day free) | ⚠️ Unknown |
| Coordinates-based | ✅ Yes | ❌ City names only |

## Troubleshooting

### "❌ Timeout météo"

1. Check internet connectivity
2. Verify DNS resolution: `ping api.open-meteo.com`
3. Check firewall/proxy settings

### "❌ Erreur format réponse météo"

1. Check API response format hasn't changed
2. Verify `forecast_hours` parameter is valid
3. Enable DEBUG_MODE for detailed logging

### "❌ Erreur récupération météo"

1. Check coordinates are valid (lat: -90 to 90, lon: -180 to 180)
2. Verify model is supported for your region
3. Check API status: https://open-meteo.com/

## References

- [Open-Meteo API Documentation](https://open-meteo.com/en/docs)
- [Météo-France AROME Model](https://www.meteofrance.fr/prevoir-le-temps/la-prevision-du-temps/latmosphere/arome-et-arpege-des-modeles-numeriques-de-prevision)
- [Weather Code Mapping](https://www.nodc.noaa.gov/archive/arc0021/0002199/1.1/data/0-data/HTML/WMO-CODE/WMO4677.HTM)
