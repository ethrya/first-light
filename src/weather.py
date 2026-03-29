"""
Fetches current-day weather for Canberra from the Open-Meteo API.

No API key required. Uses stdlib urllib only.
"""

import json
import logging
import urllib.request
from urllib.error import URLError

logger = logging.getLogger(__name__)

_OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=-35.28&longitude=149.13"
    "&daily=temperature_2m_max,temperature_2m_min,weathercode"
    "&timezone=Australia%2FSydney"
    "&forecast_days=1"
)

# WMO Weather Interpretation Codes → short description
_WMO_DESCRIPTIONS: dict[int, str] = {
    0: "sunny",
    1: "mostly sunny",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "icy fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    56: "freezing drizzle",
    57: "heavy freezing drizzle",
    61: "light rain",
    63: "rainy",
    65: "heavy rain",
    66: "freezing rain",
    67: "heavy freezing rain",
    71: "light snow",
    73: "snowy",
    75: "heavy snow",
    77: "snow grains",
    80: "light showers",
    81: "showers",
    82: "heavy showers",
    85: "snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "thunderstorm with heavy hail",
}


def fetch_canberra_weather() -> str:
    """Return a one-line weather summary for Canberra today.

    Returns a string like "Canberra: 4\u201318\u00b0C, sunny" or "" on failure.
    """
    try:
        req = urllib.request.Request(
            _OPEN_METEO_URL,
            headers={"User-Agent": "first-light-newsletter/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        daily = data["daily"]
        t_max = round(daily["temperature_2m_max"][0])
        t_min = round(daily["temperature_2m_min"][0])
        wmo = int(daily["weathercode"][0])
        description = _WMO_DESCRIPTIONS.get(wmo, "variable")

        return f"Canberra: {t_min}\u2013{t_max}\u00b0C, {description}"

    except (URLError, KeyError, IndexError, ValueError, OSError) as exc:
        logger.warning(f"Weather fetch failed: {exc}")
        return ""
