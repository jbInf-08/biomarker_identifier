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
  PieChart,
  Pie,
  Cell,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar
} from 'recharts';
import { BarChart3, PieChart as PieChartIcon, Radar as RadarIcon, Database } from 'lucide-react';

const ClinicalAnnotationChart = ({ data, title = "Clinical Annotation Results" }) => {
  const [chartType, setChartType] = useState('bar');
  const [sortBy, setSortBy] = useState('clinical_relevance_score');
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
          case 'high_relevance':
            return item.clinical_relevance_score >= 0.7;
          case 'medium_relevance':
            return item.clinical_relevance_score >= 0.4 && item.clinical_relevance_score < 0.7;
          case 'low_relevance':
            return item.clinical_relevance_score < 0.4;
          case 'cosmic_annotated':
            return item.cosmic_annotations && item.cosmic_annotations.length > 0;
          case 'clinvar_annotated':
            return item.clinvar_annotations && item.clinvar_annotations.length > 0;
          case 'oncokb_annotated':
            return item.oncokb_annotations && item.oncokb_annotations.length > 0;
          default:
            return true;
        }
      });
    }

    // Sort and limit data
    const sortedData = filteredData
      .sort((a, b) => {
        switch (sortBy) {
          case 'clinical_relevance_score':
            return b.clinical_relevance_score - a.clinical_relevance_score;
          case 'cosmic_count':
            return (b.cosmic_annotations?.length || 0) - (a.cosmic_annotations?.length || 0);
          case 'clinvar_count':
            return (b.clinvar_annotations?.length || 0) - (a.clinvar_annotations?.length || 0);
          case 'oncokb_count':
            return (b.oncokb_annotations?.length || 0) - (a.oncokb_annotations?.length || 0);
          default:
            return 0;
        }
      })
      .slice(0, topN);

    return sortedData.map((item, index) => ({
      ...item,
      rank: index + 1,
      cosmic_count: item.cosmic_annotations?.length || 0,
      clinvar_count: item.clinvar_annotations?.length || 0,
      oncokb_count: item.oncokb_annotations?.length || 0,
      total_annotations: (item.cosmic_annotations?.length || 0) + 
                       (item.clinvar_annotations?.length || 0) + 
                       (item.oncokb_annotations?.length || 0),
      relevance_level: item.clinical_relevance_score >= 0.7 ? 'High' : 
                      item.clinical_relevance_score >= 0.4 ? 'Medium' : 'Low'
    }));
  }, [data, sortBy, topN, filterBy]);

  // Color scheme for relevance levels
  const relevanceColors = {
    'High': '#10b981',
    'Medium': '#f59e0b',
    'Low': '#ef4444'
  };

  // Chart type options
  const chartTypes = [
    { value: 'bar', label: 'Bar Chart', icon: BarChart3 },
    { value: 'pie', label: 'Pie Chart', icon: PieChartIcon },
    { value: 'radar', label: 'Radar Chart', icon: RadarIcon }
  ];

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-lg max-w-xs">
          <p className="font-semibold text-gray-900">{data.gene_symbol}</p>
          <p className="text-sm text-gray-600">Clinical Relevance Score: {data.clinical_relevance_score.toFixed(3)}</p>
          <p className="text-sm text-gray-600">Relevance Level: {data.relevance_level}</p>
          <p className="text-sm text-gray-600">COSMIC Annotations: {data.cosmic_count}</p>
          <p className="text-sm text-gray-600">ClinVar Annotations: {data.clinvar_count}</p>
          <p className="text-sm text-gray-600">OncoKB Annotations: {data.oncokb_count}</p>
          <p className="text-sm text-gray-600">Total Annotations: {data.total_annotations}</p>
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
                fontSize={10}
              />
              <YAxis />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar 
                dataKey="clinical_relevance_score" 
                fill="#3b82f6" 
                name="Clinical Relevance Score"
                radius={[2, 2, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        );

      case 'pie':
        // Group by relevance level
        const relevanceData = processedData.reduce((acc, item) => {
          const level = item.relevance_level;
          acc[level] = (acc[level] || 0) + 1;
          return acc;
        }, {});

        const pieData = Object.entries(relevanceData).map(([key, value]) => ({
          name: key,
          value,
          color: relevanceColors[key]
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

      case 'radar':
        // Create radar data for database annotation counts
        const radarData = [
          {
            database: 'COSMIC',
            count: processedData.reduce((sum, item) => sum + item.cosmic_count, 0),
            max: Math.max(...processedData.map(item => item.cosmic_count))
          },
          {
            database: 'ClinVar',
            count: processedData.reduce((sum, item) => sum + item.clinvar_count, 0),
            max: Math.max(...processedData.map(item => item.clinvar_count))
          },
          {
            database: 'OncoKB',
            count: processedData.reduce((sum, item) => sum + item.oncokb_count, 0),
            max: Math.max(...processedData.map(item => item.oncokb_count))
          }
        ];

        return (
          <ResponsiveContainer width="100%" height={400}>
            <RadarChart data={radarData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <PolarGrid />
              <PolarAngleAxis dataKey="database" />
              <PolarRadiusAxis />
              <Radar
                name="Annotation Count"
                dataKey="count"
                stroke="#3b82f6"
                fill="#3b82f6"
                fillOpacity={0.3}
              />
              <Tooltip />
              <Legend />
            </RadarChart>
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
          <p className="text-gray-500">No clinical annotation data available for visualization</p>
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
                <option value="clinical_relevance_score">Clinical Relevance Score</option>
                <option value="cosmic_count">COSMIC Count</option>
                <option value="clinvar_count">ClinVar Count</option>
                <option value="oncokb_count">OncoKB Count</option>
              </select>
            </div>

            {/* Filter selector */}
            <div className="flex items-center space-x-2">
              <Database className="w-4 h-4 text-gray-500" />
              <select
                value={filterBy}
                onChange={(e) => setFilterBy(e.target.value)}
                className="input-field text-sm"
              >
                <option value="all">All Annotations</option>
                <option value="high_relevance">High Relevance (≥0.7)</option>
                <option value="medium_relevance">Medium Relevance (0.4-0.7)</option>
                <option value="low_relevance">Low Relevance (&lt;0.4)</option>
                <option value="cosmic_annotated">COSMIC Annotated</option>
                <option value="clinvar_annotated">ClinVar Annotated</option>
                <option value="oncokb_annotated">OncoKB Annotated</option>
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
            <p className="text-sm font-medium text-blue-600">Total Annotations</p>
            <p className="text-2xl font-bold text-blue-900">{data.length}</p>
          </div>
          <div className="bg-green-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-green-600">High Relevance</p>
            <p className="text-2xl font-bold text-green-900">
              {data.filter(item => item.clinical_relevance_score >= 0.7).length}
            </p>
          </div>
          <div className="bg-yellow-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-yellow-600">COSMIC Annotated</p>
            <p className="text-2xl font-bold text-yellow-900">
              {data.filter(item => item.cosmic_annotations && item.cosmic_annotations.length > 0).length}
            </p>
          </div>
          <div className="bg-purple-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-purple-600">ClinVar Annotated</p>
            <p className="text-2xl font-bold text-purple-900">
              {data.filter(item => item.clinvar_annotations && item.clinvar_annotations.length > 0).length}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ClinicalAnnotationChart;
