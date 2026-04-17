'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState, useTransition } from 'react';
import { formatDateTime, formatMoney, formatPercent, formatQuantity, numberFromString } from '@/lib/commerce-format';
import { getDashboardAnalytics } from '@/lib/api/dashboard';
import {
  BarChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
  ScatterChart,
  Scatter,
  ZAxis,
} from 'recharts';
import { HoverHint } from '@/components/ui/hover-hint';
import type {
  DashboardAnalytics,
  DashboardInsightCard,
  DashboardMetric,
  DashboardProductOpportunityPoint,
  DashboardRangeKey,
  DashboardRecentActivityItem,
  DashboardStockInvestmentRow,
  DashboardStockMovementPoint,
} from '@/types/dashboard';


type DashboardFilters = {
  range_key: DashboardRangeKey;
  location_id: string;
  from_date: string;
  to_date: string;
};

type ChartPoint = {
  label: string;
  bar: number;
  line?: number | null;
};

const DEFAULT_FILTERS: DashboardFilters = {
  range_key: 'mtd',
  location_id: '',
  from_date: '',
  to_date: '',
};

const RANGE_OPTIONS: Array<{ value: DashboardRangeKey; label: string }> = [
  { value: 'last_7_days', label: 'Last 7 days' },
  { value: 'mtd', label: 'Month to date' },
  { value: 'last_30_days', label: 'Last 30 days' },
  { value: 'last_90_days', label: 'Last 90 days' },
  { value: 'custom', label: 'Custom range' },
];

const MOVEMENT_COLORS: Record<string, string> = {
  stock_received: '#ff7a3d',
  sale_fulfilled: '#ffb38f',
  sales_return_restock: '#f55d24',
  adjustment: '#cdb49d',
};


function metricValue(metric: DashboardMetric) {
  if (metric.value === null || metric.unavailable_reason) {
    return metric.unavailable_reason ?? 'Not enough data';
  }
  if (metric.unit === 'money') {
    return `$${formatMoney(metric.value)}`;
  }
  if (metric.unit === 'percent') {
    return formatPercent(metric.value);
  }
  if (metric.unit === 'quantity') {
    return formatQuantity(metric.value);
  }
  if (metric.unit === 'days') {
    return `${numberFromString(String(metric.value)).toFixed(1)} days`;
  }
  return Intl.NumberFormat().format(numberFromString(String(metric.value)));
}


function metricDelta(metric: DashboardMetric) {
  if (metric.delta_value === null || metric.delta_direction === null) {
    return metric.help_text ?? '';
  }
  const prefix = metric.delta_direction === 'up' ? '+' : metric.delta_direction === 'down' ? '-' : '';
  const magnitude = Math.abs(numberFromString(String(metric.delta_value)));
  const formatted =
    metric.unit === 'money'
      ? `$${magnitude.toFixed(2)}`
      : metric.unit === 'quantity'
        ? magnitude.toFixed(3)
        : metric.unit === 'percent'
          ? `${magnitude.toFixed(2)}%`
          : Intl.NumberFormat().format(magnitude);
  return `${prefix}${formatted} vs previous period`;
}


function compactMoney(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return 'Not enough cost data';
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(numberFromString(String(value)));
}


