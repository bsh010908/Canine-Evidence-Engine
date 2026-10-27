"""Read credentials only from the environment, never from source files."""

import os
from dataclasses import dataclass, field

from dotenv import dotenv_values


@dataclass(frozen=True)
class Settings:
    email: str = field(repr=False)
    api_key: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls) -> "Settings":
        # Explicit cwd path; do not search parent directories for credentials.
        values = {**dotenv_values(".env"), **os.environ}
        email = (values.get("NCBI_EMAIL") or "").strip()
        if not email or "@" not in email:
            raise ValueError("Set NCBI_EMAIL to your contact email before live requests")
        return cls(email=email, api_key=(values.get("NCBI_API_KEY") or "").strip() or None)
