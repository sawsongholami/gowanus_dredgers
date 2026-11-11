"""Shared web downloads for the loaders, with automatic retries.

The outside sources (Open-Meteo, NOAA, Google Sheets, NYC Open Data, the
EPA Superfund site) now and then time out or answer with a server error
for a minute or two. get() retries those a few times, waiting longer
before each try, so a brief hiccup doesn't fail the daily load. A source
that stays down still fails after the last try.

Only GET requests are retried: asking for the same data twice is harmless.
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Seconds to wait for a server to answer. Without a timeout, requests waits
# forever, and a stalled source would hang the run until GitHub kills it.
DEFAULT_TIMEOUT = 60

# Server answers worth trying again: rate limited, or a temporary server error.
RETRY_STATUSES = (429, 500, 502, 503, 504)


def make_session(retries: int = 4, backoff: float = 5) -> requests.Session:
    """A session that retries timeouts, dropped connections and the
    RETRY_STATUSES. With the defaults it waits 0, 10, 20 and 40 seconds
    before the four retries."""
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=RETRY_STATUSES,
        allowed_methods=['GET'],
        respect_retry_after_header=True,
        # After the last try, hand back the server's answer instead of
        # raising, so each loader's own error message still applies.
        raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


_session = make_session()


def get(url: str, timeout: float = DEFAULT_TIMEOUT, **kwargs) -> requests.Response:
    """requests.get with retries and a default timeout."""
    return _session.get(url, timeout=timeout, **kwargs)
