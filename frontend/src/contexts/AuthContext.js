import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from '../services/api';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const syncTenant = (u) => {
    if (u && u.tenant_id) {
      localStorage.setItem('tenantId', u.tenant_id);
    } else {
      localStorage.removeItem('tenantId');
    }
  };

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    // Optional: bypass auth in development when backend is unavailable (set in .env: REACT_APP_DEV_BYPASS_AUTH=true)
    const devBypass = process.env.REACT_APP_DEV_BYPASS_AUTH === 'true';
    if (devBypass) {
      setUser({ id: 'dev-local', email: 'dev@local', name: 'Dev User', role: 'researcher' });
      setIsAuthenticated(true);
      setLoading(false);
      return;
    }

    try {
      const token = localStorage.getItem('authToken');
      if (token) {
        apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        const response = await apiClient.get('/auth/me');
        setUser(response.data);
        syncTenant(response.data);
        setIsAuthenticated(true);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      localStorage.removeItem('authToken');
      localStorage.removeItem('tenantId');
      delete apiClient.defaults.headers.common['Authorization'];
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    try {
      const response = await apiClient.post('/auth/login', { email, password });
      const token = response.data.access_token || response.data.token;
      const userData = response.data.user;
      
      if (!token || !userData) {
        return { success: false, error: 'Invalid response from server' };
      }
      
      localStorage.setItem('authToken', token);
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      
      setUser(userData);
      syncTenant(userData);
      setIsAuthenticated(true);
      
      return { success: true };
    } catch (error) {
      const msg = error.response?.data?.detail || error.response?.data?.message;
      return { 
        success: false, 
        error: typeof msg === 'string' ? msg : (Array.isArray(msg) ? msg[0]?.msg : 'Login failed') || 'Login failed'
      };
    }
  };

  const register = async (userData) => {
    try {
      await apiClient.post('/auth/register', userData);
      // Backend register doesn't return token - login to get session
      return await login(userData.email, userData.password);
    } catch (error) {
      const msg = error.response?.data?.detail || error.response?.data?.message || 'Registration failed';
      return { 
        success: false, 
        error: typeof msg === 'string' ? msg : (msg?.msg || 'Registration failed') 
      };
    }
  };

  const logout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('tenantId');
    delete apiClient.defaults.headers.common['Authorization'];
    setUser(null);
    setIsAuthenticated(false);
  };

  const updateProfile = async (profileData) => {
    try {
      const response = await apiClient.put('/auth/profile', profileData);
      setUser(response.data);
      syncTenant(response.data);
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.message || 'Profile update failed' 
      };
    }
  };

  const value = {
    user,
    isAuthenticated,
    loading,
    login,
    register,
    logout,
    updateProfile,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
