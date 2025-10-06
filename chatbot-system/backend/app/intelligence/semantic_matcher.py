"""
Semantic Matcher for intelligent query-to-datasource matching
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class DataSourceConfig:
    """Configuration for a data source"""
    name: str
    type: str  # "rest_api", "postgresql", "oracle", "soap"
    description: str
    schema: Dict[str, Any]  # Schema information
    keywords: List[str]
    capabilities: List[str]
    priority: int = 5
    cost_factor: float = 1.0  # Relative cost of querying this source


@dataclass
class MatchResult:
    """Result of semantic matching"""
    data_source: str
    confidence: float
    reasoning: str
    suggested_fields: List[str]
    suggested_filters: Dict[str, Any]


class SemanticMatcher:
    """
    Matches user queries to appropriate data sources using semantic understanding
    No hardcoded logic - uses embeddings and schema analysis
    """

    def __init__(self, embeddings_model: Optional[Any] = None):
        """
        Initialize semantic matcher

        Args:
            embeddings_model: Optional embeddings model for semantic similarity
        """
        self.data_sources: Dict[str, DataSourceConfig] = {}
        self.embeddings_model = embeddings_model
        self.source_embeddings: Dict[str, np.ndarray] = {}
        self.schema_index: Dict[str, List[str]] = defaultdict(list)  # field -> sources

    async def register_data_source(self, config: DataSourceConfig) -> None:
        """
        Register a data source with schema information

        Args:
            config: Data source configuration
        """
        self.data_sources[config.name] = config

        # Index schema fields
        if config.schema:
            for field_name in config.schema.get("fields", {}):
                self.schema_index[field_name.lower()].append(config.name)

        # Generate embedding for semantic matching
        if self.embeddings_model:
            try:
                embedding_text = self._create_embedding_text(config)
                embedding = await self._generate_embedding(embedding_text)
                self.source_embeddings[config.name] = embedding
            except Exception as e:
                logger.warning(f"Failed to generate embedding for {config.name}: {e}")

        logger.info(f"Registered data source: {config.name}")

    def _create_embedding_text(self, config: DataSourceConfig) -> str:
        """Create text representation for embedding generation"""
        parts = [
            config.description,
            " ".join(config.keywords),
            " ".join(config.capabilities)
        ]

        # Add schema field names
        if config.schema and "fields" in config.schema:
            parts.append(" ".join(config.schema["fields"].keys()))

        return " ".join(parts)

    async def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text"""
        if self.embeddings_model:
            embedding = await self.embeddings_model.aembed_query(text)
            return np.array(embedding)
        return None

    async def match_query_to_sources(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        top_k: int = 3
    ) -> List[MatchResult]:
        """
        Match query to best data sources

        Args:
            query: User query
            context: Additional context
            top_k: Number of sources to return

        Returns:
            List of MatchResult ordered by confidence
        """
        if not self.data_sources:
            logger.warning("No data sources registered")
            return []

        matches = []

        # Score each data source
        for source_name, config in self.data_sources.items():
            score_result = await self._score_data_source(
                query=query,
                config=config,
                context=context
            )

            if score_result:
                matches.append(score_result)

        # Sort by confidence
        matches.sort(key=lambda x: x.confidence, reverse=True)

        return matches[:top_k]

    async def _score_data_source(
        self,
        query: str,
        config: DataSourceConfig,
        context: Optional[Dict[str, Any]]
    ) -> Optional[MatchResult]:
        """
        Score how well a data source matches the query

        Args:
            query: User query
            config: Data source configuration
            context: Additional context

        Returns:
            MatchResult with confidence score
        """
        total_score = 0.0
        reasoning_parts = []

        # 1. Semantic similarity (40% weight)
        if self.embeddings_model and config.name in self.source_embeddings:
            query_embedding = await self._generate_embedding(query)
            source_embedding = self.source_embeddings[config.name]

            if query_embedding is not None and source_embedding is not None:
                semantic_score = self._cosine_similarity(query_embedding, source_embedding)
                total_score += semantic_score * 0.4
                reasoning_parts.append(f"Semantic similarity: {semantic_score:.2f}")

        # 2. Keyword matching (30% weight)
        keyword_score = self._keyword_match_score(query, config.keywords)
        total_score += keyword_score * 0.3
        if keyword_score > 0:
            reasoning_parts.append(f"Keyword match: {keyword_score:.2f}")

        # 3. Schema field matching (20% weight)
        field_score, matched_fields = self._schema_match_score(query, config.schema)
        total_score += field_score * 0.2
        if matched_fields:
            reasoning_parts.append(f"Matched fields: {', '.join(matched_fields[:3])}")

        # 4. Capability matching (10% weight)
        capability_score = self._capability_match_score(query, config.capabilities, context)
        total_score += capability_score * 0.1

        # Apply priority boost
        priority_boost = (config.priority / 10.0) * 0.1
        total_score += priority_boost

        # Suggest fields and filters
        suggested_fields = self._suggest_fields(query, config.schema)
        suggested_filters = self._suggest_filters(query, config.schema)

        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "Low confidence match"

        return MatchResult(
            data_source=config.name,
            confidence=min(total_score, 1.0),
            reasoning=reasoning,
            suggested_fields=suggested_fields,
            suggested_filters=suggested_filters
        )

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _keyword_match_score(self, query: str, keywords: List[str]) -> float:
        """Score based on keyword matching"""
        if not keywords:
            return 0.0

        query_lower = query.lower()
        matches = sum(1 for kw in keywords if kw.lower() in query_lower)

        return matches / len(keywords)

    def _schema_match_score(
        self,
        query: str,
        schema: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """
        Score based on schema field matching

        Returns:
            Tuple of (score, list of matched fields)
        """
        if not schema or "fields" not in schema:
            return 0.0, []

        query_lower = query.lower()
        fields = schema["fields"]
        matched_fields = []

        for field_name in fields:
            # Check if field name or synonyms appear in query
            field_lower = field_name.lower()
            if field_lower in query_lower or field_lower.replace("_", " ") in query_lower:
                matched_fields.append(field_name)

        score = len(matched_fields) / len(fields) if fields else 0.0
        return score, matched_fields

    def _capability_match_score(
        self,
        query: str,
        capabilities: List[str],
        context: Optional[Dict[str, Any]]
    ) -> float:
        """Score based on capability matching"""
        if not capabilities:
            return 0.0

        # Check context for required capabilities
        if context and "required_capabilities" in context:
            required = set(context["required_capabilities"])
            available = set(capabilities)
            if required:
                return len(required & available) / len(required)

        # Basic capability inference from query
        query_lower = query.lower()
        score = 0.0

        capability_keywords = {
            "read": ["show", "get", "list", "find", "what", "which"],
            "write": ["create", "add", "insert", "update", "modify"],
            "delete": ["delete", "remove"],
            "aggregate": ["total", "count", "sum", "average"]
        }

        for capability in capabilities:
            cap_lower = capability.lower()
            for cap_type, keywords in capability_keywords.items():
                if cap_type in cap_lower:
                    if any(kw in query_lower for kw in keywords):
                        score += 0.5

        return min(score, 1.0)

    def _suggest_fields(self, query: str, schema: Dict[str, Any]) -> List[str]:
        """Suggest relevant fields based on query"""
        if not schema or "fields" not in schema:
            return []

        query_lower = query.lower()
        fields = schema["fields"]
        suggested = []

        for field_name, field_info in fields.items():
            field_lower = field_name.lower()

            # Match field name in query
            if field_lower in query_lower or field_lower.replace("_", " ") in query_lower:
                suggested.append(field_name)
                continue

            # Match field description or synonyms
            if isinstance(field_info, dict):
                description = field_info.get("description", "").lower()
                synonyms = field_info.get("synonyms", [])

                if description and any(word in query_lower for word in description.split()):
                    suggested.append(field_name)
                elif any(syn.lower() in query_lower for syn in synonyms):
                    suggested.append(field_name)

        return suggested[:10]  # Limit to top 10

    def _suggest_filters(self, query: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest filters based on query analysis"""
        filters = {}

        # Extract common filter patterns
        import re
        query_lower = query.lower()

        # Status filters
        status_pattern = r'\b(open|closed|pending|resolved)\b'
        status_match = re.search(status_pattern, query_lower)
        if status_match:
            filters["status"] = status_match.group(1)

        # Priority filters
        priority_pattern = r'\b(high|medium|low) priority\b'
        priority_match = re.search(priority_pattern, query_lower)
        if priority_match:
            filters["priority"] = priority_match.group(1)

        # Date range filters
        if "today" in query_lower:
            filters["date_range"] = "today"
        elif "this week" in query_lower:
            filters["date_range"] = "this_week"
        elif "this month" in query_lower:
            filters["date_range"] = "this_month"

        # ID filters
        id_pattern = r'#(\d+)'
        id_match = re.search(id_pattern, query)
        if id_match:
            filters["id"] = id_match.group(1)

        return filters

    def get_data_source_info(self, source_name: str) -> Optional[DataSourceConfig]:
        """Get information about a registered data source"""
        return self.data_sources.get(source_name)

    def list_data_sources(self) -> List[Dict[str, Any]]:
        """List all registered data sources"""
        return [
            {
                "name": config.name,
                "type": config.type,
                "description": config.description,
                "capabilities": config.capabilities,
                "fields": list(config.schema.get("fields", {}).keys()) if config.schema else []
            }
            for config in self.data_sources.values()
        ]

    def unregister_data_source(self, source_name: str) -> bool:
        """Unregister a data source"""
        if source_name not in self.data_sources:
            return False

        # Remove from indexes
        config = self.data_sources[source_name]
        if config.schema:
            for field_name in config.schema.get("fields", {}):
                if field_name.lower() in self.schema_index:
                    self.schema_index[field_name.lower()].remove(source_name)

        # Remove embeddings
        if source_name in self.source_embeddings:
            del self.source_embeddings[source_name]

        # Remove config
        del self.data_sources[source_name]

        logger.info(f"Unregistered data source: {source_name}")
        return True
