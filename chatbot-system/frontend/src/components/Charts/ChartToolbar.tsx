/**
 * ChartToolbar Component
 * Provides export functionality for charts (PNG, SVG, CSV)
 */

import React, { useState } from 'react';
import { VisualizationData } from '@/types';
import { exportChartAsPNG, exportChartAsSVG, exportChartAsCSV } from '@/utils/chartExport';
import './ChartToolbar.scss';

interface ChartToolbarProps {
  chartRef: React.RefObject<HTMLDivElement>;
  chartData: VisualizationData;
  onExport?: (format: 'png' | 'svg' | 'csv') => void;
}

const ChartToolbar: React.FC<ChartToolbarProps> = ({ chartRef, chartData, onExport }) => {
  const [isExporting, setIsExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState<string | null>(null);

  const handleExport = async (format: 'png' | 'svg' | 'csv') => {
    if (isExporting) return;

    setIsExporting(true);
    setExportStatus(null);

    try {
      const filename = `chart-${chartData.type}-${Date.now()}`;

      switch (format) {
        case 'png':
          if (chartRef.current) {
            await exportChartAsPNG(chartRef.current, filename);
            setExportStatus('PNG exported successfully');
          }
          break;

        case 'svg':
          if (chartRef.current) {
            await exportChartAsSVG(chartRef.current, filename);
            setExportStatus('SVG exported successfully');
          }
          break;

        case 'csv':
          exportChartAsCSV(chartData, filename);
          setExportStatus('CSV exported successfully');
          break;
      }

      // Call optional callback
      if (onExport) {
        onExport(format);
      }

      // Clear status after 2 seconds
      setTimeout(() => setExportStatus(null), 2000);

    } catch (error) {
      console.error(`Failed to export chart as ${format}:`, error);
      setExportStatus(`Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setTimeout(() => setExportStatus(null), 3000);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="chart-toolbar">
      <div className="toolbar-buttons">
        <button
          className="toolbar-button"
          onClick={() => handleExport('png')}
          disabled={isExporting}
          title="Export as PNG image"
        >
          📥 PNG
        </button>

        <button
          className="toolbar-button"
          onClick={() => handleExport('svg')}
          disabled={isExporting}
          title="Export as SVG vector"
        >
          📊 SVG
        </button>

        <button
          className="toolbar-button"
          onClick={() => handleExport('csv')}
          disabled={isExporting}
          title="Export data as CSV"
        >
          📄 CSV
        </button>
      </div>

      {exportStatus && (
        <div className={`export-status ${exportStatus.includes('failed') ? 'error' : 'success'}`}>
          {exportStatus}
        </div>
      )}
    </div>
  );
};

export default ChartToolbar;
