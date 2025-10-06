"""
Response Formatter - Formats data for presentation to users.
Supports multiple output formats: text, JSON, table, markdown.
"""
import logging
from typing import List, Dict, Any, Optional, Literal
import json
from datetime import datetime

logger = logging.getLogger(__name__)


FormatType = Literal["text", "json", "table", "markdown", "summary"]


class ResponseFormatter:
    """
    Formats data into user-friendly responses.

    Capabilities:
    - Text narrative format
    - JSON structured output
    - ASCII/Markdown tables
    - Summary statistics
    - Error formatting
    - Multi-format support

    Use Cases:
    - Format query results for WebSocket
    - Generate human-readable summaries
    - Create API-ready JSON
    - Build tables for display
    """

    def __init__(self):
        """Initialize response formatter."""
        logger.info("🎨 ResponseFormatter initialized")

    def format(
        self,
        data: Any,
        format_type: FormatType = "text",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format data into specified format.

        Args:
            data: Data to format (list, dict, str, etc.)
            format_type: Output format type
            metadata: Optional metadata (query, execution time, etc.)

        Returns:
            Formatted string

        Example:
            data = [{"id": 1, "name": "John"}]
            format(data, "table") → ASCII table
            format(data, "json") → JSON string
            format(data, "text") → Human-readable text
        """
        logger.info(f"🎨 Formatting data as {format_type}...")

        try:
            if format_type == "json":
                return self._format_json(data, metadata)
            elif format_type == "table":
                return self._format_table(data, metadata)
            elif format_type == "markdown":
                return self._format_markdown(data, metadata)
            elif format_type == "summary":
                return self._format_summary(data, metadata)
            else:  # text
                return self._format_text(data, metadata)

        except Exception as e:
            logger.error(f"❌ Formatting error: {e}")
            # Fallback to JSON
            return json.dumps({"data": str(data), "error": str(e)}, indent=2)

    def _format_json(
        self,
        data: Any,
        metadata: Optional[Dict[str, Any]]
    ) -> str:
        """
        Format as JSON.

        Args:
            data: Data to format
            metadata: Optional metadata

        Returns:
            JSON string
        """
        output = {
            "data": data,
            "format": "json",
            "timestamp": datetime.utcnow().isoformat()
        }

        if metadata:
            output["metadata"] = metadata

        return json.dumps(output, indent=2, default=str)

    def _format_table(
        self,
        data: Any,
        metadata: Optional[Dict[str, Any]]
    ) -> str:
        """
        Format as ASCII table.

        Args:
            data: Data to format (must be list of dicts)
            metadata: Optional metadata

        Returns:
            ASCII table string

        Example:
            +------+--------+
            | id   | name   |
            +------+--------+
            | 1    | John   |
            | 2    | Jane   |
            +------+--------+
        """
        if not isinstance(data, list):
            return self._format_text(data, metadata)

        if not data:
            return "No data to display."

        # Ensure all items are dicts
        if not all(isinstance(item, dict) for item in data):
            return self._format_text(data, metadata)

        # Get all unique keys
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())

        # Remove metadata keys
        all_keys = all_keys - {"_source", "_sources"}
        columns = sorted(list(all_keys))

        if not columns:
            return "No columns to display."

        # Calculate column widths
        col_widths = {}
        for col in columns:
            # Start with column name length
            col_widths[col] = len(col)
            # Check data lengths
            for item in data:
                value = str(item.get(col, ""))
                col_widths[col] = max(col_widths[col], len(value))

        # Build table
        lines = []

        # Top border
        border = "+" + "+".join(["-" * (col_widths[col] + 2) for col in columns]) + "+"
        lines.append(border)

        # Header
        header = "|" + "|".join([f" {col:{col_widths[col]}} " for col in columns]) + "|"
        lines.append(header)

        # Header border
        lines.append(border)

        # Data rows
        for item in data:
            row = "|" + "|".join([
                f" {str(item.get(col, '')):{col_widths[col]}} "
                for col in columns
            ]) + "|"
            lines.append(row)

        # Bottom border
        lines.append(border)

        # Add metadata if present
        if metadata:
            lines.append("")
            lines.append(f"Rows: {len(data)}")
            if "execution_time_ms" in metadata:
                lines.append(f"Execution time: {metadata['execution_time_ms']:.1f}ms")

        return "\n".join(lines)

    def _format_markdown(
        self,
        data: Any,
        metadata: Optional[Dict[str, Any]]
    ) -> str:
        """
        Format as Markdown.

        Args:
            data: Data to format
            metadata: Optional metadata

        Returns:
            Markdown string

        Example:
            | id | name |
            |----|------|
            | 1  | John |
            | 2  | Jane |
        """
        if not isinstance(data, list):
            return self._format_text(data, metadata)

        if not data:
            return "*No data to display.*"

        # Ensure all items are dicts
        if not all(isinstance(item, dict) for item in data):
            return self._format_text(data, metadata)

        # Get columns
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())
        all_keys = all_keys - {"_source", "_sources"}
        columns = sorted(list(all_keys))

        if not columns:
            return "*No columns to display.*"

        lines = []

        # Header
        header = "| " + " | ".join(columns) + " |"
        lines.append(header)

        # Separator
        separator = "| " + " | ".join(["---" for _ in columns]) + " |"
        lines.append(separator)

        # Data rows
        for item in data:
            row = "| " + " | ".join([str(item.get(col, "")) for col in columns]) + " |"
            lines.append(row)

        # Add metadata
        if metadata:
            lines.append("")
            lines.append(f"**Rows:** {len(data)}")
            if "execution_time_ms" in metadata:
                lines.append(f"**Execution time:** {metadata['execution_time_ms']:.1f}ms")

        return "\n".join(lines)

    def _format_summary(
        self,
        data: Any,
        metadata: Optional[Dict[str, Any]]
    ) -> str:
        """
        Format as summary statistics.

        Args:
            data: Data to format
            metadata: Optional metadata

        Returns:
            Summary string
        """
        lines = ["## Summary"]

        if isinstance(data, list):
            lines.append(f"- **Total records:** {len(data)}")

            if data and isinstance(data[0], dict):
                # Count by type if _source exists
                sources = {}
                for item in data:
                    source = item.get("_source") or item.get("_sources", ["unknown"])
                    if isinstance(source, list):
                        source = ", ".join(source)
                    sources[source] = sources.get(source, 0) + 1

                if len(sources) > 1:
                    lines.append("- **Records by source:**")
                    for source, count in sources.items():
                        lines.append(f"  - {source}: {count}")

                # Show field statistics
                all_keys = set()
                for item in data:
                    all_keys.update(item.keys())
                all_keys = all_keys - {"_source", "_sources"}

                if all_keys:
                    lines.append(f"- **Fields:** {', '.join(sorted(all_keys))}")

        elif isinstance(data, dict):
            lines.append(f"- **Type:** Dictionary")
            lines.append(f"- **Keys:** {', '.join(data.keys())}")

        else:
            lines.append(f"- **Type:** {type(data).__name__}")
            lines.append(f"- **Value:** {str(data)[:100]}")

        # Add metadata
        if metadata:
            lines.append("")
            lines.append("## Metadata")
            for key, value in metadata.items():
                lines.append(f"- **{key}:** {value}")

        return "\n".join(lines)

    def _format_text(
        self,
        data: Any,
        metadata: Optional[Dict[str, Any]]
    ) -> str:
        """
        Format as human-readable text.

        Args:
            data: Data to format
            metadata: Optional metadata

        Returns:
            Text string
        """
        lines = []

        if isinstance(data, str):
            # Already a string
            lines.append(data)

        elif isinstance(data, list):
            if not data:
                lines.append("No results found.")
            elif len(data) == 1 and isinstance(data[0], dict):
                # Single record - show as key-value pairs
                lines.append("Result:")
                for key, value in data[0].items():
                    if key not in ["_source", "_sources"]:
                        lines.append(f"  {key}: {value}")
            else:
                # Multiple records
                lines.append(f"Found {len(data)} results:")
                for i, item in enumerate(data[:10], 1):  # Limit to first 10
                    if isinstance(item, dict):
                        # Show compact representation
                        key_values = [f"{k}={v}" for k, v in item.items() if k not in ["_source", "_sources"]]
                        lines.append(f"  {i}. {', '.join(key_values[:5])}")  # First 5 fields
                    else:
                        lines.append(f"  {i}. {str(item)[:100]}")

                if len(data) > 10:
                    lines.append(f"  ... and {len(data) - 10} more")

        elif isinstance(data, dict):
            # Dictionary - show as key-value pairs
            for key, value in data.items():
                if key not in ["_source", "_sources"]:
                    if isinstance(value, (dict, list)):
                        lines.append(f"{key}:")
                        lines.append(f"  {json.dumps(value, indent=2)}")
                    else:
                        lines.append(f"{key}: {value}")

        else:
            # Other types
            lines.append(str(data))

        # Add metadata if present
        if metadata:
            lines.append("")
            if "query" in metadata:
                lines.append(f"Query: {metadata['query']}")
            if "execution_time_ms" in metadata:
                lines.append(f"Execution time: {metadata['execution_time_ms']:.1f}ms")

        return "\n".join(lines)

    def format_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format an error message.

        Args:
            error: Exception that occurred
            context: Optional context (query, step, etc.)

        Returns:
            Formatted error message
        """
        lines = ["❌ Error occurred:"]
        lines.append(f"  Type: {type(error).__name__}")
        lines.append(f"  Message: {str(error)}")

        if context:
            lines.append("")
            lines.append("Context:")
            for key, value in context.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    def format_multi_source(
        self,
        sql_results: List[Any],
        api_results: List[Any],
        soap_results: List[Any],
        format_type: FormatType = "text"
    ) -> str:
        """
        Format results from multiple sources.

        Args:
            sql_results: SQL results
            api_results: API results
            soap_results: SOAP results
            format_type: Output format

        Returns:
            Formatted string with all sources
        """
        lines = []

        if sql_results:
            lines.append("## SQL Database Results")
            lines.append(self.format(sql_results, format_type))
            lines.append("")

        if api_results:
            lines.append("## REST API Results")
            lines.append(self.format(api_results, format_type))
            lines.append("")

        if soap_results:
            lines.append("## SOAP Service Results")
            lines.append(self.format(soap_results, format_type))
            lines.append("")

        if not lines:
            return "No results from any source."

        return "\n".join(lines)
