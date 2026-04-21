'use client';

import Link from 'next/link';
import {
  FormEvent,
  Fragment,
  useEffect,
  useMemo,
  useState,
  useTransition,
  type DragEvent,
} from 'react';
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  Treemap,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import { getDashboardAnalytics } from '@/lib/api/dashboard';
import { formatDateTime, formatMoney, formatPercent, formatQuantity, numberFromString } from '@/lib/commerce-format';
import type {
  DashboardAnalytics,
  DashboardMetric,
  DashboardPriceDiscountImpactPoint,
  DashboardRangeKey,
  DashboardReorderPriorityRow,
} from '@/types/dashboard';
import styles from './analytics-workspace.module.css';


type DashboardFilters = {
  range_key: DashboardRangeKey;
  location_id: string;
  from_date: string;
  to_date: string;
};

type WidgetId =
  | 'revenue_orders_aov'
  | 'gross_profit_margin'
  | 'conversion_funnel'
  | 'product_performance_quadrant'
  | 'category_brand_profit_mix'
  | 'returns_intelligence'
  | 'inventory_aging_waterfall'
  | 'sell_through_cover_matrix'
  | 'reorder_priority_scoreboard'
  | 'price_discount_impact';

type WidgetColumn = 'left' | 'right';

type WidgetLayout = {
  left: WidgetId[];
  right: WidgetId[];
  hidden: WidgetId[];
};

const WIDGET_STORAGE_KEY = 'easyecom.dashboard.widgets.v2';

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

const WIDGET_IDS: WidgetId[] = [
  'revenue_orders_aov',
  'gross_profit_margin',
  'conversion_funnel',
  'product_performance_quadrant',
  'category_brand_profit_mix',
  'returns_intelligence',
  'inventory_aging_waterfall',
  'sell_through_cover_matrix',
  'reorder_priority_scoreboard',
  'price_discount_impact',
];

const WIDGET_META: Record<WidgetId, { title: string; subtitle: string }> = {
  revenue_orders_aov: {
    title: 'Revenue + Orders + AOV Trend',
    subtitle: 'Daily/weekly revenue, completed orders, and basket size.',
  },
  gross_profit_margin: {
    title: 'Gross Profit & Margin Trend',
    subtitle: 'Revenue vs estimated gross profit with margin band.',
  },
  conversion_funnel: {
    title: 'Conversion Funnel',
    subtitle: 'Inquiry to draft, reserved, and completed conversion.',
  },
  product_performance_quadrant: {
    title: 'Product Performance Quadrant',
    subtitle: 'Velocity vs margin with revenue-weighted bubbles.',
  },
  category_brand_profit_mix: {
    title: 'Category/Brand Profit Mix',
    subtitle: 'Treemap of segments driving revenue and margin.',
  },
  returns_intelligence: {
    title: 'Returns Intelligence',
    subtitle: 'Return-rate trend and reason heatmap by product.',
  },
  inventory_aging_waterfall: {
    title: 'Inventory Aging & Dead Stock',
    subtitle: 'Stock value by aging bucket and net period change.',
  },
  sell_through_cover_matrix: {
    title: 'Sell-through vs Days of Cover',
    subtitle: 'Spot stockout risk and overstock zones fast.',
  },
  reorder_priority_scoreboard: {
    title: 'Reorder Priority Scoreboard',
    subtitle: 'Top candidates ranked by urgency score.',
  },
  price_discount_impact: {
    title: 'Price/Discount Impact Analysis',
    subtitle: 'Discount level vs unit lift and margin outcome.',
  },
};

const CHART_COLORS = {
  revenue: '#ff6a1a',
  orders: '#2f8fff',
  aov: '#2ccf9d',
  profit: '#56d6ae',
  margin: '#f5b35c',
  neutral: '#9aa7b8',
  warning: '#f97316',
  critical: '#ef4444',
  positive: '#34d399',
};

const DEFAULT_LAYOUT: WidgetLayout = normalizeWidgetLayout({
  left: [
    'revenue_orders_aov',
    'conversion_funnel',
    'category_brand_profit_mix',
    'inventory_aging_waterfall',
    'reorder_priority_scoreboard',
  ],
  right: [
    'gross_profit_margin',
    'product_performance_quadrant',
    'returns_intelligence',
    'sell_through_cover_matrix',
    'price_discount_impact',
  ],
  hidden: [],
});

