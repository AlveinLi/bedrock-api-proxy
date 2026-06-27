import { useQuery } from '@tanstack/react-query';
import { usageStatsApi } from '../services/api';

export function useUsageStats(params: {
  group?: 'range' | 'day';
  start?: string;
  end?: string;
  day?: string;
  tz?: string;
  include_empty?: boolean;
  enabled?: boolean;
}) {
  const { enabled = true, ...query } = params;
  return useQuery({
    queryKey: ['usageStats', query],
    queryFn: () => usageStatsApi.get(query),
    enabled,
  });
}
