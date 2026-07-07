import {
  AlertTriangle,
  BarChart3,
  FileText,
  Gauge,
  LayoutDashboard,
  ListChecks,
  PiggyBank,
  Search,
  Target,
  Type,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/priorities", label: "Priority Queue", icon: ListChecks },
  { to: "/alerts", label: "Alerts", icon: AlertTriangle },
  { to: "/campaigns", label: "Campaign Health", icon: Gauge },
  { to: "/keywords", label: "Keyword Health", icon: Type },
  { to: "/search-terms", label: "Search Terms", icon: Search },
  { to: "/budgets", label: "Budgets", icon: PiggyBank },
  { to: "/trends", label: "Trends", icon: BarChart3 },
  { to: "/reports", label: "Reports", icon: FileText },
];

export const APP_ICON = Target;
