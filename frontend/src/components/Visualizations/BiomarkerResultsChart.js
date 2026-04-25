import React, { useState, useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { BarChart3, Circle, TrendingUp, PieChart as PieChartIcon } from 'lucide-react';

const BiomarkerResultsChart = ({ data, title = "Biomarker Analysis Results" }) => {
  const [chartType, setChartType] = useState('bar');
  const [sortBy, setSortBy] = useState('p_value');
  const [topN, setTopN] = useState(20);

  // Process data for visualization
  const processedData = useMemo(() => {
    if (!data || !Array.isArray(data)) return [];

    // Sort and limit data
    const sortedData = [...data]
      .sort((a, b) => {
        switch (sortBy) {
          case 'p_value':
            return a.p_value - b.p_value;
          case 'effect_size':
            return Math.abs(b.effect_size) - Math.abs(a.effect_size);
          case 'fold_change':
            return Math.abs(b.fold_change) - Math.abs(a.fold_change);
          default:
            return 0;
        }
      })
      .slice(0, topN);

    return sortedData.map((item, index) => ({
      ...item,
      rank: index + 1,
      abs_effect_size: Math.abs(item.effect_size),
      abs_fold_change: Math.abs(item.fold_change),
      neg_log_p: -Math.log10(item.p_value),
      significance: item.p_value < 0.001 ? 'Highly Significant' : 
                   item.p_value < 0.01 ? 'Significant' : 
                   item.p_value < 0.05 ? 'Moderately Significant' : 'Not Significant'
    }));
  }, [data, sortBy, topN]);

  // Color scheme for significance levels
  const significanceColors = {
    'Highly Significant': '#ef4444',
    'Significant': '#f97316',
    'Moderately Significant': '#eab308',
    'Not Significant': '#6b7280'
  };

  // Chart type options
  const chartTypes = [
    { value: 'bar', label: 'Bar Chart', icon: BarChart3 },
    { value: 'scatter', label: 'Scatter Plot', icon: Circle },
    { value: 'line', label: 'Line Chart', icon: TrendingUp },
    { value: 'pie', label: 'Pie Chart', icon: PieChartIcon }
  ];

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-lg">
          <p className="font-semibold text-gray-900">{data.gene_symbol}</p>
          <p className="text-sm text-gray-600">Rank: {data.rank}</p>
          <p className="text-sm text-gray-600">P-value: {data.p_value.toExponential(3)}</p>
          <p className="text-sm text-gray-600">Effect Size: {data.effect_size.toFixed(3)}</p>
          <p className="text-sm text-gray-600">Fold Change: {data.fold_change.toFixed(3)}</p>
          <p className="text-sm text-gray-600">Significance: {data.significance}</p>
        </div>
      );
    }
    return null;
  };

  // Render chart based on type
  const renderChart = () => {
    switch (chartType) {
      case 'bar':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={processedData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="gene_symbol" 
                angle={-45}
                textAnchor="end"
                height={100}
                fontSize={12}
              />
              <YAxis />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar 
                dataKey="neg_log_p" 
                fill="#3b82f6" 
                name="-log10(P-value)"
                radius={[2, 2, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        );

      case 'scatter':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <ScatterChart data={processedData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="effect_size" 
                name="Effect Size"
                label={{ value: 'Effect Size', position: 'insideBottom', offset: -5 }}
              />
              <YAxis 
                dataKey="neg_log_p" 
                name="-log10(P-value)"
                label={{ value: '-log10(P-value)', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Scatter 
                dataKey="neg_log_p" 
                fill="#3b82f6"
                name="Biomarkers"
              />
            </ScatterChart>
          </ResponsiveContainer>
        );

      case 'line':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={processedData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="rank" 
                name="Rank"
                label={{ value: 'Biomarker Rank', position: 'insideBottom', offset: -5 }}
              />
              <YAxis 
                dataKey="neg_log_p" 
                name="-log10(P-value)"
                label={{ value: '-log10(P-value)', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="neg_log_p" 
                stroke="#3b82f6" 
                strokeWidth={2}
                name="-log10(P-value)"
                dot={{ fill: '#3b82f6', strokeWidth: 2, r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        );

      case 'pie':
        // Group by significance level
        const significanceData = processedData.reduce((acc, item) => {
          const level = item.significance;
          acc[level] = (acc[level] || 0) + 1;
          return acc;
        }, {});

        const pieData = Object.entries(significanceData).map(([key, value]) => ({
          name: key,
          value,
          color: significanceColors[key]
        }));

        return (
          <ResponsiveContainer width="100%" height={400}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={120}
                fill="#8884d8"
                dataKey="value"
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
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
          <p className="text-gray-500">No biomarker data available for visualization</p>
        </div>
      </div>
    );
  }

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

            {/* Sort by selector */}
            <div className="flex items-center space-x-2">
              <label className="text-sm font-medium text-gray-700">Sort By:</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="input-field text-sm"
              >
                <option value="p_value">P-value</option>
                <option value="effect_size">Effect Size</option>
                <option value="fold_change">Fold Change</option>
              </select>
            </div>

            {/* Top N selector */}
            <div className="flex items-center space-x-2">
              <label className="text-sm font-medium text-gray-700">Show Top:</label>
              <select
                value={topN}
                onChange={(e) => setTopN(parseInt(e.target.value))}
                className="input-field text-sm"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
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
            <p className="text-sm font-medium text-blue-600">Total Biomarkers</p>
            <p className="text-2xl font-bold text-blue-900">{data.length}</p>
          </div>
          <div className="bg-green-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-green-600">Significant (p &lt; 0.05)</p>
            <p className="text-2xl font-bold text-green-900">
              {data.filter(item => item.p_value < 0.05).length}
            </p>
          </div>
          <div className="bg-yellow-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-yellow-600">Highly Significant (p &lt; 0.001)</p>
            <p className="text-2xl font-bold text-yellow-900">
              {data.filter(item => item.p_value < 0.001).length}
            </p>
          </div>
          <div className="bg-purple-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-purple-600">Mean Effect Size</p>
            <p className="text-2xl font-bold text-purple-900">
              {data.reduce((sum, item) => sum + Math.abs(item.effect_size), 0) / data.length}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BiomarkerResultsChart;
