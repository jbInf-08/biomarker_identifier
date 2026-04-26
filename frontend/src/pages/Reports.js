import React, { useState, useEffect } from 'react';
import { usePipeline } from '../contexts/PipelineContext';
import { api } from '../services/api';
import { 
  FileText, 
  Download, 
  Eye, 
  User,
  Building,
  Settings,
  CheckCircle,
  Clock,
  XCircle
} from 'lucide-react';
import toast from 'react-hot-toast';

const Reports = () => {
  const { runs, fetchRuns, generateReport } = usePipeline();
  const [selectedRun, setSelectedRun] = useState('');
  const [reportConfig, setReportConfig] = useState({
    format: 'html',
    title: '',
    projectName: '',
    investigator: '',
    institution: '',
  });
  const [generating, setGenerating] = useState(false);
  const [generatedReports, setGeneratedReports] = useState([]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const handleConfigChange = (field, value) => {
    setReportConfig(prev => ({ ...prev, [field]: value }));
  };

  const handleGenerateReport = async () => {
    if (!selectedRun) {
      toast.error('Please select a run to generate a report for');
      return;
    }

    setGenerating(true);
    try {
      const result = await generateReport(
        selectedRun,
        reportConfig.format,
        reportConfig.title || `Biomarker Report - ${selectedRun}`
      );

      if (result.success) {
        const newReport = {
          id: Date.now(),
          runId: selectedRun,
          title: reportConfig.title || `Biomarker Report - ${selectedRun}`,
          format: reportConfig.format,
          status: 'completed',
          generatedAt: new Date().toISOString(),
          path: result.data.report_path,
        };
        
        setGeneratedReports(prev => [newReport, ...prev]);
        toast.success('Report generated successfully');
      }
    } catch (error) {
      toast.error('Failed to generate report');
    } finally {
      setGenerating(false);
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'generating':
        return <Clock className="h-5 w-5 text-blue-500 animate-pulse" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      default:
        return <Clock className="h-5 w-5 text-gray-500" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'generating':
        return 'bg-blue-100 text-blue-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const completedRuns = runs?.filter(run => run.status === 'completed') || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Reports</h1>
        <p className="mt-2 text-gray-600">
          Generate comprehensive reports for your biomarker analysis results.
        </p>
      </div>

      {/* Report Generation */}
      <div className="card">
        <div className="flex items-center mb-6">
          <Settings className="h-5 w-5 text-gray-500 mr-2" />
          <h2 className="text-lg font-semibold text-gray-900">Generate New Report</h2>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Run Selection */}
          <div>
            <label className="label">Select Run</label>
            <select
              className="input-field"
              value={selectedRun}
              onChange={(e) => setSelectedRun(e.target.value)}
            >
              <option value="">Choose a completed run...</option>
              {completedRuns.map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.run_id} - {new Date(run.timestamp).toLocaleDateString()}
                </option>
              ))}
            </select>
            {completedRuns.length === 0 && (
              <p className="mt-2 text-sm text-gray-500">
                No completed runs available. Complete an analysis first.
              </p>
            )}
          </div>

          {/* Report Format */}
          <div>
            <label className="label">Report Format</label>
            <select
              className="input-field"
              value={reportConfig.format}
              onChange={(e) => handleConfigChange('format', e.target.value)}
            >
              <option value="html">HTML</option>
              <option value="pdf">PDF</option>
            </select>
          </div>

          {/* Report Title */}
          <div>
            <label className="label">Report Title</label>
            <input
              type="text"
              className="input-field"
              placeholder="Enter report title"
              value={reportConfig.title}
              onChange={(e) => handleConfigChange('title', e.target.value)}
            />
          </div>

          {/* Project Name */}
          <div>
            <label className="label">Project Name</label>
            <input
              type="text"
              className="input-field"
              placeholder="Enter project name"
              value={reportConfig.projectName}
              onChange={(e) => handleConfigChange('projectName', e.target.value)}
            />
          </div>

          {/* Investigator */}
          <div>
            <label className="label">Investigator</label>
            <input
              type="text"
              className="input-field"
              placeholder="Enter investigator name"
              value={reportConfig.investigator}
              onChange={(e) => handleConfigChange('investigator', e.target.value)}
            />
          </div>

          {/* Institution */}
          <div>
            <label className="label">Institution</label>
            <input
              type="text"
              className="input-field"
              placeholder="Enter institution name"
              value={reportConfig.institution}
              onChange={(e) => handleConfigChange('institution', e.target.value)}
            />
          </div>
        </div>

        {/* Generate Button */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={handleGenerateReport}
            disabled={!selectedRun || generating}
            className="btn-primary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generating ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>Generating...</span>
              </>
            ) : (
              <>
                <FileText className="h-4 w-4" />
                <span>Generate Report</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Generated Reports */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center">
            <FileText className="h-5 w-5 text-gray-500 mr-2" />
            <h2 className="text-lg font-semibold text-gray-900">Generated Reports</h2>
          </div>
          <button
            onClick={() => setGeneratedReports([])}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Clear History
          </button>
        </div>

        {generatedReports.length === 0 ? (
          <div className="text-center py-8">
            <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No reports generated</h3>
            <p className="text-gray-500">Generate your first report using the form above.</p>
          </div>
        ) : (
          <div className="overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Report
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Run ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Format
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Generated
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {generatedReports.map((report) => (
                  <tr key={report.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {report.title}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {report.runId}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800">
                        {report.format.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        {getStatusIcon(report.status)}
                        <span className={`ml-2 inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(report.status)}`}>
                          {report.status}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(report.generatedAt).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                      {report.status === 'completed' && (
                        <>
                          <button
                            onClick={async () => {
                              try {
                                const { data } = await api.reports.download(report.runId, report.format);
                                const url = URL.createObjectURL(new Blob([data]));
                                window.open(url, '_blank');
                                setTimeout(() => URL.revokeObjectURL(url), 1000);
                              } catch (e) {
                                toast.error('Failed to view report');
                              }
                            }}
                            className="text-primary-600 hover:text-primary-900 flex items-center"
                          >
                            <Eye className="h-4 w-4 mr-1" />
                            View
                          </button>
                          <button
                            onClick={async () => {
                              try {
                                const { data } = await api.reports.download(report.runId, report.format);
                                const url = URL.createObjectURL(new Blob([data]));
                                const a = document.createElement('a');
                                a.href = url;
                                a.download = `report_${report.runId}.${report.format}`;
                                a.click();
                                URL.revokeObjectURL(url);
                                toast.success('Report downloaded');
                              } catch (e) {
                                toast.error('Download failed');
                              }
                            }}
                            className="text-green-600 hover:text-green-900 flex items-center"
                          >
                            <Download className="h-4 w-4 mr-1" />
                            Download
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Report Templates */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Report Templates</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors">
            <div className="flex items-center mb-2">
              <FileText className="h-5 w-5 text-primary-600 mr-2" />
              <h3 className="font-medium text-gray-900">Standard Report</h3>
            </div>
            <p className="text-sm text-gray-600 mb-3">
              Comprehensive biomarker analysis report with visualizations and statistics.
            </p>
            <button className="text-sm text-primary-600 hover:text-primary-700">
              Use Template
            </button>
          </div>

          <div className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors">
            <div className="flex items-center mb-2">
              <User className="h-5 w-5 text-primary-600 mr-2" />
              <h3 className="font-medium text-gray-900">Clinical Report</h3>
            </div>
            <p className="text-sm text-gray-600 mb-3">
              Clinical-focused report with therapeutic implications and drug targets.
            </p>
            <button className="text-sm text-primary-600 hover:text-primary-700">
              Use Template
            </button>
          </div>

          <div className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors">
            <div className="flex items-center mb-2">
              <Building className="h-5 w-5 text-primary-600 mr-2" />
              <h3 className="font-medium text-gray-900">Publication Report</h3>
            </div>
            <p className="text-sm text-gray-600 mb-3">
              Publication-ready report with detailed methodology and supplementary data.
            </p>
            <button className="text-sm text-primary-600 hover:text-primary-700">
              Use Template
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Reports;
