"""GeoIP validation for IP location verification"""

import ipaddress
import logging
import os
from typing import Any, Dict, Optional

import geoip2.database
import requests

logger = logging.getLogger(__name__)

# Local MaxMind GeoLite2 City database (optional). Without it, lookups return
# no location and the GeoIP rules simply do not fire.
GEOIP_DB_PATH = os.getenv("GEOIP_DB_PATH", "GeoLite2-City.mmdb")
# Sending subscriber IPs to a third-party lookup API is itself a data transfer
# that needs a legal basis, so the remote fallback is opt-in.
ALLOW_REMOTE_LOOKUP = os.getenv("GEOIP_ALLOW_REMOTE_LOOKUP", "0") == "1"

EU_COUNTRIES = {
    "AT",
    "BE",
    "BG",
    "HR",
    "CY",
    "CZ",
    "DK",
    "EE",
    "FI",
    "FR",
    "DE",
    "GR",
    "HU",
    "IE",
    "IT",
    "LV",
    "LT",
    "LU",
    "MT",
    "NL",
    "PL",
    "PT",
    "RO",
    "SK",
    "SI",
    "ES",
    "SE",
}

# Known VPN/Proxy providers (ASN-based)
KNOWN_VPN_PROVIDERS = {
    "AS16509": "Amazon AWS",
    "AS8452": "TeData",
    "AS12389": "Rostelecom",
    "AS9498": "Azerbaijan",
}

# High-risk ASNs (datacenter IPs often used for fraud)
HIGH_RISK_ASNS = {
    "AS16509",
    "AS16621",
    "AS14061",  # AWS
    "AS8452",
    "AS9498",  # Generic datacenter
}


