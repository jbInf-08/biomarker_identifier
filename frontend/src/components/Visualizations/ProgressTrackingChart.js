import React, { useState, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar
} from 'recharts';
import { TrendingUp, Activity, BarChart3, Clock } from 'lucide-react';

const ProgressTrackingChart = ({ data, title = "Pipeline Progress Tracking" }) => {
  const [chartType, setChartType] = useState('line');
  const [timeRange, setTimeRange] = useState('all');
  const [metric, setMetric] = useState('progress');

  // Process data for visualization
  const processedData = useMemo(() => {
    if (!data || !Array.isArray(data)) return [];

    // Filter by time range
    let filteredData = [...data];
    const now = new Date();
    
    if (timeRange !== 'all') {
      const cutoffTime = new Date();
      switch (timeRange) {
        case '1h':
          cutoffTime.setHours(now.getHours() - 1);
          break;
        case '6h':
          cutoffTime.setHours(now.getHours() - 6);
          break;
        case '24h':
          cutoffTime.setDate(now.getDate() - 1);
          break;
        case '7d':
          cutoffTime.setDate(now.getDate() - 7);
          break;
        default:
          break;
      }
      
      filteredData = filteredData.filter(item => new Date(item.timestamp) >= cutoffTime);
    }

    // Sort by timestamp
    return filteredData.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  }, [data, timeRange]);

  // Chart type options
  const chartTypes = [
    { value: 'line', label: 'Line Chart', icon: TrendingUp },
    { value: 'area', label: 'Area Chart', icon: Activity },
    { value: 'bar', label: 'Bar Chart', icon: BarChart3 }
  ];

  // Metric options
  const metrics = [
    { value: 'progress', label: 'Progress (%)' },
    { value: 'memory_usage', label: 'Memory Usage (MB)' },
    { value: 'cpu_usage', label: 'CPU Usage (%)' },
    { value: 'active_tasks', label: 'Active Tasks' }
  ];

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-lg">
          <p className="font-semibold text-gray-900">
            {new Date(data.timestamp).toLocaleString()}
          </p>
          <p className="text-sm text-gray-600">Status: {data.status}</p>
          <p className="text-sm text-gray-600">Progress: {data.progress}%</p>
          {data.memory_usage && (
            <p className="text-sm text-gray-600">Memory: {data.memory_usage} MB</p>
          )}
          {data.cpu_usage && (
            <p className="text-sm text-gray-600">CPU: {data.cpu_usage}%</p>
          )}
          {data.active_tasks && (
            <p className="text-sm text-gray-600">Active Tasks: {data.active_tasks}</p>
          )}
        </div>
      );
    }
    return null;
  };

  // Render chart based on type
  const renderChart = () => {
    const commonProps = {
      data: processedData,
      margin: { top: 20, right: 30, left: 20, bottom: 5 }
    };

    switch (chartType) {
      case 'line':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart {...commonProps}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="timestamp" 
                tickFormatter={(value) => new Date(value).toLocaleTimeString()}
                angle={-45}
                textAnchor="end"
                height={80}
              />
              <YAxis domain={[0, 100]} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Line 
                type="monotone" 
                dataKey={metric} 
                stroke="#3b82f6" 
                strokeWidth={2}
                name={metrics.find(m => m.value === metric)?.label}
                dot={{ fill: '#3b82f6', strokeWidth: 2, r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        );

      case 'area':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart {...commonProps}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="timestamp" 
                tickFormatter={(value) => new Date(value).toLocaleTimeString()}
                angle={-45}
                textAnchor="end"
                height={80}
              />
              <YAxis domain={[0, 100]} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Area 
                type="monotone" 
                dataKey={metric} 
                stroke="#3b82f6" 
                fill="#3b82f6"
                fillOpacity={0.3}
                name={metrics.find(m => m.value === metric)?.label}
              />
            </AreaChart>
          </ResponsiveContainer>
        );

      case 'bar':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <BarChart {...commonProps}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="timestamp" 
                tickFormatter={(value) => new Date(value).toLocaleTimeString()}
                angle={-45}
                textAnchor="end"
                height={80}
              />
              <YAxis domain={[0, 100]} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar 
                dataKey={metric} 
                fill="#3b82f6" 
                name={metrics.find(m => m.value === metric)?.label}
                radius={[2, 2, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        );

      default:
        return null;
    }
  };

  if (!data || data.length === 0) {
    return (
      <div className="card">
        <div className="p-6 text-center">
          <p className="text-gray-500">No progress tracking data available for visualization</p>
        </div>
      </div>
    );
  }

  // Calculate summary statistics
  const latestData = processedData[processedData.length - 1];
  const avgProgress = processedData.reduce((sum, item) => sum + item.progress, 0) / processedData.length;
  const maxProgress = Math.max(...processedData.map(item => item.progress));
  const minProgress = Math.min(...processedData.map(item => item.progress));

  return (
    <div className="card">
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          <div className="flex items-center space-x-4">
            {/* Chart type selector */}
            <div className="flex items-center space-x-2">
              <label className="text-sm font-medium text-gray-700">Chart Type:</label>
              <select
                value={chartType}
                onChange={(e) => setChartType(e.target.value)}
                className="input-field text-sm"
              >
                {chartTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Metric selector */}
            <div className="flex items-center space-x-2">
              <label className="text-sm font-medium text-gray-700">Metric:</label>
              <select
                value={metric}
                onChange={(e) => setMetric(e.target.value)}
                className="input-field text-sm"
              >
                {metrics.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Time range selector */}
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-gray-500" />
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
                className="input-field text-sm"
              >
                <option value="all">All Time</option>
                <option value="1h">Last Hour</option>
                <option value="6h">Last 6 Hours</option>
                <option value="24h">Last 24 Hours</option>
                <option value="7d">Last 7 Days</option>
              </select>
            </div>
          </div>
        </div>

        {/* Chart */}
        <div className="mb-4">
          {renderChart()}
        </div>

        {/* Summary statistics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-6">
          <div className="bg-blue-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-blue-600">Current Progress</p>
            <p className="text-2xl font-bold text-blue-900">
              {latestData ? `${latestData.progress}%` : '0%'}
            </p>
          </div>
          <div className="bg-green-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-green-600">Average Progress</p>
            <p className="text-2xl font-bold text-green-900">
              {avgProgress.toFixed(1)}%
            </p>
          </div>
          <div className="bg-yellow-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-yellow-600">Max Progress</p>
            <p className="text-2xl font-bold text-yellow-900">
              {maxProgress}%
            </p>
          </div>
          <div className="bg-purple-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-purple-600">Data Points</p>
            <p className="text-2xl font-bold text-purple-900">
              {processedData.length}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProgressTrackingChart;
