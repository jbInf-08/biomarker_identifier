import axios from 'axios';
import toast from 'react-hot-toast';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken');
    const tenantId = localStorage.getItem('tenantId');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (tenantId) {
      config.headers['X-Tenant-ID'] = tenantId;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    const status = error.response?.status;
    if (status === 401) {
      localStorage.removeItem('authToken');
      window.location.href = '/login';
    } else if (status === 429) {
      toast.error('Too many requests. Please wait and try again.');
    } else if (status >= 500) {
      toast.error('Server error. Try again in a moment.');
    }
    return Promise.reject(error);
  }
);

// API endpoints
export const api = {
  // Authentication
  auth: {
    login: (credentials) => apiClient.post('/auth/login', credentials),
    register: (userData) => apiClient.post('/auth/register', userData),
    me: () => apiClient.get('/auth/me'),
    updateProfile: (profileData) => apiClient.put('/auth/profile', profileData),
    logout: () => apiClient.post('/auth/logout'),
  },

  // Pipeline management
  pipeline: {
    getRuns: () => apiClient.get('/biomarkers/runs'),
    startPipeline: (formData) => apiClient.post('/biomarkers/run', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
    getRunStatus: (runId) => apiClient.get(`/biomarkers/runs/${runId}/status`),
    getRunResults: (runId) => apiClient.get(`/biomarkers/runs/${runId}/results`),
    deleteRun: (runId) => apiClient.delete(`/biomarkers/runs/${runId}`),
    getRunAnalyticsDashboard: (runId, topN = 150) =>
      apiClient.get(`/analysis/analytics/dashboard/${runId}?top_n=${topN}`),
  },

  // Biomarker analysis
  biomarkers: {
    getBiomarkers: (runId, topN = 50) => apiClient.get(`/biomarkers/runs/${runId}/biomarkers?top_n=${topN}`),
    getMetrics: (runId) => apiClient.get(`/biomarkers/runs/${runId}/metrics`),
  },

  // Machine learning
  ml: {
    trainModel: (runId, modelData) => apiClient.post(`/biomarkers/runs/${runId}/train-model`, modelData),
    runSHAPAnalysis: (runId, shapData) => apiClient.post(`/biomarkers/runs/${runId}/shap-analysis`, shapData),
    /** Multipart: testData, testLabels, trainedModel files + modelId query */
    evaluateModel: (modelId, testData, testLabels, trainedModel) => {
      const form = new FormData();
      form.append('test_data', testData);
      form.append('test_labels', testLabels);
      form.append('trained_model', trainedModel);
      return apiClient.post(
        `/analysis/ml/model-evaluation?model_id=${encodeURIComponent(modelId)}`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
    },
  },

  // Pathway analysis
  pathways: {
    runAnalysis: (runId, pathwayData) => apiClient.post(`/biomarkers/runs/${runId}/pathway-analysis`, pathwayData),
    networkAnalysis: (geneListFile, confidenceThreshold = 0.7) => {
      const form = new FormData();
      form.append('gene_list', geneListFile);
      return apiClient.post(
        `/analysis/pathway/network-analysis?network_type=ppi&confidence_threshold=${confidenceThreshold}`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
    },
  },

  // Annotation
  annotation: {
    annotateBiomarkers: (runId, annotationData) => apiClient.post(`/biomarkers/runs/${runId}/annotate`, annotationData),
  },

  // Reports
  reports: {
    generate: (runId, reportData) => apiClient.post(`/biomarkers/runs/${runId}/report`, reportData),
    download: (runId, format = 'html') => apiClient.get(`/biomarkers/runs/${runId}/download-report?format=${format}`, {
      responseType: 'blob'
    }),
  },

  // Clinical databases
  clinical: {
    cosmic: {
      getMutations: (params) => apiClient.get('/clinical/cosmic/mutations', { params }),
      getCancerGenes: () => apiClient.get('/clinical/cosmic/cancer-genes'),
    },
    clinvar: {
      getVariants: (params) => apiClient.get('/clinical/clinvar/variants', { params }),
    },
    oncokb: {
      getGenes: () => apiClient.get('/clinical/oncokb/genes'),
      getDrugs: () => apiClient.get('/clinical/oncokb/drugs'),
    },
  },

  // Integrations (webhooks)
  integrations: {
    listWebhooks: () => apiClient.get('/v1/integrations/webhooks'),
    createWebhook: (body) => apiClient.post('/v1/integrations/webhooks', body),
    deleteWebhook: (id) => apiClient.delete(`/v1/integrations/webhooks/${id}`),
    testWebhook: (id) => apiClient.post(`/v1/integrations/webhooks/${id}/test`),
  },

  // Collaborative research
  research: {
    listProjects: () => apiClient.get('/v1/research/projects'),
    createProject: (body) => apiClient.post('/v1/research/projects', body),
    addMember: (projectId, body) =>
      apiClient.post(`/v1/research/projects/${projectId}/members`, body),
  },

  // Public dataset links (GEO, dbGaP, FDA)
  publicData: {
    geoSeries: (accession) => apiClient.get(`/v1/public-data/geo/series/${accession}`),
    dbgapStudy: (studyId) => apiClient.get(`/v1/public-data/dbgap/study/${studyId}`),
    openfdaSearch: (params) => apiClient.get('/v1/public-data/fda/openfda/search', { params }),
  },

  // Admin: compliance checklist (see docs/COMPLIANCE_CHECKLIST_WORKFLOW.md)
  admin: {
    compliance: {
      listChecklistItems: (params = {}) =>
        apiClient.get('/v1/admin/compliance/checklist-items', { params }),
      createChecklistItem: (body) =>
        apiClient.post('/v1/admin/compliance/checklist-items', body),
      patchChecklistItem: (itemId, body) =>
        apiClient.patch(`/v1/admin/compliance/checklist-items/${itemId}`, body),
    },
  },
};

export default apiClient;
