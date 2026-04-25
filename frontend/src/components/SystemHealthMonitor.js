/**
 * System Health Monitoring Component
 * Real-time system health monitoring dashboard with metrics visualization
 */

import React, { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell
} from 'recharts';
import {
  Activity,
  Server,
  Database,
  HardDrive,
  Cpu,
  MemoryStick,
  Network,
  AlertCircle,
  CheckCircle,
  Clock
} from 'lucide-react';
import api from '../services/api';

const SystemHealthMonitor = () => {
  const [healthData, setHealthData] = useState(null);
  const [metricsHistory, setMetricsHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(5000); // 5 seconds

  useEffect(() => {
    fetchHealthData();
    
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchHealthData();
      }, refreshInterval);
      
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refreshInterval]);

  const fetchHealthData = async () => {
    try {
      const response = await api.get('/api/v1/system/health');
      const data = response.data;
      
      setHealthData(data);
      
      // Add to history (keep last 50 entries)
      setMetricsHistory(prev => {
        const newHistory = [...prev, {
          timestamp: new Date().toLocaleTimeString(),
          ...data.metrics
        }];
        return newHistory.slice(-50);
      });
      
      setLoading(false);
    } catch (error) {
      console.error('Error fetching health data:', error);
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600 bg-green-100';
      case 'warning':
        return 'text-yellow-600 bg-yellow-100';
      case 'critical':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case 'warning':
        return <AlertCircle className="h-5 w-5 text-yellow-600" />;
      case 'critical':
        return <AlertCircle className="h-5 w-5 text-red-600" />;
      default:
        return <Clock className="h-5 w-5 text-gray-600" />;
    }
  };

  if (loading && !healthData) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (!healthData) {
    return (
      <div className="card">
        <div className="text-center py-8">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-gray-600">Unable to fetch system health data</p>
        </div>
      </div>
    );
  }

  const { status, timestamp, metrics, services } = healthData;

  // Prepare chart data
  const chartData = metricsHistory.map(item => ({
    time: item.timestamp,
    cpu: item.system?.cpu_usage || 0,
    memory: item.system?.memory_usage || 0,
    disk: item.system?.disk_usage || 0
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">System Health Monitor</h2>
          <p className="text-sm text-gray-600 mt-1">
            Real-time system metrics and service status
          </p>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm text-gray-600">Auto-refresh</span>
          </label>
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="text-sm border border-gray-300 rounded px-2 py-1"
          >
            <option value={5000}>5s</option>
            <option value={10000}>10s</option>
            <option value={30000}>30s</option>
            <option value={60000}>1m</option>
          </select>
          <button
            onClick={fetchHealthData}
            className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 text-sm"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Overall Status */}
      <div className={`card ${getStatusColor(status)}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {getStatusIcon(status)}
            <div>
              <h3 className="font-semibold text-lg">System Status: {status.toUpperCase()}</h3>
              <p className="text-sm opacity-75">
                Last updated: {new Date(timestamp).toLocaleString()}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* System Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">CPU Usage</p>
              <p className="text-2xl font-bold text-gray-900">
                {metrics?.system?.cpu_usage?.toFixed(1) || 0}%
              </p>
            </div>
            <Cpu className="h-8 w-8 text-blue-500" />
          </div>
          <div className="mt-2">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all"
                style={{ width: `${metrics?.system?.cpu_usage || 0}%` }}
              ></div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Memory Usage</p>
              <p className="text-2xl font-bold text-gray-900">
                {metrics?.system?.memory_usage?.toFixed(1) || 0}%
              </p>
            </div>
            <MemoryStick className="h-8 w-8 text-purple-500" />
          </div>
          <div className="mt-2">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-purple-500 h-2 rounded-full transition-all"
                style={{ width: `${metrics?.system?.memory_usage || 0}%` }}
              ></div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Disk Usage</p>
              <p className="text-2xl font-bold text-gray-900">
                {metrics?.system?.disk_usage?.toFixed(1) || 0}%
              </p>
            </div>
            <HardDrive className="h-8 w-8 text-green-500" />
          </div>
          <div className="mt-2">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-green-500 h-2 rounded-full transition-all"
                style={{ width: `${metrics?.system?.disk_usage || 0}%` }}
              ></div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Active Connections</p>
              <p className="text-2xl font-bold text-gray-900">
                {metrics?.application?.active_connections || 0}
              </p>
            </div>
            <Network className="h-8 w-8 text-orange-500" />
          </div>
        </div>
      </div>

      {/* Service Status */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Service Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {services && Object.entries(services).map(([serviceName, serviceStatus]) => (
            <div key={serviceName} className="flex items-center justify-between p-3 bg-gray-50 rounded">
              <div className="flex items-center gap-2">
                {serviceStatus === 'running' ? (
                  <CheckCircle className="h-5 w-5 text-green-600" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-red-600" />
                )}
                <span className="font-medium text-gray-900 capitalize">{serviceName}</span>
              </div>
              <span className={`text-sm px-2 py-1 rounded ${
                serviceStatus === 'running' 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-red-100 text-red-800'
              }`}>
                {serviceStatus}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Metrics Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* CPU and Memory Usage Over Time */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Resource Usage Over Time</h3>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Area
                type="monotone"
                dataKey="cpu"
                stackId="1"
                stroke="#3b82f6"
                fill="#3b82f6"
                fillOpacity={0.6}
                name="CPU %"
              />
              <Area
                type="monotone"
                dataKey="memory"
                stackId="1"
                stroke="#8b5cf6"
                fill="#8b5cf6"
                fillOpacity={0.6}
                name="Memory %"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Disk Usage */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Disk Usage</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="disk"
                stroke="#10b981"
                strokeWidth={2}
                name="Disk %"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Database Metrics */}
      {metrics?.database && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Database className="h-5 w-5" />
            Database Metrics
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-gray-600">Status</p>
              <p className="text-lg font-semibold text-gray-900">
                {metrics.database.status || 'Unknown'}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Size</p>
              <p className="text-lg font-semibold text-gray-900">
                {metrics.database.size || 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Connections</p>
              <p className="text-lg font-semibold text-gray-900">
                {metrics.database.connections || 0}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Application Metrics */}
      {metrics?.application && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Application Metrics
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-gray-600">Request Rate</p>
              <p className="text-lg font-semibold text-gray-900">
                {metrics.application.request_rate || 0}/s
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Error Rate</p>
              <p className="text-lg font-semibold text-gray-900">
                {(metrics.application.error_rate || 0).toFixed(2)}%
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Avg Response Time</p>
              <p className="text-lg font-semibold text-gray-900">
                {(metrics.application.avg_response_time || 0).toFixed(0)}ms
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Active Tasks</p>
              <p className="text-lg font-semibold text-gray-900">
                {metrics.application.active_tasks || 0}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SystemHealthMonitor;

