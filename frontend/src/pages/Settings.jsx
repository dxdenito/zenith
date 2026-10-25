import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { Link2, Palette, ShieldAlert, User } from "lucide-react";
import AccountTab from "../components/settings/AccountTab";
import AppearanceTab from "../components/settings/AppearanceTab";
import ProfileTab from "../components/settings/ProfileTab";
import TradingLimits from "../components/trade/TradingLimits";

const TABS = [
  { key: "profile", label: "Profile", icon: User },
  { key: "account", label: "Account", icon: Link2 },
  { key: "trading", label: "Trading", icon: ShieldAlert },
  { key: "appearance", label: "Appearance", icon: Palette },
];

export default function Settings() {
  const [params, setParams] = useSearchParams();
  const [flash, setFlash] = useState(() => params.get("deriv"));
  const requested = params.get("tab");
  const valid = TABS.some((t) => t.key === requested);
  const tab = valid ? requested : flash ? "account" : "profile";

  useEffect(() => {
    if (params.has("deriv")) setParams({ tab: "account" }, { replace: true });
  }, []);

  function select(key) {
    setFlash(null);
    setParams({ tab: key }, { replace: true });
  }

  return (
    <div className="space-y-6">
      <h1 className="font-display text-4xl font-bold">Settings</h1>

      <div className="-mx-1 overflow-x-auto px-1 pb-1">
        <div
          role="tablist"
          className="flex w-max min-w-full gap-1.5 rounded-full bg-surface p-1.5 shadow-soft"
        >
          {TABS.map(({ key, label, icon: Icon }) => {
            const selected = tab === key;
            return (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => select(key)}
                className="relative flex-1 whitespace-nowrap rounded-full px-4 py-2.5"
              >
                {selected && (
                  <motion.span
                    layoutId="settings-tab"
                    transition={{ type: "spring", stiffness: 480, damping: 34 }}
                    className="absolute inset-0 rounded-full bg-brand shadow-pop"
                  />
                )}
                <span
                  className={`relative flex items-center justify-center gap-2 text-sm font-extrabold ${
                    selected ? "text-on-brand" : "text-muted"
                  }`}
                >
                  <Icon className="size-4" strokeWidth={2.6} />
                  {label}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8, transition: { duration: 0.1 } }}
          transition={{ type: "spring", stiffness: 380, damping: 32 }}
        >
          {tab === "profile" && <ProfileTab />}
          {tab === "account" && <AccountTab flash={flash} />}
          {tab === "trading" && <TradingLimits />}
          {tab === "appearance" && <AppearanceTab />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}