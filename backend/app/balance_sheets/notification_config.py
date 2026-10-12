import os
from urllib.parse import urlparse

# Deployment-wide webhook secret. It is intentionally environment-backed rather
# than stored in company settings or returned by an API response.
_configured_webhook_url = os.getenv("ANALYSIS_ALERT_WEBHOOK_URL", "").strip()
_parsed_webhook_url = urlparse(_configured_webhook_url)
ANALYSIS_ALERT_WEBHOOK_URL = (
    _configured_webhook_url
    if _parsed_webhook_url.scheme == "https" and bool(_parsed_webhook_url.netloc)
    else ""
)
