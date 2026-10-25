export function Chip({ className = "", children }) {
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-extrabold ${className}`}>{children}</span>
  );
}

export function Tile({ label, value, valueClass = "" }) {
  return (
    <div className="rounded-3xl bg-bg p-4">
      <p className="text-xs font-extrabold text-muted">{label}</p>
      <p className={`mt-1 font-display text-2xl font-bold ${valueClass}`}>{value}</p>
    </div>
  );
}