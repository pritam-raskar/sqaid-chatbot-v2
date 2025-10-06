/**
 * Message Item Component
 * Individual message display with markdown support
 */

import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Message, VisualizationData, UnifiedVisualizationData } from '@/types';
import { formatTime } from '@/utils/dateUtils';
import ChartRenderer from '../Charts/ChartRenderer';
import './MessageItem.scss';

interface MessageItemProps {
  message: Message;
  onVisualizationReceived?: (messageId: string, visualization: VisualizationData) => void;
}

const MessageItem: React.FC<MessageItemProps> = ({ message, onVisualizationReceived }) => {
  const [copied, setCopied] = useState(false);
  const [showChart, setShowChart] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy message:', err);
    }
  };

  const getStatusIcon = () => {
    switch (message.status) {
      case 'sending':
        return '⏳';
      case 'error':
        return '❌';
      case 'sent':
      default:
        return null;
    }
  };

  // Handle visualization fade-in animation
  useEffect(() => {
    if (message.visualization) {
      // Trigger fade-in animation after a short delay
      const timer = setTimeout(() => setShowChart(true), 300);
      return () => clearTimeout(timer);
    }
  }, [message.visualization]);

  // Handle chart export
  const handleChartExport = (format: 'png' | 'svg' | 'csv') => {
    console.log(`Exporting chart as ${format} for message ${message.id}`);
  };

  // Type guard to check if visualization is unified format
  const isUnifiedFormat = (viz: any): viz is UnifiedVisualizationData => {
    return viz && 'types' in viz && 'defaultType' in viz && Array.isArray(viz.types);
  };

  return (
    <div className={`message-item ${message.role}`}>
      <div className="message-avatar">
        {message.role === 'user' ? '👤' : '🤖'}
      </div>
      <div className="message-content-wrapper">
        <div className="message-content">
          {message.role === 'assistant' ? (
            <ReactMarkdown
              components={{
                // Custom renderers for markdown elements
                code: ({ node, inline, className, children, ...props }) => {
                  const match = /language-(\w+)/.exec(className || '');
                  return !inline && match ? (
                    <div className="code-block">
                      <div className="code-header">
                        <span>{match[1]}</span>
                        <button
                          onClick={() => navigator.clipboard.writeText(String(children))}
                          className="copy-button"
                        >
                          Copy
                        </button>
                      </div>
                      <pre>
                        <code className={className} {...props}>
                          {children}
                        </code>
                      </pre>
                    </div>
                  ) : (
                    <code className="inline-code" {...props}>
                      {children}
                    </code>
                  );
                },
                p: ({ children }) => <p className="message-paragraph">{children}</p>,
                ul: ({ children }) => <ul className="message-list" style={{ listStyleType: 'disc' }}>{children}</ul>,
                ol: ({ children }) => <ol className="message-list" style={{ listStyleType: 'decimal' }}>{children}</ol>,
                li: ({ children }) => <li style={{ marginBottom: '8px' }}>{children}</li>,
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="message-link">
                    {children}
                  </a>
                ),
                br: () => <br />,
              }}
            >
              {message.content}
            </ReactMarkdown>
          ) : (
            <p className="message-text">{message.content}</p>
          )}
        </div>

        {/* Render visualization if available */}
        {message.visualization && (
          <div className={`chart-wrapper ${showChart ? 'visible' : 'loading'}`}>
            {isUnifiedFormat(message.visualization) ? (
              // Unified format with multiple chart type options
              <ChartRenderer
                data={message.visualization}
                onExport={handleChartExport}
              />
            ) : Array.isArray(message.visualization) ? (
              // Legacy array format (backward compatibility)
              message.visualization.map((viz, idx) => (
                <ChartRenderer
                  key={`viz-${message.id}-${idx}`}
                  data={viz}
                  onExport={handleChartExport}
                />
              ))
            ) : (
              // Legacy single visualization format
              <ChartRenderer
                data={message.visualization}
                onExport={handleChartExport}
              />
            )}
          </div>
        )}

        <div className="message-footer">
          <span className="message-time">{formatTime(message.timestamp)}</span>
          {message.status && (
            <span className="message-status">
              {getStatusIcon()}
            </span>
          )}
          <button
            className={`copy-button ${copied ? 'copied' : ''}`}
            onClick={handleCopy}
            title="Copy message"
          >
            {copied ? '✓' : '📋'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default MessageItem;