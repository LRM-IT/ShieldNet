from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path

import maxminddb


GEOIP_COUNTRY_DATABASE = Path("/usr/share/GeoIP/GeoLite2-Country.mmdb")


def normalize_public_ip(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.split(",", 1)[0].strip()
    try:
        address = ip_address(candidate)
    except ValueError:
        return None
    if not address.is_global:
        return None
    return str(address)


@lru_cache(maxsize=1)
def _country_reader():
    if not GEOIP_COUNTRY_DATABASE.is_file():
        return None
    return maxminddb.open_database(GEOIP_COUNTRY_DATABASE)


def country_for_ip(value: str | None) -> str | None:
    candidate = normalize_public_ip(value)
    reader = _country_reader()
    if not candidate or reader is None:
        return None
    try:
        record = reader.get(candidate) or {}
    except (ValueError, OSError):
        return None
    code = record.get("country", {}).get("iso_code")
    return code.upper() if isinstance(code, str) else None
