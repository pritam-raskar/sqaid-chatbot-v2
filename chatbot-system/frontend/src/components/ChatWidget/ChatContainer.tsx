/**
 * Chat Container Component
 * Main chat interface container that manages the chat widget state
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Message, WebSocketMessage, PageContext } from '@/types';
import webSocketService from '@/services/WebSocketService';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import ChatHeader from './ChatHeader';
import LoadingIndicator from '../Common/LoadingIndicator';
import './ChatContainer.scss';

interface ChatContainerProps {
  pageContext?: PageContext;
  onAction?: (action: any) => void;
  initialSessionId?: string;
  wsUrl?: string;
}

const ChatContainer: React.FC<ChatContainerProps> = ({
  pageContext,
  onAction,
  initialSessionId,
  wsUrl = 'ws://localhost:8000/ws/chat'
}) => {
  // Step 1: State Management
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId || null);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 700, height: 900 });
  const [isResizing, setIsResizing] = useState(false);

  const messageIdCounter = useRef(0);
  const unsubscribeRefs = useRef<Array<() => void>>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const resizeStartPos = useRef({ x: 0, y: 0, width: 0, height: 0 });

  // Step 2: Lifecycle Methods
  useEffect(() => {
    // 1. Initialize WebSocket on mount
    console.log('Initializing WebSocket connection...');
    webSocketService.connect(wsUrl, sessionId || undefined);

    // 2. Subscribe to message events
    const unsubscribeMessage = webSocketService.onMessage(handleWebSocketMessage);
    const unsubscribeConnection = webSocketService.onConnectionChange(handleConnectionChange);

    unsubscribeRefs.current = [unsubscribeMessage, unsubscribeConnection];

    // 3. Handle connection status
    setIsConnected(webSocketService.isConnected());

    // Send initial context if available
    if (pageContext) {
      sendContextUpdate(pageContext);
    }

    // 4. Cleanup on unmount
    return () => {
      console.log('Cleaning up WebSocket connection...');
      unsubscribeRefs.current.forEach(unsubscribe => unsubscribe());
      webSocketService.disconnect();
    };
  }, [wsUrl]);

  // Update context when it changes
  useEffect(() => {
    if (pageContext && isConnected) {
      sendContextUpdate(pageContext);
    }
  }, [pageContext, isConnected]);

  const handleWebSocketMessage = useCallback((message: WebSocketMessage) => {
    console.log('Handling WebSocket message:', message);

    switch (message.type) {
      case 'connection_established':
        setSessionId(message.session_id || null);
        setError(null);
        break;

      case 'message_received':
        // Update message status to sent
        setMessages(prev => prev.map(msg =>
          msg.id === message.id ? { ...msg, status: 'sent' } : msg
        ));
        break;

      case 'stream_chunk':
        handleStreamChunk(message);
        break;

      case 'stream_complete':
        handleStreamComplete(message);
        setIsLoading(false);
        break;

      case 'error':
        setError(message.message || 'An error occurred');
        setIsLoading(false);
        break;

      case 'filter_generated':
        if (onAction && message.filters) {
          onAction({
            type: 'APPLY_FILTERS',
            payload: message.filters
          });
        }
        break;

      case 'visualization':
        handleVisualization(message);
        break;

      default:
        console.log('Unhandled message type:', message.type);
    }
  }, [onAction]);

  const handleConnectionChange = useCallback((connected: boolean) => {
    console.log('Connection status changed:', connected);
    setIsConnected(connected);

    if (!connected) {
      setError('Connection lost. Reconnecting...');
    } else {
      setError(null);
    }
  }, []);

  const handleStreamChunk = useCallback((message: WebSocketMessage) => {
    const { content, id } = message;

    setMessages(prev => {
      const existingMessageIndex = prev.findIndex(msg => msg.id === id);

      if (existingMessageIndex >= 0) {
        // Append to existing message
        const newMessages = [...prev];
        newMessages[existingMessageIndex] = {
          ...newMessages[existingMessageIndex],
          content: newMessages[existingMessageIndex].content + content
        };
        return newMessages;
      } else {
        // Create new assistant message
        const newMessage: Message = {
          id: id || `msg_${messageIdCounter.current++}`,
          role: 'assistant',
          content: content || '',
          timestamp: new Date().toISOString(),
          status: 'sent'
        };
        return [...prev, newMessage];
      }
    });
  }, []);

  const handleStreamComplete = useCallback((message: WebSocketMessage) => {
    // Mark message as complete
    if (message.id) {
      setMessages(prev => prev.map(msg =>
        msg.id === message.id ? { ...msg, status: 'sent' } : msg
      ));
    }
  }, []);

  const handleVisualization = useCallback((message: WebSocketMessage) => {
    console.log('Handling visualization:', message);

    // Attach visualization to the corresponding message
    const { message_id, data } = message;

    if (message_id && data) {
      setMessages(prev => prev.map(msg => {
        if (msg.id === message_id) {
          // Support multiple visualizations - convert to array or append
          const currentViz = msg.visualization;
          let newViz;

          if (Array.isArray(currentViz)) {
            // Already an array, append new visualization
            newViz = [...currentViz, data];
          } else if (currentViz) {
            // Single visualization exists, convert to array
            newViz = [currentViz, data];
          } else {
            // First visualization
            newViz = data;
          }

          console.log(`Visualization attached to message: ${message_id}`, newViz);
          return { ...msg, visualization: newViz };
        }
        return msg;
      }));
    }
  }, []);

  const sendMessage = useCallback((content: string) => {
    if (!content.trim() || !isConnected) return;

    // Create user message
    const userMessage: Message = {
      id: `msg_${messageIdCounter.current++}`,
      role: 'user',
      content: content.trim(),
      timestamp: new Date().toISOString(),
      status: 'sending'
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    // Send message via WebSocket with context
    webSocketService.sendMessage({
      type: 'chat',
      content: content.trim(),
      id: userMessage.id,
      context: pageContext || {}
    });
  }, [isConnected, pageContext]);

  const sendContextUpdate = (context: PageContext) => {
    if (!isConnected) return;

    webSocketService.sendMessage({
      type: 'context_update',
      context
    });
  };

  const clearChat = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  const toggleCollapse = useCallback(() => {
    setIsCollapsed(prev => !prev);
  }, []);

  // Resize handlers
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    resizeStartPos.current = {
      x: e.clientX,
      y: e.clientY,
      width: dimensions.width,
      height: dimensions.height
    };
  }, [dimensions]);

  const handleResizeMove = useCallback((e: MouseEvent) => {
    if (!isResizing) return;

    const deltaX = resizeStartPos.current.x - e.clientX;
    const deltaY = resizeStartPos.current.y - e.clientY;

    const newWidth = Math.max(300, Math.min(800, resizeStartPos.current.width + deltaX));
    const newHeight = Math.max(400, Math.min(900, resizeStartPos.current.height + deltaY));

    setDimensions({ width: newWidth, height: newHeight });
  }, [isResizing]);

  const handleResizeEnd = useCallback(() => {
    setIsResizing(false);
  }, []);

  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleResizeMove);
      document.addEventListener('mouseup', handleResizeEnd);
      return () => {
        document.removeEventListener('mousemove', handleResizeMove);
        document.removeEventListener('mouseup', handleResizeEnd);
      };
    }
  }, [isResizing, handleResizeMove, handleResizeEnd]);

  // Step 3: Render Logic
  return (
    <div
      ref={containerRef}
      className={`chat-container ${isCollapsed ? 'collapsed' : ''} ${isResizing ? 'resizing' : ''}`}
      style={!isCollapsed ? { width: `${dimensions.width}px`, height: `${dimensions.height}px` } : undefined}
    >
      {/* Resize handles */}
      {!isCollapsed && (
        <>
          <div className="resize-handle resize-handle-left" onMouseDown={handleResizeStart} />
          <div className="resize-handle resize-handle-top" onMouseDown={handleResizeStart} />
          <div className="resize-handle resize-handle-corner" onMouseDown={handleResizeStart} />
        </>
      )}

      {/* 1. Render header with status */}
      <ChatHeader
        isConnected={isConnected}
        sessionId={sessionId}
        onToggleCollapse={toggleCollapse}
        onClearChat={clearChat}
        isCollapsed={isCollapsed}
      />

      {!isCollapsed && (
        <>
          {/* 2. Render message list */}
          <MessageList
            messages={messages}
            isLoading={isLoading}
            error={error}
          />

          {/* 3. Show loading indicator */}
          {isLoading && <LoadingIndicator />}

          {/* 4. Render input component */}
          <MessageInput
            onSendMessage={sendMessage}
            disabled={!isConnected || isLoading}
            placeholder={
              !isConnected
                ? 'Connecting...'
                : isLoading
                ? 'Waiting for response...'
                : 'Type your message...'
            }
          />
        </>
      )}
    </div>
  );
};

export default ChatContainer;