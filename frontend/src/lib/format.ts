// Display formatters. Currency defaults to INR (the platform manages Indian
// colleges) but is overridable.

const CURRENCY = "INR";

export function money(value: number | null | undefined, currency = CURRENCY): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: value >= 1000 ? 0 : 2,
  }).format(value);
}

export function num(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-IN").format(value);
}

export function pct(value: number | null | undefined, digits = 2): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function compact(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 }).format(
    value
  );
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Google Ads API bidding-strategy enums → the names shown in the Ads UI.
const BIDDING_LABELS: Record<string, string> = {
  TARGET_SPEND: "Maximize clicks",
  MAXIMIZE_CONVERSIONS: "Maximize conversions",
  MAXIMIZE_CONVERSION_VALUE: "Maximize conversion value",
  TARGET_CPA: "Target CPA",
  TARGET_ROAS: "Target ROAS",
  TARGET_IMPRESSION_SHARE: "Target impression share",
  MANUAL_CPC: "Manual CPC",
  ENHANCED_CPC: "Enhanced CPC",
  PERCENT_CPC: "Percent CPC",
  MANUAL_CPM: "Manual CPM",
  MANUAL_CPV: "Manual CPV",
  COMMISSION: "Commission",
  PAGE_ONE_PROMOTED: "Target search page location",
};

export function biddingLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return BIDDING_LABELS[value] ?? value.replace(/_/g, " ").toLowerCase();
}

// Advertising-channel enums → Ads UI campaign-type names.
const CHANNEL_LABELS: Record<string, string> = {
  SEARCH: "Search",
  DISPLAY: "Display",
  SHOPPING: "Shopping",
  VIDEO: "Video",
  MULTI_CHANNEL: "App",
  PERFORMANCE_MAX: "Performance Max",
  DEMAND_GEN: "Demand Gen",
  DISCOVERY: "Demand Gen",
  LOCAL: "Local",
  SMART: "Smart",
};

export function channelLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return CHANNEL_LABELS[value] ?? value.replace(/_/g, " ");
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}
