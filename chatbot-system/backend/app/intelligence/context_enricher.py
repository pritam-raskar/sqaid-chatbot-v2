"""
Context Enricher for enhancing queries with session and page context
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class EnrichedContext:
    """Enriched context with all available information"""
    original_query: str
    enriched_query: str
    user_context: Dict[str, Any]
    page_context: Dict[str, Any]
    conversation_context: Dict[str, Any]
    temporal_context: Dict[str, Any]
    metadata: Dict[str, Any]


class ContextEnricher:
    """
    Enriches user queries with contextual information from:
    - User session (role, permissions, preferences)
    - Page context (current filters, selected items)
    - Conversation history (previous topics, entities)
    - Temporal context (time of day, day of week)
    """

    def __init__(self):
        """Initialize context enricher"""
        self.entity_memory: Dict[str, List[str]] = {}  # session_id -> entities

    async def enrich_query(
        self,
        query: str,
        session_id: str,
        user_info: Optional[Dict[str, Any]] = None,
        page_context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> EnrichedContext:
        """
        Enrich query with all available context

        Args:
            query: Original user query
            session_id: Session identifier
            user_info: User information (role, permissions, etc.)
            page_context: Current page context (filters, selections, etc.)
            conversation_history: Recent conversation history

        Returns:
            EnrichedContext with enriched query and metadata
        """
        # Extract entities from current query
        current_entities = self._extract_entities(query)

        # Build enrichment components
        user_context = self._build_user_context(user_info)
        page_ctx = self._build_page_context(page_context)
        conv_context = await self._build_conversation_context(
            session_id,
            conversation_history,
            current_entities
        )
        temporal_ctx = self._build_temporal_context()

        # Create enriched query
        enriched_query = await self._create_enriched_query(
            query,
            user_context,
            page_ctx,
            conv_context,
            temporal_ctx
        )

        # Update entity memory
        self._update_entity_memory(session_id, current_entities)

        return EnrichedContext(
            original_query=query,
            enriched_query=enriched_query,
            user_context=user_context,
            page_context=page_ctx,
            conversation_context=conv_context,
            temporal_context=temporal_ctx,
            metadata={
                "enrichment_timestamp": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "entities_found": len(current_entities)
            }
        )

    def _build_user_context(self, user_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build user context component"""
        if not user_info:
            return {}

        return {
            "user_id": user_info.get("user_id"),
            "role": user_info.get("role", "user"),
            "permissions": user_info.get("permissions", []),
            "preferences": user_info.get("preferences", {}),
            "assigned_cases": user_info.get("assigned_cases", [])
        }

    def _build_page_context(self, page_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build page context component"""
        if not page_context:
            return {}

        return {
            "current_filters": page_context.get("filters", {}),
            "selected_items": page_context.get("selected_items", []),
            "current_view": page_context.get("view", "default"),
            "sort_order": page_context.get("sort_order"),
            "page_url": page_context.get("url"),
            "visible_data": page_context.get("visible_data", [])
        }

    async def _build_conversation_context(
        self,
        session_id: str,
        conversation_history: Optional[List[Dict[str, Any]]],
        current_entities: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """Build conversation context from history"""
        context = {
            "recent_topics": [],
            "mentioned_entities": {},
            "previous_intent": None,
            "conversation_flow": []
        }

        if not conversation_history:
            return context

        # Analyze recent messages (last 5)
        recent_messages = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history

        # Extract topics and entities from history
        for msg in recent_messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")

                # Extract entities
                entities = self._extract_entities(content)
                for entity_type, values in entities.items():
                    if entity_type not in context["mentioned_entities"]:
                        context["mentioned_entities"][entity_type] = []
                    context["mentioned_entities"][entity_type].extend(values)

                # Extract topics (simplified - in production use NLP)
                topics = self._extract_topics(content)
                context["recent_topics"].extend(topics)

        # Deduplicate
        context["recent_topics"] = list(set(context["recent_topics"]))[:5]
        for entity_type in context["mentioned_entities"]:
            context["mentioned_entities"][entity_type] = list(set(context["mentioned_entities"][entity_type]))

        # Get remembered entities from previous interactions
        if session_id in self.entity_memory:
            context["remembered_entities"] = self.entity_memory[session_id]

        return context

    def _build_temporal_context(self) -> Dict[str, Any]:
        """Build temporal context component"""
        now = datetime.now()

        return {
            "current_time": now.isoformat(),
            "hour_of_day": now.hour,
            "day_of_week": now.strftime("%A"),
            "is_business_hours": 9 <= now.hour < 17,
            "is_weekend": now.weekday() >= 5,
            "time_zone": "UTC"  # Could be made dynamic
        }

    async def _create_enriched_query(
        self,
        query: str,
        user_context: Dict[str, Any],
        page_context: Dict[str, Any],
        conv_context: Dict[str, Any],
        temporal_context: Dict[str, Any]
    ) -> str:
        """
        Create enriched version of query with context

        The enriched query includes implicit information that helps with routing
        """
        enrichment_parts = [query]

        # Add user role context
        if user_context.get("role"):
            enrichment_parts.append(f"[User role: {user_context['role']}]")

        # Add current filter context
        if page_context.get("current_filters"):
            filters = page_context["current_filters"]
            if filters:
                filter_str = ", ".join(f"{k}={v}" for k, v in filters.items())
                enrichment_parts.append(f"[Current filters: {filter_str}]")

        # Add selected items context
        if page_context.get("selected_items"):
            items = page_context["selected_items"]
            if items:
                enrichment_parts.append(f"[Selected: {len(items)} items]")

        # Add conversation context
        if conv_context.get("recent_topics"):
            topics = ", ".join(conv_context["recent_topics"][:3])
            enrichment_parts.append(f"[Recent topics: {topics}]")

        # Add remembered entities
        if conv_context.get("mentioned_entities"):
            for entity_type, values in conv_context["mentioned_entities"].items():
                if values:
                    enrichment_parts.append(f"[Referenced {entity_type}: {', '.join(values[:2])}]")

        # Add temporal hints
        if not temporal_context.get("is_business_hours"):
            enrichment_parts.append("[Outside business hours]")

        return " ".join(enrichment_parts)

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract entities from text

        Entity types:
        - case_ids: Case/ticket identifiers
        - user_names: User or agent names
        - dates: Date references
        - amounts: Monetary amounts
        - priorities: Priority levels
        - statuses: Status values
        """
        entities: Dict[str, List[str]] = {
            "case_ids": [],
            "user_names": [],
            "dates": [],
            "amounts": [],
            "priorities": [],
            "statuses": []
        }

        # Extract case IDs
        import re
        case_ids = re.findall(r'#(\d+)', text)
        entities["case_ids"] = case_ids

        # Extract priorities
        text_lower = text.lower()
        for priority in ["high", "medium", "low"]:
            if priority in text_lower:
                entities["priorities"].append(priority)

        # Extract statuses
        for status in ["open", "closed", "pending", "resolved", "cancelled"]:
            if status in text_lower:
                entities["statuses"].append(status)

        # Extract dates (simplified)
        date_patterns = ["today", "yesterday", "this week", "this month", "last week"]
        for pattern in date_patterns:
            if pattern in text_lower:
                entities["dates"].append(pattern)

        # Extract monetary amounts
        amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)
        entities["amounts"] = amounts

        # Extract user names (capitalized words that might be names)
        # This is simplified - production would use NER
        potential_names = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', text)
        entities["user_names"] = potential_names

        # Remove empty lists
        return {k: v for k, v in entities.items() if v}

    def _extract_topics(self, text: str) -> List[str]:
        """
        Extract topics from text

        Simplified implementation - production would use topic modeling
        """
        topics = []
        text_lower = text.lower()

        topic_keywords = {
            "cases": ["case", "ticket", "request", "issue"],
            "payments": ["payment", "transaction", "transfer", "charge"],
            "users": ["user", "customer", "client", "agent"],
            "reports": ["report", "analytics", "statistics", "summary"],
            "account": ["account", "profile", "login", "access"]
        }

        for topic, keywords in topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)

        return topics

    def _update_entity_memory(self, session_id: str, entities: Dict[str, List[str]]) -> None:
        """Update entity memory for session"""
        if session_id not in self.entity_memory:
            self.entity_memory[session_id] = []

        # Add new entities
        for entity_type, values in entities.items():
            for value in values:
                entity_str = f"{entity_type}:{value}"
                if entity_str not in self.entity_memory[session_id]:
                    self.entity_memory[session_id].append(entity_str)

        # Keep only last 20 entities
        self.entity_memory[session_id] = self.entity_memory[session_id][-20:]

    def get_context_summary(self, enriched_context: EnrichedContext) -> str:
        """
        Get human-readable summary of enriched context

        Useful for debugging and logging
        """
        summary_parts = []

        # User context
        if enriched_context.user_context.get("role"):
            summary_parts.append(f"User: {enriched_context.user_context['role']}")

        # Page context
        if enriched_context.page_context.get("current_filters"):
            filter_count = len(enriched_context.page_context["current_filters"])
            summary_parts.append(f"Filters: {filter_count} active")

        # Conversation context
        if enriched_context.conversation_context.get("recent_topics"):
            topics = enriched_context.conversation_context["recent_topics"]
            summary_parts.append(f"Topics: {', '.join(topics[:2])}")

        # Entities
        entity_count = enriched_context.metadata.get("entities_found", 0)
        if entity_count > 0:
            summary_parts.append(f"Entities: {entity_count} found")

        return "; ".join(summary_parts) if summary_parts else "No context available"

    def clear_session_memory(self, session_id: str) -> None:
        """Clear entity memory for a session"""
        if session_id in self.entity_memory:
            del self.entity_memory[session_id]
            logger.info(f"Cleared entity memory for session: {session_id}")
