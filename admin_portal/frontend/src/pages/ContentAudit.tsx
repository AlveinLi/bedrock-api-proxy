import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useContentAudit } from '../hooks';
import { contentAuditApi } from '../services/api';
import { getDefaultTimezone, hoursAgoLocalInput, nowLocalInput } from '../utils';
import type { ContentAuditRecord } from '../types';
import AuditTable from '../components/audit/AuditTable';
import AuditDetailModal from '../components/audit/AuditDetailModal';
import TimezoneSelect from '../components/audit/TimezoneSelect';

export default function ContentAudit() {
  const { t } = useTranslation();
  const [tz, setTz] = useState(getDefaultTimezone());
  const [userOrOwner, setUserOrOwner] = useState('');
  const [start, setStart] = useState(hoursAgoLocalInput(24));
  const [end, setEnd] = useState(nowLocalInput());
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [selected, setSelected] = useState<ContentAuditRecord | null>(null);
  const [exporting, setExporting] = useState(false);

  // Applied filters (only update on "search" to avoid spamming)
  const [applied, setApplied] = useState({ user_or_owner: '', start: start, end: end });

  const { data, isLoading, error } = useContentAudit({
    user_or_owner: applied.user_or_owner || undefined,
    start: applied.start || undefined,
    end: applied.end || undefined,
    tz,
    page,
    page_size: pageSize,
  });

  const handleSearch = () => {
    setPage(1);
    setApplied({ user_or_owner: userOrOwner, start, end });
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      await contentAuditApi.exportMarkdown({
        user_or_owner: applied.user_or_owner || undefined,
        start: applied.start || undefined,
        end: applied.end || undefined,
        tz,
        limit: 1000,
      });
    } finally {
      setExporting(false);
    }
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-bold text-white tracking-tight">{t('contentAudit.title')}</h1>
          <p className="text-slate-400">{t('contentAudit.subtitle')}</p>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="flex items-center gap-2 h-10 px-4 rounded-lg bg-surface-dark border border-border-dark text-white text-sm font-medium hover:bg-border-dark transition-colors disabled:opacity-50"
        >
          <span className="material-symbols-outlined text-[20px]">file_download</span>
          {t('contentAudit.exportMarkdown')}
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-4 bg-surface-dark border border-border-dark rounded-xl p-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">{t('contentAudit.userOrOwner')}</label>
          <input
            type="text"
            value={userOrOwner}
            onChange={(e) => setUserOrOwner(e.target.value)}
            placeholder={t('contentAudit.userOrOwnerPlaceholder')}
            className="px-3 py-2 bg-input-bg border border-border-dark rounded-lg text-white text-sm focus:border-primary focus:ring-1 focus:ring-primary"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">{t('usageStats.start')}</label>
          <input
            type="datetime-local"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="px-3 py-2 bg-input-bg border border-border-dark rounded-lg text-white text-sm focus:border-primary focus:ring-1 focus:ring-primary"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">{t('usageStats.end')}</label>
          <input
            type="datetime-local"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="px-3 py-2 bg-input-bg border border-border-dark rounded-lg text-white text-sm focus:border-primary focus:ring-1 focus:ring-primary"
          />
        </div>
        <TimezoneSelect value={tz} onChange={setTz} />
        <button
          onClick={handleSearch}
          className="h-10 px-4 rounded-lg bg-primary text-white text-sm font-bold hover:bg-primary/90 transition-colors"
        >
          {t('common.search')}
        </button>
      </div>

      {error && (
        <div className="text-red-400 text-sm bg-red-950/30 border border-red-900/40 rounded-lg p-3">
          {(error as Error).message}
        </div>
      )}

      <AuditTable items={data?.items || []} tz={tz} isLoading={isLoading} onSelect={setSelected} />

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-400">
          {t('common.showing')} {data?.items.length || 0} / {data?.total || 0}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1 text-sm text-slate-300 border border-border-dark rounded-lg disabled:opacity-40 hover:bg-border-dark"
          >
            {t('common.previous')}
          </button>
          <span className="text-sm text-slate-400">{page} / {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="px-3 py-1 text-sm text-slate-300 border border-border-dark rounded-lg disabled:opacity-40 hover:bg-border-dark"
          >
            {t('common.next')}
          </button>
        </div>
      </div>

      {selected && (
        <AuditDetailModal record={selected} tz={tz} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
