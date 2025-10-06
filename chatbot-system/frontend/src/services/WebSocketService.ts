/**
 * WebSocket Service for real-time communication with the backend
 */

import { WebSocketMessage } from '@/types';

type MessageHandler = (message: WebSocketMessage) => void;
type ConnectionHandler = (connected: boolean) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string = '';
  private sessionId: string | null = null;
  private messageHandlers: Set<MessageHandler> = new Set();
  private connectionHandlers: Set<ConnectionHandler> = new Set();
  private messageQueue: WebSocketMessage[] = [];
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // Start with 1 second
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private isIntentionalClose = false;

  /**
   * Connect to WebSocket server
   *
   * Steps:
   * 1. Create WebSocket instance
   * 2. Set up event handlers
   * 3. Implement reconnection logic
   * 4. Start heartbeat
   */
  connect(url: string, sessionId?: string): void {
    // Step 1: Create WebSocket instance
    this.url = url;
    this.sessionId = sessionId || null;
    this.isIntentionalClose = false;

    const wsUrl = sessionId ? `${url}?session_id=${sessionId}` : url;

    console.log(`Connecting to WebSocket: ${wsUrl}`);
    this.ws = new WebSocket(wsUrl);

    // Step 2: Set up event handlers
    this.ws.onopen = this.handleOpen.bind(this);
    this.ws.onmessage = this.handleMessage.bind(this);
    this.ws.onclose = this.handleClose.bind(this);
    this.ws.onerror = this.handleError.bind(this);
  }

  /**
   * Send message through WebSocket
   *
   * Steps:
   * 1. Check connection status
   * 2. Queue if disconnected
   * 3. Serialize message
   * 4. Send via WebSocket
   * 5. Handle send errors
   */
  sendMessage(message: WebSocketMessage): void {
    // Step 1: Check connection status
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      // Step 2: Queue if disconnected
      console.log('WebSocket not connected, queueing message');
      this.messageQueue.push(message);
      return;
    }

    try {
      // Step 3: Serialize message
      const serialized = JSON.stringify(message);

      // Step 4: Send via WebSocket
      this.ws.send(serialized);
      console.log('Message sent:', message);
    } catch (error) {
      // Step 5: Handle send errors
      console.error('Error sending message:', error);
      this.messageQueue.push(message);
    }
  }

  /**
   * Handle reconnection with exponential backoff
   */
  private handleReconnection(): void {
    if (this.isIntentionalClose) {
      return;
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.notifyConnectionHandlers(false);
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000);

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    setTimeout(() => {
      this.connect(this.url, this.sessionId || undefined);
    }, delay);
  }

  private handleOpen(event: Event): void {
    console.log('WebSocket connected');
    this.reconnectAttempts = 0;
    this.notifyConnectionHandlers(true);

    // Step 4: Start heartbeat
    this.startHeartbeat();

    // Send queued messages
    this.flushMessageQueue();
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      console.log('Message received:', message);

      // Handle special message types internally
      if (message.type === 'pong' || message.type === 'heartbeat') {
        // Heartbeat response, no need to propagate
        return;
      }

      if (message.type === 'connection_established') {
        this.sessionId = message.session_id || this.sessionId;
      }

      // Notify all message handlers
      this.messageHandlers.forEach(handler => {
        try {
          handler(message);
        } catch (error) {
          console.error('Error in message handler:', error);
        }
      });
    } catch (error) {
      console.error('Error parsing message:', error);
    }
  }

  private handleClose(event: CloseEvent): void {
    console.log('WebSocket closed:', event.code, event.reason);
    this.ws = null;
    this.stopHeartbeat();
    this.notifyConnectionHandlers(false);

    // Step 3: Implement reconnection logic
    if (!this.isIntentionalClose) {
      this.handleReconnection();
    }
  }

  private handleError(event: Event): void {
    console.error('WebSocket error:', event);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();

    // Send ping every 30 seconds
    this.heartbeatInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.sendMessage({ type: 'ping' });
      }
    }, 30000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private flushMessageQueue(): void {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      if (message) {
        this.sendMessage(message);
      }
    }
  }

  private notifyConnectionHandlers(connected: boolean): void {
    this.connectionHandlers.forEach(handler => {
      try {
        handler(connected);
      } catch (error) {
        console.error('Error in connection handler:', error);
      }
    });
  }

  /**
   * Subscribe to messages
   */
  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);

    // Return unsubscribe function
    return () => {
      this.messageHandlers.delete(handler);
    };
  }

  /**
   * Subscribe to connection status changes
   */
  onConnectionChange(handler: ConnectionHandler): () => void {
    this.connectionHandlers.add(handler);

    // Return unsubscribe function
    return () => {
      this.connectionHandlers.delete(handler);
    };
  }

  /**
   * Close WebSocket connection
   */
  disconnect(): void {
    this.isIntentionalClose = true;
    this.stopHeartbeat();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.messageQueue = [];
    this.messageHandlers.clear();
    this.connectionHandlers.clear();
  }

  /**
   * Get current connection status
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Get current session ID
   */
  getSessionId(): string | null {
    return this.sessionId;
  }
}

// Export singleton instance
export const webSocketService = new WebSocketService();
export default webSocketService;