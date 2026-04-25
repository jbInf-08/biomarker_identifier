import { useEffect, useRef, useState, useCallback } from 'react';

const useWebSocket = (url, options = {}) => {
  const [socket, setSocket] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [error, setError] = useState(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const mountedRef = useRef(false);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const maxReconnectAttempts = options.maxReconnectAttempts || 5;
  const reconnectInterval = options.reconnectInterval || 3000;
  const autoConnect = options.autoConnect !== false;

  const connect = useCallback(() => {
    if (!url || !mountedRef.current) return;
    const opts = optionsRef.current;
    try {
      const ws = new WebSocket(url);
      ws.onopen = () => {
        if (!mountedRef.current) {
          try {
            ws.close(1000, 'Unmounted');
          } catch (_) { /* ignore */ }
          return;
        }
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
        if (opts.onOpen) opts.onOpen();
        try {
          ws.send(JSON.stringify({ type: 'ping' }));
        } catch (_) { /* ignore */ }
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (mountedRef.current) setLastMessage(data);
          if (data.type === 'pong') {
            setTimeout(() => {
              if (!mountedRef.current) return;
              if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping' }));
              }
            }, 25000);
          }
          if (opts.onMessage) opts.onMessage(data);
        } catch (err) {
          console.warn('WebSocket message parse error:', err);
        }
      };
      ws.onclose = (event) => {
        if (!mountedRef.current) return;
        setIsConnected(false);
        setSocket(null);
        if (opts.onClose) opts.onClose(event);
        if (
          mountedRef.current &&
          event.code !== 1000 &&
          reconnectAttempts.current < maxReconnectAttempts
        ) {
          reconnectAttempts.current += 1;
          reconnectTimeoutRef.current = setTimeout(() => connect(), reconnectInterval);
        }
      };
      ws.onerror = (err) => {
        if (mountedRef.current) setError(err);
        if (opts.onError) opts.onError(err);
      };
      if (mountedRef.current) setSocket(ws);
      else {
        try {
          ws.close(1000, 'Unmounted');
        } catch (_) { /* ignore */ }
      }
    } catch (err) {
      if (mountedRef.current) setError(err);
    }
  }, [url, maxReconnectAttempts, reconnectInterval]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    setSocket((prev) => {
      if (prev) {
        try {
          prev.close(1000, 'User disconnected');
        } catch (_) { /* ignore */ }
      }
      return null;
    });
    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((message) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(JSON.stringify(message));
      } catch (_) { /* ignore */ }
    }
  }, [socket]);

  useEffect(() => {
    mountedRef.current = true;
    if (url && autoConnect) {
      connect();
    }
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [url, autoConnect, connect, disconnect]);

  return {
    socket,
    isConnected,
    lastMessage,
    error,
    connect,
    disconnect,
    sendMessage,
  };
};

export default useWebSocket;
