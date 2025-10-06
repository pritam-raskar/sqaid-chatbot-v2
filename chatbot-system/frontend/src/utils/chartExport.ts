/**
 * Chart Export Utilities
 * Functions for exporting charts as PNG, SVG, and CSV
 */

import { toPng, toSvg } from 'html-to-image';
import { saveAs } from 'file-saver';
import { VisualizationData, ChartDataPoint, ScatterDataPoint } from '@/types';

/**
 * Export chart as PNG image
 *
 * @param chartElement - DOM element containing the chart
 * @param filename - Filename without extension
 */
export async function exportChartAsPNG(
  chartElement: HTMLElement,
  filename: string
): Promise<void> {
  try {
    // Convert to PNG data URL with high quality
    const dataUrl = await toPng(chartElement, {
      quality: 0.95,
      backgroundColor: '#ffffff',
      pixelRatio: 2 // Higher resolution
    });

    // Download the image
    saveAs(dataUrl, `${filename}.png`);
  } catch (error) {
    console.error('Error exporting chart as PNG:', error);
    throw new Error('Failed to export chart as PNG');
  }
}

/**
 * Export chart as SVG vector image
 *
 * @param chartElement - DOM element containing the chart
 * @param filename - Filename without extension
 */
export async function exportChartAsSVG(
  chartElement: HTMLElement,
  filename: string
): Promise<void> {
  try {
    // Convert to SVG data URL
    const dataUrl = await toSvg(chartElement, {
      backgroundColor: '#ffffff'
    });

    // Download the SVG
    saveAs(dataUrl, `${filename}.svg`);
  } catch (error) {
    console.error('Error exporting chart as SVG:', error);
    throw new Error('Failed to export chart as SVG');
  }
}

/**
 * Export chart data as CSV
 *
 * @param data - Visualization data
 * @param filename - Filename without extension
 */
export function exportChartAsCSV(
  data: VisualizationData,
  filename: string
): void {
  try {
    const csv = convertToCSV(data);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    saveAs(blob, `${filename}.csv`);
  } catch (error) {
    console.error('Error exporting chart as CSV:', error);
    throw new Error('Failed to export chart as CSV');
  }
}

/**
 * Convert visualization data to CSV format
 *
 * @param data - Visualization data
 * @returns CSV string
 */
function convertToCSV(data: VisualizationData): string {
  const { type, data: chartData, config } = data;

  // CSV header
  let csv = '';

  // Add title if available
  if (config?.title) {
    csv += `# ${config.title}\n`;
  }

  // Add chart type
  csv += `# Chart Type: ${type}\n`;
  csv += '\n';

  // Handle different chart types
  if (type === 'scatter') {
    // Scatter plot: X, Y, Name columns
    csv += 'X,Y,Name\n';

    (chartData as ScatterDataPoint[]).forEach((point) => {
      const name = point.name || `(${point.x}, ${point.y})`;
      csv += `${point.x},${point.y},"${escapeCsvValue(name)}"\n`;
    });
  } else {
    // Bar, Pie, Line, Area: Name, Value, Percentage (if available)
    const hasPercentage = (chartData as ChartDataPoint[]).some(
      (point) => point.percentage !== undefined
    );

    if (hasPercentage) {
      csv += 'Category,Value,Percentage\n';
    } else {
      csv += 'Category,Value\n';
    }

    (chartData as ChartDataPoint[]).forEach((point) => {
      const name = escapeCsvValue(point.name);
      const value = point.value;
      const percentage = point.percentage;

      if (hasPercentage && percentage !== undefined) {
        csv += `"${name}",${value},${percentage}%\n`;
      } else {
        csv += `"${name}",${value}\n`;
      }
    });
  }

  // Add metadata if available
  if (data.metadata) {
    csv += '\n# Metadata\n';
    Object.entries(data.metadata).forEach(([key, value]) => {
      csv += `# ${key}: ${value}\n`;
    });
  }

  return csv;
}

/**
 * Escape CSV value (handle quotes and commas)
 *
 * @param value - Value to escape
 * @returns Escaped value
 */
function escapeCsvValue(value: string): string {
  // Escape double quotes by doubling them
  return value.replace(/"/g, '""');
}

/**
 * Download data as JSON file (bonus utility)
 *
 * @param data - Data to export
 * @param filename - Filename without extension
 */
export function exportAsJSON(data: any, filename: string): void {
  try {
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
    saveAs(blob, `${filename}.json`);
  } catch (error) {
    console.error('Error exporting as JSON:', error);
    throw new Error('Failed to export as JSON');
  }
}

/**
 * Copy chart data to clipboard
 *
 * @param data - Visualization data
 * @returns Promise that resolves when copied
 */
export async function copyChartDataToClipboard(
  data: VisualizationData
): Promise<void> {
  try {
    const csv = convertToCSV(data);
    await navigator.clipboard.writeText(csv);
  } catch (error) {
    console.error('Error copying to clipboard:', error);
    throw new Error('Failed to copy chart data to clipboard');
  }
}
