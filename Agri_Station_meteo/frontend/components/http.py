"""
http.py — Shared requests Session with retry/backoff for frontend

Provides `session`, `http_get` and `http_post` helpers so all frontend
network calls reuse a single Session configured with retries.
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure retries: idempotent methods + POST allowed (some servers safe)
RETRY_STRATEGY = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]),
    backoff_factor=0.6,
    raise_on_status=False,
)

session = requests.Session()
adapter = HTTPAdapter(max_retries=RETRY_STRATEGY)
session.mount("https://", adapter)
session.mount("http://", adapter)

# Default timeout (seconds) used by helpers when not overridden
DEFAULT_TIMEOUT = 20


def http_get(url, params=None, timeout=None, **kwargs):
    to = timeout or DEFAULT_TIMEOUT
    return session.get(url, params=params, timeout=to, **kwargs)


def http_post(url, json=None, data=None, timeout=None, **kwargs):
    to = timeout or DEFAULT_TIMEOUT
    return session.post(url, json=json, data=data, timeout=to, **kwargs)
