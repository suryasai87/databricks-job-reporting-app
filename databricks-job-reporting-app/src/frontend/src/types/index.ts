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

// Matrix View Types
export interface MatrixRunCell {
  run_id: string | null;
  result_state: string | null;
  start_time: string | null;
  end_time: string | null;
  duration_seconds: number | null;
}

export interface MatrixJobRow {
  job_id: string | null;
  job_name: string | null;
  runs: (MatrixRunCell | null)[];
}

export interface MatrixData {
  jobs: MatrixJobRow[];
  days: number;
  runs_per_job: number;
}

// Metrics Types - 3-Tier Architecture

// Tier 1: Executor Metrics (Always Available)
export interface ExecutorMetric {
  executor_id: string;
  host: string;
  memory_used_mb: number;
  memory_max_mb: number;
  memory_usage_percent: number;
  gc_time_ms: number;
  shuffle_read_bytes: number;
  shuffle_write_bytes: number;
  active_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  total_duration_ms: number;
}

export interface ExecutorMetricsResponse {
  available: boolean;
  timestamp: string;
  executors: ExecutorMetric[];
  summary: {
    total_executors: number;
    total_memory_used_mb: number;
    total_memory_max_mb: number;
    avg_memory_usage_percent: number;
    total_gc_time_ms: number;
    total_shuffle_read_bytes: number;
    total_shuffle_write_bytes: number;
    total_active_tasks: number;
    total_completed_tasks: number;
    total_failed_tasks: number;
  };
}

// Tier 2: Cloud Metrics (If Configured)
export interface CloudMetric {
  instance_id: string;
  instance_type: string;
  cpu_usage_percent: number;
  memory_usage_percent: number;
  disk_read_bytes_per_sec: number;
  disk_write_bytes_per_sec: number;
  network_in_bytes_per_sec: number;
  network_out_bytes_per_sec: number;
  timestamp: string;
}

export interface CloudMetricsResponse {
  available: boolean;
  configured: boolean;
  provider?: string;
  message?: string;
  timestamp?: string;
  metrics?: CloudMetric[];
  summary?: {
    avg_cpu_percent: number;
    avg_memory_percent: number;
    total_disk_read_bytes_per_sec: number;
    total_disk_write_bytes_per_sec: number;
    total_network_in_bytes_per_sec: number;
    total_network_out_bytes_per_sec: number;
  };
}

// Tier 3: OTEL Metrics (Setup Instructions or Data)
export interface OtelMetric {
  name: string;
  value: number;
  unit: string;
  labels: Record<string, string>;
  timestamp: string;
}

export interface OtelMetricsResponse {
  available: boolean;
  configured: boolean;
  message?: string;
  endpoint?: string;
  init_script?: string;
  metrics?: OtelMetric[];
  dashboards?: {
    name: string;
    url: string;
  }[];
}

// Summary Metrics (Best Available)
export interface MetricsSummaryResponse {
  source: 'executor' | 'cloud' | 'otel';
  source_label: string;
  available_tiers: {
    executor: boolean;
    cloud: boolean;
    otel: boolean;
  };
  metrics: {
    cpu_usage_percent?: number;
    memory_usage_percent?: number;
    disk_io_bytes_per_sec?: number;
    network_io_bytes_per_sec?: number;
    gc_time_ms?: number;
    shuffle_io_bytes?: number;
    active_tasks?: number;
    completed_tasks?: number;
    failed_tasks?: number;
  };
  timestamp: string;
}
