import requests
import random

NHL_DOMAIN = "statsapi.web.nhl.com"
BASE_PATH = "/api/v1"

# Multiple Akamai CDN IPs for fallback (DNS not required)
AKAMAI_IPS = [
    "23.217.138.110",
    "23.217.138.111",
    "23.217.138.112",
    "23.217.138.113",
]

LAST_WORKING_IP = None


def try_request(url, headers, verify):
    """Low-level fetch with error handling."""
    try:
        resp = requests.get(url, headers=headers, timeout=6, verify=verify)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def try_via_ip(ip, endpoint):
    """Use direct Akamai IP with Host spoofing to bypass DNS."""
    url = f"https://{ip}{BASE_PATH}{endpoint}"
    headers = {
        "Host": NHL_DOMAIN,
        "User-Agent": "FantasyHockey/1.0"
    }
    return try_request(url, headers, verify=False)


def nhl_get(endpoint):
    """Robust NHL API accessor with domain + IP failover."""
    global LAST_WORKING_IP

    # Step 1 — Try normal domain (best security)
    url = f"https://{NHL_DOMAIN}{BASE_PATH}{endpoint}"
    data = try_request(url, {"User-Agent": "FantasyHockey/1.0"}, verify=True)
    if data:
        return data

    # Step 2 — Try cached working IP
    if LAST_WORKING_IP:
        data = try_via_ip(LAST_WORKING_IP, endpoint)
        if data:
            return data

    # Step 3 — Try all IP fallbacks
    random.shuffle(AKAMAI_IPS)
    for ip in AKAMAI_IPS:
        data = try_via_ip(ip, endpoint)
        if data:
            LAST_WORKING_IP = ip
            return data

    raise Exception("NHL API unreachable via domain or IP fallback.")
