from urllib.parse import urlparse


def is_supported_google_maps_url(value: str) -> bool:
    """Return whether a URL is an intentionally supported Google Maps share URL."""
    try:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError:
        return False

    if parsed.scheme != "https" or parsed.username or parsed.password:
        return False
    if port not in (None, 443):
        return False
    if hostname == "maps.app.goo.gl":
        return bool(parsed.path.strip("/"))
    if hostname == "maps.google.com":
        return True
    return hostname in {"google.com", "www.google.com"} and (
        parsed.path == "/maps" or parsed.path.startswith("/maps/")
    )
