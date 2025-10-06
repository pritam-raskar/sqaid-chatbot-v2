"""
Data Merger - Intelligently merges data from multiple sources.
Handles joins, correlations, and relationship detection.
"""
import logging
from typing import List, Dict, Any, Optional, Set
import json

logger = logging.getLogger(__name__)


class DataMerger:
    """
    Merges data from multiple sources using relationship detection.

    Capabilities:
    - Detect common keys (IDs, names, etc.)
    - Join data from different sources
    - Correlate related information
    - Handle missing data
    - Deduplicate results

    Use Cases:
    - Merge user data from API with alerts from SQL
    - Combine department info with employee data
    - Join case details with customer information
    """

    def __init__(self):
        """Initialize data merger."""
        logger.info("🔧 DataMerger initialized")

    def merge_results(
        self,
        sql_data: List[Dict[str, Any]],
        api_data: List[Dict[str, Any]],
        soap_data: List[Dict[str, Any]],
        merge_strategy: str = "auto"
    ) -> List[Dict[str, Any]]:
        """
        Merge data from multiple sources.

        Args:
            sql_data: Data from SQL sources
            api_data: Data from REST APIs
            soap_data: Data from SOAP services
            merge_strategy: "auto" (detect), "join" (by key), "concat" (append)

        Returns:
            Merged data as list of dicts

        Example:
            sql_data = [{"alert_id": 1, "severity": "high"}]
            api_data = [{"alert_id": 1, "user_name": "John"}]

            Result: [{"alert_id": 1, "severity": "high", "user_name": "John"}]
        """
        logger.info(
            f"🔄 Merging data: SQL={len(sql_data)}, "
            f"API={len(api_data)}, SOAP={len(soap_data)}"
        )

        # Combine all sources
        all_data = []

        # Tag data with source
        for item in sql_data:
            all_data.append({**item, "_source": "sql"})
        for item in api_data:
            all_data.append({**item, "_source": "api"})
        for item in soap_data:
            all_data.append({**item, "_source": "soap"})

        if not all_data:
            logger.warning("⚠️ No data to merge")
            return []

        # Determine merge strategy
        if merge_strategy == "auto":
            merge_strategy = self._detect_merge_strategy(all_data)
            logger.info(f"📊 Auto-detected merge strategy: {merge_strategy}")

        # Execute merge
        if merge_strategy == "join":
            merged = self._merge_by_join(all_data)
        elif merge_strategy == "concat":
            merged = all_data
        else:
            # Default: concatenate
            merged = all_data

        logger.info(f"✅ Merge complete: {len(merged)} records")
        return merged

    def _detect_merge_strategy(self, data: List[Dict[str, Any]]) -> str:
        """
        Detect appropriate merge strategy based on data structure.

        Args:
            data: All data combined

        Returns:
            "join" if common keys found, else "concat"

        Detection Logic:
        - If multiple sources have common ID fields → "join"
        - Otherwise → "concat"
        """
        if len(data) < 2:
            return "concat"

        # Find common keys across records
        common_keys = self._find_common_keys(data)

        # Check for ID-like keys
        id_keys = [k for k in common_keys if self._is_id_field(k)]

        if id_keys:
            logger.debug(f"🔑 Found ID keys for joining: {id_keys}")
            return "join"
        else:
            logger.debug("📋 No common ID keys, using concat")
            return "concat"

    def _find_common_keys(self, data: List[Dict[str, Any]]) -> Set[str]:
        """
        Find keys that appear in multiple records.

        Args:
            data: List of data records

        Returns:
            Set of common keys
        """
        if not data:
            return set()

        # Get all keys from first record
        common = set(data[0].keys())

        # Intersect with keys from other records
        for record in data[1:]:
            common = common.intersection(set(record.keys()))

        # Remove metadata keys
        common = common - {"_source"}

        return common

    def _is_id_field(self, key: str) -> bool:
        """
        Check if a field name looks like an ID field.

        Args:
            key: Field name

        Returns:
            True if looks like an ID field

        ID patterns:
        - ends with "_id" or "_ID"
        - equals "id" or "ID"
        - contains "uuid" or "guid"
        - ends with "_key"
        """
        key_lower = key.lower()

        return (
            key_lower.endswith("_id") or
            key_lower == "id" or
            "uuid" in key_lower or
            "guid" in key_lower or
            key_lower.endswith("_key") or
            key_lower.endswith("_no") or
            key_lower.endswith("_number")
        )

    def _merge_by_join(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge data by joining on common keys.

        Args:
            data: All data with _source tags

        Returns:
            Merged data

        Algorithm:
        1. Find common ID keys
        2. Group records by ID value
        3. Merge records with same ID
        4. Return merged records
        """
        # Find common ID keys
        all_keys = set()
        for record in data:
            all_keys.update(record.keys())

        id_keys = [k for k in all_keys if self._is_id_field(k)]

        if not id_keys:
            logger.warning("⚠️ No ID keys found for joining, returning concatenated")
            return data

        # Use first ID key for joining
        join_key = id_keys[0]
        logger.info(f"🔗 Joining on key: {join_key}")

        # Group by join key
        grouped: Dict[Any, List[Dict[str, Any]]] = {}
        ungrouped = []

        for record in data:
            if join_key in record:
                key_value = record[join_key]
                if key_value not in grouped:
                    grouped[key_value] = []
                grouped[key_value].append(record)
            else:
                ungrouped.append(record)

        # Merge grouped records
        merged = []
        for key_value, records in grouped.items():
            if len(records) == 1:
                merged.append(records[0])
            else:
                # Merge multiple records with same key
                merged_record = self._merge_records(records, join_key)
                merged.append(merged_record)

        # Add ungrouped records
        merged.extend(ungrouped)

        logger.info(f"🔗 Joined {len(grouped)} groups, {len(ungrouped)} ungrouped")
        return merged

    def _merge_records(
        self,
        records: List[Dict[str, Any]],
        join_key: str
    ) -> Dict[str, Any]:
        """
        Merge multiple records into one.

        Args:
            records: Records to merge (same join key value)
            join_key: Key used for joining

        Returns:
            Single merged record

        Merge Strategy:
        - Start with first record
        - Add fields from subsequent records
        - For conflicts, prefer non-null values
        - Collect sources
        """
        if not records:
            return {}

        merged = dict(records[0])
        sources = [merged.get("_source", "unknown")]

        for record in records[1:]:
            sources.append(record.get("_source", "unknown"))

            for key, value in record.items():
                if key == "_source":
                    continue

                # If key not in merged, add it
                if key not in merged:
                    merged[key] = value
                # If existing value is None but new value isn't, use new
                elif merged[key] is None and value is not None:
                    merged[key] = value
                # If both have values and they differ, create list
                elif merged[key] != value and value is not None:
                    # Convert to list if needed
                    if not isinstance(merged[key], list):
                        merged[key] = [merged[key]]
                    if value not in merged[key]:
                        merged[key].append(value)

        # Update sources
        merged["_sources"] = list(set(sources))
        if "_source" in merged:
            del merged["_source"]

        return merged

    def deduplicate(
        self,
        data: List[Dict[str, Any]],
        key_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate records.

        Args:
            data: Data to deduplicate
            key_fields: Fields to use for uniqueness (None = all fields)

        Returns:
            Deduplicated data
        """
        if not data:
            return []

        logger.info(f"🔍 Deduplicating {len(data)} records...")

        seen = set()
        unique = []

        for record in data:
            # Create key from specified fields or all fields
            if key_fields:
                key_data = {k: record.get(k) for k in key_fields if k in record}
            else:
                key_data = {k: v for k, v in record.items() if k != "_source" and k != "_sources"}

            # Convert to hashable key
            try:
                key = json.dumps(key_data, sort_keys=True)
            except (TypeError, ValueError):
                # If not JSON serializable, use str representation
                key = str(key_data)

            if key not in seen:
                seen.add(key)
                unique.append(record)

        logger.info(f"✅ Deduplication complete: {len(unique)} unique records")
        return unique

    def correlate_by_field(
        self,
        data: List[Dict[str, Any]],
        field_name: str
    ) -> Dict[Any, List[Dict[str, Any]]]:
        """
        Group records by a specific field value.

        Args:
            data: Data to correlate
            field_name: Field to group by

        Returns:
            Dictionary mapping field values to records

        Example:
            data = [
                {"user_id": 1, "name": "John"},
                {"user_id": 1, "alert_id": 100},
                {"user_id": 2, "name": "Jane"}
            ]
            correlate_by_field(data, "user_id") → {
                1: [{"user_id": 1, "name": "John"}, {"user_id": 1, "alert_id": 100}],
                2: [{"user_id": 2, "name": "Jane"}]
            }
        """
        logger.info(f"🔗 Correlating by field: {field_name}")

        correlated: Dict[Any, List[Dict[str, Any]]] = {}

        for record in data:
            if field_name in record:
                value = record[field_name]
                if value not in correlated:
                    correlated[value] = []
                correlated[value].append(record)

        logger.info(f"✅ Correlated into {len(correlated)} groups")
        return correlated

    def flatten_nested(
        self,
        data: List[Dict[str, Any]],
        max_depth: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Flatten nested structures for easier display.

        Args:
            data: Data with nested dicts/lists
            max_depth: Maximum depth to flatten

        Returns:
            Flattened data

        Example:
            {"user": {"name": "John", "age": 30}} →
            {"user.name": "John", "user.age": 30}
        """
        logger.info(f"📋 Flattening {len(data)} records (max_depth={max_depth})...")

        flattened = []
        for record in data:
            flat_record = self._flatten_dict(record, max_depth=max_depth)
            flattened.append(flat_record)

        return flattened

    def _flatten_dict(
        self,
        d: Dict[str, Any],
        parent_key: str = "",
        sep: str = ".",
        max_depth: int = 2,
        current_depth: int = 0
    ) -> Dict[str, Any]:
        """
        Recursively flatten a nested dictionary.

        Args:
            d: Dictionary to flatten
            parent_key: Parent key prefix
            sep: Separator for keys
            max_depth: Maximum depth
            current_depth: Current recursion depth

        Returns:
            Flattened dictionary
        """
        if current_depth >= max_depth:
            return {parent_key: d} if parent_key else d

        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k

            if isinstance(v, dict):
                items.extend(
                    self._flatten_dict(
                        v, new_key, sep, max_depth, current_depth + 1
                    ).items()
                )
            elif isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                # Flatten first item of list
                items.extend(
                    self._flatten_dict(
                        v[0], f"{new_key}[0]", sep, max_depth, current_depth + 1
                    ).items()
                )
            else:
                items.append((new_key, v))

        return dict(items)
