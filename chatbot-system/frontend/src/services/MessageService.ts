/**
 * Message Service
 * Handles message formatting, validation, and processing
 */

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface MessageValidationResult {
  valid: boolean;
  error?: string;
}

export class MessageService {
  private maxMessageLength: number;

  constructor(maxMessageLength: number = 10000) {
    this.maxMessageLength = maxMessageLength;
  }

  /**
   * Create a new message
   */
  createMessage(
    role: Message['role'],
    content: string,
    metadata?: Record<string, any>
  ): Message {
    return {
      id: this.generateMessageId(),
      role,
      content,
      timestamp: new Date().toISOString(),
      metadata
    };
  }

  /**
   * Validate message content
   */
  validateMessage(content: string): MessageValidationResult {
    if (!content || content.trim().length === 0) {
      return {
        valid: false,
        error: 'Message cannot be empty'
      };
    }

    if (content.length > this.maxMessageLength) {
      return {
        valid: false,
        error: `Message exceeds maximum length of ${this.maxMessageLength} characters`
      };
    }

    return { valid: true };
  }

  /**
   * Format message for display
   */
  formatMessage(message: Message): string {
    // Handle markdown, code blocks, etc.
    return message.content;
  }

  /**
   * Extract code blocks from message
   */
  extractCodeBlocks(content: string): Array<{ language: string; code: string }> {
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
    const blocks: Array<{ language: string; code: string }> = [];
    let match;

    while ((match = codeBlockRegex.exec(content)) !== null) {
      blocks.push({
        language: match[1] || 'text',
        code: match[2].trim()
      });
    }

    return blocks;
  }

  /**
   * Parse action from message
   */
  parseAction(message: Message): { action: string; data: any } | null {
    if (!message.metadata || !message.metadata.action) {
      return null;
    }

    return {
      action: message.metadata.action,
      data: message.metadata.data || {}
    };
  }

  /**
   * Group messages by conversation
   */
  groupByConversation(messages: Message[]): Message[][] {
    const groups: Message[][] = [];
    let currentGroup: Message[] = [];

    for (const message of messages) {
      currentGroup.push(message);

      // Start new group after assistant response
      if (message.role === 'assistant') {
        groups.push(currentGroup);
        currentGroup = [];
      }
    }

    if (currentGroup.length > 0) {
      groups.push(currentGroup);
    }

    return groups;
  }

  /**
   * Generate unique message ID
   */
  private generateMessageId(): string {
    return `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Filter messages by role
   */
  filterByRole(messages: Message[], role: Message['role']): Message[] {
    return messages.filter(msg => msg.role === role);
  }

  /**
   * Get message statistics
   */
  getStatistics(messages: Message[]): {
    total: number;
    byRole: Record<string, number>;
    averageLength: number;
  } {
    const byRole: Record<string, number> = {};
    let totalLength = 0;

    messages.forEach(msg => {
      byRole[msg.role] = (byRole[msg.role] || 0) + 1;
      totalLength += msg.content.length;
    });

    return {
      total: messages.length,
      byRole,
      averageLength: messages.length > 0 ? totalLength / messages.length : 0
    };
  }
}

// Singleton instance
export const messageService = new MessageService();