function compactNumber(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return '0';
  return new Intl.NumberFormat(undefined, {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(numberFromString(String(value)));
}


function toneClass(tone: DashboardInsightCard['tone']) {
  return `dashboard-insight-card tone-${tone}`;
}

type DashboardActionLead = {
  title: string;
  summary: string;
  href: string;
  cta: string;
};

function resolveActionLead(dashboard: DashboardAnalytics | null, financialVisible: boolean): DashboardActionLead {
  if (!dashboard) {
    return {
      title: 'Review inventory pressure first',
      summary: 'Start by checking low-stock variants so near-term orders do not fail.',
      href: '/inventory?tab=low-stock',
      cta: 'Open low stock',
    };
  }

  if (dashboard.tables.low_stock_variants.length) {
    return {
      title: 'Replenish low-stock variants now',
      summary: `${dashboard.tables.low_stock_variants.length} variants are at or below reorder level and can block upcoming sales.`,
      href: '/inventory?tab=low-stock',
      cta: 'Open low stock',
    };
  }

  if (dashboard.tables.slow_movers.length) {
    return {
      title: 'Move aging stock',
      summary: `${dashboard.tables.slow_movers.length} products have stock but no recent sales. Review pricing or campaign actions next.`,
      href: '/inventory',
      cta: 'Review stock',
    };
  }

  if (!dashboard.tables.top_products_by_units_sold.length) {
    return {
      title: 'Capture your first completed sale',
      summary: 'No completed sales are visible in this range yet. Finish one sale to unlock operational signals.',
      href: '/sales',
      cta: 'Open sales',
    };
  }

  return {
    title: financialVisible ? 'Validate sales quality and margin trend' : 'Validate sales momentum',
    summary: financialVisible
      ? 'Use sales quality trends to confirm growth is not sacrificing margin.'
      : 'Use sales trends to confirm demand and conversion are improving.',
    href: '/sales',
    cta: 'Open sales quality',
  };
}


function chartPoints(
  items: Array<{ period: string; revenue?: string | number; estimated_gross_profit?: string | number | null; returns_count?: number; refund_amount?: string | number | null }>
) {
  return items.map((item) => ({
    label: item.period,
    bar: numberFromString(String(item.revenue ?? item.returns_count ?? 0)),
    line: item.estimated_gross_profit !== undefined
      ? item.estimated_gross_profit === null
        ? null
        : numberFromString(String(item.estimated_gross_profit))
      : item.refund_amount === null || item.refund_amount === undefined
        ? null
        : numberFromString(String(item.refund_amount)),
  }));
}


function HorizontalBarList({
  rows,
  financialVisible,
}: {
  rows: DashboardStockInvestmentRow[];
  financialVisible: boolean;
}) {
  const maxValue = Math.max(
    ...rows.map((row) =>
      financialVisible && row.inventory_cost_value !== null
        ? numberFromString(String(row.inventory_cost_value))
        : numberFromString(String(row.on_hand_qty))
    ),
    0
  );

  return (
    <div className="dashboard-bar-list">
      {rows.map((row) => {
        const rawValue = financialVisible && row.inventory_cost_value !== null
          ? numberFromString(String(row.inventory_cost_value))
          : numberFromString(String(row.on_hand_qty));
        const width = maxValue > 0 ? Math.max(8, (rawValue / maxValue) * 100) : 0;
        return (
          <div key={row.product_id} className="dashboard-bar-row">
            <div className="dashboard-bar-meta">
              <strong>{row.product_name}</strong>
              <span>
                {financialVisible && row.inventory_cost_value !== null
                  ? compactMoney(row.inventory_cost_value)
                  : `${formatQuantity(row.on_hand_qty)} units`}
              </span>
            </div>
            <div className="dashboard-bar-track" aria-hidden="true">
              <span className="dashboard-bar-fill" style={{ width: `${width}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}


function ComboTrendChartRecharts({
  title,
  items,
  barLabel,
  lineLabel,
  moneyLine = false,
}: {
  title: string;
  items: ChartPoint[];
  barLabel: string;
  lineLabel: string;
  moneyLine?: boolean;
}) {
  if (items.length === 0) {
    return <div className="dashboard-chart-empty text-muted p-4">No data available</div>;
  }

  return (
    <div className="dashboard-chart-shell">
      <div className="dashboard-chart-legend flex items-center gap-4">
        <span className="flex items-center gap-1">
          <i className="legend-swatch bar w-2 h-2 bg-primary rounded" /> {barLabel}
        </span>
        <span className="flex items-center gap-1">
          <i className="legend-swatch line w-2 h-2 bg-info rounded" /> {lineLabel}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart
          data={items}
          margin={{ top: 20, right: 30, left: 0, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 244, 236, 0.12)" />
          <XAxis 
            dataKey="label" 
            tick={{ fontSize: 12, fill: '#aa9a8d' }} 
          />
          <YAxis 
            tick={{ fontSize: 12, fill: '#aa9a8d' }} 
          />
          <Tooltip
            labelFormatter={(value) => `${value}`}
            formatter={(value) => `$${Number(value).toLocaleString()}`}
            contentStyle={{ 
              backgroundColor: 'rgba(20, 16, 14, 0.94)', 
              padding: '8px', 
              borderRadius: '4px',
              color: '#f6efe8',
              border: '1px solid rgba(255, 244, 236, 0.12)',
              boxShadow: '0 10px 32px rgba(0, 0, 0, 0.28)'
            }}
            cursor={{ strokeWidth: 1 }}
          />
          <Legend 
            verticalAlign="top" 
            height={36} 
            formatter={(value) => value}
            labelStyle={{ fontSize: 12, fill: '#aa9a8d' }}
          />
          <Bar
            dataKey="bar"
            barSize={20}
            radius={[4, 4, 0, 0]}
            fill="#ff7a3d"
          />
          {moneyLine ? (
            <Line
              type="monotone"
              dataKey="line"
              stroke="#ffb38f"
              strokeWidth={2}
              dot={{ r: 4, strokeWidth: 2, stroke: '#17120f' }}
            />
          ) : (
            <Line
              type="monotone"
              dataKey="line"
              stroke={moneyLine ? '#ffb38f' : '#cdb49d'}
              strokeWidth={2}
              dot={{ r: 4, strokeWidth: 2, stroke: '#17120f' }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      <div className="dashboard-chart-caption flex items-center justify-between gap-4 text-sm text-muted flex-wrap">
        <span>{barLabel}: {compactNumber(items.reduce((sum, item) => sum + item.bar, 0))}</span>
        <span>
          {lineLabel}: {moneyLine
            ? compactMoney(items.reduce((sum, item) => sum + (item.line ?? 0), 0))
            : compactNumber(items.reduce((sum, item) => sum + (item.line ?? 0), 0))}
        </span>
      </div>
    </div>
  );
}


function StackedMovementChartRecharts({ items }: { items: DashboardStockMovementPoint[] }) {
  if (items.length === 0) {
    return <div className="dashboard-chart-empty text-muted p-4">No data available</div>;
  }

  const data = items.map(item => ({
    period: item.period,
    stock_received: numberFromString(String(item.stock_received)),
    sale_fulfilled: numberFromString(String(item.sale_fulfilled)),
    sales_return_restock: numberFromString(String(item.sales_return_restock)),
    adjustment: numberFromString(String(item.adjustment)),
  }));

  return (
    <div className="dashboard-chart-shell">
      <div className="dashboard-chart-legend flex items-center gap-4">
        <span className="flex items-center gap-1">
          <i className="legend-swatch received w-2 h-2 bg-green-600 rounded" /> Received</span>
        <span className="flex items-center gap-1">
          <i className="legend-swatch fulfilled w-2 h-2 bg-blue-600 rounded" /> Fulfilled</span>
        <span className="flex items-center gap-1">
          <i className="legend-swatch restocked w-2 h-2 bg-green-400 rounded" /> Restocked</span>
        <span className="flex items-center gap-1">
          <i className="legend-swatch adjusted w-2 h-2 bg-amber-400 rounded" /> Adjusted</span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart
          data={data}
          margin={{ top: 20, right: 30, left: 0, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 244, 236, 0.12)" />
          <XAxis 
            dataKey="period" 
            tick={{ fontSize: 12, fill: '#aa9a8d' }} 
          />
          <YAxis 
            tick={{ fontSize: 12, fill: '#aa9a8d' }} 
          />
          <Tooltip
            labelFormatter={(value) => `${value}`}
            formatter={(value) => `${Number(value).toLocaleString()}`}
            contentStyle={{ 
              backgroundColor: 'rgba(20, 16, 14, 0.94)', 
              padding: '8px', 
              borderRadius: '4px',
              color: '#f6efe8',
              border: '1px solid rgba(255, 244, 236, 0.12)',
              boxShadow: '0 10px 32px rgba(0, 0, 0, 0.28)'
            }}
          />
          <Legend 
            verticalAlign="top" 
            height={36} 
            formatter={(value) => value}
            labelStyle={{ fontSize: 12, fill: '#aa9a8d' }}
          />
          <Bar 
            dataKey="stock_received" 
            barSize={20} 
            radius={[4, 4, 0, 0]} 
            fill={MOVEMENT_COLORS.stock_received}
          />
          <Bar 
            dataKey="sale_fulfilled" 
            barSize={20} 
            radius={[4, 4, 0, 0]} 
            fill={MOVEMENT_COLORS.sale_fulfilled}
          />
          <Bar 
            dataKey="sales_return_restock" 
            barSize={20} 
            radius={[4, 4, 0, 0]} 
            fill={MOVEMENT_COLORS.sales_return_restock}
          />
          <Bar 
            dataKey="adjustment" 
            barSize={20} 
            radius={[4, 4, 0, 0]} 
            fill={MOVEMENT_COLORS.adjustment}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}


function OpportunityMatrixRecharts({ items }: { items: DashboardProductOpportunityPoint[] }) {
  if (items.length === 0) {
    return <div className="dashboard-chart-empty text-muted p-4">No data available</div>;
  }

  const chartData = items.map((item) => ({
    name: item.product_name,
    sales: numberFromString(String(item.sales_qty_per_day)),
    margin: numberFromString(String(item.estimated_margin_percent ?? 0)),
    inventoryCostValue: numberFromString(String(item.inventory_cost_value ?? 0)),
  }));

  return (
    <div className="dashboard-chart-shell">
      <ResponsiveContainer width="100%" height={260}>
        <ScatterChart
          margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 244, 236, 0.12)" />
          <XAxis 
            dataKey="sales"
            tick={{ fontSize: 12, fill: '#aa9a8d' }}
            label={{ value: 'Sales qty/day', position: 'insideBottom', offset: 30 }}
          />
          <YAxis 
            dataKey="margin"
            tick={{ fontSize: 12, fill: '#aa9a8d' }}
            label={{ value: 'Avg. margin %', position: 'insideLeft', offset: -40, angle: -90 }}
          />
          <ZAxis dataKey="inventoryCostValue" range={[80, 400]} name="Inventory cost value" />
          <Tooltip
            labelFormatter={(value) => `${value}`}
            formatter={(value, name) => 
              name === 'Inventory cost value' 
                ? `$${Number(value).toLocaleString()}` 
                : Number(value).toLocaleString()
            }
            contentStyle={{ 
              backgroundColor: 'rgba(20, 16, 14, 0.94)', 
              padding: '8px', 
              borderRadius: '4px',
              color: '#f6efe8',
              border: '1px solid rgba(255, 244, 236, 0.12)',
              boxShadow: '0 10px 32px rgba(0, 0, 0, 0.28)'
            }}
          />
          <Legend 
            verticalAlign="top" 
            height={36} 
            formatter={(value) => value}
            labelStyle={{ fontSize: 12, fill: '#aa9a8d' }}
          />
          <Scatter
            name="Products"
            data={chartData}
            fill="#ff7a3d"
            opacity={0.6}
            stroke="#17120f"
            strokeWidth={1}
          />
        </ScatterChart>
      </ResponsiveContainer>
      <div className="mt-2">
        <HoverHint
          text="Bubble size represents current inventory cost value. High-cover, high-margin products are the best price-test candidates."
          label="Opportunity matrix help"
        />
      </div>
    </div>
  );
}


function ActivityList({ items }: { items: DashboardRecentActivityItem[] }) {
  if (!items.length) {
    return <p className="text-muted">No recent ledger activity yet.</p>;
  }

  return (
    <ul className="activity-list space-y-2">
      {items.map((item) => (
        <li key={`${item.timestamp}-${item.label}`} className="flex items-start space-x-3">
          <div className="flex-1">
            <strong className="text-sm font-medium">{item.event_type}</strong>
            <p className="text-sm text-muted mt-0.5">{item.label}</p>
          </div>
          <div className="dashboard-activity-meta flex items-end space-x-3 text-xs text-muted">
            <span>{formatQuantity(item.quantity)}</span>
            <time dateTime={item.timestamp}>{formatDateTime(item.timestamp)}</time>
          </div>
        </li>
      ))}
    </ul>
  );
}


function SectionEmpty({
  message,
  reason,
}: {
  message: string;
  reason?: string | null;
}) {
  return <p className="text-muted">{reason ?? message}</p>;
}


export function DashboardAnalyticsWorkspace() {
  const [filters, setFilters] = useState<DashboardFilters>({ ...DEFAULT_FILTERS });
  const [customRange, setCustomRange] = useState({ from_date: '', to_date: '' });
  const [dashboard, setDashboard] = useState<DashboardAnalytics | null>(null);
  const [error, setError] = useState('');
  const [isPending, startTransition] = useTransition();

  const loadDashboard = (nextFilters: DashboardFilters) => {
    startTransition(async () => {
      try {
        const payload = await getDashboardAnalytics({
          rangeKey: nextFilters.range_key,
          fromDate: nextFilters.range_key === 'custom' ? nextFilters.from_date : undefined,
          toDate: nextFilters.range_key === 'custom' ? nextFilters.to_date : undefined,
          locationId: nextFilters.location_id || undefined,
        });
        setDashboard(payload);
        setError('');
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load dashboard analytics.');
      }
    });
  };

  useEffect(() => {
    loadDashboard(DEFAULT_FILTERS);
  }, []);

  const onRangeChange = (value: DashboardRangeKey) => {
    if (value === 'custom') {
      setFilters((current) => ({ ...current, range_key: 'custom' }));
      return;
    }
    const nextFilters = {
      ...filters,
      range_key: value,
      from_date: '',
      to_date: '',
    };
    setFilters(nextFilters);
    loadDashboard(nextFilters);
  };

  const onLocationChange = (value: string) => {
    const nextFilters = { ...filters, location_id: value };
    setFilters(nextFilters);
    if (nextFilters.range_key === 'custom' && (!nextFilters.from_date || !nextFilters.to_date)) {
      return;
    }
    loadDashboard(nextFilters);
  };

  const applyCustomRange = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!customRange.from_date || !customRange.to_date) return;
    const nextFilters = {
      ...filters,
      range_key: 'custom' as const,
      from_date: customRange.from_date,
      to_date: customRange.to_date,
    };
    setFilters(nextFilters);
    loadDashboard(nextFilters);
  };

  const financialVisible = dashboard?.visibility.can_view_financial_metrics ?? false;
  const revenueTrend = dashboard?.charts.revenue_profit_trend.items ?? [];
  const opportunityMatrix = dashboard?.charts.product_opportunity_matrix.items ?? [];
  const investmentRows = dashboard?.tables.stock_investment_by_product ?? [];
  const headlineKpi = dashboard?.kpis[0] ?? null;
  const gridKpis = dashboard?.kpis.slice(headlineKpi ? 1 : 0) ?? [];
  const actionLead = resolveActionLead(dashboard ?? null, financialVisible);

  return (
    <div className="dashboard-analytics space-y-6">
      <section className="section-card dashboard-hero-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover">
        <div className="foundation-hero">
          <p className="eyebrow text-xs text-muted uppercase tracking-wider">Business Analytics Dashboard</p>
          <h3 className="workspace-heading text-lg font-semibold mt-2">
            What to do now
            <HoverHint
              text="This dashboard blends completed sales, returns, purchase receipts, and variant-level inventory ledger movement so owners can monitor growth, pressure, and product opportunities."
              label="Dashboard controls help"
            />
          </h3>
          <article className="dashboard-action-lead bg-glass rounded-lg shadow-glass" aria-label="Dashboard first action">
            <span className="dashboard-action-eyebrow">Do this now</span>
            <strong className="dashboard-action-title">{actionLead.title}</strong>
            <p className="dashboard-action-summary">{actionLead.summary}</p>
            <div className="dashboard-action-links">
              <Link href={actionLead.href} className="dashboard-primary-action-link">
                {actionLead.cta}
              </Link>
              <Link href="/inventory" className="dashboard-secondary-action-link">
                Inventory workspace
              </Link>
              <Link href="/reports" className="dashboard-secondary-action-link">
                Reports
              </Link>
            </div>
          </article>
          {headlineKpi ? (
            <article className="dashboard-headline-kpi bg-glass rounded-lg shadow-glass" title={headlineKpi.help_text ?? undefined}>
              <p className="dashboard-headline-kpi-label text-xs text-muted">{headlineKpi.label}</p>
              <strong className="dashboard-headline-kpi-value">{metricValue(headlineKpi)}</strong>
              <span
                className={`dashboard-headline-kpi-delta delta-${headlineKpi.delta_direction ?? 'flat'} ${
                  headlineKpi.delta_direction === 'up'
                    ? 'text-green-600'
                    : headlineKpi.delta_direction === 'down'
                      ? 'text-red-600'
                      : 'text-muted'
                }`}
              >
                {metricDelta(headlineKpi)}
              </span>
            </article>
          ) : null}
        </div>
        <div className="dashboard-toolbar flex flex-wrap items-end justify-between gap-4 mt-4">
          <div className="dashboard-filters flex flex-wrap items-end gap-4">
            <label className="dashboard-filter flex flex-col">
              <span className="text-xs text-muted">Dashboard duration</span>
              <select
                aria-label="Dashboard duration"
                value={filters.range_key}
                onChange={(event) => onRangeChange(event.target.value as DashboardRangeKey)}
                className="border border-muted rounded-md bg-surface px-3 py-1 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 transition-normal w-full max-w-xs"
              >
                {RANGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="dashboard-filter flex flex-col">
              <span className="text-xs text-muted">Location</span>
              <select
                aria-label="Dashboard location"
                value={filters.location_id}
                onChange={(event) => onLocationChange(event.target.value)}
                className="border border-muted rounded-md bg-surface px-3 py-1 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 transition-normal w-full max-w-xs"
              >
                <option value="">All active locations</option>
                {(dashboard?.locations ?? []).map((location) => (
                  <option key={location.location_id} value={location.location_id}>
                    {location.name}
                  </option>
                ))}
              </select>
            </label>

            {filters.range_key === 'custom' ? (
              <form className="dashboard-custom-range flex flex-wrap items-end gap-3" onSubmit={applyCustomRange}>
                <label className="dashboard-filter flex flex-col">
                  <span className="text-xs text-muted">From</span>
                  <input
                    aria-label="Dashboard from date"
                    type="date"
                    value={customRange.from_date}
                    onChange={(event) => setCustomRange((current) => ({ ...current, from_date: event.target.value }))}
                    className="border border-muted rounded-md bg-surface px-3 py-1 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 transition-normal w-full max-w-xs"
                  />
                </label>
                <label className="dashboard-filter flex flex-col">
                  <span className="text-xs text-muted">To</span>
                  <input
                    aria-label="Dashboard to date"
                    type="date"
                    value={customRange.to_date}
                    onChange={(event) => setCustomRange((current) => ({ ...current, to_date: event.target.value }))}
                    className="border border-muted rounded-md bg-surface px-3 py-1 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 transition-normal w-full max-w-xs"
                  />
                </label>
                <button type="submit" className="btn-primary px-4 py-2">Apply</button>
              </form>
            ) : null}
          </div>

          <div className="dashboard-toolbar-meta flex flex-col items-end text-sm text-muted gap-1">
            <strong className="font-medium">{dashboard?.applied_range.label ?? 'Month to date'}</strong>
            <span>
              {dashboard
                ? `${dashboard.applied_range.from_date} to ${dashboard.applied_range.to_date} (${dashboard.applied_range.timezone})`
                : 'Loading selected range…'}
            </span>
            <span>Updated {dashboard ? formatDateTime(dashboard.generated_at) : 'now'}</span>
          </div>
        </div>
      </section>

      {error ? (
        <div className="dashboard-error bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-600">{error}</p>
          <button 
            type="button" 
            onClick={() => loadDashboard(filters)}
            className="btn-primary mt-2 px-4 py-2"
          >
            Retry
          </button>
        </div>
      ) : null}

      {isPending && !dashboard ? (
        <div className="dashboard-loading bg-glass p-6 rounded-lg shadow-glass flex items-center justify-center">
          <p className="text-muted">Loading business analytics dashboard…</p>
        </div>
      ) : null}

      {dashboard ? (
        <>
          <section className="kpi-grid dashboard-kpi-grid grid-cols-6 gap-4">
            {gridKpis.map((metric) => (
              <article 
                key={metric.id} 
                className="kpi-card dashboard-kpi-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover"
                title={metric.help_text ?? undefined}
              >
                <p className="kpi-label text-xs text-muted">{metric.label}</p>
                <h3 className="kpi-value text-2xl font-bold">{metricValue(metric)}</h3>
                <span 
                  className={`kpi-meta dashboard-kpi-meta mt-2 text-sm font-medium delta-${metric.delta_direction ?? 'flat'} ${
                    metric.delta_direction === 'up'
                      ? 'text-green-600'
                      : metric.delta_direction === 'down'
                        ? 'text-red-600'
                        : 'text-muted'
                  }`}
                >
                  {metricDelta(metric)}
                </span>
              </article>
            ))}
          </section>

          <section className="dashboard-insights grid-cols-5 gap-4">
            {dashboard.insight_cards.map((insight) => (
              <article 
                key={insight.id} 
                className={`insight-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover ${toneClass(insight.tone)}`}
              >
                <div className="flex flex-col justify-between h-full">
                  <div>
                    <h4 className="text-sm font-medium">{insight.metric_label}</h4>
                    <strong className="insight-metric-value text-xl font-bold block mt-2">{insight.metric_value}</strong>
                    <div className="mt-2">
                      <HoverHint
                        text={insight.unavailable_reason ?? insight.summary}
                        label={`${insight.metric_label} explanation`}
                      />
                    </div>
                    {insight.entity_name ? (
                      <span className="dashboard-insight-entity text-xs text-muted mt-2 block">{insight.entity_name}</span>
                    ) : null}
                  </div>
                  {insight.path ? (
                    <Link 
                      href={insight.path} 
                      className="insight-link mt-2 self-start"
                    >
                      Open
                    </Link>
                  ) : null}
                </div>
              </article>
            ))}
          </section>

          <section className="dashboard-grid dashboard-panel-grid dashboard-primary-panels grid-cols-1 gap-6 lg:grid-cols-2">
            <article className="section-card section-card-wide dashboard-section-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover col-span-1 lg:col-span-2">
              <div className="dashboard-section-head flex items-start justify-between gap-4">
                <div>
                  <p className="eyebrow text-xs text-muted uppercase tracking-wider">Stock Investment</p>
                  <h3 className="text-lg font-semibold mt-2">Stock by product</h3>
                </div>
                <Link href="/inventory" className="dashboard-inline-link text-primary font-medium hover:text-primary-dark transition-fast">Inventory workspace</Link>
              </div>
              <div className="dashboard-split-grid grid-cols-1 gap-6 lg:grid-cols-2">
                <HorizontalBarList rows={investmentRows.slice(0, 6)} financialVisible={financialVisible} />
                <div className="dashboard-table-wrap">
                  {investmentRows.length ? (
                    <table className="top-products-table w-full border-collapse">
                      <thead>
                        <tr>
                          <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Product</th>
                          <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">On hand</th>
                          <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Available</th>
                          {financialVisible ? (
                            <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Cost value</th>
                          ) : null}
                        </tr>
                      </thead>
                      <tbody>
                        {investmentRows.slice(0, 8).map((row) => (
                          <tr key={row.product_id} className="border-b">
                            <td className="px-3 py-2">{row.product_name}</td>
                            <td className="px-3 py-2">{formatQuantity(row.on_hand_qty)}</td>
                            <td className="px-3 py-2">{formatQuantity(row.available_qty)}</td>
                            {financialVisible ? (
                              <td className="px-3 py-2">{compactMoney(row.inventory_cost_value)}</td>
                            ) : null}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <SectionEmpty message="No stock has been posted yet." />
                  )}
                </div>
              </div>
            </article>

            {financialVisible ? (
              <article className="section-card dashboard-section-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover">
                <div className="dashboard-section-head flex items-start justify-between gap-4">
                  <div>
                    <p className="eyebrow text-xs text-muted uppercase tracking-wider">Sales Quality</p>
                    <h3 className="text-lg font-semibold mt-2">Revenue vs Estimated Gross Profit</h3>
                  </div>
                  <Link href="/sales" className="dashboard-inline-link text-primary font-medium hover:text-primary-dark transition-fast">Sales workspace</Link>
                </div>
                {dashboard.charts.revenue_profit_trend.items.length ? (
                  <ComboTrendChartRecharts
                    title="Revenue vs Estimated Gross Profit"
                    items={chartPoints(revenueTrend)}
                    barLabel="Revenue"
                    lineLabel="Estimated gross profit"
                    moneyLine
                  />
                ) : (
                  <SectionEmpty
                    message="No completed sales in the selected range."
                    reason={dashboard.charts.revenue_profit_trend.unavailable_reason}
                  />
                )}
              </article>
            ) : null}

            <article className="section-card dashboard-section-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover">
              <div className="dashboard-section-head flex items-start justify-between gap-4">
                <div>
                  <p className="eyebrow text-xs text-muted uppercase tracking-wider">Returns Drag</p>
                  <h3 className="text-lg font-semibold mt-2">Return volume and refund pressure</h3>
                </div>
                <Link href="/returns" className="dashboard-inline-link text-primary font-medium hover:text-primary-dark transition-fast">Returns workspace</Link>
              </div>
              {dashboard.charts.returns_trend.items.length ? (
                <ComboTrendChartRecharts
                  title="Returns trend"
                  items={chartPoints(dashboard.charts.returns_trend.items)}
                  barLabel="Returns count"
                  lineLabel={financialVisible ? 'Refund amount' : 'Refunds hidden'}
                  moneyLine={financialVisible}
                />
              ) : (
                <SectionEmpty message="No returns in the selected range." />
              )}
            </article>

            <article className="section-card dashboard-section-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover">
              <div className="dashboard-section-head flex items-start justify-between gap-4">
                <div>
                  <p className="eyebrow text-xs text-muted uppercase tracking-wider">Ledger Truth</p>
                  <h3 className="text-lg font-semibold mt-2">Stock movement trend</h3>
                </div>
                <Link href="/inventory?tab=stock" className="dashboard-inline-link text-primary font-medium hover:text-primary-dark transition-fast">Stock details</Link>
              </div>
              <StackedMovementChartRecharts items={dashboard.charts.stock_movement_trend} />
            </article>

            {financialVisible ? (
              <article className="section-card dashboard-section-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover">
                <div className="dashboard-section-head flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-lg font-semibold">Sales qty/day vs avg. margin</h3>
                  </div>
                  <Link href="/reports" className="dashboard-inline-link text-primary font-medium hover:text-primary-dark transition-fast">Reports</Link>
                </div>
                {opportunityMatrix.length ? (
                  <OpportunityMatrixRecharts items={opportunityMatrix.slice(0, 12)} />
                ) : (
                  <SectionEmpty
                    message="Complete a few fulfilled sales with cost data to unlock the opportunity matrix."
                    reason={dashboard.charts.product_opportunity_matrix.unavailable_reason}
                  />
                )}
              </article>
            ) : null}
          </section>

          <section className="dashboard-grid dashboard-panel-grid dashboard-secondary-panels grid-cols-1 gap-6 lg:grid-cols-2">
            <article className="section-card dashboard-section-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover">
              <div className="dashboard-section-head flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold">Variants needing attention</h3>
                </div>
                <Link href="/inventory?tab=low-stock" className="dashboard-inline-link text-primary font-medium hover:text-primary-dark transition-fast">Open low stock</Link>
              </div>
              {dashboard.tables.low_stock_variants.length ? (
                <table className="top-products-table w-full border-collapse">
                  <thead>
                    <tr>
                      <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Variant</th>
                      <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Available</th>
                      <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Reorder</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.tables.low_stock_variants.map((row) => (
                      <tr key={row.variant_id} className="border-b">
                        <td className="px-3 py-2">{row.label}</td>
                        <td className="px-3 py-2">{formatQuantity(row.available_qty)}</td>
                        <td className="px-3 py-2">{formatQuantity(row.reorder_level)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <SectionEmpty message="No variants are currently at or below their reorder threshold." />
              )}
            </article>

            <article className="section-card dashboard-section-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover">
              <div className="dashboard-section-head flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold">Top products by units sold</h3>
                </div>
                <Link href="/sales" className="dashboard-inline-link text-primary font-medium hover:text-primary-dark transition-fast">Open sales</Link>
              </div>
              {dashboard.tables.top_products_by_units_sold.length ? (
                <table className="top-products-table w-full border-collapse">
                  <thead>
                    <tr>
                      <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Product</th>
                      <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Units</th>
                      <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Revenue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.tables.top_products_by_units_sold.map((row) => (
                      <tr key={row.product_id} className="border-b">
                        <td className="px-3 py-2">{row.product_name}</td>
                        <td className="px-3 py-2">{formatQuantity(row.units_sold)}</td>
                        <td className="px-3 py-2">{financialVisible ? `$${formatMoney(row.revenue)}` : 'Hidden'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <SectionEmpty message="No completed sales in the selected range." />
              )}
            </article>

            {financialVisible ? (
              <article className="section-card dashboard-section-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover">
                <div className="dashboard-section-head flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-lg font-semibold">Top products by revenue</h3>
                  </div>
                  <Link href="/reports" className="dashboard-inline-link text-primary font-medium hover:text-primary-dark transition-fast">More analytics</Link>
                </div>
                {dashboard.tables.top_products_by_revenue.items.length ? (
                  <table className="top-products-table w-full border-collapse">
                    <thead>
                      <tr>
                        <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Product</th>
                        <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Revenue</th>
                        <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Units</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.tables.top_products_by_revenue.items.map((row) => (
                      <tr key={row.product_id} className="border-b">
                        <td className="px-3 py-2">{row.product_name}</td>
                        <td className="px-3 py-2">${formatMoney(row.revenue)}</td>
                        <td className="px-3 py-2">{formatQuantity(row.units_sold)}</td>
                      </tr>
                    ))}
                  </tbody>
                  </table>
                ) : (
                  <SectionEmpty
                    message="No revenue leaders to show yet."
                    reason={dashboard.tables.top_products_by_revenue.unavailable_reason}
                  />
                )}
              </article>
            ) : null}

            {financialVisible ? (
              <article className="section-card dashboard-section-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover">
                <div className="dashboard-section-head flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-lg font-semibold">Top products by estimated gross profit</h3>
                  </div>
                  <Link href="/catalog" className="dashboard-inline-link text-primary font-medium hover:text-primary-dark transition-fast">Catalog & pricing</Link>
                </div>
                {dashboard.tables.top_products_by_estimated_gross_profit.items.length ? (
                  <table className="top-products-table w-full border-collapse">
                    <thead>
                      <tr>
                        <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Product</th>
                        <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Est. GP</th>
                        <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Margin</th>
                      </tr>
                  </thead>
                  <tbody>
                    {dashboard.tables.top_products_by_estimated_gross_profit.items.map((row) => (
                      <tr key={row.product_id} className="border-b">
                        <td className="px-3 py-2">{row.product_name}</td>
                        <td className="px-3 py-2">{row.estimated_gross_profit !== null ? `$${formatMoney(row.estimated_gross_profit)}` : 'Not enough cost data'}</td>
                        <td className="px-3 py-2">{row.estimated_margin_percent !== null ? formatPercent(row.estimated_margin_percent) : 'Not enough cost data'}</td>
                      </tr>
                    ))}
                  </tbody>
                  </table>
                ) : (
                  <SectionEmpty
                    message="Estimated gross profit will appear once fulfilled sales have cost data."
                    reason={dashboard.tables.top_products_by_estimated_gross_profit.unavailable_reason}
                  />
                )}
              </article>
            ) : null}

            <article className="section-card dashboard-section-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover">
              <div className="dashboard-section-head flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold">Products with stock but no sales</h3>
                </div>
                <Link href="/inventory" className="dashboard-inline-link text-primary font-medium hover:text-primary-dark transition-fast">Review stock</Link>
              </div>
                {dashboard.tables.slow_movers.length ? (
                  <table className="top-products-table w-full border-collapse">
                    <thead>
                      <tr>
                        <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Product</th>
                      <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Available</th>
                      {financialVisible ? (
                        <th className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider border-b">Cost value</th>
                      ) : null}
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.tables.slow_movers.map((row) => (
                      <tr key={row.product_id} className="border-b">
                        <td className="px-3 py-2">{row.product_name}</td>
                        <td className="px-3 py-2">{formatQuantity(row.available_qty)}</td>
                        {financialVisible ? (
                          <td className="px-3 py-2">{compactMoney(row.inventory_cost_value)}</td>
                        ) : null}
                      </tr>
                    ))}
                  </tbody>
                  </table>
                ) : (
                  <SectionEmpty message="No slow movers in the selected range." />
                )}
            </article>

            <article className="section-card dashboard-section-card bg-glass p-6 rounded-lg shadow-glass transition-normal hover:shadow-glass-hover">
              <div className="dashboard-section-head flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold">Latest inventory and fulfillment events</h3>
                </div>
                <Link href="/inventory" className="dashboard-inline-link text-primary font-medium hover:text-primary-dark transition-fast">Open inventory</Link>
              </div>
              <ActivityList items={dashboard.tables.recent_activity} />
            </article>
          </section>
          <div className="mobile-action-safe-spacer" aria-hidden="true" />
        </>
      ) : null}
    </div>
  );
}
