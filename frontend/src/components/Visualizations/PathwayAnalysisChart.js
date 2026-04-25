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
  Treemap,
  Cell,
  ScatterChart,
  Scatter
} from 'recharts';
import { BarChart3, TreePine, Circle, Filter } from 'lucide-react';

const PathwayAnalysisChart = ({ data, title = "Pathway Analysis Results" }) => {
  const [chartType, setChartType] = useState('bar');
  const [sortBy, setSortBy] = useState('p_value');
  const [topN, setTopN] = useState(20);
  const [filterBy, setFilterBy] = useState('all');

  // Process data for visualization
  const processedData = useMemo(() => {
    if (!data || !Array.isArray(data)) return [];

    // Filter data
    let filteredData = [...data];
    if (filterBy !== 'all') {
      filteredData = filteredData.filter(item => {
        switch (filterBy) {
          case 'significant':
            return item.p_value < 0.05;
          case 'highly_significant':
            return item.p_value < 0.001;
          case 'enriched':
            return item.enrichment_score > 0;
          case 'depleted':
            return item.enrichment_score < 0;
          default:
            return true;
        }
      });
    }

    // Sort and limit data
    const sortedData = filteredData
      .sort((a, b) => {
        switch (sortBy) {
          case 'p_value':
            return a.p_value - b.p_value;
          case 'enrichment_score':
            return Math.abs(b.enrichment_score) - Math.abs(a.enrichment_score);
          case 'gene_count':
            return b.gene_count - a.gene_count;
          case 'pathway_size':
            return b.pathway_size - a.pathway_size;
          default:
            return 0;
        }
      })
      .slice(0, topN);

    return sortedData.map((item, index) => ({
      ...item,
      rank: index + 1,
      neg_log_p: -Math.log10(item.p_value),
      abs_enrichment_score: Math.abs(item.enrichment_score),
      significance: item.p_value < 0.001 ? 'Highly Significant' : 
                   item.p_value < 0.01 ? 'Significant' : 
                   item.p_value < 0.05 ? 'Moderately Significant' : 'Not Significant',
      enrichment_status: item.enrichment_score > 0 ? 'Enriched' : 'Depleted'
    }));
  }, [data, sortBy, topN, filterBy]);

  // Color scheme for significance levels
  const significanceColors = {
    'Highly Significant': '#ef4444',
    'Significant': '#f97316',
    'Moderately Significant': '#eab308',
    'Not Significant': '#6b7280'
  };

  // Color scheme for enrichment status
  const enrichmentColors = {
    'Enriched': '#10b981',
    'Depleted': '#ef4444'
  };

  // Chart type options
  const chartTypes = [
    { value: 'bar', label: 'Bar Chart', icon: BarChart3 },
    { value: 'treemap', label: 'Treemap', icon: TreePine },
    { value: 'scatter', label: 'Scatter Plot', icon: Circle }
  ];

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-lg max-w-xs">
          <p className="font-semibold text-gray-900">{data.pathway_name}</p>
          <p className="text-sm text-gray-600">Database: {data.database}</p>
          <p className="text-sm text-gray-600">P-value: {data.p_value.toExponential(3)}</p>
          <p className="text-sm text-gray-600">Enrichment Score: {data.enrichment_score.toFixed(3)}</p>
          <p className="text-sm text-gray-600">Gene Count: {data.gene_count}</p>
          <p className="text-sm text-gray-600">Pathway Size: {data.pathway_size}</p>
          <p className="text-sm text-gray-600">Significance: {data.significance}</p>
          <p className="text-sm text-gray-600">Status: {data.enrichment_status}</p>
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
                dataKey="pathway_name" 
                angle={-45}
                textAnchor="end"
                height={100}
                fontSize={10}
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

      case 'treemap':
        const treemapData = processedData.map(item => ({
          name: item.pathway_name,
          size: item.gene_count,
          value: item.neg_log_p,
          color: significanceColors[item.significance]
        }));

        return (
          <ResponsiveContainer width="100%" height={400}>
            <Treemap data={treemapData} dataKey="value">
              <Tooltip 
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="bg-white p-3 border border-gray-200 rounded shadow">
                        <p className="font-semibold">{data.name}</p>
                        <p className="text-sm">Size: {data.size}</p>
                        <p className="text-sm">Value: {data.value.toFixed(2)}</p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              {treemapData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Treemap>
          </ResponsiveContainer>
        );

      case 'scatter':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <ScatterChart data={processedData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="enrichment_score" 
                name="Enrichment Score"
                label={{ value: 'Enrichment Score', position: 'insideBottom', offset: -5 }}
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
                name="Pathways"
              />
            </ScatterChart>
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
          <p className="text-gray-500">No pathway analysis data available for visualization</p>
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
                <option value="enrichment_score">Enrichment Score</option>
                <option value="gene_count">Gene Count</option>
                <option value="pathway_size">Pathway Size</option>
              </select>
            </div>

            {/* Filter selector */}
            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-gray-500" />
              <select
                value={filterBy}
                onChange={(e) => setFilterBy(e.target.value)}
                className="input-field text-sm"
              >
                <option value="all">All Pathways</option>
                <option value="significant">Significant (p &lt; 0.05)</option>
                <option value="highly_significant">Highly Significant (p &lt; 0.001)</option>
                <option value="enriched">Enriched</option>
                <option value="depleted">Depleted</option>
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
            <p className="text-sm font-medium text-blue-600">Total Pathways</p>
            <p className="text-2xl font-bold text-blue-900">{data.length}</p>
          </div>
          <div className="bg-green-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-green-600">Significant (p &lt; 0.05)</p>
            <p className="text-2xl font-bold text-green-900">
              {data.filter(item => item.p_value < 0.05).length}
            </p>
          </div>
          <div className="bg-yellow-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-yellow-600">Enriched Pathways</p>
            <p className="text-2xl font-bold text-yellow-900">
              {data.filter(item => item.enrichment_score > 0).length}
            </p>
          </div>
          <div className="bg-purple-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-purple-600">Depleted Pathways</p>
            <p className="text-2xl font-bold text-purple-900">
              {data.filter(item => item.enrichment_score < 0).length}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PathwayAnalysisChart;
