import os
from pathlib import Path

from dotenv import load_dotenv

# This app's own settings, kept separate from mystic_auth.core.settings.Settings
# rather than added to it, since that module is a mystic_auth internal, and this
# app's own env vars (Groq credentials) have nothing to do with the
# auth/authorization template itself. Loaded the same way the pre-migration
# repo did (root .env via python-dotenv), independent of Settings' own
# pydantic-settings loading.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("GROQ_API_KEY", ""))
# Providers supported by the app use the OpenAI-compatible chat completions contract.
LLM_API_URL = os.getenv("LLM_API_URL", os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions"))
LLM_MODEL = os.getenv("LLM_MODEL", os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"))
# Backward-compatible names for existing deployment configuration.
GROQ_API_KEY = LLM_API_KEY
GROQ_API_URL = LLM_API_URL
GROQ_MODEL = LLM_MODEL
try:
    GROQ_MAX_TOKENS = max(128, min(int(os.getenv("LLM_MAX_TOKENS", os.getenv("GROQ_MAX_TOKENS", "800"))), 4000))
except ValueError:
    GROQ_MAX_TOKENS = 800
try:
    LLM_DAILY_CHAR_BUDGET = max(10_000, min(int(os.getenv("LLM_DAILY_CHAR_BUDGET", "500000")), 10_000_000))
except ValueError:
    LLM_DAILY_CHAR_BUDGET = 500_000
