/**
 * Type definitions for the chatbot system
 */

// Chart Types
export type ChartType = 'bar' | 'pie' | 'line' | 'area' | 'scatter';

export interface ChartDataPoint {
  name: string;
  value: number;
  percentage?: number; // For pie charts
}

export interface ScatterDataPoint {
  x: number;
  y: number;
  name?: string;
}

export interface ChartConfig {
  title?: string;
  xAxisLabel?: string;
  yAxisLabel?: string;
  colors?: string[];
  showLegend?: boolean;
  showGrid?: boolean;
  showPercentages?: boolean; // For pie charts
  smooth?: boolean; // For line/area charts
  showDots?: boolean; // For line/area charts
  showTrendline?: boolean; // For scatter plots
}

export interface VisualizationData {
  type: ChartType;
  data: ChartDataPoint[] | ScatterDataPoint[];
  config?: ChartConfig;
  metadata?: Record<string, any>;
}

// Unified visualization format (multiple chart types for same data)
export interface UnifiedVisualizationData {
  types: ChartType[];
  data: ChartDataPoint[] | ScatterDataPoint[];
  defaultType: ChartType;
  configs: Record<string, ChartConfig>;
  metadata?: Record<string, any>;
  count: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  status?: 'sending' | 'sent' | 'error';
  metadata?: Record<string, any>;
  visualization?: VisualizationData | VisualizationData[] | UnifiedVisualizationData; // Optional visualization data (single, array, or unified)
}

export interface ChatSession {
  id: string;
  createdAt: string;
  updatedAt: string;
  isActive: boolean;
  context?: PageContext;
}

export interface PageContext {
  pageName: string;
  dataSchema?: Record<string, any>;
  currentFilters?: FilterCriteria[];
  selectedRows?: any[];
  availableActions?: string[];
}

export interface FilterCriteria {
  field: string;
  operator: 'equals' | 'contains' | 'greater' | 'less' | 'between' | 'in';
  value: any;
  dataType?: 'string' | 'number' | 'date' | 'boolean';
}

export interface WebSocketMessage {
  type: string;
  content?: string;
  id?: string;
  message_id?: string; // For visualization messages
  data?: VisualizationData | UnifiedVisualizationData; // For visualization messages (single or unified)
  [key: string]: any;
}

export interface ChartData {
  type: 'line' | 'bar' | 'pie' | 'scatter';
  data: any[];
  options?: ChartOptions;
}

export interface ChartOptions {
  title?: string;
  xAxis?: string;
  yAxis?: string;
  colors?: string[];
  legend?: boolean;
}