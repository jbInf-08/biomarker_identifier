import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { usePipeline } from '../contexts/PipelineContext';
import { useWebSocketContext } from '../contexts/WebSocketContext';
import { 
  Activity, 
  Clock, 
  CheckCircle, 
  XCircle, 
  AlertCircle,
  RefreshCw,
  Trash2,
  Eye,
  Wifi,
  WifiOff
} from 'lucide-react';
import toast from 'react-hot-toast';

const PipelineMonitoring = () => {
  const { runs, fetchRuns, getRunStatus, deleteRun, loading } = usePipeline();
  const { 
    isConnected, 
    progressUpdates, 
    getRunProgress, 
    connectToRun
  } = useWebSocketContext();
  const [runStatuses, setRunStatuses] = useState({});
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  // Connect to WebSocket updates for running runs
  useEffect(() => {
    if (runs && isConnected) {
      const runningRuns = runs.filter(run => (run.status === 'running' || run.status === 'started'));
      runningRuns.forEach(run => {
        connectToRun(run.run_id);
      });
    }
  }, [runs, isConnected, connectToRun]);

  // Update run statuses from WebSocket progress updates
  useEffect(() => {
    if (Object.keys(progressUpdates).length === 0) return;
    
    const updates = {};
    Object.entries(progressUpdates).forEach(([runId, progress]) => {
      updates[runId] = {
        status: progress.status,
        progress: progress.progress,
        message: progress.message,
        timestamp: progress.timestamp
      };
      if (progress.status === 'completed') {
        toast.success(`Analysis ${runId} completed successfully!`);
      } else if (progress.status === 'failed') {
        toast.error(`Analysis ${runId} failed: ${progress.message || 'Unknown error'}`);
      }
    });
    setRunStatuses(prev => ({ ...prev, ...updates }));
  }, [progressUpdates]);

  const refreshStatuses = async () => {
    if (!runs || runs.length === 0) return;

    const runningRuns = runs.filter(run => run.status === 'running');
    if (runningRuns.length === 0) return;

    setRefreshing(true);
    try {
      const statusPromises = runningRuns.map(async (run) => {
        const status = await getRunStatus(run.run_id);
        return { runId: run.run_id, status };
      });

      const statuses = await Promise.all(statusPromises);
      const statusMap = {};
      statuses.forEach(({ runId, status }) => {
        if (status) {
          statusMap[runId] = {
            ...status,
            progress_percent: status.progress_percent ?? (status.progress != null ? Math.round(status.progress * 100) : undefined),
          };
        }
      });

      setRunStatuses(prev => ({ ...prev, ...statusMap }));
    } catch (error) {
      console.error('Failed to refresh statuses:', error);
    } finally {
      setRefreshing(false);
    }
  };

  const handleRefresh = async () => {
    await fetchRuns();
    await refreshStatuses();
    toast.success('Status refreshed');
  };

  const handleDeleteRun = async (runId) => {
    if (window.confirm('Are you sure you want to delete this run? This action cannot be undone.')) {
      const result = await deleteRun(runId);
      if (result.success) {
        setRunStatuses(prev => {
          const newStatuses = { ...prev };
          delete newStatuses[runId];
          return newStatuses;
        });
      }
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'running':
        return <Clock className="h-5 w-5 text-blue-500 animate-pulse" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      default:
        return <AlertCircle className="h-5 w-5 text-yellow-500" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'running':
        return 'bg-blue-100 text-blue-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-yellow-100 text-yellow-800';
    }
  };

  const getProgressPercentage = (run) => {
    if (run.progress_percent != null && !Number.isNaN(Number(run.progress_percent))) {
      return Math.min(100, Math.max(0, Number(run.progress_percent)));
    }
    if (run.progress != null && run.progress <= 1 && run.progress >= 0) {
      return Math.round(run.progress * 100);
    }
    // Check if we have real-time progress data from WebSocket
    const realTimeProgress = getRunProgress(run.run_id);
    if (realTimeProgress && realTimeProgress.progress !== undefined) {
      const p = realTimeProgress.progress;
      return p <= 1 ? p * 100 : p;
    }
    
    // Fallback to estimated progress
    if (run.status === 'completed') return 100;
    if (run.status === 'failed') return 0;
    if (run.status === 'running') {
      // Estimate progress based on time elapsed (rough approximation)
      const startTime = new Date(run.timestamp);
      const now = new Date();
      const elapsed = now - startTime;
      const estimatedDuration = 10 * 60 * 1000; // 10 minutes estimated
      return Math.min(90, (elapsed / estimatedDuration) * 100);
    }
    return 0;
  };

  const formatDuration = (startTime) => {
    const now = new Date();
    const elapsed = now - new Date(startTime);
    const minutes = Math.floor(elapsed / 60000);
    const seconds = Math.floor((elapsed % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-3xl font-bold text-gray-900">Pipeline Monitoring</h1>
            <div className="flex items-center space-x-2">
              {isConnected ? (
                <div className="flex items-center space-x-1 text-green-600">
                  <Wifi className="h-4 w-4" />
                  <span className="text-sm font-medium">Live Updates</span>
                </div>
              ) : (
                <div className="flex items-center space-x-1 text-red-600">
                  <WifiOff className="h-4 w-4" />
                  <span className="text-sm font-medium">Offline</span>
                </div>
              )}
            </div>
          </div>
          <p className="mt-2 text-gray-600">
            Monitor the status of your biomarker identification pipelines.
            {isConnected ? ' Real-time updates enabled.' : ' Using polling for updates.'}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="btn-secondary flex items-center space-x-2"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card">
          <div className="flex items-center">
            <Activity className="h-8 w-8 text-primary-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Runs</p>
              <p className="text-2xl font-semibold text-gray-900">{runs?.length || 0}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <CheckCircle className="h-8 w-8 text-green-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Completed</p>
              <p className="text-2xl font-semibold text-gray-900">
                {runs?.filter(run => run.status === 'completed').length || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <Clock className="h-8 w-8 text-blue-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Running</p>
              <p className="text-2xl font-semibold text-gray-900">
                {runs?.filter(run => run.status === 'running').length || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <XCircle className="h-8 w-8 text-red-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Failed</p>
              <p className="text-2xl font-semibold text-gray-900">
                {runs?.filter(run => run.status === 'failed').length || 0}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Runs List */}
      {loading ? (
        <div className="card">
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          </div>
        </div>
      ) : runs?.length === 0 ? (
        <div className="card">
          <div className="text-center py-8">
            <Activity className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No pipeline runs</h3>
            <p className="text-gray-500 mb-4">Start your first biomarker analysis by uploading data.</p>
            <Link to="/upload" className="btn-primary">
              Upload Data
            </Link>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Run ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Progress
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Duration
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Started
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {runs.map((run) => {
                  const currentStatus = runStatuses[run.run_id] || run;
                  const progress = getProgressPercentage(currentStatus);
                  
                  return (
                    <tr key={run.run_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">
                          {run.run_id}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          {getStatusIcon(currentStatus.status)}
                          <span className={`ml-2 inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(currentStatus.status)}`}>
                            {currentStatus.status}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full transition-all duration-300 ${
                              currentStatus.status === 'completed' 
                                ? 'bg-green-500' 
                                : currentStatus.status === 'failed'
                                ? 'bg-red-500'
                                : 'bg-blue-500'
                            }`}
                            style={{ width: `${progress}%` }}
                          ></div>
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {Math.round(progress)}%
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {currentStatus.status === 'running' ? formatDuration(run.timestamp) : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(run.timestamp).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                        <Link
                          to={`/results/${run.run_id}`}
                          className="text-primary-600 hover:text-primary-900 flex items-center"
                        >
                          <Eye className="h-4 w-4 mr-1" />
                          View
                        </Link>
                        {currentStatus.status === 'completed' && (
                          <button
                            onClick={() => handleDeleteRun(run.run_id)}
                            className="text-red-600 hover:text-red-900 flex items-center"
                          >
                            <Trash2 className="h-4 w-4 mr-1" />
                            Delete
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default PipelineMonitoring;
