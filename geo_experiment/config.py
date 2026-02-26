"""Configuration management — loads .env vars and sets up LiteLLM / Azure."""

import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _parse_azure_base() -> tuple[str, str]:
    """Extract base URL and API version from the full Azure endpoint URL."""
    raw = os.getenv("AZURE_API_BASE", "")
    parsed = urlparse(raw)
    base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else raw
    query_params = parse_qs(parsed.query)
    api_version = query_params.get("api-version", ["2024-02-01"])[0]
    return base_url, api_version


AZURE_API_BASE, AZURE_API_VERSION = _parse_azure_base()
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME", "gpt-5")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

LITELLM_MODEL = f"azure/{AZURE_DEPLOYMENT_NAME}"

# LiteLLM reads these env vars automatically for Azure calls
os.environ["AZURE_API_KEY"] = AZURE_API_KEY
os.environ["AZURE_API_BASE"] = AZURE_API_BASE
os.environ["AZURE_API_VERSION"] = AZURE_API_VERSION

REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def validate_config() -> None:
    """Raise early if required env vars are missing."""
    missing = []
    if not AZURE_API_KEY:
        missing.append("AZURE_OPENAI_API_KEY")
    if not AZURE_API_BASE:
        missing.append("AZURE_API_BASE")
    if not TAVILY_API_KEY:
        missing.append("TAVILY_API_KEY")
    if missing:
        raise EnvironmentError(
            "Missing required environment variables:\n"
            + "\n".join(f"  - {v}" for v in missing)
        )
