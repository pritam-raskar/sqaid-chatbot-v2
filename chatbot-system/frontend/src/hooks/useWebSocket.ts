/**
 * useWebSocket Hook
 * Low-level WebSocket connection hook
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { WebSocketService } from '../services/WebSocketService';

export interface UseWebSocketOptions {
  url: string;
  sessionId?: string;
  autoConnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Error) => void;
  onMessage?: (data: any) => void;
}

export interface UseWebSocketReturn {
  isConnected: boolean;
  connectionState: 'connecting' | 'connected' | 'disconnected' | 'reconnecting';
  error: Error | null;
  sendMessage: (message: any) => void;
  connect: () => void;
  disconnect: () => void;
  reconnect: () => void;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    url,
    sessionId,
    autoConnect = true,
    onOpen,
    onClose,
    onError,
    onMessage
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [connectionState, setConnectionState] = useState<UseWebSocketReturn['connectionState']>('disconnected');
  const [error, setError] = useState<Error | null>(null);

  const wsServiceRef = useRef<WebSocketService | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize WebSocket service
  useEffect(() => {
    wsServiceRef.current = WebSocketService.getInstance();

    if (autoConnect) {
      connect();
    }

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      disconnect();
    };
  }, [url, sessionId]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!wsServiceRef.current) return;

    setConnectionState('connecting');
    setError(null);

    try {
      wsServiceRef.current.connect(url, sessionId);

      // Setup event handlers
      wsServiceRef.current.onOpen(() => {
        setIsConnected(true);
        setConnectionState('connected');
        setError(null);
        onOpen?.();
      });

      wsServiceRef.current.onClose(() => {
        setIsConnected(false);
        setConnectionState('disconnected');
        onClose?.();
      });

      wsServiceRef.current.onError((err) => {
        setError(err);
        setConnectionState('disconnected');
        onError?.(err);
      });

      if (onMessage) {
        wsServiceRef.current.onMessage(onMessage);
      }

    } catch (err) {
      const error = err instanceof Error ? err : new Error('Connection failed');
      setError(error);
      setConnectionState('disconnected');
      onError?.(error);
    }
  }, [url, sessionId, onOpen, onClose, onError, onMessage]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (wsServiceRef.current) {
      wsServiceRef.current.disconnect();
      setIsConnected(false);
      setConnectionState('disconnected');
    }

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  // Reconnect to WebSocket
  const reconnect = useCallback(() => {
    setConnectionState('reconnecting');
    disconnect();

    // Wait a bit before reconnecting
    reconnectTimeoutRef.current = setTimeout(() => {
      connect();
    }, 1000);
  }, [connect, disconnect]);

  // Send message through WebSocket
  const sendMessage = useCallback((message: any) => {
    if (!wsServiceRef.current || !isConnected) {
      console.warn('WebSocket not connected, message not sent');
      return;
    }

    try {
      wsServiceRef.current.sendMessage(message);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to send message');
      setError(error);
      onError?.(error);
    }
  }, [isConnected, onError]);

  return {
    isConnected,
    connectionState,
    error,
    sendMessage,
    connect,
    disconnect,
    reconnect
  };
}
