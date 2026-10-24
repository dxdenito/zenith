import { useLocation } from "react-router-dom";
import { motion } from "motion/react";
import { navItems } from "../lib/nav";

export default function Placeholder() {
  const { pathname } = useLocation();
  const item = navItems.find((i) => i.to === pathname) ?? navItems[0];
  const Icon = item.icon;

  return (
    <div className="grid min-h-[60dvh] place-items-center text-center">
      <div className="max-w-sm">
        <motion.div
          animate={{ y: [0, -10, 0] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          className={`mx-auto mb-8 grid size-28 place-items-center rounded-[36px] shadow-pop ${item.pill} ${item.on}`}
        >
          <Icon className="size-12" strokeWidth={2.2} />
        </motion.div>
        <h1 className="font-display text-3xl font-bold">{item.label}</h1>
        <p className="mt-3 text-lg font-semibold text-muted">{item.blurb}</p>
        <span className="mt-6 inline-block rounded-full bg-surface px-5 py-2 font-extrabold shadow-soft">
          Coming soon
        </span>
      </div>
    </div>
  );
}
