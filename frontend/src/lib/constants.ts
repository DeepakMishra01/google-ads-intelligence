import {
  AlertTriangle,
  BarChart3,
  FileText,
  Gauge,
  LayoutDashboard,
  ListChecks,
  PiggyBank,
  Search,
  SearchCode,
  Sparkles,
  Target,
  Type,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  group?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/explorer", label: "Campaign Explorer", icon: SearchCode },
  { to: "/priorities", label: "Priority Queue", icon: ListChecks },
  { to: "/alerts", label: "Alerts", icon: AlertTriangle },
  { to: "/campaigns", label: "Campaign Health", icon: Gauge },
  { to: "/keywords", label: "Keyword Health", icon: Type },
  { to: "/search-terms", label: "Search Terms", icon: Search },
  { to: "/budgets", label: "Budgets", icon: PiggyBank },
  { to: "/trends", label: "Trends", icon: BarChart3 },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/ai/ad-copy", label: "AI Ad Copy Generator", icon: Sparkles, group: "AI Tools" },
];

export const APP_ICON = Target;
