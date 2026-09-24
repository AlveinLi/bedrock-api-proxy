import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ContentAuditRecord } from '../../types';
import { formatUtcDisplay } from '../../utils';
import MarkdownView from './MarkdownView';

function prettyJson(value?: string | null): string {
  if (!value) return '';
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

/** Parse request_messages; return the array if it is a JSON array, else null. */
function parseMessageArray(value?: string | null): unknown[] | null {
  if (!value) return null;
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

/**
 * Full-content detail modal for a content audit record. Long fields are shown
 * in scrollable blocks; the response can be rendered as markdown.
 */
export default function AuditDetailModal({
  record,
  tz,
  onClose,
}: {
  record: ContentAuditRecord;
  tz: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [renderMarkdown, setRenderMarkdown] = useState(true);
  const [requestExpanded, setRequestExpanded] = useState(false);

  const requestArray = parseMessageArray(record.request_messages);
  const requestDisplay =
    requestArray && !requestExpanded
      ? JSON.stringify(requestArray.slice(-2), null, 2)
      : prettyJson(record.request_messages);

  const Section = ({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) => (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-300">{title}</h3>
        {action}
      </div>
      {children}
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-start justify-center p-4">
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose}></div>
        <div className="relative w-full max-w-4xl my-8 bg-surface-dark border border-border-dark rounded-xl shadow-2xl">
          <div className="flex items-center justify-between px-6 py-4 border-b border-border-dark sticky top-0 bg-surface-dark z-10">
            <h2 className="text-lg font-bold text-white">
              {t('contentAudit.detailTitle')}
            </h2>
            <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>

          <div className="p-6 flex flex-col gap-5 max-h-[75vh] overflow-y-auto">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
              <div><span className="text-slate-500">{t('contentAudit.owner')}: </span><span className="text-white">{record.owner_name || record.user_id || '-'}</span></div>
              <div><span className="text-slate-500">{t('contentAudit.requestTime')}: </span><span className="text-white">{formatUtcDisplay(record.request_time, tz)}</span></div>
              <div><span className="text-slate-500">{t('contentAudit.model')}: </span><span className="text-white">{record.model || '-'}</span></div>
              <div><span className="text-slate-500">{t('contentAudit.apiSurface')}: </span><span className="text-white">{record.api_surface || '-'}</span></div>
              <div><span className="text-slate-500">{t('contentAudit.serviceTier')}: </span><span className="text-white">{record.service_tier || '-'}</span></div>
              <div><span className="text-slate-500">{t('contentAudit.streaming')}: </span><span className="text-white">{record.streaming ? t('common.yes') : t('common.no')}</span></div>
              <div><span className="text-slate-500">{t('contentAudit.stopReason')}: </span><span className="text-white">{record.stop_reason || '-'}</span></div>
              <div><span className="text-slate-500">{t('contentAudit.cost')}: </span><span className="text-white">${(record.cost || 0).toFixed(6)}</span></div>
              <div><span className="text-slate-500">{t('contentAudit.duration')}: </span><span className="text-white">{record.duration_ms ?? '-'}</span></div>
              <div><span className="text-slate-500">{t('contentAudit.successField')}: </span><span className="text-white">{record.success ? t('common.yes') : t('common.no')}</span></div>
              <div><span className="text-slate-500">{t('contentAudit.clientIp')}: </span><span className="text-white">{record.client_ip || '-'}</span></div>
              <div className="col-span-2 md:col-span-3"><span className="text-slate-500">{t('contentAudit.tokensCombined')}: </span><span className="text-white">{record.input_tokens}/{record.output_tokens}/{record.cache_read_tokens}/{record.cache_write_tokens}/{record.reasoning_tokens}/{record.total_tokens}</span></div>
            </div>

            <Section
              title={t('contentAudit.requestMessages')}
              action={
                requestArray ? (
                  <button
                    onClick={() => setRequestExpanded((v) => !v)}
                    className="text-xs px-2 py-1 rounded border border-border-dark text-slate-300 hover:bg-border-dark whitespace-nowrap"
                  >
                    {requestExpanded ? t('contentAudit.viewSummary') : t('contentAudit.viewFull')}
                  </button>
                ) : undefined
              }
            >
              <pre className="text-xs bg-black/30 rounded-lg p-3 overflow-x-auto max-h-72 overflow-y-auto text-slate-300 whitespace-pre-wrap">{requestDisplay}</pre>
            </Section>

            <Section
              title={t('contentAudit.response')}
              action={
                <button
                  onClick={() => setRenderMarkdown((v) => !v)}
                  className="text-xs px-2 py-1 rounded border border-border-dark text-slate-300 hover:bg-border-dark whitespace-nowrap"
                >
                  {renderMarkdown ? t('contentAudit.viewRaw') : t('contentAudit.viewMarkdown')}
                </button>
              }
            >
              <div className="bg-black/30 rounded-lg p-3 max-h-96 overflow-y-auto">
                {record.response_content ? (
                  renderMarkdown ? (
                    <MarkdownView content={record.response_content} />
                  ) : (
                    <pre className="text-xs text-slate-300 whitespace-pre-wrap">{record.response_content}</pre>
                  )
                ) : (
                  <span className="text-xs text-slate-500">{t('contentAudit.emptyResponse')}</span>
                )}
              </div>
            </Section>

            {record.system_prompt && (
              <Section title={t('contentAudit.system')}>
                <pre className="text-xs bg-black/30 rounded-lg p-3 overflow-x-auto max-h-48 overflow-y-auto text-slate-300 whitespace-pre-wrap">{prettyJson(record.system_prompt)}</pre>
              </Section>
            )}

            {record.tools && (
              <Section title={t('contentAudit.tools')}>
                <pre className="text-xs bg-black/30 rounded-lg p-3 overflow-x-auto max-h-48 overflow-y-auto text-slate-300 whitespace-pre-wrap">{prettyJson(record.tools)}</pre>
              </Section>
            )}

            {record.error_message && (
              <Section title={t('common.error')}>
                <pre className="text-xs bg-red-950/30 border border-red-900/40 rounded-lg p-3 text-red-300 whitespace-pre-wrap">{record.error_message}</pre>
              </Section>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