function isWidgetId(value: unknown): value is WidgetId {
  return typeof value === 'string' && WIDGET_IDS.includes(value as WidgetId);
}

function normalizeWidgetLayout(input: Partial<WidgetLayout> | null | undefined): WidgetLayout {
  const seen = new Set<WidgetId>();

  const normalizeColumn = (values: unknown): WidgetId[] => {
    if (!Array.isArray(values)) return [];
    const normalized: WidgetId[] = [];
    for (const value of values) {
      if (!isWidgetId(value) || seen.has(value)) continue;
      seen.add(value);
      normalized.push(value);
    }
    return normalized;
  };

  const left = normalizeColumn(input?.left);
  const right = normalizeColumn(input?.right);

  for (const widgetId of WIDGET_IDS) {
    if (seen.has(widgetId)) continue;
    if (left.length <= right.length) {
      left.push(widgetId);
    } else {
      right.push(widgetId);
    }
    seen.add(widgetId);
  }

  const hidden = Array.isArray(input?.hidden)
    ? Array.from(new Set(input?.hidden.filter((value): value is WidgetId => isWidgetId(value))))
    : [];

  return {
    left,
    right,
    hidden,
  };
}

function moneyCompact(value: number) {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

function numberCompact(value: number) {
  return new Intl.NumberFormat(undefined, {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

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

function EmptyState({ reason }: { reason?: string | null }) {
  return <div className={styles.emptyState}>{reason ?? 'No data available for this range.'}</div>;
}

function tooltipStyle() {
  return {
    backgroundColor: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 12,
    color: 'var(--text)',
  };
}

function shortName(name: string, max = 18) {
  return name.length <= max ? name : `${name.slice(0, max - 1)}…`;
}

function zoneLabel(zone: string) {
  if (zone === 'low_cover_high_velocity') return 'Low cover + high velocity';
  if (zone === 'high_cover_low_velocity') return 'High cover + low velocity';
  if (zone === 'healthy') return 'Healthy';
  return 'Watch';
}

function recommendationLabel(value: DashboardPriceDiscountImpactPoint['recommendation']) {
  if (value === 'raise') return 'Raise';
  if (value === 'discount') return 'Discount';
  return 'Keep';
}

function actionTone(value: DashboardReorderPriorityRow['recommended_action']) {
  if (value === 'Reorder now') return styles.actionCritical;
  if (value === 'Plan reorder') return styles.actionWarning;
  return styles.actionNeutral;
}

export function DashboardAnalyticsWorkspace() {
  const [filters, setFilters] = useState<DashboardFilters>({ ...DEFAULT_FILTERS });
  const [customRange, setCustomRange] = useState({ from_date: '', to_date: '' });
  const [dashboard, setDashboard] = useState<DashboardAnalytics | null>(null);
  const [error, setError] = useState('');
  const [isPending, startTransition] = useTransition();
  const [layout, setLayout] = useState<WidgetLayout>(DEFAULT_LAYOUT);
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const [draggingWidget, setDraggingWidget] = useState<WidgetId | null>(null);

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

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const raw = window.localStorage.getItem(WIDGET_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as Partial<WidgetLayout>;
      setLayout(normalizeWidgetLayout(parsed));
    } catch {
      setLayout(DEFAULT_LAYOUT);
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(WIDGET_STORAGE_KEY, JSON.stringify(layout));
  }, [layout]);

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

  const moveWidget = (widgetId: WidgetId, targetColumn: WidgetColumn, targetIndex: number) => {
    setLayout((current) => {
      const left = current.left.filter((item) => item !== widgetId);
      const right = current.right.filter((item) => item !== widgetId);
      const target = targetColumn === 'left' ? [...left] : [...right];
      const safeIndex = Math.max(0, Math.min(targetIndex, target.length));
      target.splice(safeIndex, 0, widgetId);

      return normalizeWidgetLayout(
        targetColumn === 'left'
          ? { ...current, left: target, right }
          : { ...current, left, right: target }
      );
    });
  };

  const toggleWidget = (widgetId: WidgetId) => {
    setLayout((current) => {
      const isHidden = current.hidden.includes(widgetId);
      if (isHidden) {
        return {
          ...current,
          hidden: current.hidden.filter((item) => item !== widgetId),
        };
      }
      return {
        ...current,
        hidden: [...current.hidden, widgetId],
      };
    });
  };

  const resetLayout = () => {
    setLayout(DEFAULT_LAYOUT);
  };

  const onDropToColumn = (event: DragEvent<HTMLDivElement>, column: WidgetColumn, index: number) => {
    event.preventDefault();
    if (!draggingWidget) return;
    moveWidget(draggingWidget, column, index);
    setDraggingWidget(null);
  };

  const hiddenSet = useMemo(() => new Set(layout.hidden), [layout.hidden]);
  const visibleLeft = layout.left.filter((widgetId) => !hiddenSet.has(widgetId));
  const visibleRight = layout.right.filter((widgetId) => !hiddenSet.has(widgetId));

  const financialVisible = dashboard?.visibility.can_view_financial_metrics ?? false;
  const kpis = dashboard?.kpis ?? [];

  const renderWidget = (widgetId: WidgetId) => {
    if (!dashboard) return <EmptyState reason="Loading chart data..." />;

    if (widgetId === 'revenue_orders_aov') {
      const points = dashboard.charts.revenue_orders_aov_trend.items.map((item) => ({
        period: item.period,
        revenue: numberFromString(String(item.revenue)),
        orders: item.orders,
        aov: numberFromString(String(item.aov)),
        anomaly: item.anomaly_flag,
      }));
      if (!points.length) return <EmptyState />;
      const anomalies = points.filter((item) => item.anomaly);
      return (
        <>
          <div className={styles.chartWrap}>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={points} margin={{ top: 16, right: 12, left: 2, bottom: 4 }}>
                <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" />
                <XAxis dataKey="period" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                <YAxis
                  yAxisId="left"
                  tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                  tickFormatter={(value) => `${numberCompact(value)}`}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                />
                <Tooltip contentStyle={tooltipStyle()} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line yAxisId="left" dataKey="revenue" type="monotone" stroke={CHART_COLORS.revenue} strokeWidth={2.4} dot={false} name="Revenue" />
                <Line yAxisId="right" dataKey="orders" type="monotone" stroke={CHART_COLORS.orders} strokeWidth={2.2} dot={false} name="Orders" />
                <Line yAxisId="left" dataKey="aov" type="monotone" stroke={CHART_COLORS.aov} strokeWidth={2.2} dot={false} name="AOV" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          {anomalies.length ? (
            <div className={styles.chartNote}>Anomaly flag: {anomalies.map((item) => item.period).join(', ')}</div>
          ) : (
            <div className={styles.chartNote}>No anomaly spikes in this range.</div>
          )}
        </>
      );
    }

    if (widgetId === 'gross_profit_margin') {
      const trend = dashboard.charts.gross_profit_margin_trend;
      if (!trend.items.length) return <EmptyState reason={trend.unavailable_reason} />;
      const points = trend.items.map((item) => ({
        period: item.period,
        revenue: numberFromString(String(item.revenue)),
        grossProfit:
          item.estimated_gross_profit === null
            ? null
            : numberFromString(String(item.estimated_gross_profit)),
        margin:
          item.margin_percent === null
            ? null
            : numberFromString(String(item.margin_percent)),
      }));
      return (
        <div className={styles.chartWrap}>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={points} margin={{ top: 16, right: 12, left: 2, bottom: 4 }}>
              <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" />
              <XAxis dataKey="period" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
              <YAxis yAxisId="money" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} tickFormatter={(value) => numberCompact(value)} />
              <YAxis yAxisId="margin" orientation="right" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} tickFormatter={(value) => `${value}%`} />
              <Tooltip contentStyle={tooltipStyle()} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar yAxisId="money" dataKey="revenue" fill={CHART_COLORS.revenue} name="Revenue" radius={[6, 6, 0, 0]} />
              <Line yAxisId="money" dataKey="grossProfit" stroke={CHART_COLORS.profit} strokeWidth={2.4} dot={false} name="Est. gross profit" />
              <Area yAxisId="margin" dataKey="margin" fill={CHART_COLORS.margin} fillOpacity={0.22} stroke={CHART_COLORS.margin} strokeWidth={2} name="Margin %" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (widgetId === 'conversion_funnel') {
      const funnel = dashboard.charts.conversion_funnel;
      if (!funnel.stages.length) return <EmptyState />;
      const data = funnel.stages.map((stage) => ({
        label: stage.label,
        count: stage.count,
      }));
      return (
        <>
          <div className={styles.chartWrap}>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data} layout="vertical" margin={{ top: 16, right: 8, left: 20, bottom: 4 }}>
                <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" />
                <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                <YAxis type="category" dataKey="label" width={88} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                <Tooltip contentStyle={tooltipStyle()} />
                <Bar dataKey="count" radius={[0, 6, 6, 0]} fill={CHART_COLORS.orders} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className={styles.inlineStats}>
            {funnel.stages.map((stage) => (
              <span key={stage.stage}>
                {stage.label}: {stage.count}
                {stage.conversion_percent_from_previous !== null
                  ? ` (${formatPercent(stage.conversion_percent_from_previous)} from previous)`
                  : ''}
              </span>
            ))}
          </div>
          {funnel.drop_off_reasons.length ? (
            <div className={styles.chartNote}>
              Drop-off reasons: {funnel.drop_off_reasons.map((item) => `${item.reason} (${item.count})`).join(', ')}
            </div>
          ) : null}
        </>
      );
    }

    if (widgetId === 'product_performance_quadrant') {
      const matrix = dashboard.charts.product_performance_quadrant;
      if (!matrix.items.length) return <EmptyState reason={matrix.unavailable_reason} />;

      const points = matrix.items.map((item) => ({
        product_name: shortName(item.product_name, 30),
        sales_velocity: numberFromString(String(item.sales_velocity)),
        margin: numberFromString(String(item.estimated_margin_percent ?? 0)),
        revenue: numberFromString(String(item.revenue)),
        quadrant: item.quadrant,
      }));

      const byQuadrant = {
        star: points.filter((item) => item.quadrant === 'star'),
        sleeper: points.filter((item) => item.quadrant === 'sleeper'),
        margin_killer: points.filter((item) => item.quadrant === 'margin_killer'),
        laggard: points.filter((item) => item.quadrant === 'laggard' || item.quadrant === 'watch'),
      };

      return (
        <div className={styles.chartWrap}>
          <ResponsiveContainer width="100%" height={280}>
            <ScatterChart margin={{ top: 16, right: 8, left: 8, bottom: 14 }}>
              <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" />
              <XAxis
                type="number"
                dataKey="sales_velocity"
                name="Sales velocity"
                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                label={{ value: 'Sales velocity/day', position: 'insideBottom', offset: -6 }}
              />
              <YAxis
                type="number"
                dataKey="margin"
                name="Margin"
                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                label={{ value: 'Margin %', angle: -90, position: 'insideLeft' }}
              />
              <ZAxis type="number" dataKey="revenue" range={[80, 380]} name="Revenue" />
              <Tooltip cursor={{ strokeDasharray: '4 4' }} contentStyle={tooltipStyle()} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Scatter name="Star" data={byQuadrant.star} fill="#1fbf8f" />
              <Scatter name="Sleeper" data={byQuadrant.sleeper} fill="#3b82f6" />
              <Scatter name="Margin killer" data={byQuadrant.margin_killer} fill="#f97316" />
              <Scatter name="Laggard" data={byQuadrant.laggard} fill="#9aa7b8" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (widgetId === 'category_brand_profit_mix') {
      const mix = dashboard.charts.category_brand_profit_mix;
      if (!mix.categories.length) return <EmptyState reason={mix.unavailable_reason} />;
      const treeData = mix.categories.map((category) => ({
        name: category.category,
        children: category.brands.map((brand) => ({
          name: `${category.category} / ${brand.brand}`,
          size: numberFromString(String(brand.revenue)),
        })),
      }));

      return (
        <>
          <div className={styles.chartWrap}>
            <ResponsiveContainer width="100%" height={280}>
              <Treemap
                data={treeData}
                dataKey="size"
                aspectRatio={4 / 3}
                stroke="var(--border)"
                fill={CHART_COLORS.revenue}
              >
                <Tooltip contentStyle={tooltipStyle()} formatter={(value) => moneyCompact(numberFromString(String(value)))} />
              </Treemap>
            </ResponsiveContainer>
          </div>
          <div className={styles.inlineStats}>
            {mix.categories.slice(0, 4).map((category) => (
              <span key={category.category}>
                {category.category}: ${formatMoney(category.revenue)}
              </span>
            ))}
          </div>
        </>
      );
    }

    if (widgetId === 'returns_intelligence') {
      const intelligence = dashboard.charts.returns_intelligence;
      const trend = intelligence.trend.map((point) => ({
        period: point.period,
        returnRate: numberFromString(String(point.return_rate_percent)),
        returnsCount: point.returns_count,
      }));

      const reasonOrder = intelligence.top_reasons.slice(0, 5).map((row) => row.reason);
      const products = Array.from(new Set(intelligence.heatmap.slice(0, 10).map((row) => row.product_name)));
      const matrixValue = (productName: string, reason: string) => {
        const found = intelligence.heatmap.find((row) => row.product_name === productName && row.reason === reason);
        return found ? numberFromString(String(found.returns_qty)) : 0;
      };
      const allValues = products.flatMap((productName) => reasonOrder.map((reason) => matrixValue(productName, reason)));
      const maxCellValue = Math.max(...allValues, 0);

      return (
        <>
          <div className={styles.chartWrap}>
            <ResponsiveContainer width="100%" height={220}>
              <ComposedChart data={trend} margin={{ top: 12, right: 8, left: 4, bottom: 4 }}>
                <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" />
                <XAxis dataKey="period" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                <YAxis yAxisId="left" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                <Tooltip contentStyle={tooltipStyle()} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar yAxisId="left" dataKey="returnsCount" fill={CHART_COLORS.warning} radius={[5, 5, 0, 0]} name="Returns" />
                <Line yAxisId="right" dataKey="returnRate" stroke={CHART_COLORS.critical} strokeWidth={2.4} dot={false} name="Return rate %" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {products.length && reasonOrder.length ? (
            <div className={styles.heatmapWrap}>
              <div className={styles.heatmapHeader}>Reason heatmap</div>
              <table className={styles.heatmapTable}>
                <thead>
                  <tr>
                    <th>Product</th>
                    {reasonOrder.map((reason) => (
                      <th key={reason}>{reason}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {products.map((productName) => (
                    <tr key={productName}>
                      <td>{shortName(productName, 22)}</td>
                      {reasonOrder.map((reason) => {
                        const value = matrixValue(productName, reason);
                        const intensity = maxCellValue > 0 ? value / maxCellValue : 0;
                        return (
                          <td
                            key={`${productName}-${reason}`}
                            style={{
                              background: `rgba(255, 106, 26, ${Math.min(0.8, 0.1 + intensity * 0.7)})`,
                              color: intensity > 0.55 ? '#ffffff' : 'var(--text)',
                            }}
                          >
                            {value > 0 ? value.toFixed(1) : '-'}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      );
    }

    if (widgetId === 'inventory_aging_waterfall') {
      const aging = dashboard.charts.inventory_aging_waterfall;
      if (!aging.buckets.length) return <EmptyState reason={aging.unavailable_reason} />;
      const points = aging.buckets.map((bucket) => ({
        bucket: bucket.bucket,
        onHandQty: numberFromString(String(bucket.on_hand_qty)),
        inventoryValue: numberFromString(String(bucket.inventory_value ?? 0)),
        netQtyChange: numberFromString(String(bucket.net_qty_change)),
        netValueChange: numberFromString(String(bucket.net_value_change ?? 0)),
      }));
      return (
        <div className={styles.chartWrap}>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={points} margin={{ top: 16, right: 8, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" />
              <XAxis dataKey="bucket" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
              <YAxis yAxisId="left" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
              <Tooltip contentStyle={tooltipStyle()} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {financialVisible ? (
                <Bar yAxisId="left" dataKey="inventoryValue" fill={CHART_COLORS.revenue} radius={[6, 6, 0, 0]} name="Inventory value" />
              ) : (
                <Bar yAxisId="left" dataKey="onHandQty" fill={CHART_COLORS.orders} radius={[6, 6, 0, 0]} name="On hand qty" />
              )}
              {financialVisible ? (
                <Line yAxisId="right" dataKey="netValueChange" stroke={CHART_COLORS.profit} strokeWidth={2.2} name="Net value change" />
              ) : (
                <Line yAxisId="right" dataKey="netQtyChange" stroke={CHART_COLORS.profit} strokeWidth={2.2} name="Net qty change" />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (widgetId === 'sell_through_cover_matrix') {
      const matrix = dashboard.charts.sell_through_cover_matrix.items;
      if (!matrix.length) return <EmptyState />;
      const points = matrix.map((item) => ({
        product_name: shortName(item.product_name, 24),
        sellThrough: numberFromString(String(item.sell_through_percent)),
        daysCover: item.days_cover === null ? 120 : numberFromString(String(item.days_cover)),
        revenue: numberFromString(String(item.revenue)),
        zone: item.zone,
      }));
      const zones: Array<{ zone: string; color: string }> = [
        { zone: 'low_cover_high_velocity', color: CHART_COLORS.critical },
        { zone: 'high_cover_low_velocity', color: CHART_COLORS.warning },
        { zone: 'healthy', color: CHART_COLORS.positive },
        { zone: 'watch', color: CHART_COLORS.neutral },
      ];
      return (
        <div className={styles.chartWrap}>
          <ResponsiveContainer width="100%" height={280}>
            <ScatterChart margin={{ top: 16, right: 10, left: 8, bottom: 12 }}>
              <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" />
              <XAxis
                type="number"
                dataKey="daysCover"
                name="Days cover"
                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                label={{ value: 'Days of cover', position: 'insideBottom', offset: -4 }}
              />
              <YAxis
                type="number"
                dataKey="sellThrough"
                name="Sell-through"
                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                label={{ value: 'Sell-through %', angle: -90, position: 'insideLeft' }}
              />
              <ZAxis type="number" dataKey="revenue" range={[80, 380]} />
              <Tooltip contentStyle={tooltipStyle()} />
              <Legend formatter={(value) => zoneLabel(String(value))} wrapperStyle={{ fontSize: 12 }} />
              {zones.map(({ zone, color }) => (
                <Scatter key={zone} name={zone} data={points.filter((item) => item.zone === zone)} fill={color} />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (widgetId === 'reorder_priority_scoreboard') {
      const rows = dashboard.charts.reorder_priority_scoreboard.items;
      if (!rows.length) return <EmptyState />;
      const points = rows.slice(0, 12).map((item) => ({
        product_name: shortName(item.product_name, 20),
        score: numberFromString(String(item.priority_score)),
      }));
      return (
        <>
          <div className={styles.chartWrap}>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={points} layout="vertical" margin={{ top: 12, right: 8, left: 16, bottom: 4 }}>
                <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" />
                <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                <YAxis type="category" dataKey="product_name" width={140} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                <Tooltip contentStyle={tooltipStyle()} />
                <Bar dataKey="score" fill={CHART_COLORS.warning} radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className={styles.scoreRows}>
            {rows.slice(0, 8).map((item) => (
              <div key={item.product_id} className={styles.scoreRow}>
                <strong>{shortName(item.product_name, 26)}</strong>
                <span>{item.priority_score}</span>
                <span className={actionTone(item.recommended_action)}>{item.recommended_action}</span>
              </div>
            ))}
          </div>
        </>
      );
    }

    if (widgetId === 'price_discount_impact') {
      const impact = dashboard.charts.price_discount_impact;
      if (!impact.items.length) return <EmptyState reason={impact.unavailable_reason} />;

      const points = impact.items.map((item) => ({
        product_name: shortName(item.product_name, 26),
        discountPercent: numberFromString(String(item.discount_percent)),
        unitLiftPercent: numberFromString(String(item.unit_lift_percent)),
        netMarginPercent: item.net_margin_percent === null ? 0 : numberFromString(String(item.net_margin_percent)),
        revenue: numberFromString(String(item.revenue)),
        recommendation: item.recommendation,
      }));

      const recommendationGroups: DashboardPriceDiscountImpactPoint['recommendation'][] = ['raise', 'keep', 'discount'];
      const liftBars = recommendationGroups.map((recommendation) => {
        const subset = impact.items.filter((item) => item.recommendation === recommendation);
        const averageLift = subset.length
          ? subset.reduce((sum, item) => sum + numberFromString(String(item.unit_lift_percent)), 0) / subset.length
          : 0;
        return {
          recommendation,
          averageLift,
        };
      });

      const colorByRecommendation: Record<DashboardPriceDiscountImpactPoint['recommendation'], string> = {
        raise: CHART_COLORS.critical,
        keep: CHART_COLORS.neutral,
        discount: CHART_COLORS.positive,
      };

      return (
        <>
          <div className={styles.chartWrap}>
            <ResponsiveContainer width="100%" height={250}>
              <ScatterChart margin={{ top: 12, right: 8, left: 8, bottom: 10 }}>
                <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" />
                <XAxis
                  type="number"
                  dataKey="discountPercent"
                  name="Discount %"
                  tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                  label={{ value: 'Discount %', position: 'insideBottom', offset: -4 }}
                />
                <YAxis
                  type="number"
                  dataKey="unitLiftPercent"
                  name="Unit lift %"
                  tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                  label={{ value: 'Unit lift %', angle: -90, position: 'insideLeft' }}
                />
                <ZAxis type="number" dataKey="revenue" range={[80, 360]} />
                <Tooltip contentStyle={tooltipStyle()} />
                <Legend formatter={(value) => recommendationLabel(value as DashboardPriceDiscountImpactPoint['recommendation'])} wrapperStyle={{ fontSize: 12 }} />
                {recommendationGroups.map((recommendation) => (
                  <Scatter
                    key={recommendation}
                    name={recommendation}
                    data={points.filter((item) => item.recommendation === recommendation)}
                    fill={colorByRecommendation[recommendation]}
                  />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <div className={styles.chartWrap}>
            <ResponsiveContainer width="100%" height={150}>
              <BarChart data={liftBars} margin={{ top: 6, right: 8, left: 4, bottom: 0 }}>
                <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" />
                <XAxis dataKey="recommendation" tickFormatter={(value) => recommendationLabel(value as DashboardPriceDiscountImpactPoint['recommendation'])} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                <Tooltip contentStyle={tooltipStyle()} formatter={(value) => `${numberFromString(String(value)).toFixed(2)}%`} />
                <Bar dataKey="averageLift" radius={[6, 6, 0, 0]}>
                  {liftBars.map((row) => (
                    <Cell key={row.recommendation} fill={colorByRecommendation[row.recommendation as DashboardPriceDiscountImpactPoint['recommendation']]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      );
    }

    return <EmptyState />;
  };

  const renderColumn = (column: WidgetColumn, widgetIds: WidgetId[]) => (
    <div
      className={styles.column}
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => onDropToColumn(event, column, widgetIds.length)}
    >
      <div className={styles.dropZone} onDragOver={(event) => event.preventDefault()} onDrop={(event) => onDropToColumn(event, column, 0)}>
        Drop chart here
      </div>
      {widgetIds.length === 0 ? <div className={styles.columnEmpty}>No charts selected for this column.</div> : null}
      {widgetIds.map((widgetId, index) => (
        <Fragment key={widgetId}>
          <article
            className={`${styles.widgetCard} ${draggingWidget === widgetId ? styles.widgetDragging : ''}`}
            draggable
            onDragStart={() => setDraggingWidget(widgetId)}
            onDragEnd={() => setDraggingWidget(null)}
          >
            <header className={styles.widgetHeader}>
              <div>
                <h4>{WIDGET_META[widgetId].title}</h4>
                <p>{WIDGET_META[widgetId].subtitle}</p>
              </div>
              <div className={styles.widgetActions}>
                <button type="button" className={styles.dragHandle} title="Drag chart to reposition">
                  Drag
                </button>
                <button type="button" className={styles.hideBtn} onClick={() => toggleWidget(widgetId)}>
                  Hide
                </button>
              </div>
            </header>
            {renderWidget(widgetId)}
          </article>
          <div
            className={styles.dropZone}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => onDropToColumn(event, column, index + 1)}
          >
            Drop chart here
          </div>
        </Fragment>
      ))}
    </div>
  );

  return (
    <div className={styles.dashboard}>
      <section className={styles.headerCard}>
        <div className={styles.headerTop}>
          <div>
            <h2>Dashboard Studio</h2>
            <p>Choose, arrange, and monitor the charts that matter most for your business.</p>
          </div>
          <div className={styles.headerActions}>
            <button type="button" onClick={() => setCustomizeOpen((current) => !current)}>
              {customizeOpen ? 'Close chart picker' : 'Choose charts'}
            </button>
            <button type="button" onClick={resetLayout}>Reset layout</button>
          </div>
        </div>

        <div className={styles.filtersRow}>
          <label className={styles.filterField}>
            <span>Range</span>
            <select value={filters.range_key} onChange={(event) => onRangeChange(event.target.value as DashboardRangeKey)}>
              {RANGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.filterField}>
            <span>Location</span>
            <select value={filters.location_id} onChange={(event) => onLocationChange(event.target.value)}>
              <option value="">All active locations</option>
              {(dashboard?.locations ?? []).map((location) => (
                <option key={location.location_id} value={location.location_id}>
                  {location.name}
                </option>
              ))}
            </select>
          </label>
          {filters.range_key === 'custom' ? (
            <form className={styles.customRange} onSubmit={applyCustomRange}>
              <label className={styles.filterField}>
                <span>From</span>
                <input
                  type="date"
                  value={customRange.from_date}
                  onChange={(event) => setCustomRange((current) => ({ ...current, from_date: event.target.value }))}
                />
              </label>
              <label className={styles.filterField}>
                <span>To</span>
                <input
                  type="date"
                  value={customRange.to_date}
                  onChange={(event) => setCustomRange((current) => ({ ...current, to_date: event.target.value }))}
                />
              </label>
              <button type="submit">Apply</button>
            </form>
          ) : null}
          <div className={styles.rangeMeta}>
            <strong>{dashboard?.applied_range.label ?? 'Month to date'}</strong>
            <span>
              {dashboard
                ? `${dashboard.applied_range.from_date} to ${dashboard.applied_range.to_date} (${dashboard.applied_range.timezone})`
                : 'Loading selected range...'}
            </span>
            <span>Updated {dashboard ? formatDateTime(dashboard.generated_at) : 'now'}</span>
          </div>
        </div>

        {customizeOpen ? (
          <div className={styles.chartPicker}>
            {WIDGET_IDS.map((widgetId) => (
              <label key={widgetId} className={styles.chartPickerItem}>
                <input
                  type="checkbox"
                  checked={!hiddenSet.has(widgetId)}
                  onChange={() => toggleWidget(widgetId)}
                />
                <div>
                  <strong>{WIDGET_META[widgetId].title}</strong>
                  <span>{WIDGET_META[widgetId].subtitle}</span>
                </div>
              </label>
            ))}
          </div>
        ) : null}

        {error ? (
          <div className={styles.errorBox}>
            <p>{error}</p>
            <button type="button" onClick={() => loadDashboard(filters)}>Retry</button>
          </div>
        ) : null}
      </section>

      {isPending && !dashboard ? <div className={styles.loadingBox}>Loading dashboard analytics...</div> : null}

      {dashboard ? (
        <section className={styles.kpiGrid}>
          {kpis.slice(0, 8).map((metric) => (
            <article key={metric.id} className={styles.kpiCard}>
              <p>{metric.label}</p>
              <strong>{metricValue(metric)}</strong>
              <span>{metricDelta(metric)}</span>
            </article>
          ))}
        </section>
      ) : null}

      {dashboard ? (
        <section className={styles.board}>
          {renderColumn('left', visibleLeft)}
          {renderColumn('right', visibleRight)}
        </section>
      ) : null}

      {dashboard ? (
        <footer className={styles.footerLinks}>
          <Link href="/sales">Sales</Link>
          <Link href="/returns">Returns</Link>
          <Link href="/inventory">Inventory</Link>
          <Link href="/reports">Reports</Link>
        </footer>
      ) : null}
    </div>
  );
}
