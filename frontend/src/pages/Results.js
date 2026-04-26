import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { usePipeline } from '../contexts/PipelineContext';
import { 
  BarChart3, 
  TrendingUp, 
  Download, 
  RefreshCw,
  Filter,
  Search,
  ArrowLeft,
  FileText,
  Activity,
  Database,
  Sparkles,
  Layers
} from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  ScatterChart,
  Scatter
} from 'recharts';
import toast from 'react-hot-toast';
import { apiClient } from '../services/api';

const Results = () => {
  const { runId } = useParams();
  const navigate = useNavigate();
  const { getRunResults, getBiomarkers, getRunStatus, generateReport } = usePipeline();
  
  const [results, setResults] = useState(null);
  const [biomarkers, setBiomarkers] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('biomarkers');
  const [searchTerm, setSearchTerm] = useState('');
  const [filteredBiomarkers, setFilteredBiomarkers] = useState([]);
  const [groundedInterpretation, setGroundedInterpretation] = useState(null);
  const [groundedLoading, setGroundedLoading] = useState(false);
  const [groundedNotes, setGroundedNotes] = useState('');
  const [llmStatus, setLlmStatus] = useState(null);
  const [artifactSummary, setArtifactSummary] = useState(null);

  const loadResults = useCallback(async () => {
    if (!runId) return;
    try {
      setLoading(true);
      
      const [resultsData, biomarkersData, statusData] = await Promise.all([
        getRunResults(runId),
        getBiomarkers(runId),
        getRunStatus(runId)
      ]);

      setResults(resultsData);
      setBiomarkers(biomarkersData);
      setStatus(statusData);

      try {
        const { data: art } = await apiClient.get(`/biomarkers/runs/${runId}/artifacts`);
        setArtifactSummary(art);
      } catch {
        setArtifactSummary(null);
      }
      try {
        const { data: ls } = await apiClient.get('/analysis/llm/status');
        setLlmStatus(ls);
      } catch {
        setLlmStatus({ available: false, message: 'Could not reach LLM status' });
      }
    } catch (error) {
      console.error('Failed to load results:', error);
      toast.error('Failed to load results');
    } finally {
      setLoading(false);
    }
  }, [runId, getRunResults, getBiomarkers, getRunStatus]);

  useEffect(() => {
    if (runId) {
      loadResults();
    } else {
      setLoading(false);
    }
  }, [runId, loadResults]);

  useEffect(() => {
    if (biomarkers) {
      const filtered = biomarkers.biomarkers?.filter(biomarker =>
        biomarker.gene?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        biomarker.description?.toLowerCase().includes(searchTerm.toLowerCase())
      ) || [];
      setFilteredBiomarkers(filtered);
    }
  }, [biomarkers, searchTerm]);

  const handleRefresh = async () => {
    await loadResults();
    toast.success('Results refreshed');
  };

  const handleDownloadCSV = () => {
    if (!biomarkers?.biomarkers?.length) {
      toast.error('No biomarkers to download');
      return;
    }
    const headers = ['Rank', 'Gene', 'Score', 'P-value', 'Fold Change', 'Description'];
    const rows = biomarkers.biomarkers.map((b, i) => [
      i + 1,
      b.gene,
      (b.final_score ?? b.p_value ?? 0).toFixed(4),
      (b.p_value ?? 0).toExponential(4),
      (b.fold_change ?? 0).toFixed(4),
      b.description || '',
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `biomarkers_${runId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success('Download started');
  };

  const handleGroundedInterpretation = async () => {
    const genes = (biomarkers?.biomarkers || []).slice(0, 30).map((b) => b.gene).filter(Boolean);
    if (!genes.length) {
      toast.error('No biomarker genes available for interpretation');
      return;
    }
    if (llmStatus && llmStatus.available === false) {
      toast.error(llmStatus.message || 'LLM backend not configured on server');
      return;
    }
    setGroundedLoading(true);
    setGroundedInterpretation(null);
    try {
      const pipeline_summary = {
        run_id: runId,
        total_biomarkers: biomarkers?.total_count ?? null,
        pipeline_status: status?.status ?? null,
      };
      const { data } = await apiClient.post('/analysis/llm/interpret-grounded', {
        genes,
        pipeline_summary: pipeline_summary,
        extra_context: groundedNotes.trim() || undefined,
        structured: true,
      });
      setGroundedInterpretation(data);
      toast.success('Interpretation generated');
    } catch (error) {
      const detail = error.response?.data?.detail || error.message || 'Request failed';
      toast.error(typeof detail === 'string' ? detail : 'Interpretation failed');
    } finally {
      setGroundedLoading(false);
    }
  };

  const handleSaveInterpretationSnapshot = async () => {
    if (!groundedInterpretation || !runId) return;
    try {
      await apiClient.post('/analysis/interpretations/snapshots', {
        run_id: runId,
        notes: groundedNotes.trim() || undefined,
        payload: groundedInterpretation,
      });
      toast.success('Interpretation snapshot saved');
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      toast.error(typeof detail === 'string' ? detail : 'Save failed (sign in required?)');
    }
  };

  const handleExportInterpretationMd = async () => {
    if (!runId) return;
    try {
      const { data } = await apiClient.get(
        `/analysis/interpretations/snapshots/${runId}/export.md`,
        { responseType: 'blob' }
      );
      const url = URL.createObjectURL(data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `interpretation_${runId}.md`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Download started');
    } catch (error) {
      toast.error('Export failed — save a snapshot first or sign in');
    }
  };

  const handleGenerateReport = async () => {
    const result = await generateReport(runId, 'html');
    if (result.success) {
      toast.success('Report generated');
      navigate('/reports');
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'text-green-600';
      case 'running': return 'text-blue-600';
      case 'failed': return 'text-red-600';
      default: return 'text-yellow-600';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed': return '✓';
      case 'running': return '⏳';
      case 'failed': return '✗';
      default: return '?';
    }
  };

  // Prepare data for visualizations
  const prepareBiomarkerChartData = () => {
    if (!biomarkers?.biomarkers) return [];
    
    return biomarkers.biomarkers.slice(0, 20).map((biomarker, index) => ({
      gene: biomarker.gene,
      score: biomarker.final_score || biomarker.p_value || 0,
      rank: index + 1,
      pValue: biomarker.p_value || 0,
      foldChange: biomarker.fold_change || 0,
    }));
  };

  const prepareScoreDistributionData = () => {
    if (!biomarkers?.biomarkers) return [];
    
    const scores = biomarkers.biomarkers.map(b => b.final_score || 0);
    const bins = [0, 0.2, 0.4, 0.6, 0.8, 1.0];
    const distribution = bins.slice(0, -1).map((bin, index) => ({
      range: `${bin}-${bins[index + 1]}`,
      count: scores.filter(s => s >= bin && s < bins[index + 1]).length,
    }));
    
    return distribution;
  };

  const preparePValueDistributionData = () => {
    if (!biomarkers?.biomarkers) return [];
    
    const pValues = biomarkers.biomarkers.map(b => b.p_value || 1);
    const bins = [0, 0.001, 0.01, 0.05, 0.1, 1.0];
    const distribution = bins.slice(0, -1).map((bin, index) => ({
      range: `${bin}-${bins[index + 1]}`,
      count: pValues.filter(p => p >= bin && p < bins[index + 1]).length,
    }));
    
    return distribution;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (!runId) {
    return (
      <div className="text-center py-12">
        <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">Select a Run</h3>
        <p className="text-gray-500 mb-4">Choose a run from the monitoring page or use a direct link to view results.</p>
        <button onClick={() => navigate('/monitoring')} className="btn-primary">
          View All Runs
        </button>
      </div>
    );
  }

  if (!results && !biomarkers) {
    return (
      <div className="text-center py-12">
        <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">No results found</h3>
        <p className="text-gray-500 mb-4">The selected run may not have completed yet or may have failed.</p>
        <button onClick={() => navigate('/monitoring')} className="btn-primary">
          View All Runs
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate('/monitoring')}
            className="p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Analysis Results</h1>
            <p className="mt-1 text-gray-600">Run ID: {runId}</p>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          {status && (
            <div className={`flex items-center space-x-2 ${getStatusColor(status.status)}`}>
              <span className="text-lg">{getStatusIcon(status.status)}</span>
              <span className="font-medium capitalize">{status.status}</span>
            </div>
          )}
          <button
            onClick={handleRefresh}
            className="btn-secondary flex items-center space-x-2"
          >
            <RefreshCw className="h-4 w-4" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center">
            <BarChart3 className="h-8 w-8 text-primary-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Biomarkers</p>
              <p className="text-2xl font-semibold text-gray-900">
                {biomarkers?.total_count || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <TrendingUp className="h-8 w-8 text-green-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">High Confidence</p>
              <p className="text-2xl font-semibold text-gray-900">
                {biomarkers?.biomarkers?.filter(b => (b.final_score || 0) > 0.7).length || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <Activity className="h-8 w-8 text-blue-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Significant (p&lt;0.05)</p>
              <p className="text-2xl font-semibold text-gray-900">
                {biomarkers?.biomarkers?.filter(b => (b.p_value || 1) < 0.05).length || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <FileText className="h-8 w-8 text-purple-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Analysis Status</p>
              <p className="text-2xl font-semibold text-gray-900 capitalize">
                {status?.status || 'Unknown'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {[
            { id: 'biomarkers', name: 'Biomarkers', icon: BarChart3 },
            { id: 'visualizations', name: 'Visualizations', icon: TrendingUp },
            { id: 'statistics', name: 'Statistics', icon: Activity },
            { id: 'interpretation', name: 'Interpretation', icon: Sparkles },
            { id: 'explainability', name: 'Explainability', icon: Layers },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-primary-500 text-primary-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.name}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'biomarkers' && (
        <div className="space-y-6">
          {/* Search and Filter */}
          <div className="card">
            <div className="flex items-center space-x-4">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search biomarkers by gene name or description..."
                    className="input-field pl-10"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
              </div>
              <button className="btn-secondary flex items-center space-x-2">
                <Filter className="h-4 w-4" />
                <span>Filter</span>
              </button>
            </div>
          </div>

          {/* Biomarkers Table */}
          <div className="card">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Rank
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Gene
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Score
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      P-value
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Fold Change
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Description
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredBiomarkers.map((biomarker, index) => (
                    <tr key={biomarker.gene} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {index + 1}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {biomarker.gene}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <div className="flex items-center">
                          <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                            <div
                              className="bg-primary-600 h-2 rounded-full"
                              style={{ width: `${(biomarker.final_score || 0) * 100}%` }}
                            ></div>
                          </div>
                          <span>{(biomarker.final_score || 0).toFixed(3)}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {(biomarker.p_value || 0).toExponential(2)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {(biomarker.fold_change || 0).toFixed(2)}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {biomarker.description || 'No description available'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'visualizations' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Biomarkers Chart */}
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Biomarkers</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={prepareBiomarkerChartData()}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="gene" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="score" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Score Distribution */}
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Score Distribution</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={prepareScoreDistributionData()}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="range" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* P-value Distribution */}
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">P-value Distribution</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={preparePValueDistributionData()}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="range" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#f59e0b" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Fold Change vs P-value Scatter */}
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Fold Change vs P-value</h3>
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart data={prepareBiomarkerChartData()}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="foldChange" name="Fold Change" />
                <YAxis dataKey="pValue" name="P-value" />
                <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                <Scatter dataKey="score" fill="#8b5cf6" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {activeTab === 'interpretation' && (
        <div className="space-y-6">
          <div className="card">
            <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-primary-600" />
                  Grounded interpretation
                </h3>
                <p className="text-sm text-gray-600 mt-1 max-w-2xl">
                  Summarizes top biomarker genes using the app&apos;s local knowledge snippets plus your run summary.
                  Configure the LLM backend (OpenAI API key or local transformers) on the server for full output.
                </p>
                {llmStatus && (
                  <p className={`text-xs mt-2 ${llmStatus.available ? 'text-green-700' : 'text-amber-700'}`}>
                    LLM status: {llmStatus.available ? 'available' : 'unavailable'}
                    {!llmStatus.available && llmStatus.message ? ` — ${llmStatus.message}` : ''}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={handleGroundedInterpretation}
                disabled={groundedLoading}
                className="btn-primary flex items-center justify-center space-x-2 shrink-0"
              >
                {groundedLoading ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Generating…</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    <span>Generate interpretation</span>
                  </>
                )}
              </button>
            </div>
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Optional notes for the model (cohort, contrast, hypothesis)
              </label>
              <textarea
                className="input-field w-full min-h-[80px]"
                placeholder="e.g. TCGA BRCA tumor vs normal; focus on DNA repair pathway"
                value={groundedNotes}
                onChange={(e) => setGroundedNotes(e.target.value)}
              />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" onClick={handleSaveInterpretationSnapshot} disabled={!groundedInterpretation} className="btn-secondary text-sm">
                Save snapshot
              </button>
              <button type="button" onClick={handleExportInterpretationMd} className="btn-secondary text-sm">
                Export Markdown
              </button>
            </div>
          </div>

          {groundedInterpretation && (
            <div className="space-y-4">
              <div className="card bg-primary-50/50 border border-primary-100">
                <h4 className="text-sm font-semibold text-gray-800 mb-2">Interpretation</h4>
                <div className="text-gray-800 whitespace-pre-wrap text-sm leading-relaxed">
                  {groundedInterpretation.interpretation}
                </div>
                {groundedInterpretation.structured && Object.keys(groundedInterpretation.structured || {}).length > 0 && (
                  <div className="mt-4 space-y-2 border-t border-primary-200 pt-3">
                    <h5 className="text-xs font-semibold text-gray-700 uppercase">Structured summary</h5>
                    {groundedInterpretation.structured.summary && (
                      <p className="text-sm text-gray-800"><strong>Summary:</strong> {groundedInterpretation.structured.summary}</p>
                    )}
                    {groundedInterpretation.structured.limitations && (
                      <p className="text-sm text-gray-800"><strong>Limitations:</strong> {groundedInterpretation.structured.limitations}</p>
                    )}
                    {groundedInterpretation.structured.suggested_validation && (
                      <p className="text-sm text-gray-800"><strong>Validation:</strong> {groundedInterpretation.structured.suggested_validation}</p>
                    )}
                  </div>
                )}
                {groundedInterpretation.matched_genes?.length > 0 && (
                  <p className="text-xs text-gray-500 mt-3">
                    Genes matched to local snippets: {groundedInterpretation.matched_genes.join(', ')}
                  </p>
                )}
              </div>
              {groundedInterpretation.sources?.length > 0 && (
                <div className="card">
                  <h4 className="text-sm font-semibold text-gray-900 mb-3">Sources (corpus + optional PubMed)</h4>
                  <ul className="space-y-3">
                    {groundedInterpretation.sources.map((src, idx) => (
                      <li key={src.id || idx} className="border-l-4 border-primary-400 pl-3">
                        <p className="font-medium text-gray-800 text-sm">
                          {src.title || src.id}
                          {src.pmid ? (
                            <span className="text-gray-500 font-normal"> — PMID {src.pmid}</span>
                          ) : null}
                        </p>
                        <p className="text-gray-600 text-sm mt-1">{src.snippet}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'explainability' && (
        <div className="space-y-6">
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Layers className="h-5 w-5 text-primary-600" />
              Model outputs &amp; pathway context
            </h3>
            <p className="text-sm text-gray-600 mt-1">
              When the pipeline stores SHAP, pathway, or enrichment summaries on the run, they appear here. See also{' '}
              <button type="button" className="text-primary-600 underline" onClick={() => navigate(`/clinical/${runId}`)}>
                Clinical annotation
              </button>
              .
            </p>
          </div>
          <div className="card">
            <h4 className="text-sm font-semibold text-gray-800 mb-2">Run results summary (from artifacts)</h4>
            <pre className="text-xs bg-gray-50 p-3 rounded overflow-x-auto max-h-96">
              {artifactSummary?.results_summary
                ? JSON.stringify(artifactSummary.results_summary, null, 2)
                : 'No results_summary stored for this run yet.'}
            </pre>
          </div>
        </div>
      )}

      {activeTab === 'statistics' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="card">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Analysis Summary</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600">Total genes analyzed:</span>
                  <span className="font-medium">{biomarkers?.total_count || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Significant biomarkers (p&lt;0.05):</span>
                  <span className="font-medium">
                    {biomarkers?.biomarkers?.filter(b => (b.p_value || 1) < 0.05).length || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">High confidence biomarkers:</span>
                  <span className="font-medium">
                    {biomarkers?.biomarkers?.filter(b => (b.final_score || 0) > 0.7).length || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Analysis status:</span>
                  <span className="font-medium capitalize">{status?.status || 'Unknown'}</span>
                </div>
              </div>
            </div>

            <div className="card">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Export Options</h3>
              <div className="space-y-3">
                <button onClick={handleDownloadCSV} className="w-full btn-primary flex items-center justify-center space-x-2">
                  <Download className="h-4 w-4" />
                  <span>Download Biomarkers (CSV)</span>
                </button>
                <button 
                  onClick={() => navigate(`/clinical/${runId}`)}
                  className="w-full btn-secondary flex items-center justify-center space-x-2"
                >
                  <Database className="h-4 w-4" />
                  <span>Clinical Annotation</span>
                </button>
                <button onClick={handleGenerateReport} className="w-full btn-secondary flex items-center justify-center space-x-2">
                  <FileText className="h-4 w-4" />
                  <span>Generate Report</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};


export default Results;
