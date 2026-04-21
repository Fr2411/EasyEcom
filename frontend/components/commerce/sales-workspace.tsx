'use client';

import { FormEvent, useEffect, useRef, useState, useTransition } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  cancelSalesOrder,
  confirmSalesOrder,
  fulfillSalesOrder,
  getSalesOrder,
  getSalesOrders,
  saveSalesOrder,
  searchEmbeddedCustomers,
  searchSaleVariants,
} from '@/lib/api/commerce';
import type { EmbeddedCustomer, SaleLookupVariant, SalesOrder, SalesOrderLineInput, SalesOrderPayload } from '@/types/sales';
import type { LookupOutcome, SuggestedAction } from '@/types/guided-workflow';
import {
  DraftRecommendationCard,
  IntentInput,
  MatchGroupList,
  StagedActionFooter,
  SuggestedNextStep,
  WorkspaceEmpty,
  WorkspaceNotice,
  WorkspacePanel,
  WorkspaceTabs,
} from '@/components/commerce/workspace-primitives';
import { formatDateTime, formatMoney, formatQuantity } from '@/lib/commerce-format';
import { ApiError, ApiNetworkError } from '@/lib/api/client';


type SalesTab = 'new' | 'open' | 'completed';

type DraftCustomer = {
  customer_id?: string;
  name: string;
  phone: string;
  email: string;
  address: string;
};

type DraftLine = SalesOrderLineInput & {
  label: string;
  sku: string;
  min_price: string | null;
};

type SalesIntentSuggestion = {
  kind: 'variant' | 'customer' | 'manual';
  title: string;
  detail: string;
  actionLabel?: string;
  secondaryLabel?: string;
  tone?: SuggestedAction['tone'];
};

const EMPTY_CUSTOMER: DraftCustomer = {
  name: '',
  phone: '',
  email: '',
  address: '',
};

function stripRequestUrlFromMessage(message: string) {
  return message.replace(/\s*\(https?:\/\/[^)]+\)\s*$/i, '').trim();
}

function safeSalesWorkspaceErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiNetworkError) {
    return 'Unable to reach sales services right now. Check your connection and try again.';
  }
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return 'You do not have permission to access sales in this workspace.';
    }
    if (error.status >= 500) {
      return 'Sales is temporarily unavailable. Please try again in a moment.';
    }
    return fallback;
  }
  if (error instanceof Error) {
    const cleaned = stripRequestUrlFromMessage(error.message);
    if (cleaned) {
      return cleaned;
    }
  }
  return fallback;
}

function financeStatusLabel(order: SalesOrder) {
  if (order.finance_status === 'posted') return 'Posted to finance';
  if (order.finance_status === 'reversed') return 'Finance reversed';
  if (order.finance_status === 'not_posted') return 'Not posted to finance';
  return 'Finance not yet posted';
}

function financeSummaryText(order: SalesOrder) {
  if (!order.finance_summary) return '';
  const amount = order.finance_summary.amount ? formatMoney(order.finance_summary.amount) : formatMoney(order.total_amount);
  const postedAt = order.finance_summary.posted_at ? ` at ${formatDateTime(order.finance_summary.posted_at)}` : '';
  return `${amount}${postedAt}`;
}

export function deriveSalesIntentSuggestion(
  intentLookup: LookupOutcome<SaleLookupVariant, SaleLookupVariant | EmbeddedCustomer, { name: string; phone: string; email: string }> | null
): SalesIntentSuggestion {
  if (!intentLookup) {
    return {
      kind: 'manual',
      title: 'Start with one customer, order, or product clue',
      detail: 'Type a phone number, email, SKU, barcode, or product name. The workspace will stage likely matches and suggest the next step.',
      actionLabel: 'Stage manual customer',
      tone: 'info',
    };
  }

  if (intentLookup.state === 'exact' && intentLookup.exact[0]) {
    const variant = intentLookup.exact[0];
    return {
      kind: 'variant',
      title: `Exact variant found: ${variant.label}`,
      detail: 'The item has already been staged into the order draft. Review quantity, price, and customer before confirming.',
      actionLabel: 'Add one more',
      secondaryLabel: 'Stage customer',
      tone: 'success',
    };
  }

  if (intentLookup.state === 'likely' && intentLookup.likely.length) {
    return {
      kind: 'customer',
      title: `We found ${intentLookup.likely.length} likely matches`,
      detail: 'Pick the best customer or variant below. If none are correct, continue with a manual customer and keep building the draft.',
      actionLabel: 'Stage manual customer',
      tone: 'warning',
    };
  }

  return {
    kind: 'manual',
    title: 'No direct match found',
    detail: 'Continue with a manual customer and use the suggested product results below if they fit the request.',
    actionLabel: 'Stage manual customer',
    tone: 'warning',
  };
}


