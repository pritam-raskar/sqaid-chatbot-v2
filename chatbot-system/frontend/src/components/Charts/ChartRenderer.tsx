/**
 * ChartRenderer Component
 * Dynamically renders different chart types using Recharts
 * Supports unified visualization format with multiple chart type options
 */

import React, { useRef, useState } from 'react';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  LineChart,
  Line,
  AreaChart,
  Area,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
  ResponsiveContainer,
  Label
} from 'recharts';
import {
  VisualizationData,
  UnifiedVisualizationData,
  ChartDataPoint,
  ScatterDataPoint,
  ChartConfig,
  ChartType
} from '@/types';
import ChartToolbar from './ChartToolbar';
import './ChartRenderer.scss';

interface ChartRendererProps {
  data: VisualizationData | UnifiedVisualizationData;
  onExport?: (format: 'png' | 'svg' | 'csv') => void;
}

// Type guard to check if data is unified format
const isUnifiedFormat = (data: any): data is UnifiedVisualizationData => {
  return data && 'types' in data && 'defaultType' in data && Array.isArray(data.types);
};

const ChartRenderer: React.FC<ChartRendererProps> = ({ data, onExport }) => {
  const chartRef = useRef<HTMLDivElement>(null);

  // Handle both unified and single visualization formats
  const isUnified = isUnifiedFormat(data);
  const [activeType, setActiveType] = useState<ChartType>(
    isUnified ? data.defaultType : data.type
  );

  const chartData = data.data;
  const config: ChartConfig = isUnified
    ? (data.configs[activeType] || {})
    : (data.config || {});

  // Default configuration
  const defaultConfig: ChartConfig = {
    showLegend: true,
    showGrid: true,
    colors: ['#8884d8', '#82ca9d', '#ffc658', '#ff7c7c', '#8dd1e1', '#a4de6c', '#d084d0'],
    ...config
  };

  const colors = defaultConfig.colors || [];

  // Common chart props
  const commonProps = {
    width: 600,
    height: 400,
    margin: { top: 20, right: 30, left: 20, bottom: 20 }
  };

  const renderBarChart = () => {
    return (
      <ResponsiveContainer width="100%" height={400}>
        <BarChart data={chartData as ChartDataPoint[]} {...commonProps}>
          {defaultConfig.showGrid && <CartesianGrid strokeDasharray="3 3" />}
          <XAxis dataKey="name">
            {defaultConfig.xAxisLabel && (
              <Label value={defaultConfig.xAxisLabel} offset={-5} position="insideBottom" />
            )}
          </XAxis>
          <YAxis>
            {defaultConfig.yAxisLabel && (
              <Label value={defaultConfig.yAxisLabel} angle={-90} position="insideLeft" />
            )}
          </YAxis>
          <Tooltip />
          {defaultConfig.showLegend && <Legend />}
          <Bar dataKey="value" fill={colors[0]}>
            {(chartData as ChartDataPoint[]).map((entry, index) => (
              <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  };

  const renderPieChart = () => {
    const RADIAN = Math.PI / 180;

    // Custom label renderer for pie chart
    const renderCustomLabel = ({
      cx,
      cy,
      midAngle,
      innerRadius,
      outerRadius,
      percent,
      index
    }: any) => {
      const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
      const x = cx + radius * Math.cos(-midAngle * RADIAN);
      const y = cy + radius * Math.sin(-midAngle * RADIAN);

      return (
        <text
          x={x}
          y={y}
          fill="white"
          textAnchor={x > cx ? 'start' : 'end'}
          dominantBaseline="central"
          fontSize={12}
          fontWeight="bold"
        >
          {`${(percent * 100).toFixed(0)}%`}
        </text>
      );
    };

    return (
      <ResponsiveContainer width="100%" height={400}>
        <PieChart>
          <Pie
            data={chartData as ChartDataPoint[]}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={defaultConfig.showPercentages !== false ? renderCustomLabel : undefined}
            outerRadius={120}
            fill="#8884d8"
            dataKey="value"
          >
            {(chartData as ChartDataPoint[]).map((entry, index) => (
              <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: any, name: string, props: any) => {
              const percentage = props.payload.percentage;
              return [`${value} (${percentage}%)`, name];
            }}
          />
          {defaultConfig.showLegend && <Legend />}
        </PieChart>
      </ResponsiveContainer>
    );
  };

  const renderLineChart = () => {
    return (
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={chartData as ChartDataPoint[]} {...commonProps}>
          {defaultConfig.showGrid && <CartesianGrid strokeDasharray="3 3" />}
          <XAxis dataKey="name">
            {defaultConfig.xAxisLabel && (
              <Label value={defaultConfig.xAxisLabel} offset={-5} position="insideBottom" />
            )}
          </XAxis>
          <YAxis>
            {defaultConfig.yAxisLabel && (
              <Label value={defaultConfig.yAxisLabel} angle={-90} position="insideLeft" />
            )}
          </YAxis>
          <Tooltip />
          {defaultConfig.showLegend && <Legend />}
          <Line
            type={defaultConfig.smooth ? 'monotone' : 'linear'}
            dataKey="value"
            stroke={colors[0]}
            strokeWidth={2}
            dot={defaultConfig.showDots !== false}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    );
  };

  const renderAreaChart = () => {
    return (
      <ResponsiveContainer width="100%" height={400}>
        <AreaChart data={chartData as ChartDataPoint[]} {...commonProps}>
          {defaultConfig.showGrid && <CartesianGrid strokeDasharray="3 3" />}
          <XAxis dataKey="name">
            {defaultConfig.xAxisLabel && (
              <Label value={defaultConfig.xAxisLabel} offset={-5} position="insideBottom" />
            )}
          </XAxis>
          <YAxis>
            {defaultConfig.yAxisLabel && (
              <Label value={defaultConfig.yAxisLabel} angle={-90} position="insideLeft" />
            )}
          </YAxis>
          <Tooltip />
          {defaultConfig.showLegend && <Legend />}
          <Area
            type={defaultConfig.smooth ? 'monotone' : 'linear'}
            dataKey="value"
            stroke={colors[0]}
            fill={colors[0]}
            fillOpacity={0.6}
          />
        </AreaChart>
      </ResponsiveContainer>
    );
  };

  const renderScatterChart = () => {
    return (
      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart {...commonProps}>
          {defaultConfig.showGrid && <CartesianGrid strokeDasharray="3 3" />}
          <XAxis type="number" dataKey="x">
            {defaultConfig.xAxisLabel && (
              <Label value={defaultConfig.xAxisLabel} offset={-5} position="insideBottom" />
            )}
          </XAxis>
          <YAxis type="number" dataKey="y">
            {defaultConfig.yAxisLabel && (
              <Label value={defaultConfig.yAxisLabel} angle={-90} position="insideLeft" />
            )}
          </YAxis>
          <Tooltip cursor={{ strokeDasharray: '3 3' }} />
          {defaultConfig.showLegend && <Legend />}
          <Scatter
            name="Data Points"
            data={chartData as ScatterDataPoint[]}
            fill={colors[0]}
          />
        </ScatterChart>
      </ResponsiveContainer>
    );
  };

  const renderChart = () => {
    switch (activeType) {
      case 'bar':
        return renderBarChart();
      case 'pie':
        return renderPieChart();
      case 'line':
        return renderLineChart();
      case 'area':
        return renderAreaChart();
      case 'scatter':
        return renderScatterChart();
      default:
        return <div className="chart-error">Unsupported chart type: {activeType}</div>;
    }
  };

  const getChartTypeIcon = (chartType: ChartType): string => {
    switch (chartType) {
      case 'bar': return '📊';
      case 'pie': return '🥧';
      case 'line': return '📈';
      case 'area': return '📉';
      case 'scatter': return '⚫';
      default: return '📊';
    }
  };

  const getChartTypeLabel = (chartType: ChartType): string => {
    return chartType.charAt(0).toUpperCase() + chartType.slice(1);
  };

  return (
    <div className="chart-renderer" ref={chartRef}>
      {defaultConfig.title && (
        <div className="chart-title">{defaultConfig.title}</div>
      )}

      {/* Chart type selector for unified visualizations */}
      {isUnified && data.types.length > 1 && (
        <div className="chart-type-selector">
          {data.types.map((chartType) => (
            <button
              key={chartType}
              className={`chart-type-button ${activeType === chartType ? 'active' : ''}`}
              onClick={() => setActiveType(chartType)}
              title={`View as ${getChartTypeLabel(chartType)} chart`}
            >
              <span className="chart-icon">{getChartTypeIcon(chartType)}</span>
              <span className="chart-label">{getChartTypeLabel(chartType)}</span>
            </button>
          ))}
        </div>
      )}

      {onExport && (
        <ChartToolbar
          chartRef={chartRef}
          chartData={data}
          onExport={onExport}
        />
      )}

      <div className="chart-container">
        {renderChart()}
      </div>
    </div>
  );
};

export default ChartRenderer;
