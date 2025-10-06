"""
Visualization Extractor
Extracts, validates, and enriches visualization metadata from LLM responses
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class VisualizationMetadata:
    """
    Data class for validated visualization metadata.
    """
    chart_type: str
    data: List[Dict[str, Any]]
    config: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'type': self.chart_type,
            'data': self.data,
            'config': self.config,
            'metadata': self.metadata
        }


class VisualizationExtractor:
    """
    Extracts and validates visualization metadata from LLM responses.
    Enriches data with additional calculations and formatting.
    """

    def __init__(self):
        """Initialize the extractor with validation rules."""
        self.supported_types = ['bar', 'pie', 'line', 'area', 'scatter']

        # Minimum data points required for each chart type
        self.min_data_points = {
            'bar': 1,
            'pie': 2,
            'line': 2,
            'area': 2,
            'scatter': 3
        }

        # Maximum recommended data points for optimal display
        self.max_data_points = {
            'bar': 20,
            'pie': 7,
            'line': 50,
            'area': 50,
            'scatter': 100
        }

        # Default color palettes
        self.default_colors = {
            'default': ['#8884d8', '#82ca9d', '#ffc658', '#ff7c7c', '#8dd1e1', '#a4de6c', '#d084d0'],
            'severity': ['#dc2626', '#f97316', '#fbbf24', '#3b82f6', '#10b981'],
            'status': ['#10b981', '#fbbf24', '#f97316', '#6b7280'],
            'categorical': ['#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316', '#f59e0b', '#84cc16']
        }

    def extract(self, visualization_data: Dict[str, Any]) -> Optional[VisualizationMetadata]:
        """
        Extract and validate visualization metadata.

        Args:
            visualization_data: Raw visualization data from LLM response

        Returns:
            VisualizationMetadata object or None if invalid

        Steps:
        1. Validate basic structure
        2. Validate chart type
        3. Validate data format
        4. Transform and enrich data
        5. Enrich configuration
        6. Return metadata object
        """
        try:
            # Step 1: Validate basic structure
            if not isinstance(visualization_data, dict):
                logger.warning("Visualization data is not a dictionary")
                return None

            if 'type' not in visualization_data or 'data' not in visualization_data:
                logger.warning("Missing required fields: 'type' or 'data'")
                return None

            chart_type = visualization_data['type']
            data = visualization_data['data']
            config = visualization_data.get('config', {})

            # Step 2: Validate chart type
            if chart_type not in self.supported_types:
                logger.warning(f"Unsupported chart type: {chart_type}")
                return VisualizationMetadata(
                    chart_type=chart_type,
                    data=[],
                    is_valid=False,
                    error_message=f"Unsupported chart type: {chart_type}"
                )

            # Step 3: Validate data format
            validation_result = self._validate_data(chart_type, data)
            if not validation_result['is_valid']:
                logger.warning(f"Data validation failed: {validation_result['error']}")
                return VisualizationMetadata(
                    chart_type=chart_type,
                    data=data,
                    is_valid=False,
                    error_message=validation_result['error']
                )

            # Step 4: Transform and enrich data
            enriched_data = self._transform_data(chart_type, data)

            # Step 5: Enrich configuration
            enriched_config = self._enrich_config(chart_type, config, enriched_data)

            # Step 6: Create and return metadata object
            metadata = VisualizationMetadata(
                chart_type=chart_type,
                data=enriched_data,
                config=enriched_config,
                is_valid=True,
                metadata={
                    'extracted_at': datetime.utcnow().isoformat(),
                    'data_point_count': len(enriched_data),
                    'chart_category': self._get_chart_category(chart_type)
                }
            )

            logger.info(f"Successfully extracted visualization: type={chart_type}, points={len(enriched_data)}")
            return metadata

        except Exception as e:
            logger.error(f"Error extracting visualization: {e}")
            return None

    def _validate_data(self, chart_type: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate data format for specific chart type.

        Args:
            chart_type: Type of chart
            data: Data array to validate

        Returns:
            Dictionary with is_valid flag and error message
        """
        try:
            # Check if data is a list
            if not isinstance(data, list):
                return {'is_valid': False, 'error': 'Data must be an array'}

            # Check minimum data points
            min_points = self.min_data_points.get(chart_type, 2)
            if len(data) < min_points:
                return {
                    'is_valid': False,
                    'error': f'{chart_type} chart requires at least {min_points} data points'
                }

            # Check maximum data points (warning, not error)
            max_points = self.max_data_points.get(chart_type, 100)
            if len(data) > max_points:
                logger.warning(
                    f'{chart_type} chart has {len(data)} points, '
                    f'recommended maximum is {max_points}'
                )

            # Validate data point structure
            for idx, point in enumerate(data):
                if not isinstance(point, dict):
                    return {
                        'is_valid': False,
                        'error': f'Data point {idx} is not an object'
                    }

                # Check required fields based on chart type
                if chart_type == 'scatter':
                    if 'x' not in point or 'y' not in point:
                        return {
                            'is_valid': False,
                            'error': f'Scatter plot point {idx} missing x or y coordinate'
                        }
                    # Validate numeric values
                    if not isinstance(point['x'], (int, float)) or not isinstance(point['y'], (int, float)):
                        return {
                            'is_valid': False,
                            'error': f'Scatter plot point {idx} has non-numeric coordinates'
                        }
                else:
                    if 'name' not in point or 'value' not in point:
                        return {
                            'is_valid': False,
                            'error': f'Data point {idx} missing name or value'
                        }
                    # Validate numeric value
                    if not isinstance(point['value'], (int, float)):
                        return {
                            'is_valid': False,
                            'error': f'Data point {idx} has non-numeric value'
                        }

            return {'is_valid': True, 'error': None}

        except Exception as e:
            return {'is_valid': False, 'error': f'Validation error: {str(e)}'}

    def _transform_data(self, chart_type: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform and enrich data based on chart type.

        Args:
            chart_type: Type of chart
            data: Raw data array

        Returns:
            Enriched data array
        """
        try:
            enriched_data = []

            if chart_type == 'pie':
                # Calculate percentages for pie chart
                total = sum(point.get('value', 0) for point in data)

                for point in data:
                    enriched_point = point.copy()
                    value = point.get('value', 0)
                    enriched_point['percentage'] = round((value / total * 100), 1) if total > 0 else 0
                    enriched_data.append(enriched_point)

            elif chart_type in ['line', 'area']:
                # Sort by name (assuming it's a date/time or sequential)
                # Try to parse dates, fallback to string sort
                try:
                    sorted_data = sorted(data, key=lambda x: datetime.fromisoformat(str(x['name'])))
                    enriched_data = sorted_data
                except:
                    # If not dates, keep original order or sort by name
                    enriched_data = data

            elif chart_type == 'bar':
                # Sort by value descending for better visualization
                enriched_data = sorted(data, key=lambda x: x.get('value', 0), reverse=True)

            elif chart_type == 'scatter':
                # Keep scatter data as-is, but ensure it has name field
                for point in data:
                    enriched_point = point.copy()
                    if 'name' not in enriched_point:
                        enriched_point['name'] = f"({point['x']}, {point['y']})"
                    enriched_data.append(enriched_point)

            else:
                enriched_data = data

            return enriched_data

        except Exception as e:
            logger.error(f"Error transforming data: {e}")
            return data

    def _enrich_config(
        self,
        chart_type: str,
        config: Dict[str, Any],
        data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Enrich configuration with defaults and smart suggestions.

        Args:
            chart_type: Type of chart
            config: Raw configuration
            data: Enriched data

        Returns:
            Enriched configuration
        """
        enriched_config = config.copy()

        # Add default colors if not provided
        if 'colors' not in enriched_config:
            # Try to detect category from data
            if data:
                first_name = str(data[0].get('name', '')).lower()

                # Severity detection
                if any(term in first_name for term in ['critical', 'high', 'medium', 'low', 'severe']):
                    enriched_config['colors'] = self.default_colors['severity']
                # Status detection
                elif any(term in first_name for term in ['open', 'closed', 'pending', 'resolved', 'active']):
                    enriched_config['colors'] = self.default_colors['status']
                else:
                    enriched_config['colors'] = self.default_colors['default']
            else:
                enriched_config['colors'] = self.default_colors['default']

        # Add default title if not provided
        if 'title' not in enriched_config:
            enriched_config['title'] = self._generate_default_title(chart_type, data)

        # Add default legend setting
        if 'showLegend' not in enriched_config:
            enriched_config['showLegend'] = True

        # Add default grid setting
        if 'showGrid' not in enriched_config:
            enriched_config['showGrid'] = chart_type in ['line', 'area', 'scatter', 'bar']

        # Chart-specific enrichments
        if chart_type == 'pie':
            if 'showPercentages' not in enriched_config:
                enriched_config['showPercentages'] = True

        elif chart_type in ['line', 'area']:
            if 'smooth' not in enriched_config:
                enriched_config['smooth'] = True
            if 'showDots' not in enriched_config:
                enriched_config['showDots'] = len(data) <= 20  # Only show dots if not too many points

        elif chart_type == 'scatter':
            if 'showTrendline' not in enriched_config:
                enriched_config['showTrendline'] = False

        return enriched_config

    def _generate_default_title(self, chart_type: str, data: List[Dict[str, Any]]) -> str:
        """
        Generate a default chart title based on chart type and data.

        Args:
            chart_type: Type of chart
            data: Data array

        Returns:
            Generated title string
        """
        if not data:
            return f"{chart_type.capitalize()} Chart"

        # Try to infer what the data represents
        if chart_type == 'pie':
            return "Distribution"
        elif chart_type == 'bar':
            return "Comparison"
        elif chart_type in ['line', 'area']:
            return "Trend Over Time"
        elif chart_type == 'scatter':
            return "Correlation"

        return f"{chart_type.capitalize()} Chart"

    def _get_chart_category(self, chart_type: str) -> str:
        """
        Get chart category for metadata.

        Args:
            chart_type: Type of chart

        Returns:
            Category string
        """
        categories = {
            'bar': 'comparison',
            'pie': 'composition',
            'line': 'trend',
            'area': 'trend',
            'scatter': 'correlation'
        }
        return categories.get(chart_type, 'other')

    def to_websocket_message(
        self,
        metadata: VisualizationMetadata,
        message_id: str
    ) -> Dict[str, Any]:
        """
        Convert visualization metadata to WebSocket message format.

        Args:
            metadata: VisualizationMetadata object
            message_id: Associated message ID

        Returns:
            WebSocket message dictionary
        """
        return {
            'type': 'visualization',
            'message_id': message_id,
            'data': metadata.to_dict(),
            'timestamp': datetime.utcnow().isoformat()
        }

    def validate_and_extract(
        self,
        raw_visualization: Dict[str, Any]
    ) -> tuple[bool, Optional[VisualizationMetadata], Optional[str]]:
        """
        Convenience method to validate and extract in one call.

        Args:
            raw_visualization: Raw visualization data

        Returns:
            Tuple of (is_valid, metadata, error_message)
        """
        metadata = self.extract(raw_visualization)

        if metadata is None:
            return False, None, "Failed to extract visualization"

        if not metadata.is_valid:
            return False, metadata, metadata.error_message

        return True, metadata, None
