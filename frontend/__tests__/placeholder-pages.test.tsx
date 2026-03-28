import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import AiReviewPage from '@/app/(app)/ai-review/page';
import AutomationPage from '@/app/(app)/automation/page';
import CatalogPage from '@/app/(app)/catalog/page';
import CustomersPage from '@/app/(app)/customers/page';
import DashboardPage from '@/app/(app)/dashboard/page';
import FinancePage from '@/app/(app)/finance/page';
import IntegrationsPage from '@/app/(app)/integrations/page';
import InventoryPage from '@/app/(app)/inventory/page';
import HomePage from '@/app/(app)/page';
import ProductsStockPage from '@/app/(app)/products-stock/page';
import PurchasesPage from '@/app/(app)/purchases/page';
import ReportsPage from '@/app/(app)/reports/page';
import ReturnsPage from '@/app/(app)/returns/page';
import SalesAgentPage from '@/app/(app)/sales-agent/page';
import SalesPage from '@/app/(app)/sales/page';
import SettingsPage from '@/app/(app)/settings/page';

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
  redirect: vi.fn(),
}));

vi.mock('@/lib/env', () => ({
  getPublicEnv: () => ({
    apiBaseUrl: 'https://api.easy-ecom.test',
  }),
}));

vi.mock('@/lib/api/commerce', () => ({
  getCatalogWorkspace: vi.fn(async () => ({
    query: '',
    has_multiple_locations: false,
    active_location: { location_id: 'loc-1', name: 'Main', is_default: true },
    locations: [{ location_id: 'loc-1', name: 'Main', is_default: true }],
    categories: [],
    suppliers: [],
    items: [],
  })),
  saveCatalogProduct: vi.fn(),
  getInventoryWorkspace: vi.fn(async () => ({
    query: '',
    has_multiple_locations: false,
    active_location: { location_id: 'loc-1', name: 'Main', is_default: true },
    locations: [{ location_id: 'loc-1', name: 'Main', is_default: true }],
    stock_items: [],
    low_stock_items: [],
  })),
  getInventoryIntakeLookup: vi.fn(async () => ({
    query: '',
    exact_variants: [],
    product_matches: [],
    suggested_new_product: null,
  })),
  receiveInventoryStock: vi.fn(),
  createInventoryAdjustment: vi.fn(),
  getSalesOrders: vi.fn(async () => ({ items: [] })),
  getSalesOrder: vi.fn(),
  searchSaleVariants: vi.fn(async () => ({ items: [] })),
  searchEmbeddedCustomers: vi.fn(async () => ({ items: [] })),
  saveSalesOrder: vi.fn(),
  confirmSalesOrder: vi.fn(),
  fulfillSalesOrder: vi.fn(),
  cancelSalesOrder: vi.fn(),
  getReturns: vi.fn(async () => ({ items: [] })),
  searchReturnOrders: vi.fn(async () => ({ items: [] })),
  getEligibleReturnLines: vi.fn(),
  createSalesReturn: vi.fn(),
  recordSalesReturnRefund: vi.fn(),
}));

vi.mock('@/lib/api/dashboard', () => ({
  getDashboardAnalytics: vi.fn(async () => ({
    generated_at: '2026-03-15T10:00:00+00:00',
    has_multiple_locations: false,
    selected_location_id: null,
    locations: [{ location_id: 'loc-1', name: 'Main', is_default: true }],
    applied_range: {
      range_key: 'mtd',
      label: 'Month to date',
      timezone: 'UTC',
      from_date: '2026-03-01',
      to_date: '2026-03-15',
      previous_from_date: '2026-02-14',
      previous_to_date: '2026-02-28',
      bucket: 'day',
      days: 15,
    },
    visibility: { can_view_financial_metrics: true },
    kpis: [],
    insight_cards: [],
    charts: {
      revenue_profit_trend: { items: [], unavailable_reason: null },
      stock_movement_trend: [],
      returns_trend: { items: [] },
      product_opportunity_matrix: { items: [], unavailable_reason: null },
    },
    tables: {
      stock_investment_by_product: [],
      low_stock_variants: [],
      top_products_by_units_sold: [],
      top_products_by_revenue: { items: [], unavailable_reason: null },
      top_products_by_estimated_gross_profit: { items: [], unavailable_reason: null },
      slow_movers: [],
      recent_activity: [],
    },
  })),
}));

