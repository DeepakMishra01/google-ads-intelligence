import {
  AlertTriangle,
  BarChart3,
  Building2,
  FileText,
  Gauge,
  LayoutDashboard,
  ListChecks,
  PiggyBank,
  Search,
  SearchCode,
  Sparkles,
  ClipboardCheck,
  Globe,
  Target,
  Type,
  Users,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  group?: string;
  adminOnly?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  // Performance
  { to: "/accounts", label: "Accounts", icon: Building2, group: "Performance" },
  { to: "/campaigns", label: "Campaign Health", icon: Gauge, group: "Performance" },
  { to: "/explorer", label: "Campaign Explorer", icon: SearchCode, group: "Performance" },
  { to: "/keywords", label: "Keyword Health", icon: Type, group: "Performance" },
  { to: "/search-terms", label: "Search Terms", icon: Search, group: "Performance" },
  { to: "/trends", label: "Trends", icon: BarChart3, group: "Performance" },
  { to: "/budgets", label: "Budgets", icon: PiggyBank, group: "Performance" },
  // AI Planner
  { to: "/ai/ad-copy", label: "AI Ad Copy Generator", icon: Sparkles, group: "AI Planner" },
  { to: "/landing-auditor", label: "Landing Page Auditor", icon: Globe, group: "AI Planner" },
  // Accountability
  { to: "/accountability", label: "Campaign Accountability", icon: Target, group: "Accountability" },
  { to: "/account-budgets", label: "Account Budgets", icon: Wallet, group: "Accountability" },
  { to: "/execution-audit", label: "Execution Audit", icon: ClipboardCheck, group: "Accountability" },
  { to: "/priorities", label: "Priority Queue", icon: ListChecks, group: "Accountability" },
  { to: "/alerts", label: "Alerts", icon: AlertTriangle, group: "Accountability" },
  // Reports
  { to: "/reports", label: "Reports", icon: FileText, group: "Reports" },
  // Admin (only rendered for admins)
  { to: "/admin/users", label: "Users & Access", icon: Users, group: "Admin", adminOnly: true },
];

export const APP_ICON = Target;
