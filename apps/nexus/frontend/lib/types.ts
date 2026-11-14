export type Role = "admin" | "read_only";

export interface User {
  id: number;
  email: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface AuthMe {
  user: User;
  csrf_token: string;
  expires_at: string;
}

export interface Source {
  id: number;
  slug: string;
  name: string;
  url: string;
  source_type: string;
  enabled: boolean;
  is_discovery: boolean;
  trust_level: string;
  tags: string[];
  refresh_interval_minutes: number;
  notes: string | null;
  last_attempted_at: string | null;
  last_success_at: string | null;
  last_http_status: number | null;
  etag: string | null;
  last_modified: string | null;
  config_count: number;
  new_config_count: number;
  duplicate_count: number;
  invalid_count: number;
  consecutive_failures: number;
  last_error: string | null;
  last_duration_ms: number | null;
}

export interface SourceDetail {
  source: Source;
  fetches: Array<{
    id: number;
    status: string;
    started_at: string;
    finished_at: string | null;
    http_status: number | null;
    bytes_read: number;
    parsed_count: number;
    accepted_count: number;
    duplicate_count: number;
    invalid_count: number;
    duration_ms: number | null;
    error: string | null;
    invalid_samples: Array<Record<string, string>>;
    metadata: Record<string, unknown>;
  }>;
  contribution: { configurations: number; occurrences: number; duplicates_within_latest_fetch: number };
}

export interface ConfigurationRow {
  id: number;
  fingerprint: string;
  protocol: string;
  host: string;
  port: number;
  transport: string;
  security: string;
  sni: string | null;
  credential_hint: string;
  validation_status: string;
  connectivity_status: string;
  last_tested_at: string | null;
  last_latency_ms: number | null;
  latency_avg_ms: number | null;
  test_agent: string | null;
  first_seen_at: string;
  last_seen_at: string;
  source_count: number;
  failure_count: number;
  tags: string[];
  notes: string | null;
  is_favorite: boolean;
  sources: Array<{ id: number; name: string; slug: string }>;
}

export interface ConfigurationDetail extends ConfigurationRow {
  latency_samples: number[];
  canonical_endpoint: string;
  source_links: Array<{
    source_id: number;
    name: string;
    slug: string;
    first_seen_at: string;
    last_seen_at: string;
    occurrences: number;
  }>;
}

export interface Paginated<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface OverviewKpis {
  unique_configurations: number;
  total_configurations: number;
  active_sources: number;
  sources_with_errors: number;
  tested_configurations: number;
  reachable_configurations: number;
  verified_working_configurations: number;
  verification_available: boolean;
  verification_note: string;
  failing_configurations: number;
  average_measured_latency_ms: number | null;
  last_successful_update: string | null;
  last_pipeline_run: {
    id: number;
    status: string;
    started_at: string;
    finished_at: string | null;
    published: boolean;
    accepted: number;
    new: number;
  } | null;
}

export interface DashboardSummary {
  period_days: number;
  overview: {
    generated_at: string;
    kpis: OverviewKpis;
    protocol_distribution: Array<{ protocol: string; count: number; share: number }>;
    health_distribution: Record<string, number>;
    sources: Array<{
      id: number;
      name: string;
      enabled: boolean;
      last_success_at: string | null;
      last_error: string | null;
      config_count: number;
    }>;
  };
  growth: Array<{ date: string; added: number; cumulative: number }>;
  source_contribution: Array<{
    source_id: number;
    name: string;
    configurations: number;
    occurrences: number;
    share: number;
  }>;
  latency_trend: Array<{ date: string; avg_latency_ms: number | null; samples: number }>;
  pipeline_activity: Array<{ date: string; runs: number; accepted: number; new: number }>;
  heatmap: { weeks: number; cells: Array<{ date: string; added: number; tests: number; runs: number; intensity: number }>; max_added: number };
  health: HealthSummary;
  automation: AutomationSummary;
  scheduler: SchedulerStatus;
  publication: { provider: string; directory: string; statement: string };
  latest_events: Array<{
    id: number;
    trigger: string;
    status: string;
    started_at: string;
    finished_at: string | null;
    accepted: number;
    new: number;
    invalid: number;
    published: boolean;
    publish_skipped_reason: string | null;
    error: string | null;
    sources_ok: number;
    sources_failed: number;
  }>;
  recent_source_errors: Array<{
    id: number;
    name: string;
    last_error: string | null;
    consecutive_failures: number;
    last_attempted_at: string | null;
  }>;
  recent_fetches: Array<{
    source: string;
    status: string;
    started_at: string;
    duration_ms: number | null;
    http_status: number | null;
    accepted: number;
  }>;
  upstream: UpstreamStatus;
}

export interface HealthSummary {
  queue: {
    active_workers: number;
    queued: number;
    running: number;
    concurrency_limit: number;
    max_batch: number;
  };
  total_jobs: number;
  last_test_at: string | null;
  breakdown: Array<{
    status: string;
    stage: string;
    category: string | null;
    count: number;
    avg_latency_ms: number | null;
  }>;
  agent: { label: string; region: string; tcp_enabled: boolean; concurrency: number; timeout_seconds: number };
  stages_implemented: string[];
  stages_unavailable: string[];
}

export interface AutomationSummary {
  runs: Array<PipelineRunRow>;
  next_expected_run: string | null;
  next_expected_note: string;
  error_sources: Array<{ id: number; name: string; consecutive_failures: number; last_error: string | null }>;
  profiles: number;
  enabled_sources: number;
  pipeline_in_flight?: boolean;
  scheduler?: SchedulerStatus;
}

export interface PipelineRunRow {
  id: number;
  trigger: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  sources_total: number;
  sources_ok: number;
  sources_failed: number;
  parsed?: number;
  accepted: number;
  new: number;
  invalid: number;
  published: boolean;
  publish_skipped_reason: string | null;
  error: string | null;
  details?: Record<string, unknown>;
}

export interface SchedulerStatus {
  embedded: boolean;
  enabled: boolean;
  running: boolean;
  interval_minutes: number;
  jitter_seconds: number;
  last_attempt_at: string | null;
  next_run_at: string | null;
  last_error: string | null;
  runs_started: number;
}

export interface UpstreamStatus {
  available: boolean;
  source: string;
  repo: string;
  branch: string;
  schedule_cron: string;
  schedule_note: string;
  next_expected_workflow_run: string;
  fetched_at: string;
  updated_at_utc?: string;
  total?: number;
  warning?: string | null;
  error: string | null;
  sources?: Array<{ source: string; status: string; parsed?: number; added?: number; detail?: string }>;
}

export interface SubscriptionProfile {
  id: number;
  name: string;
  description: string | null;
  filters: {
    protocols?: string[];
    connectivity?: string[];
    transports?: string[];
    source_ids?: number[];
    search?: string | null;
  };
  max_configs: number;
  sort: string;
  export_format: string;
  favorites_only: boolean;
  exclude_ids: number[];
  last_generated_at: string | null;
  last_config_count: number | null;
  created_at: string;
  updated_at: string;
  tokens: Array<{
    id: number;
    token_prefix: string;
    label: string | null;
    created_at: string;
    expires_at: string | null;
    revoked_at: string | null;
    last_used_at: string | null;
    use_count: number;
  }>;
}

export interface HealthJob {
  id: number;
  status: string;
  requested_at: string;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  completed: number;
  reachable: number;
  failed: number;
  stages: string[];
  concurrency: number;
  agent_label: string;
  agent_region: string;
  error: string | null;
}

export interface AuditEntry {
  id: number;
  actor: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  outcome: string;
  ip_address: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface CloudflareStatus {
  configured: boolean;
  enabled_by_flag: boolean;
  account_id_present: boolean;
  token_present: boolean;
  status: string;
  message: string;
  capabilities: Record<string, boolean>;
  planned_capabilities: string[];
  considerations: string[];
  deployments: Array<Record<string, unknown>>;
  research: Record<string, string>;
  quota_reference: string;
}
