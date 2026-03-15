'use client';

import { FormEvent, useEffect, useState, useTransition } from 'react';
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
  const [activeTab, setActiveTab] = useState<SalesTab>('new');
  const [variantQuery, setVariantQuery] = useState('');
  const [variantResults, setVariantResults] = useState<SaleLookupVariant[]>([]);
  const [customerPhone, setCustomerPhone] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [customerResults, setCustomerResults] = useState<EmbeddedCustomer[]>([]);
  const [customer, setCustomer] = useState<DraftCustomer>({ ...EMPTY_CUSTOMER });
  const [draftLines, setDraftLines] = useState<DraftLine[]>([]);
  const [notes, setNotes] = useState('');
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<SalesOrder | null>(null);
  const [orderQuery, setOrderQuery] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
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
        setError(loadError instanceof Error ? loadError.message : 'Unable to load orders.');
      }
    });
  };

  useEffect(() => {
    const query = searchParams.get('q') ?? '';
    setOrderQuery(query);
    loadOrders(query);
  }, [searchKey]);

  const filteredOrders = orders.filter((order) => {
    if (activeTab === 'open') {
      return order.status === 'draft' || order.status === 'confirmed';
    }
    if (activeTab === 'completed') {
      return order.status === 'completed';
    }
    return true;
  });

  const onVariantSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const payload = await searchSaleVariants({ q: variantQuery.trim() });
      setVariantResults(payload.items);
      setError('');
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : 'Unable to search saleable variants.');
    }
  };

  const onCustomerSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const payload = await searchEmbeddedCustomers({ phone: customerPhone, email: customerEmail });
      setCustomerResults(payload.items);
      setError('');
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : 'Unable to search customers.');
    }
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
            : 'Order confirmed and fulfilled.'
      );
      setDraftLines([]);
      setCustomer({ ...EMPTY_CUSTOMER });
      setCustomerPhone('');
      setCustomerEmail('');
      setCustomerResults([]);
      setVariantResults([]);
      setVariantQuery('');
      setNotes('');
      await loadOrders(orderQuery.trim());
      setActiveTab(action === 'confirm_and_fulfill' ? 'completed' : 'open');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to save order.');
    }
  };

  const loadOrderDetail = async (orderId: string) => {
    try {
      const payload = await getSalesOrder(orderId);
      setSelectedOrder(payload);
      setError('');
    } catch (detailError) {
      setError(detailError instanceof Error ? detailError.message : 'Unable to load order.');
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
      setError(actionError instanceof Error ? actionError.message : 'Unable to update order.');
    }
  };

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
        actions={
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
        }
      >
        {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
        {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}
        {isPending && !orders.length ? <WorkspaceNotice>Loading sales workspace…</WorkspaceNotice> : null}

        {activeTab === 'new' ? (
          <div className="workspace-two-column">
            <div className="workspace-stack">
              <WorkspacePanel
                title="Customer"
                hint="Lookup by phone or email, or capture a new customer inline."
              >
                <form className="workspace-form" onSubmit={onCustomerSearch}>
                  <div className="workspace-form-grid compact">
                    <label>
                      Phone
                      <input value={customerPhone} onChange={(event) => setCustomerPhone(event.target.value)} />
                    </label>
                    <label>
                      Email
                      <input value={customerEmail} onChange={(event) => setCustomerEmail(event.target.value)} />
                    </label>
                  </div>
                  <div className="workspace-inline-actions">
                    <button type="submit">Find customer</button>
                    <button
                      type="button"
                      onClick={() => {
                        setCustomerResults([]);
                        setCustomer({ ...EMPTY_CUSTOMER, phone: customerPhone, email: customerEmail });
                      }}
                    >
                      Enter manually
                    </button>
                  </div>
                </form>
                {customerResults.length ? (
                  <div className="workspace-stack">
                    {customerResults.map((item) => (
                      <button
                        key={item.customer_id}
                        type="button"
                        className="selection-card"
                        onClick={() =>
                          setCustomer({
                            customer_id: item.customer_id,
                            name: item.name,
                            phone: item.phone,
                            email: item.email,
                            address: '',
                          })
                        }
                      >
                        <strong>{item.name}</strong>
                        <span>{item.phone || item.email}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
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
              </WorkspacePanel>

              <WorkspacePanel
                title="Add sellable variants"
                hint="Only available stock appears in the search results."
              >
                <form className="workspace-search" onSubmit={onVariantSearch}>
                  <input
                    type="search"
                    value={variantQuery}
                    placeholder="Search product, variant, SKU, barcode"
                    onChange={(event) => setVariantQuery(event.target.value)}
                  />
                  <button type="submit">Find variants</button>
                </form>
                {variantResults.length ? (
                  <div className="workspace-card-grid compact">
                    {variantResults.map((variant) => (
                      <article key={variant.variant_id} className="commerce-card compact">
                        <div className="commerce-card-header">
                          <div>
                            <h4>{variant.label}</h4>
                            <p>
                              {variant.sku} · Available {formatQuantity(variant.available_to_sell)} ·
                              {' '}Price {formatMoney(variant.unit_price)} · Min {formatMoney(variant.min_price)}
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() =>
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
                              })
                            }
                          >
                            Add
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <WorkspaceEmpty
                    title="Search for saleable stock"
                    message="Use the search above to find variants by product, option, SKU, or barcode."
                  />
                )}
              </WorkspacePanel>
            </div>

            <WorkspacePanel
              title="Order draft"
              hint="Draft, confirm, or fulfill the whole order from one workspace."
            >
              {draftLines.length ? (
                <div className="table-scroll">
                  <table className="workspace-table">
                    <thead>
                      <tr>
                        <th>Variant</th>
                        <th>Quantity</th>
                        <th>Unit Price</th>
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
                              Remove
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
              <div className="workspace-actions">
                <button type="button" onClick={() => submitOrder('save_draft')} disabled={!draftLines.length}>
                  Save Draft
                </button>
                <button type="button" onClick={() => submitOrder('confirm')} disabled={!draftLines.length}>
                  Confirm
                </button>
                <button type="button" onClick={() => submitOrder('confirm_and_fulfill')} disabled={!draftLines.length}>
                  Confirm & Fulfill
                </button>
              </div>
            </WorkspacePanel>
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
    </div>
  );
}
