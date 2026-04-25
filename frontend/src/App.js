import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ROUTER_FUTURE } from './routerFuture';
import { Toaster } from 'react-hot-toast';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard';
import DataUpload from './pages/DataUpload';
import PipelineMonitoring from './pages/PipelineMonitoring';
import Results from './pages/Results';
import Reports from './pages/Reports';
import ClinicalAnnotation from './pages/ClinicalAnnotation';
import Models from './pages/Models';
import Settings from './pages/Settings';
import ComplianceAdmin from './pages/ComplianceAdmin';
import Login from './pages/Login';
import { AuthProvider } from './contexts/AuthContext';
import { PipelineProvider } from './contexts/PipelineContext';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { useTranslation } from 'react-i18next';

function App() {
  const { t } = useTranslation();
  return (
    <AuthProvider>
      <WebSocketProvider>
        <PipelineProvider>
          <Router future={ROUTER_FUTURE}>
            <div className="App">
              <a
                href="#main-content"
                className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:p-2 focus:m-2"
              >
                {t('common.skipToContent')}
              </a>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/" element={<Layout />}>
                  <Route index element={<Dashboard />} />
                  <Route path="upload" element={<DataUpload />} />
                <Route path="monitoring" element={<PipelineMonitoring />} />
                <Route path="results/:runId?" element={<Results />} />
                <Route path="reports" element={<Reports />} />
                <Route path="clinical/:runId?" element={<ClinicalAnnotation />} />
                <Route path="models" element={<Models />} />
                <Route path="settings" element={<Settings />} />
                <Route path="admin/compliance" element={<ComplianceAdmin />} />
                </Route>
              </Routes>
              <Toaster
                position="top-right"
                toastOptions={{
                  duration: 4000,
                  style: {
                    background: '#363636',
                    color: '#fff',
                  },
                  success: {
                    duration: 3000,
                    iconTheme: {
                      primary: '#10b981',
                      secondary: '#fff',
                    },
                  },
                  error: {
                    duration: 5000,
                    iconTheme: {
                      primary: '#ef4444',
                      secondary: '#fff',
                    },
                  },
                }}
              />
            </div>
          </Router>
        </PipelineProvider>
      </WebSocketProvider>
    </AuthProvider>
  );
}

export default App;
