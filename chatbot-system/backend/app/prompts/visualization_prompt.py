"""
Visualization Prompt Builder
Enhances LLM prompts with visualization detection capabilities
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class VisualizationPromptBuilder:
    """
    Builds enhanced prompts that guide LLMs to detect visualization opportunities
    and include structured metadata in responses.
    """

    def __init__(self):
        """Initialize the prompt builder."""
        self.base_instructions = self._load_base_instructions()

    def _load_base_instructions(self) -> str:
        """
        Load base visualization instructions for LLM.

        Returns:
            Formatted instruction string
        """
        return """
## Visualization Guidelines

You have the capability to enhance your responses with data visualizations. When appropriate, include visualization metadata in your response.

### When to Include Visualizations

Include visualization metadata when:
1. ✅ User explicitly requests: "show chart", "visualize", "graph", "plot", "diagram"
2. ✅ Data contains aggregations: counts, sums, averages grouped by category
3. ✅ Data shows distributions: percentages, proportions with >= 2 categories
4. ✅ Time-series data: trends over time with >= 3 data points
5. ✅ Comparative analysis: comparing values across different entities
6. ✅ Statistical summaries: showing relationships or patterns in data

DO NOT include visualization when:
- ❌ User requests a LIST of records: "show me", "list", "which", "get all", "associated", "find all"
- ❌ Single value answers ("The total is 42", "There are 5 alerts")
- ❌ Detailed record lists (tables are better for granular data)
- ❌ User requests specific format: "show as table", "list them"
- ❌ Data is too sparse (< 2 meaningful data points)
- ❌ Response is purely explanatory without quantitative data

### Supported Chart Types

Choose the appropriate chart type based on data characteristics:

**Bar Chart** (`bar`):
- Use for: Comparing discrete categories
- Best for: 2-20 categories
- Example: Alert counts by type, cases by status

**Pie Chart** (`pie`):
- Use for: Showing part-to-whole relationships
- Best for: 2-7 categories (percentages should sum to ~100%)
- Example: Distribution of alert severities, case categories

**Line Chart** (`line`):
- Use for: Time-series trends and continuous data
- Best for: >= 3 time points
- Example: Alerts over time, case volume trends

**Area Chart** (`area`):
- Use for: Cumulative trends over time
- Best for: >= 3 time points, showing magnitude of change
- Example: Cumulative case counts, stacked metrics over time

**Scatter Plot** (`scatter`):
- Use for: Correlations and relationships between two variables
- Best for: >= 5 data points
- Example: Response time vs. priority, case duration vs. complexity

### Response Format

When including visualization, append this JSON structure to your response:

```json
{
  "visualization": {
    "type": "bar|pie|line|area|scatter",
    "data": [
      {"name": "Category1", "value": 123},
      {"name": "Category2", "value": 456}
    ],
    "config": {
      "title": "Descriptive Chart Title",
      "xAxisLabel": "X-axis description",
      "yAxisLabel": "Y-axis description",
      "colors": ["#8884d8", "#82ca9d", "#ffc658"],
      "showLegend": true,
      "showGrid": true
    }
  }
}
```

### Data Format Requirements

**For Bar/Pie Charts:**
```json
{
  "data": [
    {"name": "Critical", "value": 45},
    {"name": "High", "value": 123},
    {"name": "Medium", "value": 67}
  ]
}
```

**For Line/Area Charts (time-series):**
```json
{
  "data": [
    {"name": "2024-01-01", "value": 23},
    {"name": "2024-01-02", "value": 45},
    {"name": "2024-01-03", "value": 34}
  ]
}
```

**For Scatter Plots:**
```json
{
  "data": [
    {"x": 1, "y": 23, "name": "Point1"},
    {"x": 2, "y": 45, "name": "Point2"}
  ]
}
```

### Configuration Guidelines

**Optional config fields:**
- `title`: Clear, descriptive title
- `xAxisLabel`: X-axis label (for bar, line, area, scatter)
- `yAxisLabel`: Y-axis label (for bar, line, area, scatter)
- `colors`: Array of hex colors (optional, defaults provided)
- `showLegend`: Boolean (default true)
- `showGrid`: Boolean (default true)

### Multiple Visualizations for Same Data

**IMPORTANT**: When data can be meaningfully viewed in multiple chart types, include MULTIPLE visualization blocks with the SAME data but DIFFERENT types.

For example, categorical data (like alert priorities or types) works well as BOTH pie and bar charts:

