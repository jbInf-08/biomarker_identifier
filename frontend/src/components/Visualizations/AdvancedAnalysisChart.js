/**
 * Advanced Analysis Chart Component
 * Interactive analysis tools with advanced data visualization features
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  ScatterChart,
  Scatter,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Brush,
  ReferenceLine,
  Cell
} from 'recharts';

const AdvancedAnalysisChart = ({ data, analysisType = 'multi-dimensional' }) => {
  const [selectedDimensions, setSelectedDimensions] = useState(['x', 'y']);
  const [zoomDomain, setZoomDomain] = useState(null);
  const [highlightedPoints, setHighlightedPoints] = useState([]);
  const [filterOptions, setFilterOptions] = useState({
    minValue: null,
    maxValue: null,
    geneFilter: '',
    significanceFilter: 0.05
  });
  const chartRef = useRef(null);

  // Interactive tooltip component
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-3 rounded-lg shadow-lg border border-gray-200">
          <p className="font-semibold text-gray-800">{`${label}`}</p>
          {payload.map((entry, index) => (
            <p key={index} className="text-sm" style={{ color: entry.color }}>
              {`${entry.name}: ${entry.value?.toFixed(4) || 'N/A'}`}
              {entry.payload?.pValue && (
                <span className="ml-2 text-gray-500">
                  (p={entry.payload.pValue.toFixed(4)})
                </span>
              )}
            </p>
          ))}
          {payload[0]?.payload?.geneSymbol && (
            <p className="text-xs text-gray-600 mt-1">
              Gene: {payload[0].payload.geneSymbol}
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  // Filter data based on options
  const filteredData = React.useMemo(() => {
    let filtered = [...(data || [])];

    if (filterOptions.minValue !== null) {
      filtered = filtered.filter(d => d.value >= filterOptions.minValue);
    }
    if (filterOptions.maxValue !== null) {
      filtered = filtered.filter(d => d.value <= filterOptions.maxValue);
    }
    if (filterOptions.geneFilter) {
      filtered = filtered.filter(d =>
        d.geneSymbol?.toLowerCase().includes(filterOptions.geneFilter.toLowerCase())
      );
    }
    if (filterOptions.significanceFilter) {
      filtered = filtered.filter(d =>
        d.pValue <= filterOptions.significanceFilter
      );
    }

    return filtered;
  }, [data, filterOptions]);

  // Render chart based on analysis type
  const renderChart = () => {
    switch (analysisType) {
      case 'volcano':
        return renderVolcanoPlot();
      case 'heatmap':
        return renderHeatmap();
      case 'pca':
        return renderPCAPlot();
      case 'survival':
        return renderSurvivalCurve();
      case 'network':
        return renderNetworkGraph();
      case 'multi-dimensional':
      default:
        return renderMultiDimensionalView();
    }
  };

  // Volcano plot visualization
  const renderVolcanoPlot = () => {
    const volcanoData = filteredData.map(d => ({
      x: Math.log2(Math.abs(d.foldChange || 1)),
      y: -Math.log10(d.pValue || 0.0001),
      name: d.geneSymbol || d.name,
      value: d.value,
      significant: (d.pValue || 1) < 0.05 && Math.abs(d.foldChange || 0) > 1,
      ...d
    }));

    return (
      <ResponsiveContainer width="100%" height={500}>
        <ScatterChart
          margin={{ top: 20, right: 30, bottom: 60, left: 60 }}
          data={volcanoData}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            label={{ value: 'Log2 Fold Change', position: 'insideBottom', offset: -10 }}
            dataKey="x"
          />
          <YAxis
            label={{ value: '-Log10 P-value', angle: -90, position: 'insideLeft' }}
            dataKey="y"
          />
          <Tooltip content={<CustomTooltip />} />
          <Scatter
            name="Genes"
            data={volcanoData}
            fill="#8884d8"
            onClick={(data) => {
              setHighlightedPoints([data]);
            }}
          >
            {volcanoData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.significant ? '#ff4444' : '#8884d8'}
              />
            ))}
          </Scatter>
          <ReferenceLine y={-Math.log10(0.05)} stroke="red" strokeDasharray="3 3" label="Significance" />
          <ReferenceLine x={1} stroke="blue" strokeDasharray="3 3" />
          <ReferenceLine x={-1} stroke="blue" strokeDasharray="3 3" />
        </ScatterChart>
      </ResponsiveContainer>
    );
  };

  // PCA plot visualization
  const renderPCAPlot = () => {
    const pcaData = filteredData.map(d => ({
      x: d.pc1 || d.x,
      y: d.pc2 || d.y,
      name: d.geneSymbol || d.name,
      ...d
    }));

    return (
      <ResponsiveContainer width="100%" height={500}>
        <ScatterChart
          margin={{ top: 20, right: 30, bottom: 60, left: 60 }}
          data={pcaData}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            label={{ value: 'PC1', position: 'insideBottom', offset: -10 }}
            dataKey="x"
          />
          <YAxis
            label={{ value: 'PC2', angle: -90, position: 'insideLeft' }}
            dataKey="y"
          />
          <Tooltip content={<CustomTooltip />} />
          <Scatter name="Samples" data={pcaData} fill="#8884d8" />
        </ScatterChart>
      </ResponsiveContainer>
    );
  };

  // Survival curve visualization
  const renderSurvivalCurve = () => {
    const survivalData = filteredData.map(d => ({
      time: d.time || d.x,
      survival: d.survival || d.y,
      group: d.group || 'All',
      atRisk: d.atRisk || 0,
      ...d
    }));

    return (
      <ResponsiveContainer width="100%" height={500}>
        <LineChart data={survivalData} margin={{ top: 20, right: 30, bottom: 60, left: 60 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            label={{ value: 'Time (months)', position: 'insideBottom', offset: -10 }}
            dataKey="time"
          />
          <YAxis
            label={{ value: 'Survival Probability', angle: -90, position: 'insideLeft' }}
            domain={[0, 1]}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <Line
            type="monotone"
            dataKey="survival"
            stroke="#8884d8"
            strokeWidth={2}
            dot={false}
            name="Survival"
          />
          <Area
            type="monotone"
            dataKey="survival"
            stroke="#8884d8"
            fill="#8884d8"
            fillOpacity={0.3}
          />
        </LineChart>
      </ResponsiveContainer>
    );
  };

  // Multi-dimensional view
  const renderMultiDimensionalView = () => {
    const chartData = filteredData.slice(0, 100); // Limit for performance

    return (
      <ResponsiveContainer width="100%" height={500}>
        <LineChart
          data={chartData}
          margin={{ top: 20, right: 30, bottom: 60, left: 60 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="name"
            angle={-45}
            textAnchor="end"
            height={100}
          />
          <YAxis />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <Line
            type="monotone"
            dataKey="value"
            stroke="#8884d8"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 6 }}
          />
          <Brush dataKey="name" height={30} />
        </LineChart>
      </ResponsiveContainer>
    );
  };

  // Heatmap visualization - requires heatmap-formatted data (samples x genes matrix)
  const renderHeatmap = () => {
    const hasHeatmapData = data?.length && data[0]?.hasOwnProperty?.('samples');
    return (
      <div className="w-full h-96 flex flex-col items-center justify-center border border-gray-300 rounded bg-gray-50">
        {hasHeatmapData ? (
          <p className="text-gray-600">Heatmap requires a samples×genes matrix format. Use volcano or PCA for expression data.</p>
        ) : (
          <>
            <p className="text-gray-600 font-medium">No heatmap data available</p>
            <p className="text-sm text-gray-500 mt-1">Upload expression matrix (samples × genes) for heatmap visualization</p>
          </>
        )}
      </div>
    );
  };

  // Network graph visualization - requires interaction/PPI data
  const renderNetworkGraph = () => {
    const hasNetworkData = data?.length && data.some(d => d.source || d.target);
    return (
      <div className="w-full h-96 flex flex-col items-center justify-center border border-gray-300 rounded bg-gray-50">
        {hasNetworkData ? (
          <p className="text-gray-600">Network graph requires source/target edge data. Run pathway analysis for interaction networks.</p>
        ) : (
          <>
            <p className="text-gray-600 font-medium">No network data available</p>
            <p className="text-sm text-gray-500 mt-1">Run pathway or network analysis to generate interaction data</p>
          </>
        )}
      </div>
    );
  };

  return (
    <div className="w-full bg-white rounded-lg shadow-lg p-6">
      <div className="mb-4">
        <h3 className="text-xl font-bold text-gray-800 mb-2">Advanced Analysis Visualization</h3>
        
        {/* Filter Controls */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Min Value
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              value={filterOptions.minValue || ''}
              onChange={(e) => setFilterOptions({
                ...filterOptions,
                minValue: e.target.value ? parseFloat(e.target.value) : null
              })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Value
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              value={filterOptions.maxValue || ''}
              onChange={(e) => setFilterOptions({
                ...filterOptions,
                maxValue: e.target.value ? parseFloat(e.target.value) : null
              })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Gene Filter
            </label>
            <input
              type="text"
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              placeholder="Search genes..."
              value={filterOptions.geneFilter}
              onChange={(e) => setFilterOptions({
                ...filterOptions,
                geneFilter: e.target.value
              })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Significance (p-value)
            </label>
            <input
              type="number"
              step="0.01"
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              value={filterOptions.significanceFilter}
              onChange={(e) => setFilterOptions({
                ...filterOptions,
                significanceFilter: parseFloat(e.target.value)
              })}
            />
          </div>
        </div>

        {/* Analysis Type Selector */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Analysis Type
          </label>
          <select
            className="px-4 py-2 border border-gray-300 rounded-md"
            value={analysisType}
            onChange={(e) => setSelectedDimensions(['x', 'y'])}
          >
            <option value="multi-dimensional">Multi-dimensional</option>
            <option value="volcano">Volcano Plot</option>
            <option value="pca">PCA Plot</option>
            <option value="survival">Survival Curve</option>
            <option value="heatmap">Heatmap</option>
            <option value="network">Network Graph</option>
          </select>
        </div>
      </div>

      {/* Chart */}
      <div className="w-full">
        {renderChart()}
      </div>

      {/* Statistics Summary */}
      <div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-50 p-3 rounded">
          <p className="text-sm text-gray-600">Total Points</p>
          <p className="text-xl font-bold">{filteredData.length}</p>
        </div>
        <div className="bg-gray-50 p-3 rounded">
          <p className="text-sm text-gray-600">Significant</p>
          <p className="text-xl font-bold text-green-600">
            {filteredData.filter(d => (d.pValue || 1) < 0.05).length}
          </p>
        </div>
        <div className="bg-gray-50 p-3 rounded">
          <p className="text-sm text-gray-600">Filtered</p>
          <p className="text-xl font-bold">
            {data?.length ? data.length - filteredData.length : 0}
          </p>
        </div>
        <div className="bg-gray-50 p-3 rounded">
          <p className="text-sm text-gray-600">Highlighted</p>
          <p className="text-xl font-bold text-blue-600">{highlightedPoints.length}</p>
        </div>
      </div>
    </div>
  );
};

export default AdvancedAnalysisChart;

