"""Serve and automatically load the bundled Add Bill badge."""
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig

FRONTEND_VERSION = "0.3.6"
STATIC_URL = "/monthly_bills_static"
BADGE_URL = f"{STATIC_URL}/monthly-bills-badge.js?v={FRONTEND_VERSION}"


async def async_register_frontend(hass):
    """Register once at integration setup, outside the per-entry lifecycle."""
    await hass.http.async_register_static_paths([
        StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "www"), False)
    ])
    frontend.add_extra_js_url(hass, BADGE_URL)
