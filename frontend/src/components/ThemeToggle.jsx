import { AnimatePresence, motion } from "motion/react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "../context/ThemeContext";

export default function ThemeToggle({ className = "" }) {
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";

  return (
    <motion.button
      type="button"
      onClick={toggle}
      whileTap={{ scale: 0.86 }}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className={`grid size-11 place-items-center overflow-hidden rounded-full bg-surface text-text shadow-soft ${className}`}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={theme}
          initial={{ rotate: -90, scale: 0, opacity: 0 }}
          animate={{ rotate: 0, scale: 1, opacity: 1 }}
          exit={{ rotate: 90, scale: 0, opacity: 0 }}
          transition={{ duration: 0.22 }}
          className="grid place-items-center"
        >
          {dark ? (
            <Moon className="size-5" strokeWidth={2.4} />
          ) : (
            <Sun className="size-5" strokeWidth={2.4} />
          )}
        </motion.span>
      </AnimatePresence>
    </motion.button>
  );
}
