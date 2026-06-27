import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { contentAuditApi, contentAuditHistoryApi } from '../services/api';

export function useContentAudit(params: {
  api_key?: string;
  user_id?: string;
  start?: string;
  end?: string;
  tz?: string;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: ['contentAudit', params],
    queryFn: () => contentAuditApi.list(params),
  });
}

export function useContentAuditInfo(tz?: string) {
  return useQuery({
    queryKey: ['contentAuditInfo', tz],
    queryFn: () => contentAuditHistoryApi.info(tz),
  });
}

export function useArchiveHistory(params: { start: string; end: string; tz?: string; enabled?: boolean }) {
  const { enabled = true, ...query } = params;
  return useQuery({
    queryKey: ['archiveHistory', query],
    queryFn: () => contentAuditHistoryApi.history(query),
    enabled,
  });
}

export function useStartArchive() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ keepDays, tz }: { keepDays: number; tz?: string }) =>
      contentAuditHistoryApi.archive(keepDays, tz),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contentAuditInfo'] });
      queryClient.invalidateQueries({ queryKey: ['archiveHistory'] });
    },
  });
}

export function useArchiveStatus(taskId: number | null) {
  return useQuery({
    queryKey: ['archiveStatus', taskId],
    queryFn: () => contentAuditHistoryApi.status(taskId as number),
    enabled: taskId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' ? 2000 : false;
    },
  });
}

export function useArchiveRecords(
  table: string,
  params: {
    api_key?: string;
    user_id?: string;
    start?: string;
    end?: string;
    tz?: string;
    page?: number;
    page_size?: number;
  },
  enabled = true
) {
  return useQuery({
    queryKey: ['archiveRecords', table, params],
    queryFn: () => contentAuditHistoryApi.archiveRecords(table, params),
    enabled: enabled && !!table,
  });
}
