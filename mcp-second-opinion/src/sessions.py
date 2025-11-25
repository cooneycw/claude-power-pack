"""Session management for multi-turn consultations with Gemini."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A single message in a consultation session."""

    role: str  # "user" | "assistant" | "tool_result"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tokens: Optional[Dict[str, int]] = None
    cost: float = 0.0


@dataclass
class Session:
    """A consultation session with Gemini."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    purpose: str = "code_review"
    created_at: datetime = field(default_factory=datetime.now)
    messages: List[Message] = field(default_factory=list)
    max_turns: int = field(default_factory=lambda: Config.DEFAULT_MAX_TURNS)
    cost_limit: float = field(default_factory=lambda: Config.DEFAULT_SESSION_COST_LIMIT)
    tools_enabled: List[str] = field(default_factory=list)
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    status: str = "active"  # active | closed | exceeded_limit
    summary: Optional[str] = None

    @property
    def turn_count(self) -> int:
        """Count user turns (messages with role='user')."""
        return len([m for m in self.messages if m.role == "user"])

    @property
    def total_tokens(self) -> int:
        """Total tokens used in session."""
        return self.total_input_tokens + self.total_output_tokens

    @property
    def remaining_turns(self) -> int:
        """Remaining turns before max_turns limit."""
        return max(0, self.max_turns - self.turn_count)

    @property
    def remaining_budget(self) -> float:
        """Remaining budget before cost_limit."""
        return max(0.0, self.cost_limit - self.total_cost)

    @property
    def budget_used_percent(self) -> float:
        """Percentage of budget used."""
        if self.cost_limit == 0:
            return 0.0
        return (self.total_cost / self.cost_limit) * 100

    @property
    def turns_used_percent(self) -> float:
        """Percentage of turns used."""
        if self.max_turns == 0:
            return 0.0
        return (self.turn_count / self.max_turns) * 100

    def can_continue(self) -> bool:
        """Check if session can accept more messages."""
        if self.status != "active":
            return False
        if self.turn_count >= self.max_turns:
            return False
        if self.total_cost >= self.cost_limit:
            return False
        return True

    def should_warn(self) -> bool:
        """Check if session is approaching limits."""
        return (
            self.budget_used_percent >= Config.COST_WARNING_THRESHOLD * 100
            or self.turns_used_percent >= Config.COST_WARNING_THRESHOLD * 100
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for API responses."""
        return {
            "session_id": self.id,
            "purpose": self.purpose,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "turn_count": self.turn_count,
            "max_turns": self.max_turns,
            "remaining_turns": self.remaining_turns,
            "total_cost": round(self.total_cost, 5),
            "cost_limit": self.cost_limit,
            "remaining_budget": round(self.remaining_budget, 5),
            "budget_used_percent": round(self.budget_used_percent, 1),
            "turns_used_percent": round(self.turns_used_percent, 1),
            "tools_enabled": self.tools_enabled,
            "total_tokens": {
                "input": self.total_input_tokens,
                "output": self.total_output_tokens,
                "total": self.total_tokens,
            },
        }