```json
{
  "visualization": {
    "type": "pie",
    "data": [
      {"name": "Critical", "value": 12},
      {"name": "High", "value": 34},
      {"name": "Medium", "value": 28}
    ],
    "config": {"title": "Alert Priority Distribution"}
  }
}

{
  "visualization": {
    "type": "bar",
    "data": [
      {"name": "Critical", "value": 12},
      {"name": "High", "value": 34},
      {"name": "Medium", "value": 28}
    ],
    "config": {"title": "Alert Count by Priority"}
  }
}
```

**When to provide multiple visualizations:**
- ✅ Categorical data: Provide BOTH `pie` (distribution %) AND `bar` (count comparison)
- ✅ Time-series data: Provide BOTH `line` (trend) AND `area` (cumulative)
- ✅ Always use the SAME data array for both visualizations
- ❌ Don't duplicate if user explicitly requested single chart type

### Important Rules

1. **Keep text response separate**: Always provide a complete text answer FIRST, then include visualization metadata
2. **Validate data**: Ensure all values are numeric and categories are meaningful
3. **Appropriate scale**: Don't visualize data with extreme outliers without noting them
4. **User intent**: If user says "don't show chart", respect that preference
5. **Data quality**: Only visualize when data is accurate and complete
6. **Multiple perspectives**: For categorical breakdowns, ALWAYS provide BOTH pie AND bar charts (same data, different views)

### Example Response with Multiple Visualizations

User: "Show me a breakdown of alerts by severity"

Response:
```
Based on your current alerts, here's the breakdown by severity:

- Critical: 12 alerts (15%)
- High: 34 alerts (42%)
- Medium: 28 alerts (35%)
- Low: 7 alerts (8%)

The majority of alerts are High severity (42%), followed by Medium (35%). Critical alerts represent 15% of the total.

{
  "visualization": {
    "type": "pie",
    "data": [
      {"name": "Critical", "value": 12},
      {"name": "High", "value": 34},
      {"name": "Medium", "value": 28},
      {"name": "Low", "value": 7}
    ],
    "config": {
      "title": "Alerts Distribution by Severity",
      "colors": ["#dc2626", "#f97316", "#fbbf24", "#3b82f6"],
      "showLegend": true
    }
  }
}

{
  "visualization": {
    "type": "bar",
    "data": [
      {"name": "Critical", "value": 12},
      {"name": "High", "value": 34},
      {"name": "Medium", "value": 28},
      {"name": "Low", "value": 7}
    ],
    "config": {
      "title": "Alert Count by Severity",
      "colors": ["#dc2626", "#f97316", "#fbbf24", "#3b82f6"],
      "showLegend": true
    }
  }
}
```

