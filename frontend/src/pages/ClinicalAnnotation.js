import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { usePipeline } from '../contexts/PipelineContext';
import { apiClient } from '../services/api';
import { 
  Database, 
  Search, 
  Filter, 
  Download, 
  RefreshCw,
  Star,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Info,
  ExternalLink,
  FlaskConical,
  Activity
} from 'lucide-react';
import toast from 'react-hot-toast';
import { ClinicalAnnotationChart } from '../components/Visualizations';

const ClinicalAnnotation = () => {
  const { runId } = useParams();
  const navigate = useNavigate();
  const { runs, fetchRuns } = usePipeline();
  
  const [annotations, setAnnotations] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDatabases, setSelectedDatabases] = useState(['COSMIC', 'ClinVar', 'OncoKB']);
  const [filterByRelevance, setFilterByRelevance] = useState('all');
  const [sortBy, setSortBy] = useState('relevance');
  const [cdsData, setCdsData] = useState(null);
  const [cdsLoading, setCdsLoading] = useState(false);

  const loadClinicalDecisionSupport = useCallback(async () => {
    if (!runId) return;
    setCdsLoading(true);
    try {
      const { data } = await apiClient.post('/clinical/decision-support/recommendations', {
        run_id: runId,
        patient_context: { disease_type: 'breast cancer' },
      });
      setCdsData(data);
    } catch (error) {
      console.error(error);
      toast.error('Clinical decision support request failed');
      setCdsData(null);
    } finally {
      setCdsLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    if (runId) {
      loadAnnotations();
    } else {
      setAnnotations(null);
    }
  }, [runId]);

  const loadAnnotations = useCallback(async () => {
    if (!runId) return;
    setLoading(true);
    try {
      const dbParam = selectedDatabases.map(d => `databases=${encodeURIComponent(d)}`).join('&');
      const { data } = await apiClient.post(
        `/clinical/annotate-run/${runId}?top_n=100&${dbParam}`
      );
      setAnnotations(data);
    } catch (error) {
      console.error('Failed to load annotations:', error);
      toast.error('Failed to load clinical annotations');
      setAnnotations(null);
    } finally {
      setLoading(false);
    }
  }, [runId, selectedDatabases]);

  const handleDatabaseToggle = (database) => {
    setSelectedDatabases(prev => 
      prev.includes(database) 
        ? prev.filter(db => db !== database)
        : [...prev, database]
    );
  };

  const getRelevanceColor = (score) => {
    if (score >= 0.7) return 'text-green-600 bg-green-100';
    if (score >= 0.4) return 'text-yellow-600 bg-yellow-100';
    if (score > 0) return 'text-orange-600 bg-orange-100';
    return 'text-gray-600 bg-gray-100';
  };

  const getRelevanceIcon = (score) => {
    if (score >= 0.7) return <Star className="h-4 w-4" />;
    if (score >= 0.4) return <CheckCircle className="h-4 w-4" />;
    if (score > 0) return <Info className="h-4 w-4" />;
    return <XCircle className="h-4 w-4" />;
  };

  const filteredAnnotations = annotations?.annotated_biomarkers?.filter(biomarker => {
    const matchesSearch = biomarker.gene_symbol.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesRelevance = filterByRelevance === 'all' || 
      (filterByRelevance === 'high' && biomarker.clinical_summary.clinical_relevance_score >= 0.5) ||
      (filterByRelevance === 'medium' && biomarker.clinical_summary.clinical_relevance_score >= 0.2 && biomarker.clinical_summary.clinical_relevance_score < 0.5) ||
      (filterByRelevance === 'low' && biomarker.clinical_summary.clinical_relevance_score > 0 && biomarker.clinical_summary.clinical_relevance_score < 0.2);
    
    return matchesSearch && matchesRelevance;
  }) || [];

  const sortedAnnotations = [...filteredAnnotations].sort((a, b) => {
    switch (sortBy) {
      case 'relevance':
        return b.clinical_summary.clinical_relevance_score - a.clinical_summary.clinical_relevance_score;
      case 'pvalue':
        return a.p_value - b.p_value;
      case 'foldchange':
        return Math.abs(b.fold_change) - Math.abs(a.fold_change);
      default:
        return 0;
    }
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (!runId) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Clinical Annotation</h1>
          <p className="mt-2 text-gray-600">Annotate biomarkers with clinical database information.</p>
        </div>
        <div className="card text-center py-12">
          <Database className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Select a run</h3>
          <p className="text-gray-500 mb-4">Choose a completed analysis run to view clinical annotations from COSMIC, ClinVar, and OncoKB.</p>
          <button onClick={() => navigate('/results')} className="btn-primary">
            View Results
          </button>
        </div>
      </div>
    );
  }

  if (!annotations) {
    return (
      <div className="text-center py-12">
        <Database className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">No annotations found</h3>
        <p className="text-gray-500 mb-4">Clinical annotations are not available for this run.</p>
        <button onClick={() => navigate('/monitoring')} className="btn-primary">
          Back to Monitoring
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Clinical Annotation</h1>
          <p className="mt-2 text-gray-600">
            Clinical database annotations for biomarkers in run {runId}
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={loadAnnotations}
            disabled={loading}
            className="btn-secondary flex items-center space-x-2"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <button className="btn-primary flex items-center space-x-2">
            <Download className="h-4 w-4" />
            <span>Export</span>
          </button>
        </div>
      </div>

      <div className="card border border-primary-100 bg-primary-50/40">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Clinical decision support</h2>
            <p className="text-sm text-gray-600 mt-1">
              Evidence-tier summaries from the CDS service (requires sign-in). Not medical advice.
            </p>
            {cdsData?.disclaimer && (
              <p className="text-xs text-amber-800 mt-2">{cdsData.disclaimer}</p>
            )}
          </div>
          <button
            type="button"
            onClick={loadClinicalDecisionSupport}
            disabled={cdsLoading}
            className="btn-primary shrink-0"
          >
            {cdsLoading ? 'Loading…' : 'Load CDS recommendations'}
          </button>
        </div>
        {cdsData?.recommendations?.length > 0 && (
          <ul className="mt-4 space-y-2 text-sm text-gray-800">
            {cdsData.recommendations.slice(0, 5).map((rec) => (
              <li key={rec.recommendation_id} className="border-l-4 border-primary-500 pl-2">
                <span className="font-medium">{rec.biomarker}</span>
                <span className="text-gray-500"> — evidence {rec.evidence_level}, strength {rec.strength}</span>
                <p className="text-gray-700 mt-1">{rec.recommendation}</p>
              </li>
            ))}
          </ul>
        )}
        {cdsData && (!cdsData.recommendations || cdsData.recommendations.length === 0) && (
          <p className="text-sm text-gray-600 mt-3">No recommendations returned (evidence database may be empty for these genes).</p>
        )}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center">
            <Database className="h-8 w-8 text-primary-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Annotated</p>
              <p className="text-2xl font-semibold text-gray-900">
                {annotations.annotation_summary.total_biomarkers}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <Star className="h-8 w-8 text-green-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">High Relevance</p>
              <p className="text-2xl font-semibold text-gray-900">
                {annotations.annotation_summary.high_relevance_count}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <FlaskConical className="h-8 w-8 text-blue-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Cancer Genes</p>
              <p className="text-2xl font-semibold text-gray-900">
                {sortedAnnotations.filter(b => b.clinical_summary.is_cancer_gene).length}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <Activity className="h-8 w-8 text-purple-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Therapeutic Targets</p>
              <p className="text-2xl font-semibold text-gray-900">
                {sortedAnnotations.filter(b => b.clinical_summary.has_therapeutic_implications).length}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters and Search */}
      <div className="card">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Search */}
          <div>
            <label className="label">Search Genes</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search by gene symbol..."
                className="input-field pl-10"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>

          {/* Database Selection */}
          <div>
            <label className="label">Databases</label>
            <div className="space-y-2">
              {['COSMIC', 'ClinVar', 'OncoKB'].map((db) => (
                <label key={db} className="flex items-center">
                  <input
                    type="checkbox"
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    checked={selectedDatabases.includes(db)}
                    onChange={() => handleDatabaseToggle(db)}
                  />
                  <span className="ml-2 text-sm text-gray-700">{db}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Relevance Filter */}
          <div>
            <label className="label">Relevance</label>
            <select
              className="input-field"
              value={filterByRelevance}
              onChange={(e) => setFilterByRelevance(e.target.value)}
            >
              <option value="all">All</option>
              <option value="high">High (≥0.5)</option>
              <option value="medium">Medium (0.2-0.5)</option>
              <option value="low">Low (0-0.2)</option>
            </select>
          </div>

          {/* Sort By */}
          <div>
            <label className="label">Sort By</label>
            <select
              className="input-field"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="relevance">Clinical Relevance</option>
              <option value="pvalue">P-value</option>
              <option value="foldchange">Fold Change</option>
            </select>
          </div>
        </div>
      </div>

      {/* Annotations Table */}
      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Gene
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Clinical Relevance
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  P-value
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Fold Change
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Clinical Summary
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {sortedAnnotations.map((biomarker) => (
                <tr key={biomarker.gene_symbol} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">
                      {biomarker.gene_symbol}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRelevanceColor(biomarker.clinical_summary.clinical_relevance_score)}`}>
                      {getRelevanceIcon(biomarker.clinical_summary.clinical_relevance_score)}
                      <span className="ml-1">
                        {(biomarker.clinical_summary.clinical_relevance_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {biomarker.p_value.toExponential(2)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {biomarker.fold_change.toFixed(2)}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    <div className="space-y-1">
                      {biomarker.clinical_summary.is_cancer_gene && (
                        <div className="flex items-center text-green-600">
                          <CheckCircle className="h-3 w-3 mr-1" />
                          <span className="text-xs">Cancer Gene</span>
                        </div>
                      )}
                      {biomarker.clinical_summary.has_pathogenic_variants && (
                        <div className="flex items-center text-red-600">
                          <AlertTriangle className="h-3 w-3 mr-1" />
                          <span className="text-xs">Pathogenic Variants</span>
                        </div>
                      )}
                      {biomarker.clinical_summary.has_therapeutic_implications && (
                        <div className="flex items-center text-blue-600">
                          <FlaskConical className="h-3 w-3 mr-1" />
                          <span className="text-xs">Therapeutic Target</span>
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <button className="text-primary-600 hover:text-primary-900 flex items-center">
                      <ExternalLink className="h-4 w-4 mr-1" />
                      View Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ClinicalAnnotation;
