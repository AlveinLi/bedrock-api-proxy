import { useTranslation } from 'react-i18next';
import { COMMON_TIMEZONES } from '../../utils';

export default function TimezoneSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (tz: string) => void;
}) {
  const { t } = useTranslation();
  const options = COMMON_TIMEZONES.includes(value)
    ? COMMON_TIMEZONES
    : [value, ...COMMON_TIMEZONES];
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-slate-400">{t('common.timezone')}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="px-3 py-2 bg-input-bg border border-border-dark rounded-lg text-white text-sm focus:border-primary focus:ring-1 focus:ring-primary"
      >
        {options.map((tz) => (
          <option key={tz} value={tz}>
            {tz}
          </option>
        ))}
      </select>
    </div>
  );
}
