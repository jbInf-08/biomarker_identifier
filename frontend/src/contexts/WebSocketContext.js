import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useAuth } from './AuthContext';
import useWebSocket from '../hooks/useWebSocket';
import toast from 'react-hot-toast';

const WebSocketContext = createContext();

export const useWebSocketContext = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider');
  }
  return context;
};

export const WebSocketProvider = ({ children }) => {
  const { user, isAuthenticated } = useAuth();
  const [progressUpdates, setProgressUpdates] = useState({});
  const [userUpdates, setUserUpdates] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');

  // WebSocket for user-specific updates (skip when no user id, e.g. dev bypass or backend down)
  const devBypassAuth = process.env.REACT_APP_DEV_BYPASS_AUTH === 'true';
  const userWsUrl = user?.id && isAuthenticated && !devBypassAuth
    ? `ws://localhost:8000/api/ws/user/${user.id}`
    : null;

  const {
    isConnected: isUserConnected,
    sendMessage: sendUserMessage,
    lastMessage: lastUserMessage,
  } = useWebSocket(userWsUrl, {
    autoConnect: !!userWsUrl,
    onMessage: (data) => {
      if (data.type === 'progress_update') {
        setProgressUpdates(prev => ({
          ...prev,
          [data.run_id]: data
        }));
      } else if (data.type === 'notification') {
        toast.success(data.message);
        setUserUpdates(prev => [...prev, data]);
      }
    },
    onOpen: () => {
      setConnectionStatus('connected');
    },
    onClose: () => {
      setConnectionStatus('disconnected');
    },
    onError: () => {
      setConnectionStatus('error');
      // Don't log every error to avoid console spam when backend is down
    }
  });

  // Connect to specific run progress updates
  const connectToRun = useCallback((runId) => {
    if (isUserConnected) {
      sendUserMessage({
        type: 'subscribe_run',
        run_id: runId
      });
    }
  }, [isUserConnected, sendUserMessage]);

  // Disconnect from specific run updates
  const disconnectFromRun = useCallback((runId) => {
    // Remove progress updates for this run
    setProgressUpdates(prev => {
      const newUpdates = { ...prev };
      delete newUpdates[runId];
      return newUpdates;
    });
  }, []);

  // Get progress update for a specific run
  const getRunProgress = useCallback((runId) => {
    return progressUpdates[runId] || null;
  }, [progressUpdates]);

  // Clear old progress updates
  const clearProgressUpdates = useCallback(() => {
    setProgressUpdates({});
  }, []);

  // Clear user updates
  const clearUserUpdates = useCallback(() => {
    setUserUpdates([]);
  }, []);

  // Send notification to user
  const sendNotification = useCallback((message, type = 'info') => {
    if (isUserConnected) {
      sendUserMessage({
        type: 'notification',
        message,
        notification_type: type,
        timestamp: new Date().toISOString()
      });
    }
  }, [isUserConnected, sendUserMessage]);

  const value = {
    // Connection status
    isConnected: isUserConnected,
    connectionStatus,
    
    // Progress tracking
    progressUpdates,
    getRunProgress,
    connectToRun,
    disconnectFromRun,
    clearProgressUpdates,
    
    // User updates
    userUpdates,
    clearUserUpdates,
    sendNotification,
    
    // WebSocket utilities
    sendMessage: sendUserMessage,
    lastMessage: lastUserMessage,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};
