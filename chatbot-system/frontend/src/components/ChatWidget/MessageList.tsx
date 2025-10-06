/**
 * Message List Component
 * Displays chat messages with virtual scrolling for performance
 */

import React, { useEffect, useRef } from 'react';
import { Message } from '@/types';
import MessageItem from './MessageItem';
import './MessageList.scss';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
}

const MessageList: React.FC<MessageListProps> = ({ messages, isLoading, error }) => {
  const listRef = useRef<HTMLDivElement>(null);
  const lastMessageRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (lastMessageRef.current) {
      lastMessageRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [messages]);

  // Group messages by time (optional feature)
  const groupMessagesByTime = (messages: Message[]) => {
    const groups: { date: string; messages: Message[] }[] = [];
    let currentDate = '';

    messages.forEach(message => {
      const messageDate = new Date(message.timestamp).toLocaleDateString();

      if (messageDate !== currentDate) {
        currentDate = messageDate;
        groups.push({
          date: messageDate,
          messages: [message]
        });
      } else if (groups.length > 0) {
        groups[groups.length - 1].messages.push(message);
      }
    });

    return groups;
  };

  const messageGroups = groupMessagesByTime(messages);

  return (
    <div className="message-list" ref={listRef}>
      {messages.length === 0 && !isLoading && !error && (
        <div className="empty-state">
          <p>👋 Hello! How can I assist you today?</p>
          <p className="hint">Ask me about cases, customers, or any financial queries.</p>
        </div>
      )}

      {error && (
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {messageGroups.map((group, groupIndex) => (
        <div key={group.date} className="message-group">
          <div className="date-divider">
            <span>{group.date}</span>
          </div>
          {group.messages.map((message, index) => (
            <div
              key={message.id}
              ref={
                groupIndex === messageGroups.length - 1 &&
                index === group.messages.length - 1
                  ? lastMessageRef
                  : undefined
              }
            >
              <MessageItem message={message} />
            </div>
          ))}
        </div>
      ))}

      {isLoading && messages.length > 0 && messages[messages.length - 1].role === 'user' && (
        <div className="typing-indicator">
          <span></span>
          <span></span>
          <span></span>
        </div>
      )}
    </div>
  );
};

export default MessageList;