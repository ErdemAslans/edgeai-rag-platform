"""Conversation Memory service for multi-turn chat context management."""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from collections import OrderedDict

import structlog

logger = structlog.get_logger()


@dataclass
class Message:
    """A single message in a conversation."""
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class Conversation:
    """A conversation containing multiple messages."""
    id: str
    user_id: str
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    title: Optional[str] = None
    document_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    MAX_MESSAGES = 100
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> Message:
        """Add a message to the conversation."""
        msg = Message(role=role, content=content, metadata=metadata or {})
        self.messages.append(msg)
        self.updated_at = datetime.utcnow()
        
        if len(self.messages) > self.MAX_MESSAGES:
            self.messages = self.messages[-self.MAX_MESSAGES:]
        
        return msg
    
    def add_user_message(self, content: str, metadata: Optional[Dict] = None) -> Message:
        """Add a user message."""
        return self.add_message("user", content, metadata)
    
    def add_assistant_message(self, content: str, metadata: Optional[Dict] = None) -> Message:
        """Add an assistant message."""
        return self.add_message("assistant", content, metadata)
    
    def add_system_message(self, content: str, metadata: Optional[Dict] = None) -> Message:
        """Add a system message."""
        return self.add_message("system", content, metadata)
    
    def get_messages_for_llm(self, max_messages: int = 20) -> List[Dict[str, str]]:
        """Get messages formatted for LLM API.
        
        Args:
            max_messages: Maximum recent messages to include.
            
        Returns:
            List of message dicts with role and content.
        """
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        return [{"role": m.role, "content": m.content} for m in recent]
    
    def get_context_summary(self, max_chars: int = 2000) -> str:
        """Get a summary of conversation context.
        
        Args:
            max_chars: Maximum characters for summary.
            
        Returns:
            Concatenated recent messages as context.
        """
        context_parts = []
        total_chars = 0
        
        for msg in reversed(self.messages):
            msg_text = f"{msg.role}: {msg.content}"
            if total_chars + len(msg_text) > max_chars:
                break
            context_parts.insert(0, msg_text)
            total_chars += len(msg_text)
        
        return "\n".join(context_parts)
    
    def get_last_user_query(self) -> Optional[str]:
        """Get the last user message."""
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg.content
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "title": self.title,
            "document_ids": self.document_ids,
            "metadata": self.metadata,
        }


class ConversationMemory:
    """In-memory conversation storage with TTL."""
    
    MAX_CONVERSATIONS_PER_USER = 50
    MAX_TOTAL_CONVERSATIONS = 10000
    CONVERSATION_TTL_HOURS = 24
    
    def __init__(self):
        self._conversations: OrderedDict[str, Conversation] = OrderedDict()
        self._user_conversations: Dict[str, List[str]] = {}
    
    def create_conversation(
        self,
        user_id: str,
        document_ids: Optional[List[str]] = None,
        title: Optional[str] = None,
    ) -> Conversation:
        """Create a new conversation.
        
        Args:
            user_id: User ID.
            document_ids: Optional list of document IDs to associate.
            title: Optional conversation title.
            
        Returns:
            New Conversation instance.
        """
        conv_id = str(uuid.uuid4())
        conv = Conversation(
            id=conv_id,
            user_id=user_id,
            document_ids=document_ids or [],
            title=title,
        )
        
        self._conversations[conv_id] = conv
        
        if user_id not in self._user_conversations:
            self._user_conversations[user_id] = []
        self._user_conversations[user_id].append(conv_id)
        
        if len(self._user_conversations[user_id]) > self.MAX_CONVERSATIONS_PER_USER:
            oldest_id = self._user_conversations[user_id].pop(0)
            self._conversations.pop(oldest_id, None)
        
        if len(self._conversations) > self.MAX_TOTAL_CONVERSATIONS:
            oldest_key = next(iter(self._conversations))
            oldest_conv = self._conversations.pop(oldest_key)
            if oldest_conv.user_id in self._user_conversations:
                self._user_conversations[oldest_conv.user_id] = [
                    c for c in self._user_conversations[oldest_conv.user_id]
                    if c != oldest_key
                ]
        
        logger.info(
            "Created conversation",
            conversation_id=conv_id,
            user_id=user_id,
        )
        
        return conv
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        conv = self._conversations.get(conversation_id)
        
        if conv:
            cutoff = datetime.utcnow() - timedelta(hours=self.CONVERSATION_TTL_HOURS)
            if conv.updated_at < cutoff:
                self.delete_conversation(conversation_id)
                return None
        
        return conv
    
    def get_user_conversations(
        self,
        user_id: str,
        limit: int = 20,
    ) -> List[Conversation]:
        """Get conversations for a user.
        
        Args:
            user_id: User ID.
            limit: Maximum conversations to return.
            
        Returns:
            List of conversations, most recent first.
        """
        conv_ids = self._user_conversations.get(user_id, [])
        conversations = []
        
        cutoff = datetime.utcnow() - timedelta(hours=self.CONVERSATION_TTL_HOURS)
        
        for conv_id in reversed(conv_ids):
            conv = self._conversations.get(conv_id)
            if conv and conv.updated_at >= cutoff:
                conversations.append(conv)
                if len(conversations) >= limit:
                    break
        
        return conversations
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        conv = self._conversations.pop(conversation_id, None)
        
        if conv:
            if conv.user_id in self._user_conversations:
                self._user_conversations[conv.user_id] = [
                    c for c in self._user_conversations[conv.user_id]
                    if c != conversation_id
                ]
            return True
        
        return False
    
    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> Optional[Message]:
        """Add a message to a conversation.
        
        Args:
            conversation_id: Conversation ID.
            role: Message role (user/assistant/system).
            content: Message content.
            metadata: Optional metadata.
            
        Returns:
            Created Message or None if conversation not found.
        """
        conv = self.get_conversation(conversation_id)
        if not conv:
            return None
        
        msg = conv.add_message(role, content, metadata)
        
        if conv.title is None and role == "user" and len(conv.messages) == 1:
            conv.title = content[:50] + ("..." if len(content) > 50 else "")
        
        return msg
    
    def get_or_create_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
    ) -> Conversation:
        """Get existing conversation or create new one.
        
        Args:
            user_id: User ID.
            conversation_id: Optional existing conversation ID.
            document_ids: Document IDs for new conversation.
            
        Returns:
            Conversation instance.
        """
        if conversation_id:
            conv = self.get_conversation(conversation_id)
            if conv and conv.user_id == user_id:
                return conv
        
        return self.create_conversation(user_id, document_ids)
    
    def cleanup_expired(self) -> int:
        """Remove expired conversations."""
        cutoff = datetime.utcnow() - timedelta(hours=self.CONVERSATION_TTL_HOURS)
        expired = [
            conv_id for conv_id, conv in self._conversations.items()
            if conv.updated_at < cutoff
        ]
        
        for conv_id in expired:
            self.delete_conversation(conv_id)
        
        if expired:
            logger.info("Cleaned up expired conversations", count=len(expired))
        
        return len(expired)
    
    def get_stats(self) -> Dict[str, int]:
        """Get memory stats."""
        return {
            "total_conversations": len(self._conversations),
            "total_users": len(self._user_conversations),
            "max_conversations": self.MAX_TOTAL_CONVERSATIONS,
        }


_conversation_memory: Optional[ConversationMemory] = None


def get_conversation_memory() -> ConversationMemory:
    """Get the singleton conversation memory instance."""
    global _conversation_memory
    if _conversation_memory is None:
        _conversation_memory = ConversationMemory()
    return _conversation_memory
