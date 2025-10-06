/**
 * useChatbot Hook
 * Main hook for chatbot functionality
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { WebSocketService } from '../services/WebSocketService';
import { messageService, Message } from '../services/MessageService';

export interface UseChatbotOptions {
  wsUrl: string;
  sessionId?: string;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Error) => void;
  autoConnect?: boolean;
}

export interface UseChatbotReturn {
  messages: Message[];
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
  sessionId: string | null;
  sendMessage: (content: string, context?: Record<string, any>) => void;
  clearMessages: () => void;
  reconnect: () => void;
  disconnect: () => void;
}

export function useChatbot(options: UseChatbotOptions): UseChatbotReturn {
  const {
    wsUrl,
    sessionId: initialSessionId,
    onConnect,
    onDisconnect,
    onError,
    autoConnect = true
  } = options;

  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId || null);

  const wsServiceRef = useRef<WebSocketService | null>(null);
  const messageBufferRef = useRef<string>('');

  // Initialize WebSocket service
  useEffect(() => {
    wsServiceRef.current = WebSocketService.getInstance();

    if (autoConnect) {
      connect();
    }

    return () => {
      if (wsServiceRef.current) {
        wsServiceRef.current.disconnect();
      }
    };
  }, [wsUrl]);

  // Handle WebSocket messages
  const handleMessage = useCallback((data: any) => {
    const { type } = data;

    switch (type) {
      case 'connection_established':
        setIsConnected(true);
        setSessionId(data.session_id);
        onConnect?.();
        break;

      case 'message':
        const assistantMessage = messageService.createMessage(
          'assistant',
          data.content,
          { messageId: data.id }
        );
        setMessages(prev => [...prev, assistantMessage]);
        setIsLoading(false);
        break;

      case 'stream_chunk':
        messageBufferRef.current += data.content;
        // Update last message with buffered content
        setMessages(prev => {
          const newMessages = [...prev];
          const lastMessage = newMessages[newMessages.length - 1];

          if (lastMessage && lastMessage.role === 'assistant') {
            lastMessage.content = messageBufferRef.current;
          } else {
            newMessages.push(
              messageService.createMessage('assistant', messageBufferRef.current)
            );
          }

          return newMessages;
        });
        break;

      case 'stream_complete':
        messageBufferRef.current = '';
        setIsLoading(false);
        break;

      case 'error':
        setError(data.message || 'An error occurred');
        setIsLoading(false);
        onError?.(new Error(data.message));
        break;

      case 'message_received':
        // Message acknowledged
        break;

      default:
        console.warn('Unknown message type:', type);
    }
  }, [onConnect, onError]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!wsServiceRef.current) return;

    setError(null);

    wsServiceRef.current.connect(wsUrl, sessionId || undefined);
    wsServiceRef.current.onMessage(handleMessage);

    wsServiceRef.current.onClose(() => {
      setIsConnected(false);
      onDisconnect?.();
    });

    wsServiceRef.current.onError((err) => {
      setError(err.message);
      onError?.(err);
    });
  }, [wsUrl, sessionId, handleMessage, onDisconnect, onError]);

  // Send message
  const sendMessage = useCallback((content: string, context?: Record<string, any>) => {
    if (!wsServiceRef.current || !isConnected) {
      setError('Not connected to server');
      return;
    }

    // Validate message
    const validation = messageService.validateMessage(content);
    if (!validation.valid) {
      setError(validation.error || 'Invalid message');
      return;
    }

    // Add user message to state
    const userMessage = messageService.createMessage('user', content);
    setMessages(prev => [...prev, userMessage]);

    // Send to server
    wsServiceRef.current.sendMessage({
      type: 'chat',
      content,
      context,
      id: userMessage.id
    });

    setIsLoading(true);
    setError(null);
    messageBufferRef.current = '';
  }, [isConnected]);

  // Clear messages
  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  // Reconnect
  const reconnect = useCallback(() => {
    if (wsServiceRef.current) {
      wsServiceRef.current.disconnect();
    }
    connect();
  }, [connect]);

  // Disconnect
  const disconnect = useCallback(() => {
    if (wsServiceRef.current) {
      wsServiceRef.current.disconnect();
      setIsConnected(false);
    }
  }, []);

  return {
    messages,
    isConnected,
    isLoading,
    error,
    sessionId,
    sendMessage,
    clearMessages,
    reconnect,
    disconnect
  };
}
