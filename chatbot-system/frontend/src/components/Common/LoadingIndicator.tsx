/**
 * Loading Indicator Component
 * Simple loading animation
 */

import React from 'react';
import './LoadingIndicator.scss';

interface LoadingIndicatorProps {
  text?: string;
}

const LoadingIndicator: React.FC<LoadingIndicatorProps> = ({ text = 'Thinking...' }) => {
  return (
    <div className="loading-indicator">
      <div className="spinner">
        <div className="bounce1"></div>
        <div className="bounce2"></div>
        <div className="bounce3"></div>
      </div>
      {text && <span className="loading-text">{text}</span>}
    </div>
  );
};

export default LoadingIndicator;