import { motion } from "motion/react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "../../context/ThemeContext";

const modes = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
];

export default function AppearanceTab() {
  const { theme, setTheme } = useTheme();

  return (
    <section className="rounded-[32px] bg-surface p-5 shadow-soft">
      <h2 className="mb-4 font-display text-xl font-bold">Look and feel</h2>
      <div className="flex rounded-full bg-bg p-1.5">
        {modes.map(({ value, label, icon: Icon }) => {
          const selected = theme === value;
          return (
            <button
              key={value}
              type="button"
              onClick={() => setTheme(value)}
              className="relative flex-1 rounded-full py-3"
            >
              {selected && (
                <motion.span
                  layoutId="theme-pill"
                  transition={{ type: "spring", stiffness: 480, damping: 34 }}
                  className="absolute inset-0 rounded-full bg-brand shadow-pop"
                />
              )}
              <span
                className={`relative flex items-center justify-center gap-2 font-extrabold ${
                  selected ? "text-on-brand" : "text-muted"
                }`}
              >
                <Icon className="size-5" strokeWidth={2.4} />
                {label}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}