vi.mock('@/lib/api/integrations', () => ({
  getChannelIntegrations: vi.fn(async () => ({
    items: [
      {
        channel_id: 'channel-1',
        provider: 'whatsapp',
        display_name: 'WhatsApp Sales Agent',
        status: 'active',
        external_account_id: 'waba-1',
        phone_number_id: 'phone-1',
        phone_number: '+971551234567',
        verify_token_set: true,
        inbound_secret_set: true,
        access_token_set: true,
        config_saved: true,
        webhook_verified_at: '2026-03-15T10:00:00+00:00',
        last_webhook_post_at: null,
        signature_validation_ok: null,
        graph_auth_ok: true,
        outbound_send_ok: null,
        openai_ready: false,
        openai_probe_ok: null,
        last_error_code: null,
        last_error_message: null,
        last_provider_status_code: null,
        last_provider_response_excerpt: null,
        last_diagnostic_at: '2026-03-15T10:00:00+00:00',
        next_action: 'Set OPENAI_API_KEY on the backend environment and restart the API service.',
        default_location_id: 'loc-1',
        auto_send_enabled: false,
        agent_enabled: true,
        model_name: 'gpt-4o-mini',
        persona_prompt: 'Sell honestly.',
        config: {},
        created_at: '2026-03-15T10:00:00+00:00',
        updated_at: '2026-03-15T10:00:00+00:00',
        last_inbound_at: null,
        last_outbound_at: null,
      },
    ],
  })),
  getChannelLocations: vi.fn(async () => ({
    items: [{ location_id: 'loc-1', name: 'Main', is_default: true }],
  })),
  saveWhatsAppMetaIntegration: vi.fn(async () => ({
    channel: {
      channel_id: 'channel-1',
      provider: 'whatsapp',
      display_name: 'WhatsApp Sales Agent',
      status: 'active',
      external_account_id: 'waba-1',
      phone_number_id: 'phone-1',
      phone_number: '+971551234567',
      verify_token_set: true,
      inbound_secret_set: true,
      access_token_set: true,
      config_saved: true,
      webhook_verified_at: '2026-03-15T10:00:00+00:00',
      last_webhook_post_at: null,
      signature_validation_ok: null,
      graph_auth_ok: true,
      outbound_send_ok: null,
      openai_ready: false,
      openai_probe_ok: null,
      last_error_code: null,
      last_error_message: null,
      last_provider_status_code: null,
      last_provider_response_excerpt: null,
      last_diagnostic_at: '2026-03-15T10:00:00+00:00',
      next_action: 'Set OPENAI_API_KEY on the backend environment and restart the API service.',
      default_location_id: 'loc-1',
      auto_send_enabled: false,
      agent_enabled: true,
      model_name: 'gpt-4o-mini',
      persona_prompt: 'Sell honestly.',
      config: {},
      created_at: '2026-03-15T10:00:00+00:00',
      updated_at: '2026-03-15T10:00:00+00:00',
      last_inbound_at: null,
      last_outbound_at: null,
    },
    setup_verify_token: null,
  })),
  validateWhatsAppMetaIntegration: vi.fn(async () => ({
    diagnostics: {
      config_saved: true,
      verify_token_set: true,
      webhook_verified_at: null,
      last_webhook_post_at: null,
      signature_validation_ok: null,
      graph_auth_ok: true,
      outbound_send_ok: null,
      openai_ready: false,
      openai_probe_ok: null,
      last_error_code: null,
      last_error_message: null,
      last_provider_status_code: null,
      last_provider_response_excerpt: null,
      last_diagnostic_at: '2026-03-15T10:00:00+00:00',
      next_action: 'Verify the callback URL in Meta with the exact verify token saved for this tenant.',
    },
    provider_details: {
      display_phone_number: '+971551234567',
    },
  })),
  runChannelDiagnostics: vi.fn(async () => ({
    channel: {
      channel_id: 'channel-1',
      provider: 'whatsapp',
      display_name: 'WhatsApp Sales Agent',
      status: 'active',
      external_account_id: 'waba-1',
      phone_number_id: 'phone-1',
      phone_number: '+971551234567',
      verify_token_set: true,
      inbound_secret_set: true,
      access_token_set: true,
      config_saved: true,
      webhook_verified_at: '2026-03-15T10:00:00+00:00',
      last_webhook_post_at: '2026-03-15T10:05:00+00:00',
      signature_validation_ok: true,
      graph_auth_ok: true,
      outbound_send_ok: true,
      openai_ready: false,
      openai_probe_ok: null,
      last_error_code: null,
      last_error_message: null,
      last_provider_status_code: 200,
      last_provider_response_excerpt: null,
      last_diagnostic_at: '2026-03-15T10:05:00+00:00',
      next_action: 'Set OPENAI_API_KEY on the backend environment and restart the API service.',
      default_location_id: 'loc-1',
      auto_send_enabled: false,
      agent_enabled: true,
      model_name: 'gpt-4o-mini',
      persona_prompt: 'Sell honestly.',
      config: {},
      created_at: '2026-03-15T10:00:00+00:00',
      updated_at: '2026-03-15T10:05:00+00:00',
      last_inbound_at: null,
      last_outbound_at: null,
    },
    diagnostics: {
      config_saved: true,
      verify_token_set: true,
      webhook_verified_at: '2026-03-15T10:00:00+00:00',
      last_webhook_post_at: '2026-03-15T10:05:00+00:00',
      signature_validation_ok: true,
      graph_auth_ok: true,
      outbound_send_ok: true,
      openai_ready: false,
      openai_probe_ok: null,
      last_error_code: null,
      last_error_message: null,
      last_provider_status_code: 200,
      last_provider_response_excerpt: null,
      last_diagnostic_at: '2026-03-15T10:05:00+00:00',
      next_action: 'Set OPENAI_API_KEY on the backend environment and restart the API service.',
    },
    provider_details: {
      display_phone_number: '+971551234567',
      verified_name: 'Test Number',
    },
  })),
  sendChannelSmoke: vi.fn(async () => ({
    ok: true,
    provider_event_id: 'wamid-smoke-1',
    message: 'Smoke message accepted by WhatsApp.',
    diagnostics: {
      config_saved: true,
      verify_token_set: true,
      webhook_verified_at: '2026-03-15T10:00:00+00:00',
      last_webhook_post_at: '2026-03-15T10:05:00+00:00',
      signature_validation_ok: true,
      graph_auth_ok: true,
      outbound_send_ok: true,
      openai_ready: false,
      openai_probe_ok: null,
      last_error_code: null,
      last_error_message: null,
      last_provider_status_code: 200,
      last_provider_response_excerpt: null,
      last_diagnostic_at: '2026-03-15T10:06:00+00:00',
      next_action: 'Set OPENAI_API_KEY on the backend environment and restart the API service.',
    },
    provider_details: {
      recipient: '+971500000001',
    },
  })),
}));

