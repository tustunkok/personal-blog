import asyncio
import json
import urllib.request

IP_API_URL = "http://ip-api.com/json/{}?fields=status,country,countryCode,city,regionName,isp,lat,lon"


def _fetch_geo(ip: str) -> dict | None:
    try:
        req = urllib.request.Request(IP_API_URL.format(ip))
        req.add_header("User-Agent", "personal-blog/1.0")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "success":
                return {
                    "country": data.get("countryCode"),
                    "city": data.get("city"),
                    "region": data.get("regionName"),
                    "isp": data.get("isp"),
                    "latitude": data.get("lat"),
                    "longitude": data.get("lon"),
                }
    except Exception:
        pass
    return None


def lookup_ip(ip: str) -> dict | None:
    if ip in ("127.0.0.1", "::1", "", None):
        return None
    return _fetch_geo(ip)


async def lookup_ip_async(ip: str) -> dict | None:
    if ip in ("127.0.0.1", "::1", "", None):
        return None
    return await asyncio.to_thread(_fetch_geo, ip)