function buildOrderPayload(
  customer: DraftCustomer,
  lines: DraftLine[],
  notes: string,
  action: SalesOrderPayload['action']
): SalesOrderPayload {
  return {
    customer_id: customer.customer_id,
    customer: customer.customer_id
      ? undefined
      : {
          name: customer.name,
          phone: customer.phone,
          email: customer.email,
          address: customer.address,
        },
    payment_status: 'unpaid',
    shipment_status: 'pending',
    notes,
    lines: lines.map(({ variant_id, quantity, unit_price, discount_amount }) => ({
      variant_id,
      quantity,
      unit_price,
      discount_amount,
    })),
    action,
  };
}


export function SalesWorkspace() {
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const handledSeedKeyRef = useRef('');
  const [activeTab, setActiveTab] = useState<SalesTab>('new');
  const [isCompactViewport, setIsCompactViewport] = useState(false);
  const [orderStarted, setOrderStarted] = useState(false);
  const [variantResults, setVariantResults] = useState<SaleLookupVariant[]>([]);
  const [customerPhone, setCustomerPhone] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [customerResults, setCustomerResults] = useState<EmbeddedCustomer[]>([]);
  const [intentQuery, setIntentQuery] = useState('');
  const [intentLookup, setIntentLookup] = useState<LookupOutcome<SaleLookupVariant, SaleLookupVariant | EmbeddedCustomer, { name: string; phone: string; email: string }> | null>(null);
  const [customer, setCustomer] = useState<DraftCustomer>({ ...EMPTY_CUSTOMER });
  const [draftLines, setDraftLines] = useState<DraftLine[]>([]);
  const [notes, setNotes] = useState('');
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<SalesOrder | null>(null);
  const [orderQuery, setOrderQuery] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [lookupPending, setLookupPending] = useState(false);
  const [showAdvancedTools, setShowAdvancedTools] = useState(false);
  const [isPending, startTransition] = useTransition();

  const loadOrders = (query = '') => {
    startTransition(async () => {
      try {
        const payload = await getSalesOrders({ q: query });
        setOrders(payload.items);
        if (selectedOrder) {
          const refreshed = payload.items.find((item) => item.sales_order_id === selectedOrder.sales_order_id);
          if (refreshed) {
            setSelectedOrder(refreshed);
          }
        }
        setError('');
      } catch (loadError) {
        setError(safeSalesWorkspaceErrorMessage(loadError, 'Unable to load sales orders. Try refreshing the workspace.'));
      }
    });
  };

  useEffect(() => {
    const query = searchParams.get('q') ?? '';
    setOrderQuery(query);
    loadOrders(query);
  }, [searchKey]);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      setIsCompactViewport(false);
      setOrderStarted(true);
      return;
    }

    const mobileQuery = window.matchMedia('(max-width: 900px)');
    const updateViewportState = () => {
      setIsCompactViewport(mobileQuery.matches);
      if (!mobileQuery.matches) {
        setOrderStarted(true);
      }
    };

    updateViewportState();
    mobileQuery.addEventListener('change', updateViewportState);
    return () => mobileQuery.removeEventListener('change', updateViewportState);
  }, []);

  const filteredOrders = orders.filter((order) => {
    if (activeTab === 'open') {
      return order.status === 'draft' || order.status === 'confirmed';
    }
    if (activeTab === 'completed') {
      return order.status === 'completed';
    }
    return true;
  });

  const addVariantToDraft = (variant: SaleLookupVariant) => {
    setDraftLines((current) => {
      const existing = current.find((item) => item.variant_id === variant.variant_id);
      if (existing) {
        return current.map((item) =>
          item.variant_id === variant.variant_id
            ? {
                ...item,
                quantity: String(Number(item.quantity) + 1),
              }
            : item
        );
      }
      return [
        ...current,
        {
          variant_id: variant.variant_id,
          label: variant.label,
          sku: variant.sku,
          min_price: variant.min_price,
          quantity: '1',
          unit_price: variant.unit_price,
          discount_amount: '0',
        },
      ];
    });
  };

  useEffect(() => {
    const seedVariantId = (searchParams.get('seed_variant_id') ?? '').trim();
    const seedSku = (searchParams.get('seed_sku') ?? '').trim();
    if (!seedVariantId && !seedSku) {
      handledSeedKeyRef.current = '';
      return;
    }

    const seedKey = `${seedVariantId}|${seedSku}`;
    if (handledSeedKeyRef.current === seedKey) {
      return;
    }
    handledSeedKeyRef.current = seedKey;

    const seedLookup = seedSku || seedVariantId;
    setOrderStarted(true);
    setActiveTab('new');
    setNotice('');
    setError('');
    setLookupPending(true);

    void (async () => {
      try {
        const payload = await searchSaleVariants({ q: seedLookup });
        setVariantResults(payload.items);

        const seededVariant =
          payload.items.find((item) => seedVariantId && item.variant_id === seedVariantId)
          ?? payload.items.find((item) => seedSku && item.sku.toLowerCase() === seedSku.toLowerCase())
          ?? payload.items.find((item) => seedSku && item.barcode.toLowerCase() === seedSku.toLowerCase());

        if (!seededVariant) {
          setNotice('Inventory prefill could not resolve the selected variant. Continue with the normal sales flow.');
          return;
        }

        addVariantToDraft(seededVariant);
        setNotice(`Seeded ${seededVariant.label} from Inventory.`);
        setError('');
      } catch (seedError) {
        setError(safeSalesWorkspaceErrorMessage(seedError, 'Unable to prefill the selected inventory variant. Continue with normal sales flow.'));
      } finally {
        setLookupPending(false);
      }
    })();
  }, [searchKey]);

  const runIntentLookup = async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) {
      setIntentLookup(null);
      setVariantResults([]);
      setCustomerResults([]);
      return;
    }

    setLookupPending(true);
    try {
      const [variantsPayload, customersPayload] = await Promise.all([
        searchSaleVariants({ q: trimmed }),
        searchEmbeddedCustomers({
          phone: trimmed,
          email: trimmed.includes('@') ? trimmed : undefined,
        }),
      ]);

      const exactVariants = variantsPayload.items.filter((item) => {
        const lower = trimmed.toLowerCase();
        return item.sku.toLowerCase() === lower || item.barcode.toLowerCase() === lower;
      });

      const likely = [
        ...variantsPayload.items.filter((item) => !exactVariants.some((exact) => exact.variant_id === item.variant_id)),
        ...customersPayload.items,
      ];

      const suggestion: LookupOutcome<SaleLookupVariant, SaleLookupVariant | EmbeddedCustomer, { name: string; phone: string; email: string }> = {
        state:
          exactVariants.length
            ? 'exact'
            : likely.length
              ? 'likely'
              : 'new',
        query: trimmed,
        exact: exactVariants,
        likely,
        suggestedNew: {
          name: '',
          phone: trimmed.includes('@') ? '' : trimmed,
          email: trimmed.includes('@') ? trimmed : '',
        },
      };

      setVariantResults(variantsPayload.items);
      setCustomerResults(customersPayload.items);
      setIntentLookup(suggestion);
      setError('');

      if (exactVariants[0]) {
        addVariantToDraft(exactVariants[0]);
        setNotice(`Added ${exactVariants[0].label} to the draft. Review quantity and customer details before saving.`);
      }
    } catch (lookupError) {
      setError(safeSalesWorkspaceErrorMessage(lookupError, 'Unable to interpret the sales intent. Try another customer or product clue.'));
    } finally {
      setLookupPending(false);
    }
  };

  const useCustomer = (item: EmbeddedCustomer) => {
    setCustomer({
      customer_id: item.customer_id,
      name: item.name,
      phone: item.phone,
      email: item.email,
      address: '',
    });
    setNotice(`Customer ${item.name} is staged for this order.`);
  };

  const stageManualCustomer = () => {
    setCustomerResults([]);
    setCustomer((current) => ({
      ...current,
      phone: current.phone || (intentLookup?.suggestedNew?.phone ?? customerPhone),
      email: current.email || (intentLookup?.suggestedNew?.email ?? customerEmail),
    }));
    setNotice('Manual customer entry is ready. Complete the customer details and review the draft.');
  };

  const submitOrder = async (action: SalesOrderPayload['action']) => {
    setNotice('');
    setError('');
    const invalidLine = draftLines.find((line) => {
      const quantity = Number(line.quantity || '0');
      const unitPrice = Number(line.unit_price || '0');
      const discount = Number(line.discount_amount || '0');
      if (!Number.isFinite(quantity) || !Number.isFinite(unitPrice) || quantity <= 0 || unitPrice <= 0) {
        return true;
      }
      if (!line.min_price) {
        return false;
      }
      const minPrice = Number(line.min_price);
      if (!Number.isFinite(minPrice) || minPrice <= 0) {
        return false;
      }
      return quantity * unitPrice - discount < quantity * minPrice;
    });
    if (invalidLine) {
      setError(`Line price for ${invalidLine.label} is below its minimum selling price.`);
      return;
    }
    try {
      const response = await saveSalesOrder(buildOrderPayload(customer, draftLines, notes, action));
      setSelectedOrder(response.order);
      setNotice(
        action === 'save_draft'
          ? 'Draft order saved.'
          : action === 'confirm'
            ? 'Order confirmed and stock reserved.'
            : response.order.finance_status === 'posted'
              ? `Order fulfilled and ${financeStatusLabel(response.order).toLowerCase()}.`
              : 'Order confirmed and fulfilled.'
      );
      setDraftLines([]);
      setCustomer({ ...EMPTY_CUSTOMER });
      setCustomerPhone('');
      setCustomerEmail('');
      setCustomerResults([]);
      setVariantResults([]);
      setIntentQuery('');
      setIntentLookup(null);
      setNotes('');
      await loadOrders(orderQuery.trim());
      setActiveTab(action === 'confirm_and_fulfill' ? 'completed' : 'open');
    } catch (submitError) {
      setError(safeSalesWorkspaceErrorMessage(submitError, 'Unable to save the order. Review details and try again.'));
    }
  };

  const loadOrderDetail = async (orderId: string) => {
    try {
      const payload = await getSalesOrder(orderId);
      setSelectedOrder(payload);
      setError('');
    } catch (detailError) {
      setError(safeSalesWorkspaceErrorMessage(detailError, 'Unable to load order details right now.'));
    }
  };

  const runOrderAction = async (action: 'confirm' | 'fulfill' | 'cancel', orderId: string) => {
    try {
      const response =
        action === 'confirm'
          ? await confirmSalesOrder(orderId)
          : action === 'fulfill'
            ? await fulfillSalesOrder(orderId)
            : await cancelSalesOrder(orderId);
      setSelectedOrder(response.order);
      setNotice(
        action === 'confirm'
          ? 'Draft order confirmed.'
          : action === 'fulfill'
            ? 'Order fulfilled and stock deducted.'
            : 'Order cancelled and reservation released.'
      );
      await loadOrders(orderQuery.trim());
    } catch (actionError) {
      setError(safeSalesWorkspaceErrorMessage(actionError, 'Unable to update the order right now. Try again.'));
    }
  };

  const intentSuggestion = deriveSalesIntentSuggestion(intentLookup);
  const shouldGateMobileStart = isCompactViewport && !orderStarted;
  const showOrderSearchInHeader = !(isCompactViewport && activeTab === 'new');

  return (
    <div className="workspace-stack">
      <WorkspaceTabs
        tabs={[
          { id: 'new', label: 'New Order' },
          { id: 'open', label: 'Open Orders' },
          { id: 'completed', label: 'Completed' },
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <WorkspacePanel
        title="Order-first sales workspace"
        hint="Create orders from available variants only, reserve truthfully, and fulfill with audited stock impact."
        actions={showOrderSearchInHeader ? (
          <form
            className="workspace-search"
            onSubmit={(event) => {
              event.preventDefault();
              loadOrders(orderQuery.trim());
            }}
          >
            <input
              type="search"
              value={orderQuery}
              placeholder="Search order number, phone, email"
              onChange={(event) => setOrderQuery(event.target.value)}
            />
            <button type="submit">Search</button>
          </form>
        ) : null}
      >
        {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
        {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}
        {isPending && !orders.length ? <WorkspaceNotice>Loading sales workspace…</WorkspaceNotice> : null}

        {activeTab === 'new' ? (
          <div className={shouldGateMobileStart ? 'workspace-two-column sales-start-focus-mode' : 'workspace-two-column'}>
            <div className="workspace-stack">
              <DraftRecommendationCard
                title="Start new order"
                summary={
                  shouldGateMobileStart
                    ? 'Open a new order first so the team can immediately capture the sale.'
                    : isCompactViewport
                      ? 'Order started. Next: enter one customer or product clue below to stage the draft.'
                    : 'Start with one buyer or product clue, then stage customer and lines before confirmation.'
                }
                actions={(
                  <button
                    type="button"
                    className={`btn-primary sales-start-order-btn${shouldGateMobileStart ? ' sales-start-order-btn--mobile-gate' : ''}`}
                    onClick={() => {
                      setOrderStarted(true);
                      setShowAdvancedTools(false);
                      setIntentLookup(null);
                      setVariantResults([]);
                      setCustomerResults([]);
                      stageManualCustomer();
                    }}
                  >
                    Start new order
                  </button>
                )}
              >
                <div className="workspace-inline-actions">
                  {!shouldGateMobileStart ? (
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => setShowAdvancedTools((current) => !current)}
                    >
                      {showAdvancedTools ? 'Hide advanced matching tools' : 'Show advanced matching tools'}
                    </button>
                  ) : null}
                </div>
              </DraftRecommendationCard>

              {!shouldGateMobileStart ? (
              <IntentInput
                label="Who is buying or what do they want?"
                hint="Use one clue to stage the fastest path to a completed order and avoid back-and-forth lookup work."
                value={intentQuery}
                placeholder="Phone, email, order clue, SKU, barcode, or product"
                pending={lookupPending}
                submitLabel="Find customer or item"
                onChange={setIntentQuery}
                onSubmit={() => runIntentLookup(intentQuery)}
              >
                <span className="guided-assist-chip">One clue is enough. Stage the best match, then keep the order moving.</span>
              </IntentInput>
              ) : null}

              {!shouldGateMobileStart && showAdvancedTools ? (
                <SuggestedNextStep
                  suggestion={intentSuggestion}
                  onPrimary={() => {
                    if (intentSuggestion.kind === 'variant' && intentLookup?.exact[0]) {
                      addVariantToDraft(intentLookup.exact[0]);
                      return;
                    }
                    stageManualCustomer();
                  }}
                  onSecondary={() => {
                    if (intentLookup?.query) {
                      setCustomerPhone(intentLookup.suggestedNew?.phone ?? '');
                      setCustomerEmail(intentLookup.suggestedNew?.email ?? '');
                    }
                    stageManualCustomer();
                  }}
                />
              ) : null}

              {!shouldGateMobileStart && showAdvancedTools ? (
                <MatchGroupList
                  title="Likely customer matches"
                  description="Reuse known customer profiles to shorten checkout time and reduce order-entry errors."
                  items={customerResults}
                  emptyMessage="No customer account matched yet."
                  renderItem={(item) => (
                    <article key={item.customer_id} className="guided-match-item">
                      <div className="guided-match-item-header">
                        <div>
                          <h5>{item.name}</h5>
                          <p>{item.phone || item.email || 'No contact details'}</p>
                        </div>
                        <button type="button" onClick={() => useCustomer(item)}>
                          Use customer
                        </button>
                      </div>
                    </article>
                  )}
                />
              ) : null}

              {!shouldGateMobileStart && showAdvancedTools ? (
                <MatchGroupList
                  title="Likely saleable items"
                  description="Only sellable variants are shown so the draft stays aligned with real available stock."
                  items={variantResults}
                  emptyMessage="No sellable variants matched the current clue yet."
                  renderItem={(variant) => (
                    <article key={variant.variant_id} className="guided-match-item">
                      <div className="guided-match-item-header">
                        <div>
                          <h5>{variant.label}</h5>
                          <p>{variant.sku}</p>
                        </div>
                        <button type="button" onClick={() => addVariantToDraft(variant)}>
                          Add to draft order
                        </button>
                      </div>
                      <div className="guided-match-item-meta">
                        <span>Available {formatQuantity(variant.available_to_sell)}</span>
                        <span>Effective selling price {formatMoney(variant.unit_price)}</span>
                        <span>Min {formatMoney(variant.min_price)}</span>
                      </div>
                    </article>
                  )}
                />
              ) : null}

              {!shouldGateMobileStart ? (
                <DraftRecommendationCard
                  title="Customer staging"
                  summary={customer.customer_id
                    ? `Existing customer ${customer.name} is staged for this order.`
                    : customer.name || customer.phone || customer.email
                      ? 'A manual customer draft is staged. Complete missing details now to prevent fulfillment delays.'
                      : 'No customer is staged yet. Use the intent bar to prefill this step and reduce checkout time.'}
                >
                  <div className="workspace-inline-actions">
                    <label>
                      Phone
                      <input value={customerPhone} onChange={(event) => setCustomerPhone(event.target.value)} />
                    </label>
                    <label>
                      Email
                      <input value={customerEmail} onChange={(event) => setCustomerEmail(event.target.value)} />
                    </label>
                    <button type="button" onClick={() => void runIntentLookup(customerPhone || customerEmail)}>
                      Refresh customer clues
                    </button>
                  </div>
                  <div className="workspace-form-grid compact">
                    <label>
                      Name
                      <input
                        value={customer.name}
                        onChange={(event) => setCustomer((current) => ({ ...current, name: event.target.value }))}
                        required
                      />
                    </label>
                    <label>
                      Phone
                      <input
                        value={customer.phone}
                        onChange={(event) => setCustomer((current) => ({ ...current, phone: event.target.value }))}
                        required
                      />
                    </label>
                    <label>
                      Email
                      <input
                        value={customer.email}
                        onChange={(event) => setCustomer((current) => ({ ...current, email: event.target.value }))}
                      />
                    </label>
                  </div>
                </DraftRecommendationCard>
              ) : null}
            </div>

            {!shouldGateMobileStart ? (
            <DraftRecommendationCard
              title="Order draft"
              summary={draftLines.length
                ? `${draftLines.length} line${draftLines.length === 1 ? '' : 's'} staged. Validate pricing now so margin stays protected before confirmation.`
                : 'No lines staged yet.'}
              summaryHint={!draftLines.length ? 'The draft is empty. Stage customer and variant details first so the order can move to confirmation without rework.' : undefined}
            >
              {draftLines.length ? (
                <div className="table-scroll">
                  <table className="workspace-table">
                    <thead>
                      <tr>
                        <th>Variant</th>
                        <th>Quantity</th>
                        <th>Line Selling Price</th>
                        <th>Discount</th>
                        <th>Total</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {draftLines.map((line) => (
                        <tr key={line.variant_id}>
                          <td>{line.label}</td>
                          <td>
                            <input
                              value={line.quantity}
                              onChange={(event) =>
                                setDraftLines((current) =>
                                  current.map((item) =>
                                    item.variant_id === line.variant_id ? { ...item, quantity: event.target.value } : item
                                  )
                                )
                              }
                            />
                          </td>
                          <td>
                            <input
                              value={line.unit_price}
                              onChange={(event) =>
                                setDraftLines((current) =>
                                  current.map((item) =>
                                    item.variant_id === line.variant_id ? { ...item, unit_price: event.target.value } : item
                                  )
                                )
                              }
                            />
                          </td>
                          <td>
                            <input
                              value={line.discount_amount}
                              onChange={(event) =>
                                setDraftLines((current) =>
                                  current.map((item) =>
                                    item.variant_id === line.variant_id
                                      ? { ...item, discount_amount: event.target.value }
                                      : item
                                  )
                                )
                              }
                            />
                          </td>
                          <td>
                            <div>{formatMoney(Number(line.quantity) * Number(line.unit_price) - Number(line.discount_amount || '0'))}</div>
                            {line.min_price ? <div className="workspace-field-note">Min {formatMoney(line.min_price)}</div> : null}
                          </td>
                          <td>
                            <button
                              type="button"
                              onClick={() => setDraftLines((current) => current.filter((item) => item.variant_id !== line.variant_id))}
                            >
                              Remove line
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <WorkspaceEmpty
                  title="No variants in the draft"
                  message="Add one or many available variants to start the order."
                />
              )}
              <label>
                Order notes
                <textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} />
              </label>
              <div className="sales-post-start-action-region">
                <StagedActionFooter summary="No stock or finance write happens until you choose draft, confirm, or confirm and fulfill.">
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => submitOrder('save_draft')}
                    disabled={!draftLines.length}
                  >
                    Review before saving
                  </button>
                  <button
                    type="button"
                    className="btn-primary sales-primary-next-action"
                    onClick={() => submitOrder('confirm')}
                    disabled={!draftLines.length}
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    className="secondary sales-finalize-action"
                    onClick={() => submitOrder('confirm_and_fulfill')}
                    disabled={!draftLines.length}
                  >
                    Confirm & Fulfill
                  </button>
                </StagedActionFooter>
                <p className="sales-primary-action-note">
                  Primary next action is <strong>Confirm</strong>. Use Confirm &amp; Fulfill only after draft lines and pricing are reviewed.
                </p>
              </div>
            </DraftRecommendationCard>
            ) : null}
          </div>
        ) : (
          <div className="workspace-two-column">
            <div className="workspace-stack">
              {filteredOrders.length ? (
                filteredOrders.map((order) => (
                  <button
                    key={order.sales_order_id}
                    type="button"
                    className={`selection-card ${selectedOrder?.sales_order_id === order.sales_order_id ? 'active' : ''}`}
                    onClick={() => loadOrderDetail(order.sales_order_id)}
                  >
                    <strong>{order.order_number}</strong>
                    <span>{order.customer_name} · {order.status} · {formatMoney(order.total_amount)}</span>
                    {order.finance_status ? <span className="status-pill">{financeStatusLabel(order)}</span> : null}
                  </button>
                ))
              ) : (
                <WorkspaceEmpty
                  title={activeTab === 'open' ? 'No open orders' : 'No completed orders'}
                  message="Orders will appear here as staff create and move them through the lifecycle."
                />
              )}
            </div>

            <WorkspacePanel
              title={selectedOrder ? selectedOrder.order_number : 'Order detail'}
              description={selectedOrder ? `${selectedOrder.customer_name} · ${selectedOrder.status}` : 'Select an order to inspect or act on it.'}
            >
              {selectedOrder ? (
                <>
                  <div className="commerce-card-meta">
                    <span>Customer: {selectedOrder.customer_phone || selectedOrder.customer_email}</span>
                    <span>Ordered: {formatDateTime(selectedOrder.ordered_at)}</span>
                    <span>Total: {formatMoney(selectedOrder.total_amount)}</span>
                  </div>
                  <div className="workspace-inline-actions">
                    <span className="status-pill">{financeStatusLabel(selectedOrder)}</span>
                    {selectedOrder.finance_summary ? <span>{financeSummaryText(selectedOrder)}</span> : null}
                    {selectedOrder.payment_status ? <span>Payment {selectedOrder.payment_status}</span> : null}
                  </div>
                  <div className="table-scroll">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>Variant</th>
                          <th>Ordered</th>
                          <th>Fulfilled</th>
                          <th>Reserved</th>
                          <th>Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedOrder.lines.map((line) => (
                          <tr key={line.sales_order_item_id}>
                            <td>{line.label}</td>
                            <td>{formatQuantity(line.quantity)}</td>
                            <td>{formatQuantity(line.quantity_fulfilled)}</td>
                            <td>{formatQuantity(line.reserved_quantity)}</td>
                            <td>{formatMoney(line.line_total)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="workspace-actions">
                    {selectedOrder.status === 'draft' ? (
                      <button type="button" onClick={() => runOrderAction('confirm', selectedOrder.sales_order_id)}>
                        Confirm order
                      </button>
                    ) : null}
                    {selectedOrder.status === 'confirmed' ? (
                      <button type="button" onClick={() => runOrderAction('fulfill', selectedOrder.sales_order_id)}>
                        Fulfill order
                      </button>
                    ) : null}
                    {(selectedOrder.status === 'draft' || selectedOrder.status === 'confirmed') ? (
                      <button type="button" onClick={() => runOrderAction('cancel', selectedOrder.sales_order_id)}>
                        Cancel order
                      </button>
                    ) : null}
                  </div>
                </>
              ) : (
                <WorkspaceEmpty
                  title="No order selected"
                  message="Choose an order from the list to review details and next actions."
                />
              )}
            </WorkspacePanel>
          </div>
        )}
      </WorkspacePanel>
      <div className="mobile-action-safe-spacer" aria-hidden="true" />
    </div>
  );
}
