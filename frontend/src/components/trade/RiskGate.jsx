import { useState } from "react";
import { motion } from "motion/react";
import { AlertTriangle } from "lucide-react";

export default function RiskGate({ disclaimer, onAccept, busy }) {
  const [agree, setAgree] = useState(false);
  return (
    <section className="rounded-[32px] bg-surface p-6 shadow-soft">
      <h2 className="font-display text-2xl font-bold">Read this first</h2>
      <ul className="mt-3 space-y-2 text-sm font-semibold text-muted">
        {disclaimer.points.map((p) => (
          <li key={p} className="flex gap-2">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-brand" strokeWidth={2.6} />
            <span>{p}</span>
          </li>
        ))}
      </ul>
      <label className="mt-5 flex items-start gap-3 font-bold">
        <input
          type="checkbox"
          checked={agree}
          onChange={(e) => setAgree(e.target.checked)}
          className="mt-1 size-5"
        />
        <span>I have read this and I understand I will most likely lose money.</span>
      </label>
      <motion.button
        type="button"
        whileTap={{ scale: 0.96 }}
        disabled={!agree || busy}
        onClick={onAccept}
        className="mt-4 h-12 rounded-full bg-brand px-6 font-extrabold text-on-brand disabled:opacity-50"
      >
        I understand, continue
      </motion.button>
    </section>
  );
}