"""
Configuration management for ApexVol MCP Server.

Uses REST API calls to ApexVol platform - no local provider imports needed.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Server configuration."""

    # API URL for ApexVol platform
    api_url: str = os.getenv('APEXVOL_API_URL', 'https://apexvol.com')

    # API token for authentication
    api_token: str = os.getenv('APEXVOL_API_TOKEN', '')

    @classmethod
    def validate(cls) -> list[str]:
        """
        Validate configuration and return list of errors.
        """
        errors = []

        if not cls.api_token:
            errors.append("APEXVOL_API_TOKEN is required")
        elif not cls.api_token.startswith('avmcp_'):
            errors.append("APEXVOL_API_TOKEN must start with 'avmcp_'")

        return errors


config = Config()
