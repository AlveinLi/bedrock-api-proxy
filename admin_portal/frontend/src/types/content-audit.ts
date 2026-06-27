export interface ContentAuditRecord {
  id: number;
  request_id?: string;
  api_key: string;
  user_id?: string;
  owner_name?: string;
  request_time: string;
  model?: string;
  resolved_model?: string;
  api_surface?: string;
  service_tier?: string;
  system_prompt?: string | null;
  request_messages?: string | null;
  tools?: string | null;
  response_content?: string | null;
  stop_reason?: string;
  streaming?: boolean;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
  cost: number;
  duration_ms?: number | null;
  success: boolean;
  error_message?: string | null;
  client_ip?: string | null;
  created_at?: string;
}

export interface ContentAuditListResponse {
  items: ContentAuditRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface ContentAuditInfo {
  total: number;
  earliest_request_time: string | null;
  days_since_earliest: number | null;
  timezone: string;
}

export interface ArchiveTask {
  task_id: number;
  archive_table_name: string | null;
  status: string;
}

export interface ArchiveHistoryRecord {
  id: number;
  archive_time: string;
  archive_table_name: string;
  record_count: number;
  data_start_time?: string | null;
  data_end_time?: string | null;
  duration_ms: number;
  status: string;
  keep_days?: number | null;
  cutoff_time?: string | null;
  error_message?: string | null;
}
