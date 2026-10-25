import { motion } from "motion/react";
import { Chip } from "./atoms";

function StrategyCard({ strategy, selected, onPick, disabled }) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.98 }}
      disabled={disabled}
      onClick={() => onPick(strategy.key)}
      className={`w-full rounded-[32px] bg-surface p-5 text-left shadow-soft disabled:opacity-60 ${
        selected ? "ring-4 ring-brand" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="font-display text-xl font-bold">{strategy.name}</p>
        <Chip className="bg-bg text-text">{strategy.contract}</Chip>
      </div>
      <p className="mt-2 text-sm font-semibold text-muted">{strategy.summary}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Chip className="bg-honey text-ink">needs {strategy.break_even}% wins</Chip>
        <Chip className="bg-bg text-text">house margin {strategy.margin}%</Chip>
      </div>
      <p className="mt-3 rounded-2xl bg-bg p-3 text-xs font-bold text-muted">{strategy.tested}</p>
    </motion.button>
  );
}

export default function StrategyPicker({ strategies, pick, onPick, disabled }) {
  return (
    <section className="space-y-4">
      <h2 className="font-display text-2xl font-bold">Strategy</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        {strategies.map((s) => (
          <StrategyCard
            key={s.key}
            strategy={s}
            selected={pick === s.key}
            onPick={onPick}
            disabled={disabled}
          />
        ))}
      </div>
    </section>
  );
}