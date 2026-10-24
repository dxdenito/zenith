import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, Plus, X } from "lucide-react";
import Sparkline from "../components/Sparkline";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { useLiveTicks } from "../lib/useLiveTicks";

const UP = "text-emerald-600 dark:text-emerald-400";

const group = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } };
const rise = {
  hidden: { opacity: 0, y: 22, scale: 0.96 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring", stiffness: 300, damping: 24 } },
};

function direction(list) {
  if (!list || list.length < 2) return 0;
  return Math.sign(list[list.length - 1].quote - list[list.length - 2].quote);
}

function toneFor(dir) {
  if (dir > 0) return UP;
  if (dir < 0) return "text-brand";
  return "text-text";
}

function chartTone(tone) {
  return tone === "text-text" ? "text-muted" : tone;
}

function digitColor(digit) {
  return digit % 2 === 0 ? "bg-sky text-ink" : "bg-honey text-ink";
}

function StatusChip({ status }) {
  const live = status === "live";
  return (
    <span
      className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm font-extrabold ${
        live ? "bg-lime text-ink" : "bg-honey text-ink"
      }`}
    >
      <motion.span
        animate={{ opacity: [1, 0.3, 1] }}
        transition={{ duration: 1.4, repeat: Infinity }}
        className="size-2 rounded-full bg-current"
      />
      {live ? "Live" : "Reconnecting"}
    </span>
  );
}

function MarketCard({ item, list, onOpen }) {
  const last = list?.[list.length - 1];
  const tone = toneFor(direction(list));
  const values = (list ?? []).slice(-60).map((t) => t.quote);

  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.97 }}
      whileHover={{ y: -3 }}
      onClick={() => onOpen(item)}
      className="w-full rounded-[32px] bg-surface p-5 text-left shadow-soft"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-display text-lg font-bold">{item.name}</p>
          <p className="text-xs font-extrabold text-muted">{item.symbol}</p>
        </div>
        {last && (
          <motion.span
            key={last.epoch}
            initial={{ scale: 0.6 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 500, damping: 18 }}
            className={`grid size-10 shrink-0 place-items-center rounded-full font-display text-lg font-bold ${digitColor(last.digit)}`}
          >
            {last.digit}
          </motion.span>
        )}
      </div>
      <p className={`mt-3 font-display text-3xl font-bold ${tone}`}>
        {last ? last.quote.toFixed(item.pip_decimals) : "—"}
      </p>
      <Sparkline values={values} height={56} className={`mt-2 ${chartTone(tone)}`} />
    </motion.button>
  );
}

function Detail({ item, list, onClose }) {
  const data = list ?? [];
  const last = data[data.length - 1];
  const tone = toneFor(direction(data));
  const recent = data.slice(-10);
  const counts = Array(10).fill(0);
  data.forEach((t) => {
    counts[t.digit] += 1;
  });
  const total = data.length;
  const evenTotal = counts.reduce((sum, c, d) => (d % 2 === 0 ? sum + c : sum), 0);
  const evenPct = total ? Math.round((evenTotal / total) * 100) : 0;

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate font-display text-2xl font-bold">{item.name}</p>
          <p className="text-sm font-extrabold text-muted">{item.symbol}</p>
        </div>
        <motion.button
          type="button"
          whileTap={{ scale: 0.9 }}
          onClick={onClose}
          aria-label="Close"
          className="grid size-11 shrink-0 place-items-center rounded-full bg-bg"
        >
          <X className="size-5" strokeWidth={2.6} />
        </motion.button>
      </div>

      <motion.p
        key={last?.epoch}
        initial={{ opacity: 0.5, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        className={`mt-5 font-display text-5xl font-bold ${tone}`}
      >
        {last ? last.quote.toFixed(item.pip_decimals) : "—"}
      </motion.p>
      <Sparkline
        values={data.slice(-120).map((t) => t.quote)}
        height={120}
        className={`mt-3 ${chartTone(tone)}`}
      />

      <h3 className="mt-6 font-display text-lg font-bold">Last digits</h3>
      <div className="mt-3 flex gap-1.5">
        {recent.map((t) => (
          <motion.span
            key={t.epoch}
            layout
            initial={{ scale: 0.4, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 500, damping: 24 }}
            className={`grid aspect-square min-w-0 flex-1 place-items-center rounded-full text-sm font-extrabold ${digitColor(t.digit)}`}
          >
            {t.digit}
          </motion.span>
        ))}
      </div>

      <h3 className="mt-6 font-display text-lg font-bold">Even or odd</h3>
      <div className="mt-3 flex h-4 overflow-hidden rounded-full bg-bg">
        <motion.div animate={{ width: `${evenPct}%` }} className="bg-sky" />
        <motion.div animate={{ width: `${total ? 100 - evenPct : 0}%` }} className="bg-honey" />
      </div>
      <p className="mt-2 text-sm font-bold text-muted">
        Even {evenPct}% · Odd {total ? 100 - evenPct : 0}% · last {total} ticks
      </p>

      <h3 className="mt-6 font-display text-lg font-bold">Digit spread</h3>
      <p className="text-sm font-semibold text-muted">Each digit lands about 10% of the time.</p>
      <div className="relative mt-3 flex h-28 items-end gap-1.5">
        <div className="absolute inset-x-0 top-1/2 border-t-2 border-dashed border-muted/40" />
        {counts.map((c, d) => {
          const pct = total ? (c / total) * 100 : 0;
          return (
            <div key={d} className="relative flex h-full flex-1 flex-col justify-end">
              <motion.div
                animate={{ height: `${Math.min(100, pct * 5)}%` }}
                transition={{ type: "spring", stiffness: 260, damping: 24 }}
                className={`rounded-t-xl ${digitColor(d)}`}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-1 flex gap-1.5">
        {counts.map((c, d) => (
          <div key={d} className="flex-1 text-center">
            <p className="text-sm font-extrabold">{d}</p>
            <p className="text-[10px] font-bold text-muted">
              {total ? Math.round((c / total) * 100) : 0}%
            </p>
          </div>
        ))}
      </div>
      <p className="mt-5 rounded-3xl bg-bg p-4 text-sm font-semibold text-muted">
        These numbers show the past. They do not tell you the next tick.
      </p>
    </div>
  );
}

export default function Markets() {
  const { user } = useAuth();
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(null);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState("");
  const owner = user.role === "owner";

  const load = useCallback(async () => {
    try {
      setItems(await api.symbols());
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const usable = useMemo(
    () => (items ?? []).filter((s) => s.families.length > 0 && !s.is_suspended),
    [items]
  );
  const watched = usable.filter((s) => s.collect);
  const others = usable.filter((s) => !s.collect);
  const { ticks, status } = useLiveTicks(watched.map((s) => s.symbol));

  async function add(item) {
    setBusy(item.symbol);
    try {
      await api.setCollect(item.symbol, true);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-4xl font-bold">Markets</h1>
          <p className="mt-1 text-lg font-semibold text-muted">Tap a market to see it up close.</p>
        </div>
        {watched.length > 0 && <StatusChip status={status} />}
      </div>

      {error && (
        <p className="rounded-3xl bg-brand/10 px-5 py-3 text-sm font-bold text-brand">{error}</p>
      )}

      {items === null && !error && (
        <div className="grid gap-4 sm:grid-cols-2">
          {[0, 1, 2].map((n) => (
            <div key={n} className="h-44 animate-pulse rounded-[32px] bg-surface" />
          ))}
        </div>
      )}

      {items !== null && watched.length === 0 && (
        <p className="rounded-[32px] bg-surface p-6 font-bold text-muted shadow-soft">
          {owner
            ? "No markets are being watched yet. Add one below."
            : "No markets are being watched yet."}
        </p>
      )}

      <motion.div variants={group} initial="hidden" animate="show" className="grid gap-4 sm:grid-cols-2">
        {watched.map((item) => (
          <motion.div key={item.symbol} variants={rise}>
            <MarketCard item={item} list={ticks[item.symbol]} onOpen={setOpen} />
          </motion.div>
        ))}
      </motion.div>

      {owner && others.length > 0 && (
        <section className="rounded-[32px] bg-surface p-5 shadow-soft">
          <motion.button
            type="button"
            whileTap={{ scale: 0.97 }}
            onClick={() => setMore((v) => !v)}
            className="flex w-full items-center justify-between font-display text-xl font-bold"
          >
            Add more markets
            <motion.span animate={{ rotate: more ? 180 : 0 }}>
              <ChevronDown className="size-6" strokeWidth={2.6} />
            </motion.span>
          </motion.button>
          <AnimatePresence initial={false}>
            {more && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <p className="mt-2 text-sm font-semibold text-muted">
                  New markets start showing ticks within a few seconds.
                </p>
                <div className="mt-3 space-y-2">
                  {others.map((item) => (
                    <div key={item.symbol} className="flex items-center gap-3 rounded-3xl bg-bg p-3 pl-5">
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-extrabold">{item.name}</p>
                        <p className="text-xs font-bold text-muted">{item.symbol}</p>
                      </div>
                      <motion.button
                        type="button"
                        whileTap={{ scale: 0.9 }}
                        disabled={busy === item.symbol}
                        onClick={() => add(item)}
                        className="flex h-10 items-center gap-1 rounded-full bg-brand px-4 text-sm font-extrabold text-on-brand disabled:opacity-60"
                      >
                        <Plus className="size-4" strokeWidth={3} />
                        Add
                      </motion.button>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </section>
      )}

      {createPortal(
        <AnimatePresence>
          {open && (
            <>
              <motion.div
                key="backdrop"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setOpen(null)}
                className="fixed inset-0 z-50 bg-black/50"
              />
              <div
                key="wrap"
                className="pointer-events-none fixed inset-0 z-50 flex items-end justify-center lg:items-center"
              >
                <motion.div
                  initial={{ y: 80, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: 80, opacity: 0 }}
                  transition={{ type: "spring", stiffness: 320, damping: 30 }}
                  className="pointer-events-auto max-h-[90dvh] w-full overflow-y-auto rounded-t-[36px] bg-surface p-6 text-text shadow-lift lg:max-w-lg lg:rounded-[36px]"
                  style={{ paddingBottom: "calc(1.5rem + env(safe-area-inset-bottom, 0px))" }}
                >
                  <Detail item={open} list={ticks[open.symbol]} onClose={() => setOpen(null)} />
                </motion.div>
              </div>
            </>
          )}
        </AnimatePresence>,
        document.body
      )}
    </div>
  );
}