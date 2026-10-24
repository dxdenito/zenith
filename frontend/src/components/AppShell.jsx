import { useEffect, useRef } from "react";
import { NavLink, useLocation, useOutlet } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { useAuth } from "../context/AuthContext";
import { navItems } from "../lib/nav";
import Brand from "./Brand";
import ThemeToggle from "./ThemeToggle";
   import AccountSwitcher from "./AccountSwitcher";

const pageVariants = {
  enter: (d) => ({ opacity: 0, x: d * 36 }),
  center: {
    opacity: 1,
    x: 0,
    transition: { type: "spring", stiffness: 380, damping: 32 },
  },
  exit: (d) => ({ opacity: 0, x: d * -36, transition: { duration: 0.12 } }),
};

function Page() {
  const { pathname } = useLocation();
  const outlet = useOutlet();
  const index = Math.max(0, navItems.findIndex((item) => item.to === pathname));
  const previous = useRef(index);
  const direction = index >= previous.current ? 1 : -1;

  useEffect(() => {
    previous.current = index;
  }, [index]);

  return (
    <AnimatePresence mode="wait" initial={false} custom={direction}>
      <motion.div
        key={pathname}
        custom={direction}
        variants={pageVariants}
        initial="enter"
        animate="center"
        exit="exit"
      >
        {outlet}
      </motion.div>
    </AnimatePresence>
  );
}

function Sidebar({ user }) {
  const name = user.full_name || user.email;

  return (
    <aside className="fixed inset-y-0 left-0 hidden w-72 flex-col justify-between p-6 lg:flex">
      <div>
          <div className="mb-6 px-2">
             <Brand />
           </div>
           <div className="mb-8 px-2">
             <AccountSwitcher />
           </div>
        <nav className="space-y-2">
          {navItems.map(({ to, label, icon: Icon, pill, on, end }) => (
            <NavLink key={to} to={to} end={end} className="block rounded-full">
              {({ isActive }) => (
                <motion.div
                  whileTap={{ scale: 0.96 }}
                  className={`relative flex items-center gap-3 rounded-full px-5 py-3.5 font-extrabold ${
                    isActive ? on : "text-muted hover:text-text"
                  }`}
                >
                  {isActive && (
                    <motion.span
                      layoutId="side-pill"
                      transition={{ type: "spring", stiffness: 420, damping: 34 }}
                      className={`absolute inset-0 rounded-full shadow-soft ${pill}`}
                    />
                  )}
                  <Icon className="relative size-5" strokeWidth={2.4} />
                  <span className="relative">{label}</span>
                </motion.div>
              )}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="rounded-3xl bg-surface p-4 shadow-soft">
        <div className="flex items-center gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-full bg-deep font-display text-lg font-bold text-on-deep">
            {name.charAt(0).toUpperCase()}
          </span>
          <div className="min-w-0">
            <p className="truncate font-extrabold">{name}</p>
            <p className="truncate text-xs font-bold text-muted">{user.tenant.name}</p>
          </div>
          <ThemeToggle className="ml-auto bg-bg shadow-none" />
        </div>
      </div>
    </aside>
  );
}

function TopBar() {
  return (
    <header
      className="sticky top-0 z-20 flex items-center justify-between bg-bg/90 px-5 pb-3 backdrop-blur lg:hidden"
      style={{ paddingTop: "calc(0.75rem + env(safe-area-inset-top, 0px))" }}
    >
        <Brand />
         <div className="flex items-center gap-2">
           <AccountSwitcher />
           <ThemeToggle />
         </div>
    </header>
  );
}

function TabBar() {
  return (
    <nav
      className="fixed inset-x-3 z-30 flex rounded-[32px] bg-surface p-2 shadow-lift lg:hidden"
      style={{ bottom: "calc(0.75rem + env(safe-area-inset-bottom, 0px))" }}
    >
      {navItems.map(({ to, label, icon: Icon, pill, on, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={() => navigator.vibrate?.(8)}
          className="relative flex-1 rounded-3xl"
        >
          {({ isActive }) => (
            <motion.div
              whileTap={{ scale: 0.86 }}
              className={`relative flex flex-col items-center gap-0.5 py-2.5 text-[11px] font-extrabold ${
                isActive ? on : "text-muted"
              }`}
            >
              {isActive && (
                <motion.span
                  layoutId="tab-pill"
                  transition={{ type: "spring", stiffness: 520, damping: 34 }}
                  className={`absolute inset-0 rounded-3xl ${pill}`}
                />
              )}
              <motion.span
                className="relative"
                animate={{ y: isActive ? -1 : 0, scale: isActive ? 1.14 : 1 }}
                transition={{ type: "spring", stiffness: 520, damping: 16 }}
              >
                <Icon className="size-6" strokeWidth={2.4} />
              </motion.span>
              <span className="relative">{label}</span>
            </motion.div>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

export default function AppShell() {
  const { user } = useAuth();

  return (
    <div className="min-h-dvh lg:pl-72">
      <Sidebar user={user} />
      <TopBar />
      <main className="mx-auto w-full max-w-5xl overflow-x-clip px-5 pb-36 pt-5 lg:px-10 lg:pb-12 lg:pt-10">
        <Page />
      </main>
      <TabBar />
    </div>
  );
}