class GeoIPValidator:
    """Validate IP addresses and detect VPN/proxy usage"""

    def __init__(self):
        self.ip_cache: Dict[str, Dict] = {}
        self.max_cache_size = 10000
        self.last_seen: Dict[str, Dict] = {}
        self._reader = None
        if os.path.exists(GEOIP_DB_PATH):
            try:
                self._reader = geoip2.database.Reader(GEOIP_DB_PATH)
            except Exception as e:
                logger.warning(f"Could not open GeoIP database {GEOIP_DB_PATH}: {e}")

    def validate_ip_region_consistency(self, ip_address: str, claimed_region: str) -> Dict[str, Any]:
        """
        Check if IP location matches claimed region.
        Returns flags and risk score adjustments.
        """
        try:
            # Check cache first
            if ip_address in self.ip_cache:
                location_data = self.ip_cache[ip_address]
            else:
                location_data = self._get_ip_location(ip_address)
                self._cache_location(ip_address, location_data)

            flags = []
            score_adjustment = 0

            actual_country = location_data.get("country_code", "")

            # Check region consistency ("EU" matches any member state)
            claimed = claimed_region.upper()
            region_ok = actual_country == claimed or (claimed == "EU" and actual_country in EU_COUNTRIES)
            if actual_country and not region_ok:
                flags.append("ip_region_mismatch")
                score_adjustment += 3
                logger.warning(
                    f"IP region mismatch: {ip_address} claims {claimed_region} "
                    f"but located in {actual_country}"
                )

            # Check for VPN/Proxy
            vpn_info = self._detect_vpn_proxy(location_data)
            if vpn_info.get("is_vpn"):
                flags.append("vpn_detected")
                # VPN itself isn't bad, but adds to risk
                score_adjustment += 1
                logger.info(f"VPN detected: {ip_address} via {vpn_info.get('provider')}")

            # Check for datacenter IP (high risk for fraud)
            if location_data.get("is_datacenter"):
                flags.append("datacenter_ip")
                score_adjustment += 2
                logger.warning(f"Datacenter IP detected: {ip_address}")

            # Check for impossible travel
            return {
                "flags": flags,
                "score_adjustment": score_adjustment,
                "location": {
                    "country": actual_country,
                    "region": location_data.get("region", ""),
                    "city": location_data.get("city", ""),
                    "latitude": location_data.get("latitude"),
                    "longitude": location_data.get("longitude"),
                },
                "vpn_info": vpn_info,
                "is_datacenter": location_data.get("is_datacenter", False),
            }

        except Exception as e:
            logger.error(f"GeoIP validation error for {ip_address}: {e}")
            return {
                "flags": ["geoip_lookup_failed"],
                "score_adjustment": 0,
                "location": None,
                "vpn_info": None,
            }

    def detect_impossible_travel(
        self, user_id: str, current_ip: str, last_location: Dict, current_timestamp: float
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if user traveled impossible distance in given time.
        E.g., Seoul to New York in 1 hour = impossible without supersonic jet
        """
        try:
            current_location = self._get_ip_location(current_ip)

            if not (last_location and last_location.get("latitude")):
                return None
            if current_location.get("latitude") is None:
                return None

            # Calculate distance (Haversine formula)
            from math import atan2, cos, radians, sin, sqrt

            lat1, lon1 = radians(last_location["latitude"]), radians(last_location["longitude"])
            lat2, lon2 = radians(current_location["latitude"]), radians(current_location["longitude"])

            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            distance_km = 6371 * c  # Earth radius

            # Max speed: commercial plane = 900 km/h
            time_hours = (current_timestamp - last_location.get("timestamp", 0)) / 3600

            if time_hours > 0:
                speed_kmh = distance_km / time_hours

                # If faster than airplane speed, it's impossible
                if speed_kmh > 1000:
                    return {
                        "impossible_travel": True,
                        "distance_km": distance_km,
                        "speed_kmh": speed_kmh,
                        "from": f"{last_location.get('city', '')}, {last_location.get('country', '')}",
                        "to": f"{current_location.get('city', '')}, {current_location.get('country_code', '')}",
                        "risk": "critical" if speed_kmh > 5000 else "high",
                    }

            return None

        except Exception as e:
            logger.error(f"Impossible travel detection error: {e}")
            return None

    def check_user_travel(self, user_id: str, ip_address: str, timestamp: float) -> Optional[Dict[str, Any]]:
        """Compare this IP's location with the user's last seen location."""
        location = self.ip_cache.get(ip_address) or self._get_ip_location(ip_address)
        previous = self.last_seen.get(user_id)
        result = None
        if previous:
            result = self.detect_impossible_travel(user_id, ip_address, previous, timestamp)
        if location.get("latitude") is not None:
            self.last_seen[user_id] = {
                **location,
                "country": location.get("country_code", ""),
                "timestamp": timestamp,
            }
        return result

    def _get_ip_location(self, ip_address: str) -> Dict[str, Any]:
        """
        Get location info from IP address.
        Uses a local MaxMind GeoIP2 database, or an opt-in remote API.
        Private, reserved and documentation ranges are never looked up.
        """
        try:
            ip = ipaddress.ip_address(ip_address)
        except ValueError:
            return {}
        if not ip.is_global:
            return {}
        try:
            if self._reader is not None:
                response = self._reader.city(ip_address)
                return {
                    "country_code": response.country.iso_code,
                    "country_name": response.country.name,
                    "region": response.subdivisions[0].iso_code if response.subdivisions else "",
                    "city": response.city.name or "",
                    "latitude": response.location.latitude,
                    "longitude": response.location.longitude,
                    "is_datacenter": False,
                }

            if not ALLOW_REMOTE_LOOKUP:
                return {}

            # Opt-in fallback to free IP API
            response = requests.get(f"https://ipapi.co/{ip_address}/json/", timeout=5)
            data = response.json()

            return {
                "country_code": data.get("country_code", ""),
                "country_name": data.get("country_name", ""),
                "region": data.get("region", ""),
                "city": data.get("city", ""),
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "is_datacenter": data.get("org", "").lower().find("datacenter") > -1,
            }

        except Exception as e:
            logger.error(f"Failed to get IP location for {ip_address}: {e}")
            return {}

    def _detect_vpn_proxy(self, location_data: Dict) -> Dict[str, Any]:
        """Detect if IP is from VPN/Proxy service"""
        try:
            # Check if location suggests VPN (e.g., VPN provider headquarters)
            city = location_data.get("city", "").lower()
            country = location_data.get("country_code", "")

            vpn_hubs = {
                "amsterdam": "NL",
                "bucharest": "RO",
                "hong kong": "HK",
                "panama city": "PA",
                "singapore": "SG",
            }

            for hub_city, hub_country in vpn_hubs.items():
                if hub_city in city or country == hub_country:
                    # Additional VPN indicator
                    return {"is_vpn": True, "provider": "Unknown VPN Service", "likelihood": "medium"}

            return {"is_vpn": False}

        except Exception as e:
            logger.error(f"VPN detection error: {e}")
            return {"is_vpn": False}

    def _cache_location(self, ip_address: str, location_data: Dict) -> None:
        """Cache IP location to avoid repeated lookups"""
        if len(self.ip_cache) >= self.max_cache_size:
            # Simple FIFO eviction
            oldest_key = next(iter(self.ip_cache))
            del self.ip_cache[oldest_key]

        self.ip_cache[ip_address] = location_data


# Global instance
geoip_validator = GeoIPValidator()
