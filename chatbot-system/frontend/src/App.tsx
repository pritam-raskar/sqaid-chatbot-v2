/**
 * Main App Component
 * Demonstrates the chat widget integration
 */

import React, { useState } from 'react';
import ChatContainer from './components/ChatWidget/ChatContainer';
import { PageContext } from './types';
import './App.css';

function App() {
  // Example page context that would come from the parent application
  const [pageContext, setPageContext] = useState<PageContext>({
    pageName: 'alert-summary',
    dataSchema: {
      columns: ['case_id', 'priority', 'status', 'created_date', 'amount'],
      filterable: true
    },
    currentFilters: [],
    availableActions: ['filter', 'sort', 'export']
  });

  // Handler for actions from the chatbot
  const handleChatbotAction = (action: any) => {
    console.log('Chatbot action received:', action);

    switch (action.type) {
      case 'APPLY_FILTERS':
        // Apply filters to the parent table
        console.log('Applying filters:', action.payload);
        setPageContext(prev => ({
          ...prev,
          currentFilters: action.payload.filters
        }));
        break;

      case 'SORT_DATA':
        console.log('Sorting data:', action.payload);
        // Handle sorting logic
        break;

      case 'EXPORT_DATA':
        console.log('Exporting data:', action.payload);
        // Handle export logic
        break;

      default:
        console.log('Unknown action:', action.type);
    }
  };

  return (
    <div className="App">
      {/* Example parent application content */}
      <div className="main-content">
        <header className="app-header">
          <h1>Financial Case Management System</h1>
          <p>Demo: Alert Summary Page</p>
        </header>

        <div className="demo-table">
          <h2>Alert Summary Table</h2>
          <p>Current Filters: {pageContext.currentFilters?.length || 0} active</p>
          <div className="table-placeholder">
            <p>This is where your main application table would be.</p>
            <p>The chatbot can interact with this table through filters and actions.</p>
          </div>
        </div>
      </div>

      {/* Chat Widget */}
      <ChatContainer
        pageContext={pageContext}
        onAction={handleChatbotAction}
        wsUrl={import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/chat"}
      />
    </div>
  );
}

export default App;