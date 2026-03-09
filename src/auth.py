"""Google OAuth2 authentication with token caching."""

import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
TOKEN_FILE = "token.json"


def get_credentials(credentials_path: str) -> Credentials:
    """Load or create OAuth2 credentials, caching the token locally.

    Args:
        credentials_path: Path to the credentials.json downloaded from Google Cloud Console.

    Returns:
        Valid Google OAuth2 Credentials object.

    Raises:
        FileNotFoundError: If credentials.json does not exist at the given path.
    """
    creds_file = Path(credentials_path)
    if not creds_file.exists():
        raise FileNotFoundError(
            f"credentials.json not found at '{credentials_path}'.\n"
            "Download it from Google Cloud Console → APIs & Services → Credentials.\n"
            "See README.md for full instructions."
        )

    creds: Credentials | None = None

    # Reuse cached token if it exists
    token_path = Path(TOKEN_FILE)
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Refresh expired token, or run full OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
            creds = flow.run_local_server(port=0)

        # Persist token for future runs
        with open(token_path, "w") as fh:
            fh.write(creds.to_json())

    return creds
