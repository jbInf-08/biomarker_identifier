import React, { useState } from 'react';
import { Outlet, Navigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import Sidebar from './Sidebar';
import Header from './Header';
import ProtectedRoute from './ProtectedRoute';
import { useTranslation } from 'react-i18next';

const Layout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { isAuthenticated, loading, user } = useAuth();
  const { t } = useTranslation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div
          className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600"
          aria-label={t('common.loading')}
        ></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col lg:flex-row">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} user={user} />
      
      <div className="flex-1 flex flex-col min-w-0">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        
        <main id="main-content" className="flex-1 py-6" tabIndex="-1">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
            <ProtectedRoute>
              <Outlet />
            </ProtectedRoute>
          </div>
        </main>
      </div>
    </div>
  );
};

export default Layout;
