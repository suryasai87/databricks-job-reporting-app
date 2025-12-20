import axios from 'axios';
import type {
  User,
  JobRun,
  RunSummary,
  CostSummary,
  FailedJob,
  ProlongedJob,
  ClusterConfig,
  Overlap,
  Anomaly,
  RetryStats,
  MatrixData,
  ExecutorMetricsResponse,
  CloudMetricsResponse,
  OtelMetricsResponse,
  MetricsSummaryResponse,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Auth endpoints
export const getAuthStatus = async (): Promise<User> => {
  const response = await api.get('/auth/status');
  return response.data;
};

export const getUserProfile = async (): Promise<User> => {
  const response = await api.get('/user/profile');
  return response.data;
};

// Jobs endpoints
export const getJobRuns = async (days: number = 7, limit: number = 1000): Promise<JobRun[]> => {
  const response = await api.get('/jobs/runs', { params: { days, limit } });
  return response.data;
};

export const getRunSummary = async (days: number = 7): Promise<RunSummary> => {
  const response = await api.get('/jobs/summary', { params: { days } });
  return response.data;
};

export const getJobRunsByType = async (days: number = 7): Promise<Record<string, number>> => {
  const response = await api.get('/jobs/by-type', { params: { days } });
  return response.data;
};

export const getDailyRuns = async (days: number = 30): Promise<any[]> => {
  const response = await api.get('/jobs/daily', { params: { days } });
  return response.data;
};

// Matrix View endpoint
export const getJobsMatrix = async (days: number = 7, runsPerJob: number = 20): Promise<MatrixData> => {
  const response = await api.get('/jobs/matrix', { params: { days, runs_per_job: runsPerJob } });
  return response.data;
};

// Cost endpoints
export const getCostSummary = async (days: number = 30): Promise<CostSummary> => {
  const response = await api.get('/costs/summary', { params: { days } });
  return response.data;
};

export const getDailyCosts = async (days: number = 30): Promise<any[]> => {
  const response = await api.get('/costs/daily', { params: { days } });
  return response.data;
};

export const getTopExpensiveJobs = async (days: number = 30, limit: number = 10): Promise<any[]> => {
  const response = await api.get('/costs/top-jobs', { params: { days, limit } });
  return response.data;
};

export const getCostByIdentity = async (days: number = 30): Promise<any[]> => {
  const response = await api.get('/costs/by-identity', { params: { days } });
  return response.data;
};

// Health endpoints
export const getFailedJobs = async (days: number = 7): Promise<FailedJob[]> => {
  const response = await api.get('/health/failed-jobs', { params: { days } });
  return response.data;
};

export const getProlongedJobs = async (
  warningMinutes: number = 60,
  criticalMinutes: number = 180
): Promise<ProlongedJob[]> => {
  const response = await api.get('/health/prolonged-jobs', {
    params: { warning_minutes: warningMinutes, critical_minutes: criticalMinutes },
  });
  return response.data;
};

export const getAnomalies = async (
  days: number = 7,
  warningThreshold: number = 2.0,
  criticalThreshold: number = 3.0
): Promise<Anomaly[]> => {
  const response = await api.get('/health/anomalies', {
    params: { days, warning_threshold: warningThreshold, critical_threshold: criticalThreshold },
  });
  return response.data;
};

export const getRetryStats = async (days: number = 7): Promise<RetryStats[]> => {
  const response = await api.get('/health/retry-stats', { params: { days } });
  return response.data;
};

// Cluster endpoints
export const getClusterConfigs = async (jobId?: string, runId?: string): Promise<ClusterConfig[]> => {
  const response = await api.get('/clusters/configs', { params: { job_id: jobId, run_id: runId } });
  return response.data;
};

// Overlap analysis
export const getOverlaps = async (days: number = 7): Promise<Overlap[]> => {
  const response = await api.get('/analysis/overlaps', { params: { days } });
  return response.data;
};

export const getConcurrentJobsOverTime = async (hours: number = 24): Promise<any[]> => {
  const response = await api.get('/analysis/concurrent', { params: { hours } });
  return response.data;
};

// AI Assistant (Genie) endpoints
export const startGenieConversation = async (spaceId: string): Promise<string> => {
  const response = await api.post('/genie/conversations', { space_id: spaceId });
  return response.data.conversation_id;
};

export const sendGenieMessage = async (
  spaceId: string,
  conversationId: string,
  message: string
): Promise<string> => {
  const response = await api.post(`/genie/conversations/${conversationId}/messages`, {
    space_id: spaceId,
    message,
  });
  return response.data.response;
};

export const getGenieSpaces = async (): Promise<any[]> => {
  const response = await api.get('/genie/spaces');
  return response.data;
};

// Reports
export const generateReport = async (
  reportType: string,
  startDate: string,
  endDate: string
): Promise<any> => {
  const response = await api.post('/reports/generate', {
    report_type: reportType,
    start_date: startDate,
    end_date: endDate,
  });
  return response.data;
};

// Metrics endpoints - 3-Tier Architecture

// Tier 1: Executor Metrics (Always Available)
export const getExecutorMetrics = async (): Promise<ExecutorMetricsResponse> => {
  const response = await api.get('/metrics/executors');
  return response.data;
};

// Tier 2: Cloud Metrics (If Configured)
export const getCloudMetrics = async (): Promise<CloudMetricsResponse> => {
  const response = await api.get('/metrics/cloud');
  return response.data;
};

// Tier 3: OTEL Metrics Status
export const getOtelStatus = async (): Promise<OtelMetricsResponse> => {
  const response = await api.get('/metrics/otel/status');
  return response.data;
};

// Summary Metrics (Best Available)
export const getMetricsSummary = async (): Promise<MetricsSummaryResponse> => {
  const response = await api.get('/metrics/summary');
  return response.data;
};

export default api;
