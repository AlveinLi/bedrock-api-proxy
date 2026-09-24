import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useUsageStats } from '../hooks';
import { formatTokens, getDefaultTimezone, todayInTz, shiftDay, hoursAgoLocalInput, nowLocalInput } from '../utils';
import TimezoneSelect from '../components/audit/TimezoneSelect';

export default function UsageStats() {
  const { t } = useTranslation();
  const [tz, setTz] = useState(getDefaultTimezone());
  const [mode, setMode] = useState<'range' | 'day'>('range');
  const [start, setStart] = useState(hoursAgoLocalInput(24));
  const [end, setEnd] = useState(nowLocalInput());
  const [day, setDay] = useState(todayInTz(getDefaultTimezone()));
  const [includeEmpty, setIncludeEmpty] = useState(false);

  const query =
    mode === 'day'
      ? { group: 'day' as const, day, tz, include_empty: includeEmpty }
      : { group: 'range' as const, start, end, tz, include_empty: includeEmpty };

  const { data, isLoading, error } = useUsageStats(query);

  const totals = (data?.items || []).reduce(
    (acc, r) => {
      acc.input += r.input_tokens;
      acc.output += r.output_tokens;
      acc.cacheRead += r.cache_read_tokens;
      acc.cacheWrite += r.cache_write_tokens;
      acc.total += r.total_tokens;
      acc.requests += r.requests;
      acc.cost += r.total_cost;
      return acc;
    },
    { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0, requests: 0, cost: 0 }
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold text-white tracking-tight">{t('usageStats.title')}</h1>
        <p className="text-slate-400">{t('usageStats.subtitle')}</p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-4 bg-surface-dark border border-border-dark rounded-xl p-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">{t('usageStats.mode')}</label>
          <div className="flex rounded-lg overflow-hidden border border-border-dark">
            <button
              onClick={() => setMode('range')}
              className={`px-3 py-2 text-sm ${mode === 'range' ? 'bg-primary text-white' : 'bg-transparent text-slate-300'}`}
            >
              {t('usageStats.rangeMode')}
            </button>
            <button
              onClick={() => setMode('day')}
              className={`px-3 py-2 text-sm ${mode === 'day' ? 'bg-primary text-white' : 'bg-transparent text-slate-300'}`}
            >
              {t('usageStats.dayMode')}
            </button>
          </div>
        </div>

        {mode === 'range' ? (
          <>
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
          </>
        ) : (
          <div className="flex items-end gap-2">
            <button
              onClick={() => setDay((d) => shiftDay(d, -1))}
              className="px-3 py-2 rounded-lg bg-surface-dark border border-border-dark text-slate-300 hover:bg-border-dark"
              title={t('usageStats.prevDay')}
            >
              <span className="material-symbols-outlined text-[20px]">chevron_left</span>
            </button>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-400">{t('usageStats.day')}</label>
              <input
                type="date"
                value={day}
                onChange={(e) => setDay(e.target.value)}
                className="px-3 py-2 bg-input-bg border border-border-dark rounded-lg text-white text-sm focus:border-primary focus:ring-1 focus:ring-primary"
              />
            </div>
            <button
              onClick={() => setDay((d) => shiftDay(d, 1))}
              className="px-3 py-2 rounded-lg bg-surface-dark border border-border-dark text-slate-300 hover:bg-border-dark"
              title={t('usageStats.nextDay')}
            >
              <span className="material-symbols-outlined text-[20px]">chevron_right</span>
            </button>
          </div>
        )}

        <TimezoneSelect value={tz} onChange={setTz} />

        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={includeEmpty}
            onChange={(e) => setIncludeEmpty(e.target.checked)}
            className="rounded border-border-dark bg-input-bg"
          />
          {t('usageStats.includeEmpty')}
        </label>
      </div>

      {error && (
        <div className="text-red-400 text-sm bg-red-950/30 border border-red-900/40 rounded-lg p-3">
          {(error as Error).message}
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard label={t('usageStats.totalTokens')} value={formatTokens(totals.total)} />
        <SummaryCard label={t('usageStats.requests')} value={totals.requests.toLocaleString()} />
        <SummaryCard label={t('usageStats.totalCost')} value={`$${totals.cost.toFixed(4)}`} />
        <SummaryCard label={t('usageStats.users')} value={String(data?.count || 0)} />
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-border-dark bg-surface-dark shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-[#151b28] border-b border-border-dark">
              <tr>
                <Th>{t('usageStats.owner')}</Th>
                <Th right>{t('usageStats.input')}</Th>
                <Th right>{t('usageStats.output')}</Th>
                <Th right>{t('usageStats.cacheRead')}</Th>
                <Th right>{t('usageStats.cacheWrite')}</Th>
                <Th right>{t('usageStats.totalTokens')}</Th>
                <Th right>{t('usageStats.requests')}</Th>
                <Th right>{t('usageStats.totalCost')}</Th>
                <Th right>{t('usageStats.dailyLimit')}</Th>
                <Th right>{t('usageStats.monthlyBudget')}</Th>
                <Th>{t('usageStats.serviceTier')}</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-dark">
              {isLoading ? (
                <tr>
                  <td colSpan={11} className="px-6 py-12 text-center">
                    <span className="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span>
                  </td>
                </tr>
              ) : (data?.items.length || 0) === 0 ? (
                <tr>
                  <td colSpan={11} className="px-6 py-12 text-center text-slate-400">{t('usageStats.noData')}</td>
                </tr>
              ) : (
                data?.items.map((r) => (
                  <tr key={r.api_key} className="hover:bg-[#1e2536] transition-colors">
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-white">{r.owner}</td>
                    <Td>{formatTokens(r.input_tokens)}</Td>
                    <Td>{formatTokens(r.output_tokens)}</Td>
                    <Td>{formatTokens(r.cache_read_tokens)}</Td>
                    <Td>{formatTokens(r.cache_write_tokens)}</Td>
                    <Td>{formatTokens(r.total_tokens)}</Td>
                    <Td>{r.requests.toLocaleString()}</Td>
                    <Td>${r.total_cost.toFixed(4)}</Td>
                    <Td>{r.daily_token_limit > 0 ? `${formatTokens(r.daily_token_limit * 10000)}` : '—'}</Td>
                    <Td>{r.monthly_budget > 0 ? `$${r.monthly_budget.toFixed(2)}` : '—'}</Td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-300">{r.service_tier}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-dark border border-border-dark rounded-xl p-4 flex flex-col gap-1">
      <span className="text-xs text-slate-400">{label}</span>
      <span className="text-2xl font-bold text-white">{value}</span>
    </div>
  );
}

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <th className={`px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider ${right ? 'text-right' : ''}`}>
      {children}
    </th>
  );
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-4 py-3 whitespace-nowrap text-right text-xs text-white">{children}</td>;
}
