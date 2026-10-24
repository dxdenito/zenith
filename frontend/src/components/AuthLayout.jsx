import { useEffect } from "react";
import { motion, useAnimationControls } from "motion/react";
import Brand from "./Brand";
import ThemeToggle from "./ThemeToggle";

const float = (duration, distance) => ({
  animate: { y: [0, -distance, 0] },
  transition: { duration, repeat: Infinity, ease: "easeInOut" },
});

export default function AuthLayout({ title, subtitle, shake = 0, footer, children }) {
  const controls = useAnimationControls();

  useEffect(() => {
    if (shake) controls.start({ x: [0, -10, 10, -8, 8, 0], transition: { duration: 0.4 } });
  }, [shake, controls]);

  return (
    <div className="flex min-h-dvh flex-col overflow-hidden bg-brand lg:flex-row">
      <section
        className="relative flex flex-col justify-between overflow-hidden px-6 pb-20 text-on-brand lg:w-1/2 lg:px-14 lg:pb-14 lg:pt-14"
        style={{ paddingTop: "calc(1.5rem + env(safe-area-inset-top, 0px))" }}
      >
        <motion.span
          {...float(5, 14)}
          className="absolute -right-12 -top-10 size-52 rounded-full bg-white/20"
        />
        <motion.span
          {...float(4, 10)}
          className="absolute right-24 top-44 size-16 rounded-full bg-honey"
        />
        <motion.span
          {...float(6, 16)}
          className="absolute -left-10 bottom-10 size-32 rounded-full bg-berry/80 lg:bottom-24"
        />
        <motion.span
          {...float(3.5, 8)}
          className="absolute bottom-28 right-12 hidden size-10 rounded-full bg-lime lg:block"
        />
        <div className="relative flex items-center justify-between">
          <div className="text-white">
            <Brand inverted />
          </div>
          <ThemeToggle className="lg:hidden" />
        </div>
        <div className="relative mt-12 text-white lg:mt-0">
          <h1 className="font-display text-5xl font-bold leading-[1.05] lg:text-7xl">
            Trade calm.
            <br />
            See clearly.
          </h1>
          <p className="mt-4 max-w-sm text-lg font-semibold text-white/85">
            Small steps, clear numbers, and nothing noisy.
          </p>
        </div>
      </section>

      <motion.section
        initial={{ y: 80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 220, damping: 26, delay: 0.1 }}
        className="relative -mt-10 flex flex-1 items-start justify-center rounded-t-[40px] bg-surface px-6 pt-9 lg:mt-0 lg:items-center lg:rounded-none lg:rounded-l-[56px]"
        style={{ paddingBottom: "calc(2.5rem + env(safe-area-inset-bottom, 0px))" }}
      >
        <div className="absolute right-8 top-8 hidden lg:block">
          <ThemeToggle className="bg-bg shadow-none" />
        </div>
        <motion.div animate={controls} className="w-full max-w-md">
          <h2 className="font-display text-3xl font-bold">{title}</h2>
          <p className="mt-2 text-base font-semibold text-muted">{subtitle}</p>
          <div className="mt-7">{children}</div>
          {footer && <div className="mt-8 text-center font-bold text-muted">{footer}</div>}
        </motion.div>
      </motion.section>
    </div>
  );
}
