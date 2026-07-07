// Shared visual mappings for health scores, severities, and budget risk.

export function healthColor(score: number): string {
  if (score >= 80) return "#16a34a"; // healthy
  if (score >= 60) return "#d97706"; // warning
  if (score >= 40) return "#ea580c"; // high
  return "#dc2626"; // critical
}

export function healthBadgeClass(level: string): string {
  switch (level) {
    case "healthy":
      return "bg-green-100 text-green-700";
    case "warning":
      return "bg-amber-100 text-amber-700";
    case "high":
      return "bg-orange-100 text-orange-700";
    case "critical":
      return "bg-red-100 text-red-700";
    default:
      return "bg-slate-100 text-slate-600";
  }
}

export function severityBadgeClass(sev: string): string {
  switch (sev) {
    case "critical":
      return "bg-red-100 text-red-700";
    case "high":
      return "bg-orange-100 text-orange-700";
    case "medium":
      return "bg-amber-100 text-amber-700";
    default:
      return "bg-slate-100 text-slate-600";
  }
}

export function riskBadgeClass(risk: string): string {
  switch (risk) {
    case "critical":
      return "bg-red-100 text-red-700";
    case "warning":
      return "bg-amber-100 text-amber-700";
    default:
      return "bg-green-100 text-green-700";
  }
}

export function statusBadgeClass(status: string): string {
  switch (status) {
    case "open":
      return "bg-red-100 text-red-700";
    case "resolved":
      return "bg-green-100 text-green-700";
    case "dismissed":
      return "bg-slate-100 text-slate-500";
    default:
      return "bg-slate-100 text-slate-600";
  }
}

export const CHART_COLORS = {
  cost: "#2563eb",
  clicks: "#16a34a",
  impressions: "#7c3aed",
  ctr: "#ea580c",
  conversions: "#0891b2",
};
