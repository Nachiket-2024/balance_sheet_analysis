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

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# Groq's OpenAI-compatible chat completions endpoint.
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
