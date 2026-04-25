import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { usePipeline } from '../contexts/PipelineContext';
import { api } from '../services/api';
import { useTranslation } from 'react-i18next';
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Cell
} from 'recharts';
import { 
  Upload, 
  Activity, 
  BarChart3, 
  FileText,
  TrendingUp,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle
} from 'lucide-react';

const Dashboard = () => {
  const { runs, fetchRuns, loading } = usePipeline();
  const { t } = useTranslation();
  const [analytics, setAnalytics] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  const stats = useMemo(() => {
    if (!runs || runs.length === 0) {
      return {
        totalRuns: 0,
        completedRuns: 0,
        runningRuns: 0,
        failedRuns: 0,
      };
    }
    return {
      totalRuns: runs.length,
      completedRuns: runs.filter(run => run.status === 'completed').length,
      runningRuns: runs.filter(run => run.status === 'running').length,
      failedRuns: runs.filter(run => run.status === 'failed').length,
    };
  }, [runs]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  useEffect(() => {
    const completedRun = (runs || []).find(r => r.status === 'completed');
    if (!completedRun) {
      setAnalytics(null);
      return;
    }
    const runId = completedRun.run_id || completedRun.id;
    if (!runId) return;
    setAnalyticsLoading(true);
    api.pipeline
      .getRunAnalyticsDashboard(runId, 200)
      .then((res) => setAnalytics(res.data))
      .catch(() => setAnalytics(null))
      .finally(() => setAnalyticsLoading(false));
  }, [runs]);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'running':
        return <Clock className="h-5 w-5 text-blue-500" />;
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

  const quickActions = [
    {
      name: 'Upload Data',
      description: 'Start a new biomarker analysis',
      href: '/upload',
      icon: Upload,
      color: 'bg-primary-500 hover:bg-primary-600',
    },
    {
      name: 'Monitor Pipelines',
      description: 'Track running analyses',
      href: '/monitoring',
      icon: Activity,
      color: 'bg-green-500 hover:bg-green-600',
    },
    {
      name: 'View Results',
      description: 'Explore analysis results',
      href: '/results',
      icon: BarChart3,
      color: 'bg-blue-500 hover:bg-blue-600',
    },
    {
      name: 'Generate Reports',
      description: 'Create analysis reports',
      href: '/reports',
      icon: FileText,
      color: 'bg-purple-500 hover:bg-purple-600',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">{t('dashboard.title')}</h1>
        <p className="mt-2 text-gray-600">
          {t('dashboard.subtitle')}
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <TrendingUp className="h-8 w-8 text-primary-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Runs</p>
              <p className="text-2xl font-semibold text-gray-900">{stats.totalRuns}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <CheckCircle className="h-8 w-8 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Completed</p>
              <p className="text-2xl font-semibold text-gray-900">{stats.completedRuns}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Clock className="h-8 w-8 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Running</p>
              <p className="text-2xl font-semibold text-gray-900">{stats.runningRuns}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <XCircle className="h-8 w-8 text-red-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Failed</p>
              <p className="text-2xl font-semibold text-gray-900">{stats.failedRuns}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {quickActions.map((action) => {
            const Icon = action.icon;
            return (
              <Link
                key={action.name}
                to={action.href}
                className="card hover:shadow-md transition-shadow duration-200"
              >
                <div className="flex items-center">
                  <div className={`flex-shrink-0 p-3 rounded-lg ${action.color} text-white`}>
                    <Icon className="h-6 w-6" />
                  </div>
                  <div className="ml-4">
                    <h3 className="text-sm font-medium text-gray-900">{action.name}</h3>
                    <p className="text-sm text-gray-500">{action.description}</p>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Recent Runs */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">Recent Runs</h2>
          <Link
            to="/monitoring"
            className="text-sm text-primary-600 hover:text-primary-700 font-medium"
          >
            View all
          </Link>
        </div>

        {loading ? (
          <div className="card">
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            </div>
          </div>
        ) : runs.length === 0 ? (
          <div className="card">
            <div className="text-center py-8">
              <Activity className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No runs yet</h3>
              <p className="text-gray-500 mb-4">Start your first biomarker analysis by uploading data.</p>
              <Link
                to="/upload"
                className="btn-primary"
              >
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
                      Started
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {runs.slice(0, 5).map((run) => (
                    <tr key={run.run_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">
                          {run.run_id}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          {getStatusIcon(run.status)}
                          <span className={`ml-2 inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(run.status)}`}>
                            {run.status}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(run.timestamp).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <Link
                          to={`/results/${run.run_id}`}
                          className="text-primary-600 hover:text-primary-900"
                        >
                          View Results
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Analytics Dashboard + pseudo-3D view */}
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Analytics Dashboard</h2>
        {analyticsLoading ? (
          <div className="card">
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            </div>
          </div>
        ) : !analytics ? (
          <div className="card">
            <p className="text-gray-500">
              Run a completed analysis to unlock dashboard and 3D biomarker view.
            </p>
          </div>
        ) : (
          <div className="card space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div><p className="text-xs text-gray-500">Run</p><p className="font-semibold">{analytics.run_id}</p></div>
              <div><p className="text-xs text-gray-500">Points</p><p className="font-semibold">{analytics.summary?.total_points}</p></div>
              <div><p className="text-xs text-gray-500">Significant</p><p className="font-semibold text-green-700">{analytics.summary?.significant_points}</p></div>
              <div><p className="text-xs text-gray-500">Median |log2FC|</p><p className="font-semibold">{Number(analytics.summary?.median_abs_log2_fc || 0).toFixed(2)}</p></div>
            </div>
            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 20, right: 20, left: 10, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="x" name="log2 fold change" />
                  <YAxis dataKey="y" name="-log10(p)" />
                  <Tooltip
                    formatter={(value, name) =>
                      [typeof value === 'number' ? value.toFixed(3) : value, name]
                    }
                    labelFormatter={(_, payload) => payload?.[0]?.payload?.name || 'Gene'}
                  />
                  <Scatter data={analytics.three_d_points || []} name="Biomarkers">
                    {(analytics.three_d_points || []).map((point, idx) => (
                      <Cell
                        key={`pt-${idx}`}
                        fill={point.z > 0.65 ? '#7c3aed' : point.z > 0.35 ? '#2563eb' : '#9ca3af'}
                      />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <p className="text-xs text-gray-500">
              3D depth cue: marker color intensity reflects z-score (combined significance + feature importance).
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
