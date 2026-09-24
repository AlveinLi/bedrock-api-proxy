import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  useContentAuditInfo,
  useArchiveHistory,
  useStartArchive,
  useArchiveStatus,
  useArchiveRecords,
} from '../hooks';
import { contentAuditHistoryApi } from '../services/api';
import { getDefaultTimezone, formatUtcDisplay, hoursAgoLocalInput, nowLocalInput } from '../utils';
import type { ContentAuditRecord } from '../types';
import AuditTable from '../components/audit/AuditTable';
import AuditDetailModal from '../components/audit/AuditDetailModal';
import TimezoneSelect from '../components/audit/TimezoneSelect';

export default function ContentAuditHistory() {
  const { t } = useTranslation();
  const [tz, setTz] = useState(getDefaultTimezone());
  const [keepDays, setKeepDays] = useState<number>(30);
  const [taskId, setTaskId] = useState<number | null>(null);

  // History filter (by archived data window)
  const [histStart, setHistStart] = useState(hoursAgoLocalInput(24 * 90));
  const [histEnd, setHistEnd] = useState(nowLocalInput());
  const [appliedHist, setAppliedHist] = useState({ start: histStart, end: histEnd });

  // Selected archive table viewer
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [archivePage, setArchivePage] = useState(1);
  const [selectedRecord, setSelectedRecord] = useState<ContentAuditRecord | null>(null);

  const { data: info } = useContentAuditInfo(tz);
  const startArchive = useStartArchive();
  const { data: status } = useArchiveStatus(taskId);
  const { data: history, isLoading: historyLoading } = useArchiveHistory({
    start: appliedHist.start,
    end: appliedHist.end,
    tz,
  });
  const { data: archiveData, isLoading: archiveLoading } = useArchiveRecords(
    selectedTable || '',
    { tz, page: archivePage, page_size: 20 },
    !!selectedTable
  );

  const handleArchive = async () => {
    if (!Number.isInteger(keepDays) || keepDays <= 0) {
      alert(t('contentAuditHistory.invalidDays'));
      return;
    }
    if (!confirm(t('contentAuditHistory.confirmArchive', { days: keepDays }))) return;
    const task = await startArchive.mutateAsync({ keepDays, tz });
    setTaskId(task.task_id);
  };

  const handleExportArchive = async () => {
    if (!selectedTable) return;
    await contentAuditHistoryApi.exportArchiveMarkdown(selectedTable, { tz, limit: 1000 });
  };

  const archiveTotalPages = archiveData
    ? Math.max(1, Math.ceil(archiveData.total / archiveData.page_size))
    : 1;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold text-white tracking-tight">{t('contentAuditHistory.title')}</h1>
        <p className="text-slate-400">{t('contentAuditHistory.subtitle')}</p>
      </div>

      {/* Info + archive action */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-surface-dark border border-border-dark rounded-xl p-4 flex flex-col gap-1">
          <span className="text-xs text-slate-400">{t('contentAuditHistory.currentRows')}</span>
          <span className="text-2xl font-bold text-white">{(info?.total || 0).toLocaleString()}</span>
        </div>
        <div className="bg-surface-dark border border-border-dark rounded-xl p-4 flex flex-col gap-1">
          <span className="text-xs text-slate-400">{t('contentAuditHistory.earliestDate')}</span>
          <span className="text-lg font-bold text-white">{info?.earliest_request_time || '—'}</span>
          {info?.days_since_earliest != null && (
            <span className="text-xs text-slate-500">{t('contentAuditHistory.daysSpan', { days: info.days_since_earliest })}</span>
          )}
        </div>
        <div className="bg-surface-dark border border-border-dark rounded-xl p-4 flex flex-col gap-2">
          <label className="text-xs text-slate-400">{t('contentAuditHistory.keepDays')}</label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={1}
              value={keepDays}
              onChange={(e) => setKeepDays(parseInt(e.target.value) || 0)}
              className="w-24 px-3 py-2 bg-input-bg border border-border-dark rounded-lg text-white text-sm focus:border-primary focus:ring-1 focus:ring-primary"
            />
            <button
              onClick={handleArchive}
              disabled={startArchive.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-white text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[20px]">archive</span>
              {t('contentAuditHistory.archiveButton')}
            </button>
          </div>
          {status && (
            <span className={`text-xs ${status.status === 'failed' ? 'text-red-400' : status.status === 'done' ? 'text-emerald-400' : 'text-amber-400'}`}>
              {t('contentAuditHistory.taskStatus')}: {status.status}
              {status.status === 'done' && ` (${status.record_count} ${t('contentAuditHistory.rowsArchived')})`}
              {status.status === 'failed' && status.error_message ? ` - ${status.error_message}` : ''}
            </span>
          )}
        </div>
      </div>

      <TimezoneSelect value={tz} onChange={setTz} />

      {/* Archive history filter */}
      <div className="flex flex-wrap items-end gap-4 bg-surface-dark border border-border-dark rounded-xl p-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">{t('contentAuditHistory.dataStart')}</label>
          <input
            type="datetime-local"
            value={histStart}
            onChange={(e) => setHistStart(e.target.value)}
            className="px-3 py-2 bg-input-bg border border-border-dark rounded-lg text-white text-sm focus:border-primary focus:ring-1 focus:ring-primary"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">{t('contentAuditHistory.dataEnd')}</label>
          <input
            type="datetime-local"
            value={histEnd}
            onChange={(e) => setHistEnd(e.target.value)}
            className="px-3 py-2 bg-input-bg border border-border-dark rounded-lg text-white text-sm focus:border-primary focus:ring-1 focus:ring-primary"
          />
        </div>
        <button
          onClick={() => setAppliedHist({ start: histStart, end: histEnd })}
          className="h-10 px-4 rounded-lg bg-primary text-white text-sm font-bold hover:bg-primary/90 transition-colors"
        >
          {t('common.search')}
        </button>
      </div>

      {/* Archive history table */}
      <div className="overflow-hidden rounded-xl border border-border-dark bg-surface-dark shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-[#151b28] border-b border-border-dark">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{t('contentAuditHistory.archiveTime')}</th>
                <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{t('contentAuditHistory.archiveTable')}</th>
                <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">{t('contentAuditHistory.rows')}</th>
                <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{t('contentAuditHistory.dataWindow')}</th>
                <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{t('common.status')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-dark">
              {historyLoading ? (
                <tr><td colSpan={5} className="px-6 py-12 text-center"><span className="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span></td></tr>
              ) : (history?.items.length || 0) === 0 ? (
                <tr><td colSpan={5} className="px-6 py-12 text-center text-slate-400">{t('contentAuditHistory.noArchives')}</td></tr>
              ) : (
                history?.items.map((h) => (
                  <tr key={h.id} className="hover:bg-[#1e2536] transition-colors">
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-300">{formatUtcDisplay(h.archive_time, tz)}</td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <button
                        onClick={() => { setSelectedTable(h.archive_table_name); setArchivePage(1); }}
                        className="text-sm text-primary hover:underline font-mono"
                        disabled={h.status !== 'done'}
                      >
                        {h.archive_table_name}
                      </button>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right text-xs text-white">{(h.record_count || 0).toLocaleString()}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-400">
                      {h.data_start_time ? formatUtcDisplay(h.data_start_time, tz) : '—'}
                      {' → '}
                      {h.data_end_time ? formatUtcDisplay(h.data_end_time, tz) : '—'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs">
                      <span className={h.status === 'failed' ? 'text-red-400' : h.status === 'done' ? 'text-emerald-400' : 'text-amber-400'}>
                        {h.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Selected archive table records */}
      {selectedTable && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white">
              {t('contentAuditHistory.viewingArchive')}: <span className="font-mono text-primary">{selectedTable}</span>
            </h2>
            <div className="flex gap-2">
              <button
                onClick={handleExportArchive}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-dark border border-border-dark text-white text-sm hover:bg-border-dark"
              >
                <span className="material-symbols-outlined text-[18px]">file_download</span>
                {t('contentAudit.exportMarkdown')}
              </button>
              <button
                onClick={() => setSelectedTable(null)}
                className="px-3 py-2 rounded-lg bg-surface-dark border border-border-dark text-slate-300 text-sm hover:bg-border-dark"
              >
                {t('common.close')}
              </button>
            </div>
          </div>
          <AuditTable items={archiveData?.items || []} tz={tz} isLoading={archiveLoading} onSelect={setSelectedRecord} />
          <div className="flex items-center justify-end gap-2">
            <button
              onClick={() => setArchivePage((p) => Math.max(1, p - 1))}
              disabled={archivePage <= 1}
              className="px-3 py-1 text-sm text-slate-300 border border-border-dark rounded-lg disabled:opacity-40 hover:bg-border-dark"
            >
              {t('common.previous')}
            </button>
            <span className="text-sm text-slate-400">{archivePage} / {archiveTotalPages}</span>
            <button
              onClick={() => setArchivePage((p) => Math.min(archiveTotalPages, p + 1))}
              disabled={archivePage >= archiveTotalPages}
              className="px-3 py-1 text-sm text-slate-300 border border-border-dark rounded-lg disabled:opacity-40 hover:bg-border-dark"
            >
              {t('common.next')}
            </button>
          </div>
        </div>
      )}

      {selectedRecord && (
        <AuditDetailModal record={selectedRecord} tz={tz} onClose={() => setSelectedRecord(null)} />
      )}
    </div>
  );
}
