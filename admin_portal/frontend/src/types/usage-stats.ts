export interface UsageStatsRow {
  api_key: string;
  owner: string;
  user_id?: string;
  // Aggregated metrics (summed over the window)
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  total_tokens: number;
  requests: number;
  total_cost: number;
  // Per-user configuration attributes (not summed)
  daily_token_limit: number;
  monthly_budget: number;
  service_tier: string;
}

export interface UsageStatsWindow {
  mode: 'range' | 'day';
  tz: string;
  start?: string;
  end?: string;
  day?: string;
}

export interface UsageStatsResponse {
  window: UsageStatsWindow;
  items: UsageStatsRow[];
  count: number;
}