vi.mock('@/lib/api/sales-agent', () => ({
  getSalesAgentConversations: vi.fn(async () => ({
    items: [],
  })),
  getSalesAgentConversation: vi.fn(),
  handoffSalesAgentConversation: vi.fn(),
  approveSalesAgentDraft: vi.fn(),
  rejectSalesAgentDraft: vi.fn(),
  getSalesAgentOrders: vi.fn(async () => ({
    items: [],
  })),
  confirmSalesAgentOrder: vi.fn(),
}));

vi.mock('@/lib/api/finance', () => ({
  getFinanceOverview: vi.fn(async () => ({
    sales_revenue: 300,
    expense_total: 50,
    receivables: 50,
    payables: 20,
    cash_in: 250,
    cash_out: 50,
    net_operating: 200,
  })),
  getFinanceWorkspace: vi.fn(async () => ({
    overview: {
      sales_revenue: 300,
      expense_total: 50,
      receivables: 50,
      payables: 20,
      cash_in: 250,
      cash_out: 50,
      net_operating: 200,
    },
    transactions: [],
    receivables: [],
    payables: [],
  })),
  getFinanceReport: vi.fn(async () => ({
    from_date: '2026-03-01',
    to_date: '2026-03-15',
    expense_total: 50,
    expense_trend: [{ period: '2026-03-15', amount: 50 }],
    receivables_total: 50,
    payables_total: 20,
    net_operating_snapshot: 200,
    deferred_metrics: [],
  })),
  getFinanceTransactions: vi.fn(async () => ({
    transactions: [],
    total: 0,
    limit: 50,
    offset: 0,
  })),
  createFinanceTransaction: vi.fn(),
}));