class SessionManager:
    """Manages session lifecycle and persistence."""

    def __init__(self, persist_dir: Optional[str] = None):
        """
        Initialize session manager.

        Args:
            persist_dir: Directory for session persistence (optional, for future use)
        """
        self._sessions: Dict[str, Session] = {}
        self._persist_dir = persist_dir
        self._daily_cost: float = 0.0
        self._daily_cost_reset: datetime = datetime.now()

    def _check_daily_limit(self) -> bool:
        """Check if daily spending limit has been reached."""
        # Reset daily counter if it's a new day
        if self._daily_cost_reset.date() < datetime.now().date():
            self._daily_cost = 0.0
            self._daily_cost_reset = datetime.now()

        return self._daily_cost < Config.GLOBAL_DAILY_LIMIT

    async def create(
        self,
        purpose: str = "code_review",
        max_turns: Optional[int] = None,
        cost_limit: Optional[float] = None,
        tools_enabled: Optional[List[str]] = None,
    ) -> Session:
        """
        Create a new consultation session.

        Args:
            purpose: Session purpose (code_review, architecture, debugging, brainstorm)
            max_turns: Maximum conversation turns (default from config)
            cost_limit: Maximum cost for session (default from config)
            tools_enabled: List of tools Gemini can use

        Returns:
            New Session object
        """
        if not self._check_daily_limit():
            raise ValueError(
                f"Daily spending limit (${Config.GLOBAL_DAILY_LIMIT}) reached. "
                "Try again tomorrow or increase GLOBAL_DAILY_LIMIT."
            )

        session = Session(
            purpose=purpose,
            max_turns=max_turns or Config.DEFAULT_MAX_TURNS,
            cost_limit=cost_limit or Config.DEFAULT_SESSION_COST_LIMIT,
            tools_enabled=tools_enabled or ["web_search", "fetch_url"],
        )

        self._sessions[session.id] = session
        logger.info(f"Created session {session.id} for {purpose}")

        return session

    async def get(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session if found, None otherwise
        """
        return self._sessions.get(session_id)

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tokens: Optional[Dict[str, int]] = None,
        cost: float = 0.0,
    ) -> Message:
        """
        Add a message to a session.

        Args:
            session_id: Session identifier
            role: Message role (user, assistant, tool_result)
            content: Message content
            tool_calls: List of tool calls made (for assistant messages)
            tokens: Token counts for this message
            cost: Cost of this message

        Returns:
            The created Message object

        Raises:
            ValueError: If session not found or cannot accept messages
        """
        session = await self.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if not session.can_continue():
            raise ValueError(
                f"Session {session_id} cannot accept more messages. "
                f"Status: {session.status}, Turns: {session.turn_count}/{session.max_turns}, "
                f"Cost: ${session.total_cost:.4f}/${session.cost_limit}"
            )

        message = Message(
            role=role,
            content=content,
            tool_calls=tool_calls,
            tokens=tokens,
            cost=cost,
        )

        session.messages.append(message)

        # Update session totals
        if tokens:
            session.total_input_tokens += tokens.get("input", 0)
            session.total_output_tokens += tokens.get("output", 0)

        session.total_cost += cost
        self._daily_cost += cost

        # Check if limits exceeded after this message
        if session.total_cost >= session.cost_limit:
            session.status = "exceeded_limit"
            logger.warning(f"Session {session_id} exceeded cost limit")
        elif session.turn_count >= session.max_turns:
            session.status = "exceeded_limit"
            logger.warning(f"Session {session_id} exceeded turn limit")

        logger.debug(
            f"Added {role} message to session {session_id}: "
            f"tokens={tokens}, cost=${cost:.5f}"
        )

        return message

    async def close(
        self,
        session_id: str,
        summary: Optional[str] = None,
    ) -> Session:
        """
        Close a session.

        Args:
            session_id: Session identifier
            summary: Optional summary of the session

        Returns:
            The closed Session object

        Raises:
            ValueError: If session not found
        """
        session = await self.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.status = "closed"
        session.summary = summary

        logger.info(
            f"Closed session {session_id}: "
            f"{session.turn_count} turns, "
            f"${session.total_cost:.4f} cost, "
            f"{session.total_tokens} tokens"
        )

        return session

    async def list_sessions(
        self,
        status: str = "all",
        limit: int = 10,
    ) -> List[Session]:
        """
        List sessions filtered by status.

        Args:
            status: Filter by status (active, closed, all)
            limit: Maximum number of sessions to return

        Returns:
            List of Session objects
        """
        sessions = list(self._sessions.values())

        if status != "all":
            sessions = [s for s in sessions if s.status == status]

        # Sort by creation time, newest first
        sessions.sort(key=lambda s: s.created_at, reverse=True)

        return sessions[:limit]

    async def get_history(
        self,
        session_id: str,
        include_tool_calls: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session identifier
            include_tool_calls: Whether to include tool call details

        Returns:
            List of message dictionaries

        Raises:
            ValueError: If session not found
        """
        session = await self.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        history = []
        for msg in session.messages:
            entry = {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "tokens": msg.tokens,
                "cost": round(msg.cost, 5),
            }
            if include_tool_calls and msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            history.append(entry)

        return history

    def get_daily_stats(self) -> Dict[str, Any]:
        """Get daily usage statistics."""
        return {
            "daily_cost": round(self._daily_cost, 4),
            "daily_limit": Config.GLOBAL_DAILY_LIMIT,
            "daily_remaining": round(Config.GLOBAL_DAILY_LIMIT - self._daily_cost, 4),
            "active_sessions": len([s for s in self._sessions.values() if s.status == "active"]),
            "total_sessions": len(self._sessions),
        }


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get or create the global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
