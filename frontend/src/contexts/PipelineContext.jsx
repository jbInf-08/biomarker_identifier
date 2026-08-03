import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { apiClient } from '../services/api';
import toast from 'react-hot-toast';

const PipelineContext = createContext();

export const usePipeline = () => {
  const context = useContext(PipelineContext);
  if (!context) {
    throw new Error('usePipeline must be used within a PipelineProvider');
  }
  return context;
};

function isNetworkError(error) {
  return error?.code === 'ERR_NETWORK' || error?.message === 'Network Error' || !error?.response;
}

export const PipelineProvider = ({ children }) => {
  const [runs, setRuns] = useState([]);
  const [currentRun, setCurrentRun] = useState(null);
  const [loading, setLoading] = useState(false);
  const backendUnavailableToastShown = useRef(false);

  const normalizeRun = (run) => ({
    run_id: run.run_id || run.id,
    status: run.status,
    timestamp: run.timestamp || run.created_at,
    project_name: run.project_name,
    progress: run.progress,
    analysis_type: run.analysis_type,
  });

  const fetchRuns = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/biomarkers/runs');
      const rawRuns = Array.isArray(response.data) ? response.data : (response.data?.runs || []);
      setRuns(rawRuns.map(normalizeRun));
    } catch (error) {
      setRuns([]);
      if (isNetworkError(error)) {
        if (!backendUnavailableToastShown.current) {
          backendUnavailableToastShown.current = true;
          toast.error('Backend unavailable. Start the server or work offline.');
        }
      } else if (error?.response?.status === 401 || error?.response?.status === 403) {
        /* Auth required - show empty state, no toast spam */
      } else {
        console.error('Failed to fetch runs:', error);
        toast.error('Failed to fetch pipeline runs');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const startPipeline = async (formData) => {
    try {
      setLoading(true);
      const response = await apiClient.post('/biomarkers/run', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      const data = response.data;
      const newRun = normalizeRun({
        ...data,
        run_id: data.run_id,
        status: data.status || 'started',
        timestamp: new Date().toISOString(),
      });
      setRuns(prev => [newRun, ...prev]);
      setCurrentRun(newRun);
      
      toast.success('Pipeline started successfully');
      return { success: true, runId: data.run_id };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Failed to start pipeline';
      toast.error(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  };

  const getRunStatus = async (runId) => {
    try {
      const response = await apiClient.get(`/biomarkers/runs/${runId}/status`);
      return response.data;
    } catch (error) {
      console.error('Failed to get run status:', error);
      return null;
    }
  };

  const getRunResults = async (runId) => {
    try {
      const response = await apiClient.get(`/biomarkers/runs/${runId}/results`);
      return response.data;
    } catch (error) {
      console.error('Failed to get run results:', error);
      return null;
    }
  };

  const getBiomarkers = async (runId, topN = 50) => {
    try {
      const response = await apiClient.get(`/biomarkers/runs/${runId}/biomarkers?top_n=${topN}`);
      return response.data;
    } catch (error) {
      console.error('Failed to get biomarkers:', error);
      return null;
    }
  };

  const trainModel = async (runId, modelType, selectedFeatures, cvFolds = 5) => {
    try {
      const response = await apiClient.post(`/biomarkers/runs/${runId}/train-model`, {
        model_type: modelType,
        selected_features: selectedFeatures,
        cv_folds: cvFolds,
      });
      
      toast.success('Model training completed');
      return { success: true, data: response.data };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Model training failed';
      toast.error(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  const runSHAPAnalysis = async (runId, modelType, backgroundSamples = 100) => {
    try {
      const response = await apiClient.post(`/biomarkers/runs/${runId}/shap-analysis`, {
        model_type: modelType,
        background_samples: backgroundSamples,
      });
      
      toast.success('SHAP analysis completed');
      return { success: true, data: response.data };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'SHAP analysis failed';
      toast.error(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  const runPathwayAnalysis = async (runId, analysisType = 'both', geneSets = ['KEGG', 'REACTOME', 'GO_BP']) => {
    try {
      const response = await apiClient.post(`/biomarkers/runs/${runId}/pathway-analysis`, {
        analysis_type: analysisType,
        gene_sets: geneSets,
      });
      
      toast.success('Pathway analysis completed');
      return { success: true, data: response.data };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Pathway analysis failed';
      toast.error(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  const annotateBiomarkers = async (runId, databases = ['COSMIC', 'ClinVar', 'OncoKB'], topN = 50) => {
    try {
      const response = await apiClient.post(`/biomarkers/runs/${runId}/annotate`, {
        databases,
        top_n: topN,
      });
      
      toast.success('Biomarker annotation completed');
      return { success: true, data: response.data };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Biomarker annotation failed';
      toast.error(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  const generateReport = async (runId, reportFormat = 'html', reportTitle = null) => {
    try {
      const response = await apiClient.post(`/biomarkers/runs/${runId}/report`, {
        report_format: reportFormat,
        report_title: reportTitle,
      });
      
      toast.success('Report generated successfully');
      return { success: true, data: response.data };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Report generation failed';
      toast.error(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  const deleteRun = async (runId) => {
    try {
      await apiClient.delete(`/biomarkers/runs/${runId}`);
      setRuns(prev => prev.filter(run => run.run_id !== runId));
      if (currentRun?.run_id === runId) {
        setCurrentRun(null);
      }
      toast.success('Run deleted successfully');
      return { success: true };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Failed to delete run';
      toast.error(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  const value = {
    runs,
    currentRun,
    loading,
    fetchRuns,
    startPipeline,
    getRunStatus,
    getRunResults,
    getBiomarkers,
    trainModel,
    runSHAPAnalysis,
    runPathwayAnalysis,
    annotateBiomarkers,
    generateReport,
    deleteRun,
    setCurrentRun,
  };

  return (
    <PipelineContext.Provider value={value}>
      {children}
    </PipelineContext.Provider>
  );
};
