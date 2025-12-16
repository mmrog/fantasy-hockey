import requests
import random

# Modern NHL web API (this is what you've been curling successfully)
NHL_DOMAIN = "api-web.nhle.com"
BASE_PATH = "/v1"

# Optional: Akamai/CDN IPs for fallback if DNS breaks again
AKAMAI_IPS = [
    "23.217.138.110",
    "23.217.138.111",
    "23.217.138.112",
    "23.217.138.113",
]

LAST_WORKING_IP = None

# Browser-like headers (needed for some endpoints like /player/.../landing)
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}


def try_request(url, headers, verify: bool):
    """
    Low-level helper with:
      - DEFAULT_HEADERS merged in
      - short timeout
      - JSON decode guarded
    """
    merged_headers = DEFAULT_HEADERS.copy()
    merged_headers.update(headers or {})

    try:
        resp = requests.get(url, headers=merged_headers, timeout=6, verify=verify)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def try_via_ip(ip: str, endpoint: str):
    """
    Use direct IP + Host spoofing as a fallback if DNS breaks.
    """
    url = f"https://{ip}{BASE_PATH}{endpoint}"
    headers = {
        "Host": NHL_DOMAIN,
    }
    return try_request(url, headers, verify=False)


def nhl_get(endpoint: str):
    """
    Main NHL accessor used everywhere else in your app.

    Tries:
      1. Normal domain with proper headers
      2. Last known working IP (if any)
      3. All fallback IPs
    """
    global LAST_WORKING_IP

    # 1) Normal domain (best case)
    url = f"https://{NHL_DOMAIN}{BASE_PATH}{endpoint}"
    data = try_request(url, {}, verify=True)
    if data:
        return data

    # 2) Cached working IP
    if LAST_WORKING_IP:
        data = try_via_ip(LAST_WORKING_IP, endpoint)
        if data:
            return data

    # 3) Cycle all fallback IPs
    random.shuffle(AKAMAI_IPS)
    for ip in AKAMAI_IPS:
        data = try_via_ip(ip, endpoint)
        if data:
            LAST_WORKING_IP = ip
            return data

    raise Exception("NHL API unreachable via domain or fallback IPs.")
