export default function ProviderBadge({ provider }) {
  const styles = {
    rime: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    browser: 'bg-amber-100 text-amber-800 border-amber-200',
    unavailable: 'bg-red-100 text-red-800 border-red-200',
  };
  const labels = {
    rime: 'speech: rime mistv3',
    browser: 'speech: browser fallback (degraded)',
    unavailable: 'speech: unavailable',
  };
  const key = styles[provider] ? provider : 'unavailable';

  return (
    <span
      className={`text-[11px] font-mono px-2.5 py-1 rounded-full border ${styles[key]}`}
    >
      {provider ? labels[key] : 'speech: idle'}
    </span>
  );
}
