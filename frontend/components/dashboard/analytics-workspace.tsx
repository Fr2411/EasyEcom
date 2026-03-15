'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState, useTransition } from 'react';
import { formatDateTime, formatMoney, formatPercent, formatQuantity, numberFromString } from '@/lib/commerce-format';
import { getDashboardAnalytics } from '@/lib/api/dashboard';
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
  stock_received: '#0f766e',
  sale_fulfilled: '#1d4ed8',
  sales_return_restock: '#16a34a',
  adjustment: '#f59e0b',
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


function ComboTrendChart({
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
  const width = 640;
  const height = 220;
  const padding = 26;
  const chartHeight = 150;
  const chartWidth = width - padding * 2;
  const maxValue = Math.max(
    ...items.flatMap((item) => [item.bar, item.line ?? 0]),
    0
  );
  const slotWidth = items.length ? chartWidth / items.length : 0;
  const barWidth = Math.min(32, Math.max(12, slotWidth * 0.45));
  const linePoints = items
    .map((item, index) => {
      if (item.line === null || item.line === undefined || maxValue <= 0) return null;
      const x = padding + slotWidth * index + slotWidth / 2;
      const y = padding + chartHeight - (item.line / maxValue) * chartHeight;
      return `${x},${y}`;
    })
    .filter(Boolean)
    .join(' ');

  return (
    <div className="dashboard-chart-shell">
      <div className="dashboard-chart-legend">
        <span><i className="legend-swatch bar" /> {barLabel}</span>
        <span><i className="legend-swatch line" /> {lineLabel}</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="dashboard-svg-chart" role="img" aria-label={title}>
        <line x1={padding} x2={width - padding} y1={padding + chartHeight} y2={padding + chartHeight} className="chart-axis" />
        {items.map((item, index) => {
          const x = padding + slotWidth * index + (slotWidth - barWidth) / 2;
          const barHeight = maxValue > 0 ? (item.bar / maxValue) * chartHeight : 0;
          const y = padding + chartHeight - barHeight;
          return (
            <g key={item.label}>
              <rect x={x} y={y} width={barWidth} height={barHeight} rx="4" className="chart-bar" />
              <text x={x + barWidth / 2} y={padding + chartHeight + 18} textAnchor="middle" className="chart-label">
                {item.label}
              </text>
            </g>
          );
        })}
        {linePoints ? <polyline points={linePoints} fill="none" className="chart-line" /> : null}
        {items.map((item, index) => {
          if (item.line === null || item.line === undefined || maxValue <= 0) return null;
          const x = padding + slotWidth * index + slotWidth / 2;
          const y = padding + chartHeight - (item.line / maxValue) * chartHeight;
          return <circle key={`${item.label}-point`} cx={x} cy={y} r="4" className="chart-point" />;
        })}
      </svg>
      <div className="dashboard-chart-caption">
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


function StackedMovementChart({ items }: { items: DashboardStockMovementPoint[] }) {
  const width = 640;
  const height = 220;
  const padding = 26;
  const chartHeight = 150;
  const chartWidth = width - padding * 2;
  const slotWidth = items.length ? chartWidth / items.length : 0;
  const barWidth = Math.min(34, Math.max(14, slotWidth * 0.48));
  const totals = items.map((item) =>
    ['stock_received', 'sale_fulfilled', 'sales_return_restock', 'adjustment']
      .reduce((sum, key) => sum + numberFromString(String(item[key as keyof DashboardStockMovementPoint])), 0)
  );
  const maxTotal = Math.max(...totals, 0);

  return (
    <div className="dashboard-chart-shell">
      <div className="dashboard-chart-legend">
        <span><i className="legend-swatch received" /> Received</span>
        <span><i className="legend-swatch fulfilled" /> Fulfilled</span>
        <span><i className="legend-swatch restocked" /> Restocked</span>
        <span><i className="legend-swatch adjusted" /> Adjusted</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="dashboard-svg-chart" role="img" aria-label="Stock movement trend">
        <line x1={padding} x2={width - padding} y1={padding + chartHeight} y2={padding + chartHeight} className="chart-axis" />
        {items.map((item, index) => {
          const x = padding + slotWidth * index + (slotWidth - barWidth) / 2;
          const segments = [
            ['stock_received', numberFromString(String(item.stock_received))],
            ['sale_fulfilled', numberFromString(String(item.sale_fulfilled))],
            ['sales_return_restock', numberFromString(String(item.sales_return_restock))],
            ['adjustment', numberFromString(String(item.adjustment))],
          ] as const;
          let runningY = padding + chartHeight;

          return (
            <g key={item.period}>
              {segments.map(([key, value]) => {
                const segmentHeight = maxTotal > 0 ? (value / maxTotal) * chartHeight : 0;
                runningY -= segmentHeight;
                return (
                  <rect
                    key={`${item.period}-${key}`}
                    x={x}
                    y={runningY}
                    width={barWidth}
                    height={segmentHeight}
                    rx="4"
                    fill={MOVEMENT_COLORS[key]}
                  />
                );
              })}
              <text x={x + barWidth / 2} y={padding + chartHeight + 18} textAnchor="middle" className="chart-label">
                {item.period}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}


function OpportunityMatrix({ items }: { items: DashboardProductOpportunityPoint[] }) {
  const width = 640;
  const height = 260;
  const padding = 40;
  const maxX = Math.max(...items.map((item) => numberFromString(String(item.sales_qty_per_day))), 0.1);
  const maxY = Math.max(...items.map((item) => numberFromString(String(item.estimated_margin_percent ?? 0))), 1);
  const maxBubble = Math.max(...items.map((item) => numberFromString(String(item.inventory_cost_value ?? 0))), 1);

  return (
    <div className="dashboard-chart-shell">
      <svg viewBox={`0 0 ${width} ${height}`} className="dashboard-svg-chart" role="img" aria-label="Product opportunity matrix">
        <line x1={padding} x2={width - padding} y1={height - padding} y2={height - padding} className="chart-axis" />
        <line x1={padding} x2={padding} y1={padding} y2={height - padding} className="chart-axis" />
        <line x1={padding} x2={width - padding} y1={(height - padding + padding) / 2} y2={(height - padding + padding) / 2} className="chart-grid" />
        <line x1={(width - padding + padding) / 2} x2={(width - padding + padding) / 2} y1={padding} y2={height - padding} className="chart-grid" />
        {items.map((item) => {
          const x = padding + (numberFromString(String(item.sales_qty_per_day)) / maxX) * (width - padding * 2);
          const y = height - padding - ((numberFromString(String(item.estimated_margin_percent ?? 0)) / maxY) * (height - padding * 2));
          const radius = 8 + (numberFromString(String(item.inventory_cost_value ?? 0)) / maxBubble) * 18;
          return (
            <g key={item.product_id}>
              <circle cx={x} cy={y} r={radius} className="opportunity-bubble" />
              <text x={x} y={y + 4} textAnchor="middle" className="bubble-label">
                {item.product_name.slice(0, 8)}
              </text>
            </g>
          );
        })}
        <text x={width / 2} y={height - 8} textAnchor="middle" className="chart-label">Sales qty/day</text>
        <text x={16} y={height / 2} textAnchor="middle" className="chart-label" transform={`rotate(-90 16 ${height / 2})`}>
          Avg. margin %
        </text>
      </svg>
    </div>
  );
}


function ActivityList({ items }: { items: DashboardRecentActivityItem[] }) {
  if (!items.length) {
    return <p className="muted">No recent ledger activity yet.</p>;
  }

  return (
    <ul className="activity-list">
      {items.map((item) => (
        <li key={`${item.timestamp}-${item.label}`}>
          <div>
            <strong>{item.event_type}</strong>
            <p>{item.label}</p>
          </div>
          <div className="dashboard-activity-meta">
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
  return <p className="muted">{reason ?? message}</p>;
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

  return (
    <div className="dashboard-analytics">
      <section className="section-card dashboard-hero-card">
        <div className="foundation-hero">
          <p className="eyebrow">Business Analytics Dashboard</p>
          <h3>MTD by default, with product, stock, and margin intelligence built from transactional truth.</h3>
          <p>
            This view blends completed sales, returns, purchase receipts, and variant-level inventory ledger movement so
            owners can spot growth, pressure, and product opportunities early.
          </p>
        </div>
        <div className="dashboard-toolbar">
          <div className="dashboard-filters">
            <label className="dashboard-filter">
              <span>Dashboard duration</span>
              <select
                aria-label="Dashboard duration"
                value={filters.range_key}
                onChange={(event) => onRangeChange(event.target.value as DashboardRangeKey)}
              >
                {RANGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="dashboard-filter">
              <span>Location</span>
              <select
                aria-label="Dashboard location"
                value={filters.location_id}
                onChange={(event) => onLocationChange(event.target.value)}
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
              <form className="dashboard-custom-range" onSubmit={applyCustomRange}>
                <label className="dashboard-filter">
                  <span>From</span>
                  <input
                    aria-label="Dashboard from date"
                    type="date"
                    value={customRange.from_date}
                    onChange={(event) => setCustomRange((current) => ({ ...current, from_date: event.target.value }))}
                  />
                </label>
                <label className="dashboard-filter">
                  <span>To</span>
                  <input
                    aria-label="Dashboard to date"
                    type="date"
                    value={customRange.to_date}
                    onChange={(event) => setCustomRange((current) => ({ ...current, to_date: event.target.value }))}
                  />
                </label>
                <button type="submit">Apply</button>
              </form>
            ) : null}
          </div>

          <div className="dashboard-toolbar-meta">
            <strong>{dashboard?.applied_range.label ?? 'Month to date'}</strong>
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
        <div className="dashboard-error">
          <p>{error}</p>
          <button type="button" onClick={() => loadDashboard(filters)}>Retry</button>
        </div>
      ) : null}

      {isPending && !dashboard ? <div className="dashboard-loading">Loading business analytics dashboard…</div> : null}

      {dashboard ? (
        <>
          <section className="kpi-grid dashboard-kpi-grid">
            {dashboard.kpis.map((metric) => (
              <article key={metric.id} className="kpi-card dashboard-kpi-card" title={metric.help_text ?? undefined}>
                <p>{metric.label}</p>
                <h3>{metricValue(metric)}</h3>
                <span className={`kpi-meta dashboard-kpi-meta delta-${metric.delta_direction ?? 'flat'}`}>
                  {metricDelta(metric)}
                </span>
              </article>
            ))}
          </section>

          <section className="dashboard-insights">
            {dashboard.insight_cards.map((insight) => (
              <article key={insight.id} className={toneClass(insight.tone)}>
                <div>
                  <p className="eyebrow">{insight.title}</p>
                  <h4>{insight.metric_label}</h4>
                  <strong>{insight.metric_value}</strong>
                  <p>{insight.unavailable_reason ?? insight.summary}</p>
                  {insight.entity_name ? <span className="dashboard-insight-entity">{insight.entity_name}</span> : null}
                </div>
                {insight.path ? (
                  <Link href={insight.path} className="dashboard-inline-link">
                    Open
                  </Link>
                ) : null}
              </article>
            ))}
          </section>

          <section className="dashboard-grid dashboard-panel-grid">
            <article className="section-card section-card-wide dashboard-section-card">
              <div className="dashboard-section-head">
                <div>
                  <p className="eyebrow">Stock Investment</p>
                  <h3>Stock by product</h3>
                </div>
                <Link href="/inventory" className="dashboard-inline-link">Inventory workspace</Link>
              </div>
              <div className="dashboard-split-grid">
                <HorizontalBarList rows={investmentRows.slice(0, 6)} financialVisible={financialVisible} />
                <div className="dashboard-table-wrap">
                  {investmentRows.length ? (
                    <table className="top-products-table">
                      <thead>
                        <tr>
                          <th>Product</th>
                          <th>On hand</th>
                          <th>Available</th>
                          {financialVisible ? <th>Cost value</th> : null}
                        </tr>
                      </thead>
                      <tbody>
                        {investmentRows.slice(0, 8).map((row) => (
                          <tr key={row.product_id}>
                            <td>{row.product_name}</td>
                            <td>{formatQuantity(row.on_hand_qty)}</td>
                            <td>{formatQuantity(row.available_qty)}</td>
                            {financialVisible ? <td>{compactMoney(row.inventory_cost_value)}</td> : null}
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
              <article className="section-card dashboard-section-card">
                <div className="dashboard-section-head">
                  <div>
                    <p className="eyebrow">Sales Quality</p>
                    <h3>Revenue vs Estimated Gross Profit</h3>
                  </div>
                  <Link href="/sales" className="dashboard-inline-link">Sales workspace</Link>
                </div>
                {dashboard.charts.revenue_profit_trend.items.length ? (
                  <ComboTrendChart
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

            <article className="section-card dashboard-section-card">
              <div className="dashboard-section-head">
                <div>
                  <p className="eyebrow">Returns Drag</p>
                  <h3>Return volume and refund pressure</h3>
                </div>
                <Link href="/returns" className="dashboard-inline-link">Returns workspace</Link>
              </div>
              {dashboard.charts.returns_trend.items.length ? (
                <ComboTrendChart
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

            <article className="section-card dashboard-section-card">
              <div className="dashboard-section-head">
                <div>
                  <p className="eyebrow">Ledger Truth</p>
                  <h3>Stock movement trend</h3>
                </div>
                <Link href="/inventory?tab=stock" className="dashboard-inline-link">Stock details</Link>
              </div>
              <StackedMovementChart items={dashboard.charts.stock_movement_trend} />
            </article>

            {financialVisible ? (
              <article className="section-card dashboard-section-card">
                <div className="dashboard-section-head">
                  <div>
                    <p className="eyebrow">Opportunity Matrix</p>
                    <h3>Sales qty/day vs avg. margin</h3>
                  </div>
                  <Link href="/reports" className="dashboard-inline-link">Reports</Link>
                </div>
                {opportunityMatrix.length ? (
                  <>
                    <OpportunityMatrix items={opportunityMatrix.slice(0, 12)} />
                    <p className="muted">
                      Bubble size represents current inventory cost value. High-cover, high-margin products are the best
                      price-test candidates.
                    </p>
                  </>
                ) : (
                  <SectionEmpty
                    message="Complete a few fulfilled sales with cost data to unlock the opportunity matrix."
                    reason={dashboard.charts.product_opportunity_matrix.unavailable_reason}
                  />
                )}
              </article>
            ) : null}
          </section>

          <section className="dashboard-grid dashboard-panel-grid">
            <article className="section-card dashboard-section-card">
              <div className="dashboard-section-head">
                <div>
                  <p className="eyebrow">Low Stock</p>
                  <h3>Variants needing attention</h3>
                </div>
                <Link href="/inventory?tab=low-stock" className="dashboard-inline-link">Open low stock</Link>
              </div>
              {dashboard.tables.low_stock_variants.length ? (
                <table className="top-products-table">
                  <thead>
                    <tr>
                      <th>Variant</th>
                      <th>Available</th>
                      <th>Reorder</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.tables.low_stock_variants.map((row) => (
                      <tr key={row.variant_id}>
                        <td>{row.label}</td>
                        <td>{formatQuantity(row.available_qty)}</td>
                        <td>{formatQuantity(row.reorder_level)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <SectionEmpty message="No variants are currently at or below their reorder threshold." />
              )}
            </article>

            <article className="section-card dashboard-section-card">
              <div className="dashboard-section-head">
                <div>
                  <p className="eyebrow">Volume Leaders</p>
                  <h3>Top products by units sold</h3>
                </div>
                <Link href="/sales" className="dashboard-inline-link">Open sales</Link>
              </div>
              {dashboard.tables.top_products_by_units_sold.length ? (
                <table className="top-products-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Units</th>
                      <th>Revenue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.tables.top_products_by_units_sold.map((row) => (
                      <tr key={row.product_id}>
                        <td>{row.product_name}</td>
                        <td>{formatQuantity(row.units_sold)}</td>
                        <td>{financialVisible ? `$${formatMoney(row.revenue)}` : 'Hidden'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <SectionEmpty message="No completed sales in the selected range." />
              )}
            </article>

            {financialVisible ? (
              <article className="section-card dashboard-section-card">
                <div className="dashboard-section-head">
                  <div>
                    <p className="eyebrow">Revenue Leaders</p>
                    <h3>Top products by revenue</h3>
                  </div>
                  <Link href="/reports" className="dashboard-inline-link">More analytics</Link>
                </div>
                {dashboard.tables.top_products_by_revenue.items.length ? (
                  <table className="top-products-table">
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>Revenue</th>
                        <th>Units</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboard.tables.top_products_by_revenue.items.map((row) => (
                        <tr key={row.product_id}>
                          <td>{row.product_name}</td>
                          <td>${formatMoney(row.revenue)}</td>
                          <td>{formatQuantity(row.units_sold)}</td>
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
              <article className="section-card dashboard-section-card">
                <div className="dashboard-section-head">
                  <div>
                    <p className="eyebrow">Margin Leaders</p>
                    <h3>Top products by estimated gross profit</h3>
                  </div>
                  <Link href="/catalog" className="dashboard-inline-link">Catalog & pricing</Link>
                </div>
                {dashboard.tables.top_products_by_estimated_gross_profit.items.length ? (
                  <table className="top-products-table">
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>Est. GP</th>
                        <th>Margin</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboard.tables.top_products_by_estimated_gross_profit.items.map((row) => (
                        <tr key={row.product_id}>
                          <td>{row.product_name}</td>
                          <td>{row.estimated_gross_profit !== null ? `$${formatMoney(row.estimated_gross_profit)}` : 'Not enough cost data'}</td>
                          <td>{row.estimated_margin_percent !== null ? formatPercent(row.estimated_margin_percent) : 'Not enough cost data'}</td>
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

            <article className="section-card dashboard-section-card">
              <div className="dashboard-section-head">
                <div>
                  <p className="eyebrow">Slow Movers</p>
                  <h3>Products with stock but no sales</h3>
                </div>
                <Link href="/inventory" className="dashboard-inline-link">Review stock</Link>
              </div>
              {dashboard.tables.slow_movers.length ? (
                <table className="top-products-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Available</th>
                      {financialVisible ? <th>Cost value</th> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.tables.slow_movers.map((row) => (
                      <tr key={row.product_id}>
                        <td>{row.product_name}</td>
                        <td>{formatQuantity(row.available_qty)}</td>
                        {financialVisible ? <td>{compactMoney(row.inventory_cost_value)}</td> : null}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <SectionEmpty message="No slow movers in the selected range." />
              )}
            </article>

            <article className="section-card dashboard-section-card">
              <div className="dashboard-section-head">
                <div>
                  <p className="eyebrow">Recent Activity</p>
                  <h3>Latest inventory and fulfillment events</h3>
                </div>
                <Link href="/inventory" className="dashboard-inline-link">Open inventory</Link>
              </div>
              <ActivityList items={dashboard.tables.recent_activity} />
            </article>
          </section>
        </>
      ) : null}
    </div>
  );
}
