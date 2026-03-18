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
        model_name: 'gpt-5-mini',
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
  saveWhatsAppMetaIntegration: vi.fn(),
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
      model_name: 'gpt-5-mini',
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

const cases = [
  ['Home', HomePage, /the product foundation is live again/i],
  ['Dashboard', DashboardPage, /business analytics dashboard/i],
  ['Reports', ReportsPage, /reset in progress|rebuild foundation/i],
  ['Catalog', CatalogPage, /variant-first catalog/i],
  ['Customers', CustomersPage, /embedded customer records/i],
  ['Inventory', InventoryPage, /variant-level inventory control/i],
  ['Sales', SalesPage, /order-first sales workspace/i],
  ['Sales Agent', SalesAgentPage, /no pending agent orders/i],
  ['Finance', FinancePage, /reset in progress|rebuild foundation/i],
  ['Returns', ReturnsPage, /return and restock control/i],
  ['Integrations & Channels', IntegrationsPage, /whatsapp meta channel/i],
  ['AI Review Inbox', AiReviewPage, /reset in progress|rebuild foundation/i],
  ['Automation', AutomationPage, /reset in progress|rebuild foundation/i],
  ['Settings', SettingsPage, /reset in progress|rebuild foundation/i],
] as const;

describe('Business pages', () => {
  afterEach(() => {
    cleanup();
  });

  test.each(cases)('%s renders its current workspace shell', async (_title, PageComponent, matcher) => {
    render(<PageComponent />);
    await waitFor(() => expect(screen.getByText(matcher)).toBeTruthy());
  });

  test('purchases route redirects into inventory receive stock', async () => {
    vi.resetModules();
    const redirectMock = vi.fn();
    vi.doMock('next/navigation', () => ({
      redirect: redirectMock,
    }));

    const module = await import('@/app/(app)/purchases/page');
    module.default();

    expect(redirectMock).toHaveBeenCalledWith('/inventory?tab=receive');
    vi.doUnmock('next/navigation');
    vi.resetModules();
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
});
