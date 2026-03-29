"""
Fetches current-day weather for Canberra from the Open-Meteo API.

No API key required. Uses stdlib urllib only.
Primary: BOM endpoint. Fallback: forecast endpoint.
"""

import json
import logging
import urllib.request
from urllib.error import URLError

logger = logging.getLogger(__name__)

_BOM_URL = (
    "https://api.open-meteo.com/v1/bom"
    "?latitude=-35.28&longitude=149.13"
    "&daily=temperature_2m_max,temperature_2m_min"
    ",precipitation_sum,precipitation_probability_max,weathercode"
    "&timezone=Australia%2FSydney"
    "&forecast_days=1"
)

_FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=-35.28&longitude=149.13"
    "&daily=temperature_2m_max,temperature_2m_min"
    ",precipitation_sum,precipitation_probability_max,weathercode"
    "&timezone=Australia%2FSydney"
    "&forecast_days=1"
)

_HEADERS = {"User-Agent": "first-light-newsletter/1.0"}
_TIMEOUT = 5

_WMO_DESCRIPTIONS: dict = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "heavy showers",
    85: "light snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with light hail",
    99: "thunderstorm with heavy hail",
}


def fetch_canberra_weather() -> str:
    """Return a one-line weather summary for Canberra today.

    Returns e.g. "Canberra: 4\u201318\u00b0C, partly cloudy. Frost likely early. 30% chance of rain."
    Returns "" on any failure.
    """
    try:
        daily = _fetch_daily(_BOM_URL)

        t_max = round(daily["temperature_2m_max"][0])
        t_min = round(daily["temperature_2m_min"][0])
        wmo = int(daily["weathercode"][0])
        precip_sum = _safe_float(daily.get("precipitation_sum", [None])[0])

        # precipitation_probability_max can be null on the BOM endpoint
        prob = _safe_int(daily.get("precipitation_probability_max", [None])[0])
        if prob is None:
            # Try fallback endpoint for that field
            try:
                fallback = _fetch_daily(_FORECAST_URL)
                prob = _safe_int(
                    fallback.get("precipitation_probability_max", [None])[0]
                )
            except Exception:
                prob = None
            # Last resort: infer from precip_sum and weathercode
            if prob is None:
                if precip_sum is not None and precip_sum > 0:
                    prob = 60  # rain recorded, treat as likely
                elif wmo in (51, 53, 55, 61, 63, 65, 80, 81, 82):
                    prob = 50
                elif wmo in (95, 96, 99):
                    prob = 80

        description = _WMO_DESCRIPTIONS.get(wmo, "variable")

        parts = [f"Canberra: {t_min}\u2013{t_max}\u00b0C, {description}."]

        # Practical notes
        if t_min <= 0:
            parts.append("Sub-zero start.")
        elif t_min <= 2:
            parts.append("Frost likely early.")

        if wmo in (95, 96, 99):
            parts.append("Storms expected.")
        elif t_max >= 40:
            parts.append("Extreme heat.")
        elif t_max >= 35:
            parts.append("Hot day \u2014 stay hydrated.")

        # Rain chance
        if prob is not None and prob > 0:
            if prob <= 20:
                parts.append("Slight chance of rain.")
            elif prob <= 50:
                parts.append(f"{prob}% chance of rain.")
            elif prob <= 80:
                parts.append(f"{prob}% chance of rain \u2014 bring an umbrella.")
            else:
                parts.append("Rain likely.")

        return " ".join(parts)

    except Exception as exc:
        logger.warning(f"Weather fetch failed: {exc}")
        return ""


def _fetch_daily(url: str) -> dict:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["daily"]


def _safe_float(val) -> float | None:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None
