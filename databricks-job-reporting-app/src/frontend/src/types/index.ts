export interface User {
  email: string;
  name?: string;
  source: string;
  authenticated: boolean;
}

export interface JobRun {
  workspace_id: string | null;
  job_id: string | null;
  run_id: string | null;
  job_name: string | null;
  start_time: string | null;
  end_time: string | null;
  duration_seconds: number | null;
  result_state: string | null;
  termination_code: string | null;
  trigger_type: string | null;
  run_type: string | null;
  run_as: string | null;
  creator_id: string | null;
  cost_usd?: number | null;
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
  job_id: string | null;
  job_name: string | null;
  total_runs: number | string;
  failed_runs: number | string;
  success_rate: number;
  run_as: string | null;
  last_run: string | null;
}

export interface ProlongedJob {
  job_id: string | null;
  job_name: string | null;
  run_id: string | null;
  running_minutes: number;
  avg_duration_minutes: number;
  duration_status: 'NORMAL' | 'WARNING' | 'CRITICAL' | 'ANOMALY';
}

export interface ClusterConfig {
  cluster_id: string | null;
  cluster_name?: string | null;
  cluster_type: string | null;
  warehouse_id?: string | null;
  run_type?: string | null;
  job_name?: string | null;
  driver_node_type?: string | null;
  worker_node_type?: string | null;
  min_workers?: number | null;
  max_workers?: number | null;
  fixed_workers?: number | null;
  dbr_version?: string | null;
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
