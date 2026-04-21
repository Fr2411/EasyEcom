'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
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
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel, WorkspaceTabs } from '@/components/commerce/workspace-primitives';
import { ApiError, ApiNetworkError } from '@/lib/api/client';
import { formatDateTime, formatMoney, formatQuantity } from '@/lib/commerce-format';

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
    if (cleaned) return cleaned;
  }
  return fallback;
}

function buildOrderPayload(
  customer: DraftCustomer,
  lines: DraftLine[],
  notes: string,
  action: SalesOrderPayload['action'],
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

function financeStatusLabel(order: SalesOrder) {
  if (order.finance_status === 'posted') return 'Posted to finance';
  if (order.finance_status === 'reversed') return 'Finance reversed';
  if (order.finance_status === 'not_posted') return 'Not posted to finance';
  return 'Finance not yet posted';
}

function buildSeedKey(searchParams: { get: (name: string) => string | null }) {
  return [
    (searchParams.get('seed_order_id') ?? '').trim(),
    (searchParams.get('seed_variant_id') ?? '').trim(),
    (searchParams.get('seed_sku') ?? '').trim(),
    (searchParams.get('seed_phone') ?? '').trim(),
    (searchParams.get('seed_email') ?? '').trim(),
    (searchParams.get('seed_name') ?? '').trim(),
  ].join('|');
}

export function SalesWorkspace() {
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const handledSeedKeyRef = useRef('');
  const handledOrderSeedRef = useRef('');
  const [activeTab, setActiveTab] = useState<SalesTab>('new');
  const [lookupQuery, setLookupQuery] = useState('');
  const [lookupPending, setLookupPending] = useState(false);
  const [variantResults, setVariantResults] = useState<SaleLookupVariant[]>([]);
  const [customerResults, setCustomerResults] = useState<EmbeddedCustomer[]>([]);
  const [customer, setCustomer] = useState<DraftCustomer>({ ...EMPTY_CUSTOMER });
  const [draftLines, setDraftLines] = useState<DraftLine[]>([]);
  const [notes, setNotes] = useState('');
  const [orderQuery, setOrderQuery] = useState('');
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(true);
  const [selectedOrder, setSelectedOrder] = useState<SalesOrder | null>(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const loadOrders = async (query = '') => {
    setOrdersLoading(true);
    try {
      const payload = await getSalesOrders({ q: query });
      setOrders(payload.items ?? []);
      setError('');
    } catch (loadError) {
      setError(safeSalesWorkspaceErrorMessage(loadError, 'Unable to load sales orders.'));
    } finally {
      setOrdersLoading(false);
    }
  };

  useEffect(() => {
    const tab = (searchParams.get('tab') ?? '').trim();
    const q = (searchParams.get('q') ?? '').trim();
    setOrderQuery(q);
    if (tab === 'open' || tab === 'completed' || tab === 'new') {
      setActiveTab(tab);
    } else if (q) {
      setActiveTab('open');
    }
    void loadOrders(q);
  }, [searchKey]);

  useEffect(() => {
    const seedOrderId = (searchParams.get('seed_order_id') ?? '').trim();
    if (!seedOrderId) {
      handledOrderSeedRef.current = '';
      return;
    }
    if (handledOrderSeedRef.current === seedOrderId) {
      return;
    }
    handledOrderSeedRef.current = seedOrderId;
    setActiveTab('open');
    setNotice('');
    setError('');

    void (async () => {
      try {
        const order = await getSalesOrder(seedOrderId);
        const nextTab = order.status === 'completed' ? 'completed' : 'open';
        setSelectedOrder(order);
        setOrderQuery(order.order_number);
        setActiveTab(nextTab);
        await loadOrders(order.order_number);
        setNotice(`Opened order ${order.order_number}.`);
      } catch (seedError) {
        setError(safeSalesWorkspaceErrorMessage(seedError, 'Unable to open the requested order.'));
      }
    })();
  }, [searchKey]);

  const addVariantToDraft = (variant: SaleLookupVariant) => {
    setDraftLines((current) => {
      const existing = current.find((item) => item.variant_id === variant.variant_id);
      if (existing) {
        return current.map((item) =>
          item.variant_id === variant.variant_id
            ? { ...item, quantity: String(Number(item.quantity || '0') + 1) }
            : item,
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
    const seedKey = buildSeedKey(searchParams);
    if (!seedKey.replaceAll('|', '')) {
      handledSeedKeyRef.current = '';
      return;
    }
    if (handledSeedKeyRef.current === seedKey) {
      return;
    }
    handledSeedKeyRef.current = seedKey;

    const seedVariantId = (searchParams.get('seed_variant_id') ?? '').trim();
    const seedSku = (searchParams.get('seed_sku') ?? '').trim();
    const seedPhone = (searchParams.get('seed_phone') ?? '').trim();
    const seedEmail = (searchParams.get('seed_email') ?? '').trim();
    const seedName = (searchParams.get('seed_name') ?? '').trim();
    const seedOrderId = (searchParams.get('seed_order_id') ?? '').trim();

    if (seedOrderId) {
      return;
    }

    setActiveTab('new');

    if (seedName || seedPhone || seedEmail) {
      setCustomer((current) => ({
        ...current,
        name: seedName || current.name,
        phone: seedPhone || current.phone,
        email: seedEmail || current.email,
      }));
      setNotice('Customer details were prefilled for a new order.');
    }

    if (seedPhone || seedEmail) {
      void (async () => {
        try {
          const payload = await searchEmbeddedCustomers({
            phone: seedPhone || undefined,
            email: seedEmail || undefined,
          });
          setCustomerResults(payload.items ?? []);
          const matched = payload.items?.[0];
          if (matched) {
            setCustomer({
              customer_id: matched.customer_id,
              name: matched.name,
              phone: matched.phone,
              email: matched.email,
              address: '',
            });
          }
        } catch {
          // Keep the seeded customer draft even if lookup fails.
        }
      })();
    }

    if (seedVariantId || seedSku) {
      setLookupPending(true);
      void (async () => {
        try {
          const seedLookup = seedSku || seedVariantId;
          const payload = await searchSaleVariants({ q: seedLookup });
          setVariantResults(payload.items ?? []);
          const seededVariant =
            payload.items.find((item) => seedVariantId && item.variant_id === seedVariantId) ??
            payload.items.find((item) => seedSku && item.sku.toLowerCase() === seedSku.toLowerCase());
          if (!seededVariant) {
            setNotice('Inventory prefill could not resolve that variant. Continue with the normal sales flow.');
            return;
          }
          addVariantToDraft(seededVariant);
          setNotice(`Added ${seededVariant.label} from Inventory.`);
        } catch (seedError) {
          setError(safeSalesWorkspaceErrorMessage(seedError, 'Unable to prefill the selected variant.'));
        } finally {
          setLookupPending(false);
        }
      })();
    }
  }, [searchKey]);

  const runLookup = async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) {
      setVariantResults([]);
      setCustomerResults([]);
      return;
    }

    setLookupPending(true);
    setNotice('');
    try {
      const normalizedPhone = trimmed.replace(/\D/g, '');
      const shouldLookupCustomers = normalizedPhone.length >= 3 || trimmed.includes('@');
      const [variantsPayload, customersPayload] = await Promise.all([
        searchSaleVariants({ q: trimmed }),
        shouldLookupCustomers
          ? searchEmbeddedCustomers({
              phone: normalizedPhone.length >= 3 ? trimmed : undefined,
              email: trimmed.includes('@') ? trimmed : undefined,
            })
          : Promise.resolve({ items: [] as EmbeddedCustomer[] }),
      ]);
      setVariantResults(variantsPayload.items ?? []);
      setCustomerResults(customersPayload.items ?? []);
      setError('');

      const exactVariant = variantsPayload.items.find((item) => item.sku.toLowerCase() === trimmed.toLowerCase());
      if (exactVariant) {
        addVariantToDraft(exactVariant);
        setNotice(`Added ${exactVariant.label} to the order.`);
      } else if (!customer.phone && /^\+?[0-9][0-9\s-]{5,}$/.test(trimmed)) {
        setCustomer((current) => ({ ...current, phone: trimmed }));
      } else if (!customer.email && trimmed.includes('@')) {
        setCustomer((current) => ({ ...current, email: trimmed }));
      }
    } catch (lookupError) {
      setError(safeSalesWorkspaceErrorMessage(lookupError, 'Unable to search products or customers right now.'));
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
    setNotice(`Customer ${item.name} is attached to the order.`);
  };

  const submitOrder = async (action: SalesOrderPayload['action']) => {
    if (!draftLines.length) {
      setError('Add at least one line before saving the order.');
      return;
    }
    if (!customer.customer_id && !customer.name.trim()) {
      setError('Customer name is required for a new order.');
      return;
    }

    const invalidLine = draftLines.find((line) => {
      const quantity = Number(line.quantity || '0');
      const unitPrice = Number(line.unit_price || '0');
      const discount = Number(line.discount_amount || '0');
      if (!Number.isFinite(quantity) || !Number.isFinite(unitPrice) || quantity <= 0 || unitPrice <= 0) {
        return true;
      }
      if (!line.min_price) return false;
      const minPrice = Number(line.min_price);
      return Number.isFinite(minPrice) && minPrice > 0 && quantity * unitPrice - discount < quantity * minPrice;
    });
    if (invalidLine) {
      setError(`Line price for ${invalidLine.label} is below its minimum selling price.`);
      return;
    }

    setSaving(true);
    setNotice('');
    setError('');
    try {
      const response = await saveSalesOrder(buildOrderPayload(customer, draftLines, notes, action));
      setSelectedOrder(response.order);
      setDraftLines([]);
      setCustomer({ ...EMPTY_CUSTOMER });
      setLookupQuery('');
      setVariantResults([]);
      setCustomerResults([]);
      setNotes('');
      await loadOrders(orderQuery.trim());
      setActiveTab(action === 'confirm_and_fulfill' ? 'completed' : 'open');
      setNotice(
        action === 'save_draft'
          ? `Draft order ${response.order.order_number} saved.`
          : action === 'confirm'
            ? `Order ${response.order.order_number} reserved and moved to open orders.`
            : `Sale ${response.order.order_number} completed and stock updated.`,
      );
    } catch (submitError) {
      setError(safeSalesWorkspaceErrorMessage(submitError, 'Unable to save the order.'));
    } finally {
      setSaving(false);
    }
  };

  const loadOrderDetail = async (orderId: string) => {
    try {
      const payload = await getSalesOrder(orderId);
      setSelectedOrder(payload);
      setError('');
    } catch (detailError) {
      setError(safeSalesWorkspaceErrorMessage(detailError, 'Unable to load order details.'));
    }
  };

  const runOrderAction = async (action: 'confirm' | 'fulfill' | 'cancel', orderId: string) => {
    setNotice('');
    setError('');
    try {
      const response =
        action === 'confirm'
          ? await confirmSalesOrder(orderId)
          : action === 'fulfill'
            ? await fulfillSalesOrder(orderId)
            : await cancelSalesOrder(orderId);
      setSelectedOrder(response.order);
      await loadOrders(orderQuery.trim());
      setNotice(
        action === 'confirm'
          ? `Order ${response.order.order_number} reserved and moved to open orders.`
          : action === 'fulfill'
            ? `Sale ${response.order.order_number} completed and stock updated.`
            : `Order ${response.order.order_number} cancelled.`,
      );
    } catch (actionError) {
      setError(safeSalesWorkspaceErrorMessage(actionError, 'Unable to update the order.'));
    }
  };

  const resetComposer = () => {
    setActiveTab('new');
    setLookupQuery('');
    setVariantResults([]);
    setCustomerResults([]);
    setCustomer({ ...EMPTY_CUSTOMER });
    setDraftLines([]);
    setNotes('');
    setNotice('');
    setError('');
  };

  const filteredOrders = orders.filter((order) => {
    if (activeTab === 'open') {
      return order.status === 'draft' || order.status === 'confirmed';
    }
    if (activeTab === 'completed') {
      return order.status === 'completed';
    }
    return true;
  });

  const orderSummary = useMemo(() => {
    const subtotal = draftLines.reduce((sum, line) => sum + Number(line.quantity || '0') * Number(line.unit_price || '0'), 0);
    const discount = draftLines.reduce((sum, line) => sum + Number(line.discount_amount || '0'), 0);
    return {
      subtotal,
      discount,
      total: subtotal - discount,
    };
  }, [draftLines]);

  return (
    <div className="operations-page sales-module">
      <div className="operations-toolbar">
        <div>
          <h2>Find product, attach customer, complete the sale</h2>
        </div>
        <div className="operations-toolbar-actions">
          <button type="button" className="btn-primary" onClick={resetComposer}>New Order</button>
        </div>
      </div>

      <WorkspaceTabs
        tabs={[
          { id: 'new', label: 'New' },
          { id: 'open', label: 'Open' },
          { id: 'completed', label: 'Completed' },
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      {activeTab === 'new' ? (
        <WorkspacePanel title="Order desk" description="One search row, one cart, and one customer block. Everything else is secondary.">
          <div className="operations-split-layout sales-desk-layout">
            <div className="operations-detail-stack">
              <form
                className="operations-search-bar"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runLookup(lookupQuery);
                }}
              >
                <input
                  type="search"
                  value={lookupQuery}
                  placeholder="Search SKU, product, phone, or email"
                  onChange={(event) => setLookupQuery(event.target.value)}
                />
                <button type="submit" className="btn-primary" disabled={lookupPending}>
                  {lookupPending ? 'Searching…' : 'Search'}
                </button>
              </form>

              {(variantResults.length || customerResults.length) ? (
                <div className="operations-dual-section sales-results-grid">
                  <section>
                    <div className="operations-section-heading">
                      <h4>Matching items</h4>
                    </div>
                    {variantResults.length ? (
                      <div className="operations-list-stack compact">
                        {variantResults.map((variant) => (
                          <button key={variant.variant_id} type="button" className="operations-list-card static as-button" onClick={() => addVariantToDraft(variant)}>
                            <div className="operations-list-card-head">
                              <strong>{variant.label}</strong>
                              <span>{formatMoney(variant.unit_price)}</span>
                            </div>
                            <p>{variant.sku}</p>
                            <div className="operations-inline-meta compact">
                              <span>Available {formatQuantity(variant.available_to_sell)}</span>
                              {variant.min_price ? <span>Min {formatMoney(variant.min_price)}</span> : null}
                            </div>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <WorkspaceEmpty title="No item match" message="Search by SKU or product name to stage a saleable variant." />
                    )}
                  </section>

                  <section>
                    <div className="operations-section-heading">
                      <h4>Matching customers</h4>
                    </div>
                    {customerResults.length ? (
                      <div className="operations-list-stack compact">
                        {customerResults.map((item) => (
                          <button key={item.customer_id} type="button" className="operations-list-card static as-button" onClick={() => useCustomer(item)}>
                            <div className="operations-list-card-head">
                              <strong>{item.name}</strong>
                              <span>Use</span>
                            </div>
                            <p>{item.phone || item.email || 'No contact details'}</p>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <WorkspaceEmpty title="No customer match" message="Phone and email lookups will show here when an existing customer is found." />
                    )}
                  </section>
                </div>
              ) : null}

              <section className="operations-subsection-block">
                <div className="operations-section-heading">
                  <h4>Customer</h4>
                </div>
                <div className="operations-form-grid compact">
                  <label>
                    Name
                    <input
                      value={customer.name}
                      onChange={(event) => setCustomer((current) => ({ ...current, name: event.target.value }))}
                    />
                  </label>
                  <label>
                    Phone
                    <input
                      value={customer.phone}
                      onChange={(event) => setCustomer((current) => ({ ...current, phone: event.target.value }))}
                    />
                  </label>
                  <label>
                    Email
                    <input
                      value={customer.email}
                      onChange={(event) => setCustomer((current) => ({ ...current, email: event.target.value }))}
                    />
                  </label>
                  <label className="field-span-2">
                    Address
                    <textarea
                      rows={2}
                      value={customer.address}
                      onChange={(event) => setCustomer((current) => ({ ...current, address: event.target.value }))}
                    />
                  </label>
                </div>
              </section>
            </div>

            <div className="operations-detail-stack">
              <section className="operations-subsection-block">
                <div className="operations-section-heading">
                  <h4>Cart</h4>
                </div>
                {draftLines.length ? (
                  <div className="table-scroll">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>Item</th>
                          <th>Qty</th>
                          <th>Price</th>
                          <th>Discount</th>
                          <th>Total</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {draftLines.map((line) => (
                          <tr key={line.variant_id}>
                            <td>
                              <strong>{line.label}</strong>
                              <div className="workspace-field-note">{line.sku}</div>
                            </td>
                            <td>
                              <input
                                value={line.quantity}
                                onChange={(event) =>
                                  setDraftLines((current) => current.map((item) => item.variant_id === line.variant_id ? { ...item, quantity: event.target.value } : item))
                                }
                              />
                            </td>
                            <td>
                              <input
                                value={line.unit_price}
                                onChange={(event) =>
                                  setDraftLines((current) => current.map((item) => item.variant_id === line.variant_id ? { ...item, unit_price: event.target.value } : item))
                                }
                              />
                            </td>
                            <td>
                              <input
                                value={line.discount_amount}
                                onChange={(event) =>
                                  setDraftLines((current) => current.map((item) => item.variant_id === line.variant_id ? { ...item, discount_amount: event.target.value } : item))
                                }
                              />
                            </td>
                            <td>
                              {formatMoney(Number(line.quantity || '0') * Number(line.unit_price || '0') - Number(line.discount_amount || '0'))}
                              {line.min_price ? <div className="workspace-field-note">Min {formatMoney(line.min_price)}</div> : null}
                            </td>
                            <td>
                              <button type="button" onClick={() => setDraftLines((current) => current.filter((item) => item.variant_id !== line.variant_id))}>Remove</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <WorkspaceEmpty title="Cart is empty" message="Search and add at least one saleable variant to start the order." />
                )}
              </section>

              <section className="operations-subsection-block">
                <div className="operations-section-heading">
                  <h4>Order summary</h4>
                </div>
                <div className="operations-definition-grid compact">
                  <div>
                    <dt>Subtotal</dt>
                    <dd>{formatMoney(orderSummary.subtotal)}</dd>
                  </div>
                  <div>
                    <dt>Discount</dt>
                    <dd>{formatMoney(orderSummary.discount)}</dd>
                  </div>
                  <div>
                    <dt>Total</dt>
                    <dd>{formatMoney(orderSummary.total)}</dd>
                  </div>
                  <div>
                    <dt>Payment</dt>
                    <dd>Unpaid</dd>
                  </div>
                </div>
                <label>
                  Notes
                  <textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} />
                </label>
                <div className="operations-toolbar-actions wrap">
                  <button type="button" className="secondary" onClick={() => void submitOrder('save_draft')} disabled={saving || !draftLines.length}>Save Draft</button>
                  <button type="button" className="secondary" onClick={() => void submitOrder('confirm')} disabled={saving || !draftLines.length}>Reserve Order</button>
                  <button type="button" className="btn-primary" onClick={() => void submitOrder('confirm_and_fulfill')} disabled={saving || !draftLines.length}>
                    {saving ? 'Saving…' : 'Complete Sale'}
                  </button>
                </div>
              </section>
            </div>
          </div>
        </WorkspacePanel>
      ) : (
        <WorkspacePanel
          title={activeTab === 'open' ? 'Open orders' : 'Completed sales'}
          description={activeTab === 'open' ? 'Draft and confirmed orders waiting for the next action.' : 'Finished sales with posted stock and finance context.'}
          actions={
            <form
              className="operations-search-bar compact"
              onSubmit={(event) => {
                event.preventDefault();
                void loadOrders(orderQuery.trim());
              }}
            >
              <input
                type="search"
                value={orderQuery}
                placeholder="Search order number, phone, or email"
                onChange={(event) => setOrderQuery(event.target.value)}
              />
              <button type="submit" className="secondary">Search</button>
            </form>
          }
        >
          <div className="operations-split-layout sales-history-layout">
            <div className="operations-list-stack">
              {ordersLoading ? <div className="reports-loading">Loading orders…</div> : null}
              {!ordersLoading && filteredOrders.length ? (
                filteredOrders.map((order) => (
                  <button
                    key={order.sales_order_id}
                    type="button"
                    className={selectedOrder?.sales_order_id === order.sales_order_id ? 'operations-list-card active as-button' : 'operations-list-card as-button'}
                    onClick={() => void loadOrderDetail(order.sales_order_id)}
                  >
                    <div className="operations-list-card-head">
                      <strong>{order.order_number}</strong>
                      <span className="status-pill">{order.status}</span>
                    </div>
                    <p>{order.customer_name || order.customer_phone || 'No customer name'}</p>
                    <div className="operations-inline-meta compact">
                      <span>{order.payment_status}</span>
                      <span>{formatMoney(order.total_amount)}</span>
                    </div>
                  </button>
                ))
              ) : null}
              {!ordersLoading && !filteredOrders.length ? (
                <WorkspaceEmpty title={activeTab === 'open' ? 'No open orders' : 'No completed sales'} message="Orders in this state will appear here automatically." />
              ) : null}
            </div>

            <div className="operations-detail-stack">
              {selectedOrder ? (
                <>
                  <div className="operations-section-heading">
                    <h4>{selectedOrder.order_number}</h4>
                    <p>{selectedOrder.customer_name || selectedOrder.customer_phone || 'No customer details'} · {selectedOrder.status}</p>
                  </div>
                  <div className="operations-inline-meta wrap">
                    <span>{selectedOrder.customer_phone || selectedOrder.customer_email || 'No contact saved'}</span>
                    <span>{formatDateTime(selectedOrder.ordered_at)}</span>
                    <span>{financeStatusLabel(selectedOrder)}</span>
                    <span>{selectedOrder.payment_status}</span>
                  </div>
                  <div className="table-scroll">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>Item</th>
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
                  {selectedOrder.notes ? <WorkspaceNotice tone="info">{selectedOrder.notes}</WorkspaceNotice> : null}
                  <div className="operations-toolbar-actions wrap">
                    {selectedOrder.status === 'draft' ? <button type="button" className="secondary" onClick={() => void runOrderAction('confirm', selectedOrder.sales_order_id)}>Reserve Order</button> : null}
                    {selectedOrder.status === 'confirmed' ? <button type="button" className="btn-primary" onClick={() => void runOrderAction('fulfill', selectedOrder.sales_order_id)}>Complete Sale</button> : null}
                    {(selectedOrder.status === 'draft' || selectedOrder.status === 'confirmed') ? <button type="button" className="secondary" onClick={() => void runOrderAction('cancel', selectedOrder.sales_order_id)}>Cancel Order</button> : null}
                  </div>
                </>
              ) : (
                <WorkspaceEmpty title="Select an order" message="Choose one order from the list to review its lines and next actions." />
              )}
            </div>
          </div>
        </WorkspacePanel>
      )}
      <div className="mobile-action-safe-spacer" aria-hidden="true" />
    </div>
  );
}
