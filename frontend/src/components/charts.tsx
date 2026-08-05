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
const GRID = "#eef1f6";
const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid #e6e9f0",
  fontSize: 12,
  boxShadow: "0 10px 28px -6px rgb(16 24 40 / 0.16)",
  padding: "8px 11px",
} as const;
const activeDot = { r: 4, strokeWidth: 2, stroke: "#fff" } as const;

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
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={axis} tickLine={false} />
        <YAxis tickFormatter={(v) => compact(v)} tick={axis} tickLine={false} width={48} />
        <Tooltip
          formatter={(v: number) => money(v)}
          labelFormatter={(l) => shortDate(String(l))}
          contentStyle={tooltipStyle} cursor={{ stroke: "#cbd5e1", strokeWidth: 1 }}
        />
        <Area
          type="monotone"
          dataKey="cost"
          name="Spend"
          stroke={CHART_COLORS.cost}
          strokeWidth={2}
          fill="url(#spend)"
          activeDot={activeDot}
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
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={axis} tickLine={false} />
        <YAxis tickFormatter={(v) => compact(v)} tick={axis} tickLine={false} width={48} />
        <Tooltip
          labelFormatter={(l) => shortDate(String(l))}
          contentStyle={tooltipStyle} cursor={{ stroke: "#cbd5e1", strokeWidth: 1 }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="clicks" name="Clicks" stroke={CHART_COLORS.clicks} strokeWidth={2} dot={false} activeDot={activeDot} isAnimationActive={false} />
        <Line
          type="monotone"
          dataKey="impressions"
          name="Impressions"
          stroke={CHART_COLORS.impressions}
          strokeWidth={2}
          dot={false} activeDot={activeDot}
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
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={axis} tickLine={false} />
        <YAxis tickFormatter={(v) => compact(v)} tick={axis} tickLine={false} width={40} />
        <Tooltip
          labelFormatter={(l) => shortDate(String(l))}
          contentStyle={tooltipStyle} cursor={{ stroke: "#cbd5e1", strokeWidth: 1 }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="campaigns" name="Campaigns" stroke={CHART_COLORS.cost} strokeWidth={2} dot={false} activeDot={activeDot} isAnimationActive={false} />
        <Line type="monotone" dataKey="keywords" name="Keywords" stroke={CHART_COLORS.clicks} strokeWidth={2} dot={false} activeDot={activeDot} isAnimationActive={false} />
        <Line
          type="monotone"
          dataKey="search_terms"
          name="Search terms"
          stroke={CHART_COLORS.ctr}
          strokeWidth={2}
          dot={false} activeDot={activeDot}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