vi.mock('@/lib/api/reports', () => ({
  getReportsOverview: vi.fn(async () => ({
    from_date: '2026-03-01',
    to_date: '2026-03-15',
    sales_revenue_total: 300,
    sales_count: 2,
    expense_total: 50,
    returns_total: 1,
    purchases_total: 500,
  })),
  getSalesReport: vi.fn(async () => ({
    from_date: '2026-03-01',
    to_date: '2026-03-15',
    sales_count: 2,
    revenue_total: 300,
    sales_trend: [],
    top_products: [{ product_id: 'product-1', product_name: 'Trail Runner', qty_sold: 2, revenue: 200 }],
    top_customers: [],
    deferred_metrics: [],
  })),
  getInventoryReport: vi.fn(async () => ({
    from_date: '2026-03-01',
    to_date: '2026-03-15',
    total_skus_with_stock: 2,
    total_stock_units: 12,
    low_stock_items: [],
    stock_movement_trend: [],
    inventory_value: 450,
    deferred_metrics: [],
  })),
  getPurchasesReport: vi.fn(async () => ({
    from_date: '2026-03-01',
    to_date: '2026-03-15',
    purchases_count: 1,
    purchases_subtotal: 500,
    purchases_trend: [],
    deferred_metrics: [],
  })),
  getFinanceReport: vi.fn(async () => ({
    from_date: '2026-03-01',
    to_date: '2026-03-15',
    expense_total: 50,
    expense_trend: [],
    receivables_total: 50,
    payables_total: null,
    net_operating_snapshot: -350,
    deferred_metrics: [],
  })),
  getReturnsReport: vi.fn(async () => ({
    from_date: '2026-03-01',
    to_date: '2026-03-15',
    returns_count: 1,
    return_qty_total: 1,
    return_amount_total: 50,
    deferred_metrics: [],
  })),
  getProductsReport: vi.fn(async () => ({
    from_date: '2026-03-01',
    to_date: '2026-03-15',
    highest_selling: [{ product_id: 'product-1', product_name: 'Trail Runner', qty_sold: 2, revenue: 200 }],
    low_or_zero_movement: [],
    deferred_metrics: [],
  })),
}));

vi.mock('@/lib/api/settings', () => ({
  getSettingsWorkspace: vi.fn(async () => ({
    tenant_context: {
      client_id: 'client-1',
      business_name: 'Acme Store',
      status: 'active',
      currency_code: 'AED',
    },
    profile: {
      business_name: 'Acme Store',
      contact_name: 'Asha',
      owner_name: 'Owner',
      email: 'ops@acme.test',
      phone: '+9715000000',
      address: 'Dubai',
      website_url: 'https://acme.test',
      whatsapp_number: '+9715000000',
      timezone: 'Asia/Dubai',
      currency_code: 'AED',
      currency_symbol: 'AED',
      notes: 'Core tenant',
    },
    defaults: {
      default_location_name: 'Main Warehouse',
      low_stock_threshold: 5,
      allow_backorder: false,
      require_discount_approval: false,
    },
    prefixes: {
      sales_prefix: 'SO',
      purchases_prefix: 'PO',
      returns_prefix: 'RT',
    },
  })),
  updateSettingsWorkspace: vi.fn(),
}));

