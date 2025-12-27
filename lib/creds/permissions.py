"""Permission model for database operations.

This module provides access control for database operations:
- AccessLevel: Enum defining read/write/admin access
- OperationType: Enum of SQL operation types
- PermissionConfig: Configuration for session permissions

Default behavior is READ_ONLY to prevent accidental data modification.
Write operations require explicit permission upgrade.

SECURITY NOTE - SQL Injection Prevention:
    This module controls WHAT operations are allowed, but does NOT prevent
    SQL injection. Always use parameterized queries:

    ✅ SAFE:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})

    ❌ UNSAFE (SQL injection vulnerable):
        cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
        cursor.execute("SELECT * FROM users WHERE id = " + user_id)

    The permission system should be used ALONGSIDE parameterized queries,
    not as a replacement for them.

Usage:
    from lib.creds.permissions import PermissionConfig, AccessLevel, OperationType

    # Default: read-only
    config = PermissionConfig()
    allowed, reason = config.can_execute(OperationType.SELECT, "users")
    # (True, "Allowed")

    allowed, reason = config.can_execute(OperationType.DELETE, "users")
    # (False, "Operation delete requires admin access")

    # Upgrade to read-write
    config = PermissionConfig(access_level=AccessLevel.READ_WRITE)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class AccessLevel(Enum):
    """Database access levels.

    Levels are hierarchical:
    - READ_ONLY < READ_WRITE < ADMIN

    Each level includes permissions of lower levels.
    """

    READ_ONLY = "read"  # SELECT only
    READ_WRITE = "write"  # SELECT, INSERT, UPDATE, CREATE
    ADMIN = "admin"  # All operations including DELETE, DROP, TRUNCATE, ALTER


class OperationType(Enum):
    """SQL operation types with risk classification."""

    # Read operations (safe)
    SELECT = "select"
    EXPLAIN = "explain"

    # Write operations (require READ_WRITE)
    INSERT = "insert"
    UPDATE = "update"
    CREATE = "create"
    COPY = "copy"  # COPY ... FROM

    # Destructive operations (require ADMIN)
    DELETE = "delete"
    DROP = "drop"
    TRUNCATE = "truncate"
    ALTER = "alter"

    # Very dangerous operations (require ADMIN + confirmation)
    DROP_DATABASE = "drop_database"
    DROP_TABLE = "drop_table"
    TRUNCATE_TABLE = "truncate_table"


# Map operations to minimum required access level
OPERATION_ACCESS: dict[OperationType, AccessLevel] = {
    # Read operations
    OperationType.SELECT: AccessLevel.READ_ONLY,
    OperationType.EXPLAIN: AccessLevel.READ_ONLY,
    # Write operations
    OperationType.INSERT: AccessLevel.READ_WRITE,
    OperationType.UPDATE: AccessLevel.READ_WRITE,
    OperationType.CREATE: AccessLevel.READ_WRITE,
    OperationType.COPY: AccessLevel.READ_WRITE,
    # Destructive operations
    OperationType.DELETE: AccessLevel.ADMIN,
    OperationType.DROP: AccessLevel.ADMIN,
    OperationType.TRUNCATE: AccessLevel.ADMIN,
    OperationType.ALTER: AccessLevel.ADMIN,
    OperationType.DROP_DATABASE: AccessLevel.ADMIN,
    OperationType.DROP_TABLE: AccessLevel.ADMIN,
    OperationType.TRUNCATE_TABLE: AccessLevel.ADMIN,
}

# Access level ordering for comparisons
ACCESS_LEVEL_ORDER = {
    AccessLevel.READ_ONLY: 0,
    AccessLevel.READ_WRITE: 1,
    AccessLevel.ADMIN: 2,
}


def access_level_gte(current: AccessLevel, required: AccessLevel) -> bool:
    """Check if current access level is >= required level."""
    return ACCESS_LEVEL_ORDER[current] >= ACCESS_LEVEL_ORDER[required]


@dataclass
class PermissionConfig:
    """Permission configuration for a database session.

    Controls what operations are allowed based on:
    - Access level (read/write/admin)
    - Table whitelist/blacklist
    - Operations requiring user confirmation

    Default is READ_ONLY with confirmation required for destructive ops.

    Example:
        # Read-only access
        config = PermissionConfig()

        # Read-write access to specific tables
        config = PermissionConfig(
            access_level=AccessLevel.READ_WRITE,
            allowed_tables=["users", "orders"],
        )

        # Admin access (use with caution)
        config = PermissionConfig(access_level=AccessLevel.ADMIN)
    """

    access_level: AccessLevel = AccessLevel.READ_ONLY
    allowed_tables: Optional[List[str]] = None  # None = all tables allowed
    denied_tables: Optional[List[str]] = None  # Explicit deny list
    require_confirmation: List[OperationType] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Set default confirmation requirements if not specified."""
        if not self.require_confirmation:
            # Default: require confirmation for destructive operations
            self.require_confirmation = [
                OperationType.DELETE,
                OperationType.DROP,
                OperationType.DROP_DATABASE,
                OperationType.DROP_TABLE,
                OperationType.TRUNCATE,
                OperationType.TRUNCATE_TABLE,
                OperationType.ALTER,
            ]

    def can_execute(
        self,
        operation: OperationType,
        table: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Check if an operation is allowed.

        Args:
            operation: The SQL operation type.
            table: Optional table name (for table-level restrictions).

        Returns:
            Tuple of (allowed: bool, reason: str).
            If allowed, reason is "Allowed".
            If denied, reason explains why.
        """
        # Check access level
        required = OPERATION_ACCESS.get(operation, AccessLevel.ADMIN)
        if not access_level_gte(self.access_level, required):
            return False, f"Operation {operation.value} requires {required.value} access"

        # Check table restrictions
        if table:
            # Denied tables take precedence
            if self.denied_tables and table.lower() in [
                t.lower() for t in self.denied_tables
            ]:
                return False, f"Table '{table}' is in deny list"

            # Check allowed tables (if whitelist is set)
            if self.allowed_tables is not None:
                if table.lower() not in [t.lower() for t in self.allowed_tables]:
                    return False, f"Table '{table}' is not in allow list"

        return True, "Allowed"

    def needs_confirmation(self, operation: OperationType) -> bool:
        """Check if operation requires user confirmation.

        Args:
            operation: The SQL operation type.

        Returns:
            True if user confirmation should be requested.
        """
        return operation in self.require_confirmation

    def describe(self) -> str:
        """Return human-readable description of permissions.

        Returns:
            Multi-line description of current permissions.
        """
        lines = [f"Access Level: {self.access_level.value}"]

        if self.allowed_tables:
            lines.append(f"Allowed Tables: {', '.join(self.allowed_tables)}")
        else:
            lines.append("Allowed Tables: ALL")

        if self.denied_tables:
            lines.append(f"Denied Tables: {', '.join(self.denied_tables)}")

        if self.require_confirmation:
            ops = [op.value for op in self.require_confirmation]
            lines.append(f"Requires Confirmation: {', '.join(ops)}")

        return "\n".join(lines)

    @classmethod
    def read_only(cls, tables: Optional[List[str]] = None) -> "PermissionConfig":
        """Create read-only configuration.

        Args:
            tables: Optional list of allowed tables.

        Returns:
            Read-only PermissionConfig.
        """
        return cls(access_level=AccessLevel.READ_ONLY, allowed_tables=tables)

    @classmethod
    def read_write(
        cls,
        tables: Optional[List[str]] = None,
        denied_tables: Optional[List[str]] = None,
    ) -> "PermissionConfig":
        """Create read-write configuration.

        Args:
            tables: Optional list of allowed tables.
            denied_tables: Optional list of denied tables.

        Returns:
            Read-write PermissionConfig.
        """
        return cls(
            access_level=AccessLevel.READ_WRITE,
            allowed_tables=tables,
            denied_tables=denied_tables,
        )

    @classmethod
    def admin(cls, require_confirmation: bool = True) -> "PermissionConfig":
        """Create admin configuration.

        Args:
            require_confirmation: If True, still require confirmation for
                                  destructive operations.

        Returns:
            Admin PermissionConfig.
        """
        config = cls(access_level=AccessLevel.ADMIN)
        if not require_confirmation:
            config.require_confirmation = []
        return config
