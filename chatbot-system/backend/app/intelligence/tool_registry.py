"""
Tool Registry for managing data source tools and semantic matching
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from langchain_core.tools import Tool, BaseTool
from langchain_core.embeddings import Embeddings
import numpy as np
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolMetadata:
    """Metadata for registered tools"""
    name: str
    description: str
    capabilities: List[str]
    keywords: List[str]
    data_source: str
    priority: int = 5
    embedding: Optional[np.ndarray] = None


class ToolRegistry:
    """
    Registry for managing and discovering tools based on semantic similarity
    Enables intelligent tool selection without hardcoded logic
    """

    def __init__(self, embeddings: Optional[Embeddings] = None):
        """
        Initialize tool registry

        Args:
            embeddings: Optional embeddings model for semantic search
        """
        self.tools: Dict[str, BaseTool] = {}
        self.metadata: Dict[str, ToolMetadata] = {}
        self.embeddings = embeddings
        self.capability_index: Dict[str, List[str]] = defaultdict(list)
        self.keyword_index: Dict[str, List[str]] = defaultdict(list)

    async def register_tool(
        self,
        tool: BaseTool,
        capabilities: List[str],
        keywords: List[str],
        data_source: str,
        priority: int = 5
    ) -> None:
        """
        Register a tool with metadata for semantic matching

        Args:
            tool: LangChain tool instance
            capabilities: List of capabilities (e.g., ["query_cases", "filter_data"])
            keywords: Keywords for matching (e.g., ["case", "ticket", "support"])
            data_source: Data source name (e.g., "postgresql", "rest_api")
            priority: Priority level (1-10, higher = more preferred)
        """
        name = tool.name

        # Create metadata
        metadata = ToolMetadata(
            name=name,
            description=tool.description,
            capabilities=capabilities,
            keywords=keywords,
            data_source=data_source,
            priority=priority
        )

        # Generate embedding if embeddings model available
        if self.embeddings:
            try:
                embedding_text = f"{tool.description} {' '.join(keywords)} {' '.join(capabilities)}"
                metadata.embedding = await self._generate_embedding(embedding_text)
            except Exception as e:
                logger.warning(f"Failed to generate embedding for {name}: {e}")

        # Store tool and metadata
        self.tools[name] = tool
        self.metadata[name] = metadata

        # Index by capabilities and keywords
        for capability in capabilities:
            self.capability_index[capability.lower()].append(name)

        for keyword in keywords:
            self.keyword_index[keyword.lower()].append(name)

        logger.info(f"Registered tool: {name} with {len(capabilities)} capabilities")

    async def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text"""
        if self.embeddings:
            embedding = await self.embeddings.aembed_query(text)
            return np.array(embedding)
        return None

    async def find_best_tools(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        top_k: int = 3,
        min_score: float = 0.5
    ) -> List[BaseTool]:
        """
        Find best matching tools for a query using semantic search

        Args:
            query: User query
            context: Additional context (e.g., current filters, user role)
            top_k: Number of tools to return
            min_score: Minimum similarity score

        Returns:
            List of best matching tools
        """
        if not self.tools:
            logger.warning("No tools registered in registry")
            return []

        # Generate query embedding
        query_embedding = None
        if self.embeddings:
            query_embedding = await self._generate_embedding(query)

        # Score all tools
        tool_scores: Dict[str, float] = {}

        for name, metadata in self.metadata.items():
            score = await self._calculate_tool_score(
                query=query,
                query_embedding=query_embedding,
                metadata=metadata,
                context=context
            )
            tool_scores[name] = score

        # Sort by score and priority
        sorted_tools = sorted(
            tool_scores.items(),
            key=lambda x: (x[1], self.metadata[x[0]].priority),
            reverse=True
        )

        # Filter by minimum score and return top k
        result = []
        for tool_name, score in sorted_tools[:top_k]:
            if score >= min_score:
                result.append(self.tools[tool_name])
                logger.debug(f"Selected tool: {tool_name} (score: {score:.3f})")

        return result

    async def _calculate_tool_score(
        self,
        query: str,
        query_embedding: Optional[np.ndarray],
        metadata: ToolMetadata,
        context: Optional[Dict[str, Any]]
    ) -> float:
        """
        Calculate relevance score for a tool

        Combines:
        1. Semantic similarity (if embeddings available)
        2. Keyword matching
        3. Capability matching
        4. Context hints
        """
        score = 0.0

        # 1. Semantic similarity (40% weight)
        if query_embedding is not None and metadata.embedding is not None:
            similarity = self._cosine_similarity(query_embedding, metadata.embedding)
            score += similarity * 0.4

        # 2. Keyword matching (30% weight)
        query_lower = query.lower()
        keyword_matches = sum(1 for kw in metadata.keywords if kw.lower() in query_lower)
        if metadata.keywords:
            keyword_score = keyword_matches / len(metadata.keywords)
            score += keyword_score * 0.3

        # 3. Capability matching (20% weight)
        if context and "required_capabilities" in context:
            required = set(context["required_capabilities"])
            available = set(metadata.capabilities)
            if required:
                capability_score = len(required & available) / len(required)
                score += capability_score * 0.2

        # 4. Context hints (10% weight)
        if context:
            # Prefer specific data source if mentioned
            if "preferred_source" in context:
                if metadata.data_source == context["preferred_source"]:
                    score += 0.1

            # Boost score for mentioned data sources in query
            if metadata.data_source.lower() in query_lower:
                score += 0.1

        return min(score, 1.0)  # Cap at 1.0

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def get_tools_by_capability(self, capability: str) -> List[BaseTool]:
        """Get all tools with a specific capability"""
        tool_names = self.capability_index.get(capability.lower(), [])
        return [self.tools[name] for name in tool_names]

    def get_tools_by_keyword(self, keyword: str) -> List[BaseTool]:
        """Get all tools matching a keyword"""
        tool_names = self.keyword_index.get(keyword.lower(), [])
        return [self.tools[name] for name in tool_names]

    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools"""
        return list(self.tools.values())

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a specific tool by name"""
        return self.tools.get(name)

    def unregister_tool(self, name: str) -> bool:
        """
        Unregister a tool

        Args:
            name: Tool name

        Returns:
            True if tool was removed, False if not found
        """
        if name not in self.tools:
            return False

        # Remove from indexes
        metadata = self.metadata[name]
        for capability in metadata.capabilities:
            if capability.lower() in self.capability_index:
                self.capability_index[capability.lower()].remove(name)

        for keyword in metadata.keywords:
            if keyword.lower() in self.keyword_index:
                self.keyword_index[keyword.lower()].remove(name)

        # Remove tool and metadata
        del self.tools[name]
        del self.metadata[name]

        logger.info(f"Unregistered tool: {name}")
        return True

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all registered tools with metadata

        Returns:
            List of tool information dictionaries
        """
        result = []
        for name, tool in self.tools.items():
            metadata = self.metadata[name]
            result.append({
                "name": name,
                "description": tool.description,
                "capabilities": metadata.capabilities,
                "keywords": metadata.keywords,
                "data_source": metadata.data_source,
                "priority": metadata.priority
            })
        return result

    def clear(self) -> None:
        """Clear all registered tools"""
        self.tools.clear()
        self.metadata.clear()
        self.capability_index.clear()
        self.keyword_index.clear()
        logger.info("Cleared all tools from registry")