**Note**: The backend will automatically merge these into a single visualization block with toggle buttons for switching between pie and bar views.
"""

    def build_enhanced_prompt(
        self,
        base_prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Enhance base prompt with visualization instructions.

        Args:
            base_prompt: Original system prompt or user query context
            context: Additional context (query, user preferences, etc.)

        Returns:
            Enhanced prompt with visualization guidelines

        Steps:
        1. Combine base instructions with existing prompt
        2. Add context-specific hints if available
        3. Format for optimal LLM understanding
        """
        # Step 1: Combine base prompt with visualization instructions
        enhanced = f"{base_prompt}\n\n{self.base_instructions}"

        # Step 2: Add context-specific hints
        if context:
            query = context.get('query', '').lower()

            # Detect explicit visualization requests
            viz_keywords = [
                'chart', 'graph', 'plot', 'visualize', 'show me',
                'diagram', 'pie', 'bar', 'line', 'trend'
            ]

            if any(keyword in query for keyword in viz_keywords):
                enhanced += f"""

### Context Note
The user's query contains visualization-related keywords. Strongly consider including
visualization metadata if the data supports it.
User query: "{context.get('query', '')}"
"""

            # Detect aggregation queries
            agg_keywords = [
                'count', 'total', 'sum', 'average', 'breakdown',
                'distribution', 'by type', 'by status', 'grouped'
            ]

            if any(keyword in query for keyword in agg_keywords):
                enhanced += f"""

### Data Aggregation Detected
The query appears to request aggregated data, which is ideal for visualization.
Consider using bar or pie charts to present the results clearly.
"""

        # Step 3: Add final formatting note
        enhanced += """

### Response Structure Reminder
1. Provide complete text answer first
2. Include visualization JSON at the end (if appropriate)
3. Ensure JSON is valid and properly formatted
"""

        return enhanced

    def _extract_all_json_blocks(self, response: str) -> list[str]:
        """
        Extract all JSON blocks from response.

        Args:
            response: LLM response string

        Returns:
            List of JSON strings
        """
        json_blocks = []
        pos = 0

        while pos < len(response):
            # Find next opening brace
            start_idx = response.find('{', pos)
            if start_idx == -1:
                break

            # Find matching closing brace
            brace_count = 0
            end_idx = start_idx

            for i in range(start_idx, len(response)):
                if response[i] == '{':
                    brace_count += 1
                elif response[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break

            if brace_count == 0:
                json_str = response[start_idx:end_idx + 1]
                json_blocks.append(json_str)
                pos = end_idx + 1
            else:
                # No matching closing brace found
                break

        return json_blocks

    def validate_visualization_response(
        self,
        response: str
    ) -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Validate LLM response for proper visualization metadata.

        Now supports MULTIPLE visualization JSON blocks in a single response.

        Args:
            response: LLM response string

        Returns:
            Tuple of (is_valid, visualization_data, error_message)
            visualization_data can be a single viz dict or a list of viz dicts

        Steps:
        1. Check if response contains visualization metadata
        2. Extract all JSON blocks
        3. Validate each visualization
        4. Return all valid visualizations
        """
        try:
            # Step 1: Check for visualization metadata
            if '"visualization"' not in response and "'visualization'" not in response:
                # No visualization in response - this is valid (not all responses need viz)
                return True, None, None

            # Step 2: Extract all JSON blocks
            json_blocks = self._extract_all_json_blocks(response)

            if not json_blocks:
                return False, None, "No valid JSON found in response"

            # Step 3: Parse and validate each JSON block
            valid_visualizations = []

            for json_str in json_blocks:
                try:
                    data = json.loads(json_str)

                    # Check if this is a visualization object
                    if 'visualization' not in data:
                        continue

                    viz = data['visualization']

                    # Validate this visualization
                    is_valid, error = self._validate_single_visualization(viz)

                    if is_valid:
                        valid_visualizations.append(viz)
                        logger.info(f"Validated visualization: type={viz['type']}, data_points={len(viz['data'])}")
                    else:
                        logger.warning(f"Skipping invalid visualization: {error}")

                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping invalid JSON block: {str(e)}")
                    continue

            # Step 4: Return results
            if not valid_visualizations:
                return False, None, "No valid visualizations found in response"

            # Return single visualization or list of visualizations
            if len(valid_visualizations) == 1:
                return True, valid_visualizations[0], None
            else:
                return True, valid_visualizations, None

        except Exception as e:
            logger.error(f"Error validating visualization response: {e}")
            return False, None, f"Validation error: {str(e)}"

    def _validate_single_visualization(
        self,
        viz: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a single visualization object.

        Args:
            viz: Visualization dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Required fields
        if 'type' not in viz:
            return False, "Missing 'type' field in visualization"

        if 'data' not in viz:
            return False, "Missing 'data' field in visualization"

        # Validate data format
        supported_types = ['bar', 'pie', 'line', 'area', 'scatter']

        if viz['type'] not in supported_types:
            return False, f"Unsupported chart type: {viz['type']}"

        if not isinstance(viz['data'], list):
            return False, "'data' must be an array"

        if len(viz['data']) == 0:
            return False, "'data' array is empty"

        # Validate data point structure
        for idx, point in enumerate(viz['data']):
            if not isinstance(point, dict):
                return False, f"Data point {idx} is not an object"

            # Check for required fields based on chart type
            if viz['type'] == 'scatter':
                if 'x' not in point or 'y' not in point:
                    return False, f"Scatter plot data point {idx} missing 'x' or 'y'"
            else:
                if 'name' not in point or 'value' not in point:
                    return False, f"Data point {idx} missing 'name' or 'value'"

        return True, None

    def extract_text_and_visualization(
        self,
        response: str
    ) -> tuple[str, Optional[Dict[str, Any] | list[Dict[str, Any]]]]:
        """
        Separate text content from visualization metadata.

        Now supports multiple visualizations in a single response.

        Args:
            response: Full LLM response

        Returns:
            Tuple of (text_content, visualization_data)
            visualization_data can be:
            - None (no visualization)
            - Dict (single visualization)
            - List[Dict] (multiple visualizations)
        """
        try:
            # Find first JSON block
            start_idx = response.find('{')

            if start_idx == -1:
                # No JSON found, return full response as text
                return response.strip(), None

            # Extract text before first JSON block
            text_content = response[:start_idx].strip()

            # Extract and validate visualization(s)
            is_valid, viz_data, error = self.validate_visualization_response(response)

            if is_valid and viz_data:
                return text_content, viz_data
            else:
                # If validation failed, return full response as text
                if error:
                    logger.warning(f"Visualization validation failed: {error}")
                return response.strip(), None

        except Exception as e:
            logger.error(f"Error extracting text and visualization: {e}")
            return response.strip(), None
