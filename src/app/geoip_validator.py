"""GeoIP validation for IP location verification"""

import logging
from typing import Dict, Any, Optional
from functools import lru_cache
import geoip2.database
import requests

logger = logging.getLogger(__name__)

# Known VPN/Proxy providers (ASN-based)
KNOWN_VPN_PROVIDERS = {
    "AS16509": "Amazon AWS",
    "AS8452": "TeData",
    "AS12389": "Rostelecom",
    "AS9498": "Azerbaijan",
}

# High-risk ASNs (datacenter IPs often used for fraud)
HIGH_RISK_ASNS = {
    "AS16509", "AS16621", "AS14061",  # AWS
    "AS8452", "AS9498",                # Generic datacenter
}

class GeoIPValidator:
    """Validate IP addresses and detect VPN/proxy usage"""
    
    def __init__(self):
        self.ip_cache: Dict[str, Dict] = {}
        self.max_cache_size = 10000
        
    def validate_ip_region_consistency(
        self, 
        ip_address: str, 
        claimed_region: str
    ) -> Dict[str, Any]:
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
            
            # Check region consistency
            if actual_country and actual_country != claimed_region.upper():
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
        self,
        user_id: str,
        current_ip: str,
        last_location: Dict,
        current_timestamp: float
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if user traveled impossible distance in given time.
        E.g., Seoul to New York in 1 hour = impossible without supersonic jet
        """
        try:
            current_location = self._get_ip_location(current_ip)
            
            if not (last_location and last_location.get("latitude")):
                return None
            
            # Calculate distance (Haversine formula)
            from math import radians, sin, cos, sqrt, atan2
            
            lat1, lon1 = radians(last_location["latitude"]), radians(last_location["longitude"])
            lat2, lon2 = radians(current_location["latitude"]), radians(current_location["longitude"])
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
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
                        "from": f"{last_location['city']}, {last_location['country']}",
                        "to": f"{current_location['city']}, {current_location['country']}",
                        "risk": "critical" if speed_kmh > 5000 else "high"
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Impossible travel detection error: {e}")
            return None
    
    def _get_ip_location(self, ip_address: str) -> Dict[str, Any]:
        """
        Get location info from IP address.
        Uses MaxMind GeoIP2 or fallback to IP API.
        """
        try:
            # Try MaxMind GeoIP2 database if available
            try:
                reader = geoip2.database.Reader('GeoLite2-City.mmdb')
                response = reader.city(ip_address)
                return {
                    "country_code": response.country.iso_code,
                    "country_name": response.country.name,
                    "region": response.subdivisions[0].iso_code if response.subdivisions else "",
                    "city": response.city.name or "",
                    "latitude": response.location.latitude,
                    "longitude": response.location.longitude,
                    "is_datacenter": False,
                }
            except:
                pass
            
            # Fallback to free IP API
            response = requests.get(
                f"https://ipapi.co/{ip_address}/json/",
                timeout=5
            )
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
                    return {
                        "is_vpn": True,
                        "provider": "Unknown VPN Service",
                        "likelihood": "medium"
                    }
            
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
