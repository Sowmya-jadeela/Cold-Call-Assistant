import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client


# Locate backend/.env regardless of the terminal's working directory.
BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE)

supabase: Client | None = None


def initialize_database() -> Client | None:
    """Initialize the Supabase client using backend/.env."""

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()

    if not url or not key:
        return None

    if "YOUR_" in url.upper() or "YOUR_" in key.upper():
        return None

    try:
        return create_client(url, key)
    except Exception as exc:
        raise RuntimeError(
            "Could not initialize Supabase. Check SUPABASE_URL "
            "and SUPABASE_KEY in backend/.env."
        ) from exc


supabase = initialize_database()


def get_database() -> Client:
    """Return the configured Supabase client."""

    if supabase is None:
        raise RuntimeError(
            f"Supabase is not configured. Check this file: {ENV_FILE}"
        )

    return supabase