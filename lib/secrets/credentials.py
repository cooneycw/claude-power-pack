"""Credential dataclasses with automatic masking.

This module provides typed credential containers that:
- Mask sensitive values in __repr__ and __str__
- Provide safe property access for display purposes
- Provide explicit methods for actual value access (use sparingly)

Usage:
    from lib.secrets.credentials import DatabaseCredentials

    creds = DatabaseCredentials.from_dict({
        "host": "localhost",
        "port": 5432,
        "database": "myapp",
        "username": "appuser",
        "password": "secret123"
    })

    print(creds)
    # DatabaseCredentials(host='localhost', port=5432, database='myapp',
    #                     username='appuser', password=SecretValue('****'))

    print(creds.connection_string)
    # postgresql://appuser:****@localhost:5432/myapp

    # For actual connection (use sparingly):
    dsn = creds.dsn  # Returns dict with real password

Pattern adapted from:
    nhl-api/src/nhl_api/config/secrets.py:42-69
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .base import SecretValue


@dataclass(frozen=True)
class DatabaseCredentials:
    """PostgreSQL/MySQL database connection credentials with masking.

    This dataclass stores database credentials securely:
    - Password is wrapped in SecretValue and excluded from repr
    - connection_string property shows masked password
    - dsn property returns real values for actual connections

    Attributes:
        host: Database server hostname or IP
        port: Database server port
        database: Database name
        username: Database username
        _password: Wrapped password (use .password property or .dsn)
    """

    host: str
    port: int
    database: str
    username: str
    _password: SecretValue = field(repr=False)

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        host_key: str = "host",
        port_key: str = "port",
        database_key: str = "database",
        username_key: str = "username",
        password_key: str = "password",
    ) -> "DatabaseCredentials":
        """Create DatabaseCredentials from a dictionary.

        Supports flexible key mapping for different secret formats.

        Args:
            data: Dictionary containing credential fields
            host_key: Key for host value (default: "host")
            port_key: Key for port value (default: "port")
            database_key: Key for database value (default: "database")
            username_key: Key for username value (default: "username")
            password_key: Key for password value (default: "password")

        Returns:
            DatabaseCredentials instance

        Example:
            # AWS RDS format
            creds = DatabaseCredentials.from_dict(
                data,
                host_key="POSTGRES_HOST",
                username_key="POSTGRES_USER",
                password_key="POSTGRES_PASSWORD"
            )
        """
        # Handle port as string or int
        port_val = data.get(port_key, 5432)
        if isinstance(port_val, str):
            port_val = int(port_val)

        return cls(
            host=data.get(host_key, "localhost"),
            port=port_val,
            database=data.get(database_key, ""),
            username=data.get(username_key, ""),
            _password=SecretValue(data.get(password_key)),
        )

    @property
    def password(self) -> Optional[str]:
        """Get the actual password value.

        WARNING: Use sparingly and never log the result.

        Returns:
            The actual password string.
        """
        return self._password.get_secret_value()

    @property
    def connection_string(self) -> str:
        """Return connection string with MASKED password for display.

        Safe to log or display - password is shown as ****.

        Returns:
            Connection string like: postgresql://user:****@host:port/database
        """
        return f"postgresql://{self.username}:****@{self.host}:{self.port}/{self.database}"

    @property
    def connection_string_real(self) -> str:
        """Return connection string with REAL password for actual connections.

        WARNING: Never log this! Use for actual database connections only.

        Returns:
            Connection string with real password.
        """
        return (
            f"postgresql://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @property
    def dsn(self) -> Dict[str, Any]:
        """Return connection parameters for database drivers.

        Use this for asyncpg.connect(), psycopg2.connect(), etc.
        Contains real password - don't log this dictionary.

        Returns:
            Dict with host, port, database, user, password keys.
        """
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.username,
            "password": self.password,
        }

    @property
    def dsn_masked(self) -> Dict[str, Any]:
        """Return connection parameters with masked password.

        Safe for logging or display.

        Returns:
            Dict with host, port, database, user, password (masked) keys.
        """
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.username,
            "password": "****",
        }

    def __repr__(self) -> str:
        """Return masked representation."""
        return (
            f"DatabaseCredentials(host='{self.host}', port={self.port}, "
            f"database='{self.database}', username='{self.username}', "
            f"password=SecretValue('****'))"
        )

    def __str__(self) -> str:
        """Return masked string representation."""
        return self.__repr__()


@dataclass(frozen=True)
class APICredentials:
    """API key credentials with masking.

    Attributes:
        _api_key: Wrapped API key (use .api_key property)
        base_url: Optional base URL for the API
        name: Optional identifier for this credential
    """

    _api_key: SecretValue = field(repr=False)
    base_url: str = ""
    name: str = ""

    @classmethod
    def from_value(
        cls,
        api_key: str,
        base_url: str = "",
        name: str = "",
    ) -> "APICredentials":
        """Create APICredentials from a raw API key.

        Args:
            api_key: The raw API key string
            base_url: Optional base URL
            name: Optional identifier

        Returns:
            APICredentials instance
        """
        return cls(
            _api_key=SecretValue(api_key),
            base_url=base_url,
            name=name,
        )

    @property
    def api_key(self) -> Optional[str]:
        """Get the actual API key value.

        WARNING: Use sparingly and never log the result.

        Returns:
            The actual API key string.
        """
        return self._api_key.get_secret_value()

    @property
    def masked_key(self) -> str:
        """Return a partially masked key for display.

        Shows first 4 and last 4 characters if key is long enough.

        Returns:
            Masked key like: "sk-Ab...xYz"
        """
        key = self._api_key.get_secret_value()
        if not key:
            return "****"
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"

    def __repr__(self) -> str:
        """Return masked representation."""
        parts = [f"api_key=SecretValue('****')"]
        if self.base_url:
            parts.append(f"base_url='{self.base_url}'")
        if self.name:
            parts.append(f"name='{self.name}'")
        return f"APICredentials({', '.join(parts)})"

    def __str__(self) -> str:
        """Return masked string representation."""
        return self.__repr__()
