import { useTranslation } from 'react-i18next';
import type { ContentAuditRecord } from '../../types';
import { formatUtcDisplay } from '../../utils';

function truncate(value: string | null | undefined, max = 80): string {
  if (!value) return '';
  const oneLine = value.replace(/\s+/g, ' ').trim();
  return oneLine.length > max ? `${oneLine.slice(0, max)}…` : oneLine;
}

/** Presentational table of content audit records with an expand action. */
export default function AuditTable({
  items,
  tz,
  isLoading,
  onSelect,
}: {
  items: ContentAuditRecord[];
  tz: string;
  isLoading?: boolean;
  onSelect: (record: ContentAuditRecord) => void;
}) {
  const { t } = useTranslation();

  return (
    <div className="overflow-hidden rounded-xl border border-border-dark bg-surface-dark shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead className="bg-[#151b28] border-b border-border-dark">
            <tr>
              <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{t('contentAudit.requestTime')}</th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{t('contentAudit.owner')}</th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{t('contentAudit.model')}</th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{t('contentAudit.response')}</th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">{t('contentAudit.totalTokens')}</th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">{t('common.actions')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-dark">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center">
                  <span className="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span>
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-slate-400">{t('contentAudit.noRecords')}</td>
              </tr>
            ) : (
              items.map((r) => (
                <tr key={r.id} className="hover:bg-[#1e2536] transition-colors">
                  <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-300">{formatUtcDisplay(r.request_time, tz)}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-white">{r.owner_name || r.user_id || '-'}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-300">{r.model || '-'}</td>
                  <td className="px-4 py-3 text-xs text-slate-400 max-w-md">{truncate(r.response_content)}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-xs text-white">{(r.total_tokens || 0).toLocaleString()}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-right">
                    <button
                      onClick={() => onSelect(r)}
                      className="p-2 text-slate-400 hover:text-primary hover:bg-border-dark rounded-lg transition-colors"
                      title={t('contentAudit.expand')}
                    >
                      <span className="material-symbols-outlined text-[20px]">open_in_full</span>
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
