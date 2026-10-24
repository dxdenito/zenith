import { Activity, House, Settings, Target, TrendingUp } from "lucide-react";

export const navItems = [
  {
    to: "/",
    label: "Home",
    icon: House,
    pill: "bg-brand",
    on: "text-on-brand",
    end: true,
  },
  {
    to: "/markets",
    label: "Markets",
    icon: TrendingUp,
    pill: "bg-lime",
    on: "text-ink",
    blurb: "Live ticks from the synthetic markets, all in one calm view.",
  },
  {
    to: "/analysis",
    label: "Analysis",
    icon: Activity,
    pill: "bg-honey",
    on: "text-ink",
    blurb: "Tests that show what the numbers really say, in plain words.",
  },
  {
    to: "/trade",
    label: "Trade",
    icon: Target,
    pill: "bg-berry",
    on: "text-white",
    blurb: "Place and track trades safely, starting with Demo.",
  },
  {
    to: "/settings",
    label: "Settings",
    icon: Settings,
    pill: "bg-deep",
    on: "text-on-deep",
  },
];
