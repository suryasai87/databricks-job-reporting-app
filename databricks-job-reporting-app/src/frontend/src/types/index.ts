export interface User {
  email: string;
  name?: string;
  source: string;
  authenticated: boolean;
}

export interface JobRun {
  workspace_id: string;
  job_id: string;
  run_id: string;
  job_name: string;
  start_time: string;
  end_time: string | null;
  duration_seconds: number | null;
  result_state: string | null;
  termination_code: string | null;
  trigger_type: string;
  run_type: string;
  run_as: string;
  creator_id: string;
  cost_usd?: number;
}

export interface Job {
  job_id: string;
  workspace_id: string;
  name: string;
  description?: string;
  creator_id?: string;
  run_as?: string;
  tags?: Record<string, string>;
  is_active: boolean;
}

export interface RunSummary {
  total_runs: number;
  succeeded: number;
  failed: number;
  running: number;
  success_rate: number;
}

export interface CostSummary {
  total_cost_usd: number;
  total_dbus: number;
  unique_jobs: number;
  total_runs: number;
}

export interface FailedJob {
  job_id: string;
  job_name: string;
  total_runs: number;
  failed_runs: number;
  success_rate: number;
  run_as: string;
  last_run: string;
}

export interface ProlongedJob {
  job_id: string;
  job_name: string;
  run_id: string;
  running_minutes: number;
  avg_duration_minutes: number;
  duration_status: 'NORMAL' | 'WARNING' | 'CRITICAL' | 'ANOMALY';
}

export interface ClusterConfig {
  cluster_id: string;
  cluster_name: string;
  cluster_type: string;
  driver_node_type: string;
  worker_node_type: string;
  min_workers?: number;
  max_workers?: number;
  fixed_workers?: number;
  dbr_version: string;
}

export interface Overlap {
  job_a: string;
  job_b: string;
  run_a: string;
  run_b: string;
  overlap_minutes: number;
}

export interface Anomaly {
  job_id: string;
  job_name: string;
  run_id: string;
  metric_name: string;
  metric_value: number;
  expected_value: number;
  z_score: number;
  severity: 'WARNING' | 'CRITICAL';
}

export interface RetryStats {
  job_id: string;
  job_name: string;
  runs_with_retries: number;
  total_retries: number;
  retry_success_rate: number;
  avg_attempts_per_run: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isLoading?: boolean;
}

export interface GenieConversation {
  conversation_id: string;
  messages: ChatMessage[];
}