vi.mock('@/lib/api/purchases', () => ({
  listPurchaseOrders: vi.fn(async () => ({
    items: [
      {
        purchase_id: 'purchase-1',
        purchase_no: 'PO-1001',
        purchase_date: '2026-03-14',
        supplier_id: 'supplier-1',
        supplier_name: 'Trusted Supplier',
        reference_no: 'REF-1',
        subtotal: 500,
        status: 'received',
        created_at: '2026-03-14T10:00:00+00:00',
      },
    ],
  })),
}));

vi.mock('@/lib/api/ai-review', () => ({
  getAiReviewDrafts: vi.fn(async () => ({
    items: [],
  })),
  getAiReviewDraft: vi.fn(),
  approveAiReviewDraft: vi.fn(),
  rejectAiReviewDraft: vi.fn(),
}));

vi.mock('@/lib/api/automation', () => ({
  getAutomationOverview: vi.fn(async () => ({
    module: 'automation',
    status: 'skeleton',
    summary: 'Automation is mounted as a tenant-safe read-only skeleton while workflows are rebuilt.',
    metrics: [
      { label: 'Rules', value: '0', hint: 'No automation rules configured yet' },
      { label: 'Active rules', value: '0', hint: 'No enabled rules available' },
      { label: 'Recent runs', value: '0', hint: 'No execution history yet' },
    ],
  })),
  getAutomationRules: vi.fn(async () => ({ items: [] })),
  getAutomationRuns: vi.fn(async () => ({ items: [] })),
}));

const cases = [
  ['Home', HomePage, /the product foundation is live again/i],
  ['Dashboard', DashboardPage, /business analytics dashboard/i],
  ['Reports', ReportsPage, /loading tenant reports|sales revenue/i],
  ['Catalog', CatalogPage, /variant-first catalog/i],
  ['Customers', CustomersPage, /embedded customer records/i],
  ['Inventory', InventoryPage, /variant-level inventory control/i],
  ['Purchases', PurchasesPage, /trusted supplier/i],
  ['Sales', SalesPage, /order-first sales workspace/i],
  ['Sales Agent', SalesAgentPage, /no pending agent orders/i],
  ['Finance', FinancePage, 'Record manual finance entry'],
  ['Returns', ReturnsPage, /return and restock control/i],
  ['Integrations & Channels', IntegrationsPage, /whatsapp meta channel/i],
  ['AI Review Inbox', AiReviewPage, /choose a draft from the queue/i],
  ['Automation', AutomationPage, /start with low-stock alerts, failed-channel follow-up, and sla reminders/i],
  ['Settings', SettingsPage, /tenant settings|business name/i],
] as const;

describe('Business pages', () => {
  afterEach(() => {
    cleanup();
  });

  test.each(cases)('%s renders its current workspace shell', async (_title, PageComponent, matcher) => {
    render(<PageComponent />);
    await waitFor(() => expect(screen.getByText(matcher)).toBeTruthy());
  });

  test('purchases page explains receive-stock ownership in inventory', async () => {
    render(<PurchasesPage />);
    await waitFor(() => expect(screen.getByText(/canonical ledger-backed write path/i)).toBeTruthy());
  });

  test('legacy products-stock route redirects into inventory receive stock', async () => {
    vi.resetModules();
    const redirectMock = vi.fn();
    vi.doMock('next/navigation', () => ({
      redirect: redirectMock,
    }));

    const module = await import('@/app/(app)/products-stock/page');
    module.default();

    expect(redirectMock).toHaveBeenCalledWith('/inventory?tab=receive');
    vi.doUnmock('next/navigation');
    vi.resetModules();
  });

  test('preloaded products-stock page import remains available', () => {
    expect(ProductsStockPage).toBeTruthy();
  });
});
