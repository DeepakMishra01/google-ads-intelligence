import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { compact, money, shortDate } from "@/lib/format";
import { CHART_COLORS } from "@/lib/ui";
import type { GrowthPoint, TrendPoint } from "@/lib/types";

const axis = { fontSize: 11, stroke: "#94a3b8" } as const;

/** Spend-over-time area chart. */
export function SpendAreaChart({ data, height = 240 }: { data: TrendPoint[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 5, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="spend" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART_COLORS.cost} stopOpacity={0.3} />
            <stop offset="100%" stopColor={CHART_COLORS.cost} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={axis} tickLine={false} />
        <YAxis tickFormatter={(v) => compact(v)} tick={axis} tickLine={false} width={48} />
        <Tooltip
          formatter={(v: number) => money(v)}
          labelFormatter={(l) => shortDate(String(l))}
          contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12 }}
        />
        <Area
          type="monotone"
          dataKey="cost"
          name="Spend"
          stroke={CHART_COLORS.cost}
          strokeWidth={2}
          fill="url(#spend)"
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Clicks + impressions dual-line chart. */
export function EngagementChart({ data, height = 240 }: { data: TrendPoint[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={axis} tickLine={false} />
        <YAxis tickFormatter={(v) => compact(v)} tick={axis} tickLine={false} width={48} />
        <Tooltip
          labelFormatter={(l) => shortDate(String(l))}
          contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="clicks" name="Clicks" stroke={CHART_COLORS.clicks} strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line
          type="monotone"
          dataKey="impressions"
          name="Impressions"
          stroke={CHART_COLORS.impressions}
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Active entity growth over time. */
export function GrowthChart({ data, height = 240 }: { data: GrowthPoint[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={axis} tickLine={false} />
        <YAxis tickFormatter={(v) => compact(v)} tick={axis} tickLine={false} width={40} />
        <Tooltip
          labelFormatter={(l) => shortDate(String(l))}
          contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="campaigns" name="Campaigns" stroke="#2563eb" strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line type="monotone" dataKey="keywords" name="Keywords" stroke="#16a34a" strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line
          type="monotone"
          dataKey="search_terms"
          name="Search terms"
          stroke="#ea580c"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
