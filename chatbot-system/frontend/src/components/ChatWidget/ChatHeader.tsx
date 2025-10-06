/**
 * Chat Header Component
 * Displays connection status and controls
 */

import React from 'react';
import './ChatHeader.scss';

interface ChatHeaderProps {
  isConnected: boolean;
  sessionId: string | null;
  onToggleCollapse: () => void;
  onClearChat: () => void;
  isCollapsed: boolean;
}

const ChatHeader: React.FC<ChatHeaderProps> = ({
  isConnected,
  sessionId,
  onToggleCollapse,
  onClearChat,
  isCollapsed
}) => {
  return (
    <div className="chat-header">
      <div className="chat-header-left">
        <div className={`connection-indicator ${isConnected ? 'connected' : 'disconnected'}`} />
        <span className="chat-title">Financial Assistant</span>
        {sessionId && !isCollapsed && (
          <span className="session-id" title={sessionId}>
            Session: {sessionId.slice(0, 8)}...
          </span>
        )}
      </div>
      <div className="chat-header-actions">
        {!isCollapsed && (
          <button
            className="header-button"
            onClick={onClearChat}
            title="Clear chat"
            aria-label="Clear chat"
          >
            🗑️
          </button>
        )}
        <button
          className="header-button"
          onClick={onToggleCollapse}
          title={isCollapsed ? 'Expand' : 'Collapse'}
          aria-label={isCollapsed ? 'Expand' : 'Collapse'}
        >
          {isCollapsed ? '▲' : '▼'}
        </button>
      </div>
    </div>
  );
};

export default ChatHeader;