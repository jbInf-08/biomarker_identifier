import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { usePipeline } from '../contexts/PipelineContext';
import { useWebSocketContext } from '../contexts/WebSocketContext';
import { useNavigate } from 'react-router-dom';
import { 
  Upload, 
  X, 
  CheckCircle, 
  Settings,
  Play
} from 'lucide-react';
import toast from 'react-hot-toast';

const DataUpload = () => {
  const { startPipeline, loading } = usePipeline();
  const { connectToRun } = useWebSocketContext();
  const navigate = useNavigate();
  
  const [files, setFiles] = useState({
    expression: null,
    labels: null,
  });
  
  const [config, setConfig] = useState({
    runName: '',
    normalizationMethod: 'log2',
    statisticalTest: 'welch_t',
    alpha: 0.05,
    mlModels: ['logistic_regression', 'random_forest'],
  });

  const onDropExpression = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      setFiles(prev => ({ ...prev, expression: acceptedFiles[0] }));
      toast.success('Expression file uploaded successfully');
    }
  }, []);

  const onDropLabels = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      setFiles(prev => ({ ...prev, labels: acceptedFiles[0] }));
      toast.success('Labels file uploaded successfully');
    }
  }, []);

  const { getRootProps: getExpressionRootProps, getInputProps: getExpressionInputProps, isDragActive: isExpressionDragActive, open: openExpression } = useDropzone({
    onDrop: onDropExpression,
    accept: {
      'text/csv': ['.csv'],
      'text/tab-separated-values': ['.tsv'],
      'text/plain': ['.txt'],
    },
    multiple: false,
    noClick: true,
    noKeyboard: true,
  });

  const { getRootProps: getLabelsRootProps, getInputProps: getLabelsInputProps, isDragActive: isLabelsDragActive, open: openLabels } = useDropzone({
    onDrop: onDropLabels,
    accept: {
      'text/csv': ['.csv'],
      'text/tab-separated-values': ['.tsv'],
      'text/plain': ['.txt'],
    },
    multiple: false,
    noClick: true,
    noKeyboard: true,
  });

  const removeFile = (fileType) => {
    setFiles(prev => ({ ...prev, [fileType]: null }));
  };

  const handleConfigChange = (field, value) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!files.expression || !files.labels) {
      toast.error('Please upload both expression and labels files');
      return;
    }

    const formData = new FormData();
    formData.append('expression_file', files.expression);
    formData.append('labels_file', files.labels);
    formData.append('run_name', config.runName || `run_${Date.now()}`);
    formData.append('config', JSON.stringify({
      normalization_method: config.normalizationMethod,
      stats_methods: [config.statisticalTest],
      alpha: config.alpha,
      selection_methods: config.mlModels,
    }));

    const result = await startPipeline(formData);
    
    if (result.success) {
      // Connect to WebSocket updates for this run
      connectToRun(result.runId);
      navigate(`/monitoring`);
    }
  };

  const FileUploadArea = ({ fileType, getRootProps, getInputProps, isDragActive, file, onSelectClick }) => (
    <div
      {...getRootProps()}
      className={`
        border-2 border-dashed rounded-lg p-6 text-center transition-colors duration-200
        ${isDragActive 
          ? 'border-primary-400 bg-primary-50' 
          : file 
            ? 'border-green-400 bg-green-50' 
            : 'border-gray-300 hover:border-gray-400'
        }
      `}
    >
      <input {...getInputProps()} />
      {file ? (
        <div className="space-y-2">
          <CheckCircle className="h-8 w-8 text-green-500 mx-auto" />
          <p className="text-sm font-medium text-green-700">{file.name}</p>
          <p className="text-xs text-green-600">
            {(file.size / 1024 / 1024).toFixed(2)} MB
          </p>
          <div className="flex items-center justify-center gap-2">
            <button
              type="button"
              onClick={onSelectClick}
              className="text-sm text-primary-600 hover:text-primary-700 font-medium"
            >
              Change file
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                removeFile(fileType);
              }}
              className="text-red-500 hover:text-red-700"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <Upload className="h-8 w-8 text-gray-400 mx-auto" />
          <p className="text-sm font-medium text-gray-700">
            {isDragActive ? 'Drop the file here' : `Upload ${fileType} file`}
          </p>
          <p className="text-xs text-gray-500 mb-3">
            Drag and drop or
          </p>
          <button
            type="button"
            onClick={onSelectClick}
            className="btn-primary text-sm"
          >
            Browse files...
          </button>
        </div>
      )}
    </div>
  );

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Data Upload</h1>
        <p className="mt-2 text-gray-600">
          Upload your expression data and sample labels to start biomarker identification.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* File Upload Section */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Files</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="label">
                Expression Data File
                <span className="text-red-500 ml-1">*</span>
              </label>
              <FileUploadArea
                fileType="expression"
                getRootProps={getExpressionRootProps}
                getInputProps={getExpressionInputProps}
                isDragActive={isExpressionDragActive}
                file={files.expression}
                onSelectClick={openExpression}
              />
              <p className="mt-2 text-xs text-gray-500">
                Gene expression matrix with genes as rows and samples as columns
              </p>
            </div>

            <div>
              <label className="label">
                Sample Labels File
                <span className="text-red-500 ml-1">*</span>
              </label>
              <FileUploadArea
                fileType="labels"
                getRootProps={getLabelsRootProps}
                getInputProps={getLabelsInputProps}
                isDragActive={isLabelsDragActive}
                file={files.labels}
                onSelectClick={openLabels}
              />
              <p className="mt-2 text-xs text-gray-500">
                Sample labels with sample IDs and corresponding phenotypes
              </p>
            </div>
          </div>
        </div>

        {/* Configuration Section */}
        <div className="card">
          <div className="flex items-center mb-4">
            <Settings className="h-5 w-5 text-gray-500 mr-2" />
            <h2 className="text-lg font-semibold text-gray-900">Pipeline Configuration</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="label">Run Name</label>
              <input
                type="text"
                className="input-field"
                placeholder="Enter a name for this run"
                value={config.runName}
                onChange={(e) => handleConfigChange('runName', e.target.value)}
              />
            </div>

            <div>
              <label className="label">Normalization Method</label>
              <select
                className="input-field"
                value={config.normalizationMethod}
                onChange={(e) => handleConfigChange('normalizationMethod', e.target.value)}
              >
                <option value="log2">Log2</option>
                <option value="z_score">Z-score</option>
                <option value="quantile">Quantile</option>
                <option value="tmm">TMM</option>
              </select>
            </div>

            <div>
              <label className="label">Statistical Test</label>
              <select
                className="input-field"
                value={config.statisticalTest}
                onChange={(e) => handleConfigChange('statisticalTest', e.target.value)}
              >
                <option value="welch_t">Welch t-test</option>
                <option value="wilcoxon">Wilcoxon</option>
                <option value="anova">ANOVA</option>
              </select>
            </div>

            <div>
              <label className="label">Significance Level (α)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                className="input-field"
                value={config.alpha}
                onChange={(e) => handleConfigChange('alpha', parseFloat(e.target.value))}
              />
            </div>
          </div>

          <div className="mt-6">
            <label className="label">Machine Learning Models</label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { value: 'logistic_regression', label: 'Logistic Regression' },
                { value: 'random_forest', label: 'Random Forest' },
                { value: 'svm', label: 'SVM' },
                { value: 'xgboost', label: 'XGBoost' },
              ].map((model) => (
                <label key={model.value} className="flex items-center">
                  <input
                    type="checkbox"
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    checked={config.mlModels.includes(model.value)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        handleConfigChange('mlModels', [...config.mlModels, model.value]);
                      } else {
                        handleConfigChange('mlModels', config.mlModels.filter(m => m !== model.value));
                      }
                    }}
                  />
                  <span className="ml-2 text-sm text-gray-700">{model.label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading || !files.expression || !files.labels}
            className="btn-primary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>Starting Pipeline...</span>
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                <span>Start Biomarker Pipeline</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default DataUpload;
