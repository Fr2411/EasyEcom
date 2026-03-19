'use client';

import Link from 'next/link';
import { FormEvent, Fragment, useEffect, useState, useTransition } from 'react';

import {
  approveSalesAgentDraft,
  confirmSalesAgentOrder,
  getSalesAgentConversation,
  getSalesAgentConversations,
  getSalesAgentOrders,
  handoffSalesAgentConversation,
  rejectSalesAgentDraft,
} from '@/lib/api/sales-agent';
import { getChannelIntegrations } from '@/lib/api/integrations';
import { WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { formatDateTime, formatMoney, formatQuantity } from '@/lib/commerce-format';
import type { ChannelIntegration } from '@/types/integrations';
import type { SalesOrder } from '@/types/sales';
import type { SalesAgentConversationDetail, SalesAgentConversationRow, SalesAgentDraft } from '@/types/sales-agent';


function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asRecordArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === 'object') as Record<string, unknown>[] : [];
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => `${item}`.trim()).filter(Boolean) : [];
}

function asString(value: unknown) {
  return `${value ?? ''}`.trim();
}

export function SalesAgentWorkspace() {
  const [integrations, setIntegrations] = useState<ChannelIntegration[]>([]);
  const [conversations, setConversations] = useState<SalesAgentConversationRow[]>([]);
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [expandedConversationId, setExpandedConversationId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SalesAgentConversationDetail | null>(null);
  const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [isPending, startTransition] = useTransition();

  const loadWorkspace = (nextQuery = query, nextStatus = status) => {
    startTransition(async () => {
      try {
        const [integrationPayload, conversationPayload, orderPayload] = await Promise.all([
          getChannelIntegrations(),
          getSalesAgentConversations({ q: nextQuery, status: nextStatus || undefined }),
          getSalesAgentOrders('draft'),
        ]);
        setIntegrations(integrationPayload.items);
        setConversations(conversationPayload.items);
        setOrders(orderPayload.items);
        setError('');
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load the Sales Agent workspace.');
      }
    });
  };

  useEffect(() => {
    loadWorkspace('', '');
  }, []);

  const expandConversation = async (conversationId: string) => {
    if (expandedConversationId === conversationId) {
      setExpandedConversationId(null);
      setDetail(null);
      return;
    }
    try {
      const payload = await getSalesAgentConversation(conversationId);
      setExpandedConversationId(conversationId);
      setDetail(payload);
      if (payload.latest_draft) {
        setDraftEdits((current) => ({
          ...current,
          [payload.latest_draft!.draft_id]: payload.latest_draft!.final_text || payload.latest_draft!.ai_draft_text,
        }));
      }
      setError('');
    } catch (detailError) {
      setError(detailError instanceof Error ? detailError.message : 'Unable to load conversation detail.');
    }
  };

  const applySearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    loadWorkspace(query.trim(), status);
  };

  const onApproveDraft = async (draft: SalesAgentDraft) => {
    try {
      const edited = draftEdits[draft.draft_id] ?? draft.final_text ?? draft.ai_draft_text;
      await approveSalesAgentDraft(draft.draft_id, edited);
      setNotice('Draft approved and sent to WhatsApp.');
      await refreshExpandedConversation(draft.conversation_id);
      loadWorkspace();
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : 'Unable to approve the draft.');
    }
  };

  const onRejectDraft = async (draft: SalesAgentDraft) => {
    try {
      await rejectSalesAgentDraft(draft.draft_id, 'Rejected from Sales Agent workspace');
      setNotice('Draft moved to handoff.');
      await refreshExpandedConversation(draft.conversation_id);
      loadWorkspace();
    } catch (rejectError) {
      setError(rejectError instanceof Error ? rejectError.message : 'Unable to reject the draft.');
    }
  };

  const onHandoffConversation = async (conversationId: string) => {
    try {
      await handoffSalesAgentConversation(conversationId, 'Escalated from Sales Agent workspace');
      setNotice('Conversation has been handed off for manual follow-up.');
      await refreshExpandedConversation(conversationId);
      loadWorkspace();
    } catch (handoffError) {
      setError(handoffError instanceof Error ? handoffError.message : 'Unable to hand off the conversation.');
    }
  };

  const onConfirmOrder = async (orderId: string) => {
    try {
      await confirmSalesAgentOrder(orderId);
      setNotice('Agent-created draft order confirmed.');
      if (detail?.linked_order?.sales_order_id === orderId) {
        await refreshExpandedConversation(detail.conversation_id);
      }
      loadWorkspace();
    } catch (confirmError) {
      setError(confirmError instanceof Error ? confirmError.message : 'Unable to confirm the draft order.');
    }
  };

  const refreshExpandedConversation = async (conversationId: string) => {
    if (expandedConversationId !== conversationId) {
      return;
    }
    const payload = await getSalesAgentConversation(conversationId);
    setDetail(payload);
  };

  const activeIntegration = integrations.find((item) => item.status === 'active') ?? integrations[0] ?? null;

  return (
    <div className="workspace-stack sales-agent-stack">
      {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}
      {!activeIntegration ? (
        <WorkspaceNotice tone="info">
          No active WhatsApp channel is configured yet. Connect one from <Link href="/integrations">Integrations</Link> before expecting live conversations.
        </WorkspaceNotice>
      ) : null}

      <WorkspacePanel
        title="Recent conversations"
        description="Each row is the latest sales-agent conversation. Expand a row to inspect the full timeline, the AI draft, and any linked draft order."
        hint="Conversation spend and customer type are snapshots for speed; sales tables remain the canonical financial truth."
        actions={
          <form className="workspace-search" onSubmit={applySearch}>
            <input
              type="search"
              value={query}
              placeholder="Search customer, WhatsApp, or message"
              onChange={(event) => setQuery(event.target.value)}
            />
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All statuses</option>
              <option value="open">Open</option>
              <option value="needs_review">Needs review</option>
              <option value="handoff">Handoff</option>
            </select>
            <button type="submit">Filter</button>
          </form>
        }
      >
        {isPending && !conversations.length ? <div className="dashboard-loading">Loading Sales Agent workspace…</div> : null}
        {conversations.length ? (
          <div className="sales-agent-table-wrap">
            <table className="workspace-table sales-agent-table">
              <thead>
                <tr>
                  <th>Conversation</th>
                  <th>Status</th>
                  <th>Customer type</th>
                  <th>Lifetime spend</th>
                  <th>Latest order</th>
                  <th>Recommendations</th>
                  <th aria-label="Expand row" />
                </tr>
              </thead>
              <tbody>
                {conversations.map((conversation) => {
                  const isExpanded = expandedConversationId === conversation.conversation_id;
                  const conversationDetail = isExpanded ? detail : null;
                  const draft = conversationDetail?.latest_draft ?? null;
                  const linkedOrder = conversationDetail?.linked_order ?? conversation.linked_order;
                  const trace = draft ? asRecord(asRecord(draft.grounding).trace) : asRecord(conversationDetail?.latest_trace);
                  const traceRuntime = asRecord(trace.runtime);
                  const traceFacts = asRecord(trace.facts_pack);
                  const traceConstraints = asRecord(traceFacts.active_constraints);
                  const traceCatalogSummary = asRecord(traceFacts.catalog_summary);
                  const traceRangeSummary = asRecord(traceFacts.range_summary);
                  const traceConversationState = asRecord(trace.conversation_state_after || traceFacts.conversation_state);
                  const traceReplyContract = asRecord(trace.reply_contract);
                  const traceDecision = asRecord(trace.decision);
                  const traceOfferPolicy = asRecord(traceFacts.offer_policy);
                  const tracePrimaryMatches = asRecordArray(traceFacts.primary_matches);
                  const traceAlternatives = asRecordArray(traceFacts.alternatives);
                  const traceUpsells = asRecordArray(traceFacts.upsell_candidates);
                  const traceOfferSteps = asRecordArray(traceOfferPolicy.auto_discount_steps);
                  const traceReasonCodes = asStringArray(traceDecision.reason_codes ?? traceFacts.reason_codes);
                  const traceCorrections = asStringArray(traceConversationState.customer_corrections);
                  const traceSupportedBrands = asStringArray(traceCatalogSummary.top_brand_options || traceCatalogSummary.supported_brands);
                  const traceSupportedNeeds = asStringArray(traceCatalogSummary.supported_need_labels);
                  return (
                    <Fragment key={conversation.conversation_id}>
                      <tr>
                        <td>
                          <strong>{conversation.customer_name || conversation.customer_phone || 'Unknown customer'}</strong>
                          <p className="admin-muted">{conversation.customer_phone || conversation.external_sender_id}</p>
                          <p className="sales-agent-preview">{conversation.last_message_preview}</p>
                          <small>{conversation.last_message_at ? formatDateTime(conversation.last_message_at) : 'No messages yet'}</small>
                        </td>
                        <td>
                          <strong className={`sales-agent-status-pill status-${conversation.status}`}>{conversation.status.replaceAll('_', ' ')}</strong>
                          <p className="admin-muted">{conversation.latest_intent || 'No intent yet'}</p>
                        </td>
                        <td>
                          <strong>{conversation.customer_type}</strong>
                          <p className="admin-muted">{conversation.behavior_tags.join(', ') || 'No tags yet'}</p>
                        </td>
                        <td>${formatMoney(conversation.lifetime_spend)}</td>
                        <td>{linkedOrder ? `${linkedOrder.order_number} · ${linkedOrder.status}` : 'No draft order'}</td>
                        <td>{conversation.latest_recommended_products_summary || 'No recommendations yet'}</td>
                        <td>
                          <button type="button" onClick={() => expandConversation(conversation.conversation_id)}>
                            {isExpanded ? 'Collapse' : 'Expand'}
                          </button>
                        </td>
                      </tr>
                      {isExpanded && conversationDetail ? (
                        <tr>
                          <td colSpan={7}>
                            <div className="sales-agent-expanded">
                              <div className="sales-agent-expanded-main">
                                <h4>Full conversation</h4>
                                <div className="sales-agent-timeline">
                                  {conversationDetail.messages.map((message) => (
                                    <article key={message.message_id} className={`sales-agent-message direction-${message.direction}`}>
                                      <header>
                                        <strong>{message.direction === 'inbound' ? 'Customer' : 'Sales Agent'}</strong>
                                        <span>{formatDateTime(message.occurred_at)}</span>
                                      </header>
                                      <p>{message.message_text || message.content_summary}</p>
                                      {message.mentions.length ? (
                                        <div className="sales-agent-mentions">
                                          {message.mentions.map((mention) => (
                                            <span key={mention.mention_id}>
                                              {mention.mention_role}: {mention.label || mention.variant_id || mention.product_id}
                                              {mention.available_to_sell ? ` · ${formatQuantity(mention.available_to_sell)} avail` : ''}
                                            </span>
                                          ))}
                                        </div>
                                      ) : null}
                                    </article>
                                  ))}
                                </div>
                              </div>

                              <aside className="sales-agent-expanded-side">
                                <section className="sales-agent-side-card">
                                  <h4>AI draft</h4>
                                  {draft ? (
                                    <>
                                      <p className="admin-muted">
                                        {draft.intent} · confidence {draft.confidence ?? 'n/a'} · {draft.status}
                                      </p>
                                      <textarea
                                        rows={7}
                                        value={draftEdits[draft.draft_id] ?? draft.final_text ?? draft.ai_draft_text}
                                        onChange={(event) =>
                                          setDraftEdits((current) => ({
                                            ...current,
                                            [draft.draft_id]: event.target.value,
                                          }))
                                        }
                                      />
                                      <div className="sales-agent-side-actions">
                                        <button type="button" onClick={() => onApproveDraft(draft)}>
                                          Approve & Send
                                        </button>
                                        <button type="button" className="secondary" onClick={() => onRejectDraft(draft)}>
                                          Reject
                                        </button>
                                        <button type="button" className="secondary" onClick={() => onHandoffConversation(conversation.conversation_id)}>
                                          Handoff
                                        </button>
                                      </div>
                                    </>
                                  ) : (
                                    <p className="admin-muted">No review draft is waiting on this conversation.</p>
                                  )}
                                </section>

                                <section className="sales-agent-side-card">
                                  <h4>Warehouse trace</h4>
                                  {Object.keys(trace).length ? (
                                    <div className="sales-agent-trace">
                                      <div className="sales-agent-trace-pills">
                                        <span>Answer type: {asString(traceRuntime.answer_type) || 'n/a'}</span>
                                        <span>Next action: {asString(traceRuntime.next_required_action) || 'n/a'}</span>
                                        <span>Helper: {traceRuntime.helper_used ? 'yes' : 'no'}</span>
                                        <span>Sales model: {traceRuntime.sales_model_used ? 'yes' : 'no'}</span>
                                        <span>Ack sent: {traceRuntime.review_ack_sent ? 'yes' : 'no'}</span>
                                      </div>
                                      {traceReasonCodes.length ? (
                                        <p className="admin-muted">Reason codes: {traceReasonCodes.join(', ')}</p>
                                      ) : null}
                                      {Object.keys(traceConstraints).length ? (
                                        <div className="sales-agent-trace-block">
                                          <strong>Active constraints</strong>
                                          <ul className="sales-agent-trace-list">
                                            {asString(traceConstraints.active_brand) ? (
                                              <li>
                                                <span>Brand</span>
                                                <small>{asString(traceConstraints.active_brand)}</small>
                                              </li>
                                            ) : null}
                                            {asString(traceConstraints.active_product_family) ? (
                                              <li>
                                                <span>Product family</span>
                                                <small>{asString(traceConstraints.active_product_family)}</small>
                                              </li>
                                            ) : null}
                                            {asString(traceConstraints.active_need_label) ? (
                                              <li>
                                                <span>Need</span>
                                                <small>{asString(traceConstraints.active_need_label)}</small>
                                              </li>
                                            ) : null}
                                            {asString(traceConstraints.active_category) ? (
                                              <li>
                                                <span>Category</span>
                                                <small>{asString(traceConstraints.active_category)}</small>
                                              </li>
                                            ) : null}
                                            {asString(traceConstraints.active_color) ? (
                                              <li>
                                                <span>Color</span>
                                                <small>{asString(traceConstraints.active_color)}</small>
                                              </li>
                                            ) : null}
                                            {asString(traceConstraints.active_size) ? (
                                              <li>
                                                <span>Size</span>
                                                <small>{asString(traceConstraints.active_size)}</small>
                                              </li>
                                            ) : null}
                                            {asString(traceConstraints.active_price_intent) ? (
                                              <li>
                                                <span>Price intent</span>
                                                <small>{asString(traceConstraints.active_price_intent)}</small>
                                              </li>
                                            ) : null}
                                            {asString(traceConstraints.budget_posture) ? (
                                              <li>
                                                <span>Budget posture</span>
                                                <small>{asString(traceConstraints.budget_posture)}</small>
                                              </li>
                                            ) : null}
                                          </ul>
                                        </div>
                                      ) : null}
                                      {(asString(traceCatalogSummary.summary_text) || traceSupportedBrands.length || traceSupportedNeeds.length) ? (
                                        <div className="sales-agent-trace-block">
                                          <strong>Warehouse summary</strong>
                                          {asString(traceCatalogSummary.summary_text) ? <p className="admin-muted">{asString(traceCatalogSummary.summary_text)}</p> : null}
                                          <ul className="sales-agent-trace-list">
                                            {traceSupportedBrands.length ? (
                                              <li>
                                                <span>Brands</span>
                                                <small>{traceSupportedBrands.join(', ')}</small>
                                              </li>
                                            ) : null}
                                            {traceSupportedNeeds.length ? (
                                              <li>
                                                <span>Needs</span>
                                                <small>{traceSupportedNeeds.join(', ')}</small>
                                              </li>
                                            ) : null}
                                          </ul>
                                        </div>
                                      ) : null}
                                      {Object.keys(traceRangeSummary).length ? (
                                        <div className="sales-agent-trace-block">
                                          <strong>Range summary</strong>
                                          <ul className="sales-agent-trace-list">
                                            <li>
                                              <span>Price range</span>
                                              <small>
                                                ${formatMoney(asString(traceRangeSummary.min_price))} to ${formatMoney(asString(traceRangeSummary.max_price))}
                                              </small>
                                            </li>
                                            <li>
                                              <span>Candidates</span>
                                              <small>{asString(traceRangeSummary.candidate_count) || '0'}</small>
                                            </li>
                                          </ul>
                                        </div>
                                      ) : null}
                                      {Object.keys(traceConversationState).length ? (
                                        <div className="sales-agent-trace-block">
                                          <strong>Conversation state</strong>
                                          <ul className="sales-agent-trace-list">
                                            <li>
                                              <span>Unresolved turns</span>
                                              <small>{asString(traceConversationState.unresolved_turn_count) || '0'}</small>
                                            </li>
                                            {asString(traceConversationState.last_customer_need_summary) ? (
                                              <li>
                                                <span>Latest need</span>
                                                <small>{asString(traceConversationState.last_customer_need_summary)}</small>
                                              </li>
                                            ) : null}
                                            {traceCorrections.length ? (
                                              <li>
                                                <span>Corrections</span>
                                                <small>{traceCorrections.join(', ')}</small>
                                              </li>
                                            ) : null}
                                          </ul>
                                        </div>
                                      ) : null}
                                      {Object.keys(traceReplyContract).length ? (
                                        <div className="sales-agent-trace-block">
                                          <strong>Reply contract</strong>
                                          <ul className="sales-agent-trace-list">
                                            {asString(traceReplyContract.reply_mode) ? (
                                              <li>
                                                <span>Mode</span>
                                                <small>{asString(traceReplyContract.reply_mode)}</small>
                                              </li>
                                            ) : null}
                                            <li>
                                              <span>Must acknowledge</span>
                                              <small>{traceReplyContract.must_acknowledge ? 'yes' : 'no'}</small>
                                            </li>
                                            <li>
                                              <span>Needs review</span>
                                              <small>{traceReplyContract.needs_review ? 'yes' : 'no'}</small>
                                            </li>
                                          </ul>
                                        </div>
                                      ) : null}
                                      {tracePrimaryMatches.length ? (
                                        <div className="sales-agent-trace-block">
                                          <strong>Primary matches</strong>
                                          <ul className="sales-agent-trace-list">
                                            {tracePrimaryMatches.map((item) => (
                                              <li key={asString(item.variant_id)}>
                                                <span>{asString(item.label)}</span>
                                                <small>
                                                  ${formatMoney(asString(item.unit_price))} · {formatQuantity(asString(item.available_to_sell))} avail
                                                </small>
                                              </li>
                                            ))}
                                          </ul>
                                        </div>
                                      ) : null}
                                      {traceAlternatives.length ? (
                                        <div className="sales-agent-trace-block">
                                          <strong>Alternatives</strong>
                                          <ul className="sales-agent-trace-list">
                                            {traceAlternatives.map((item) => (
                                              <li key={asString(item.variant_id)}>
                                                <span>{asString(item.label)}</span>
                                                <small>${formatMoney(asString(item.unit_price))}</small>
                                              </li>
                                            ))}
                                          </ul>
                                        </div>
                                      ) : null}
                                      {traceUpsells.length ? (
                                        <div className="sales-agent-trace-block">
                                          <strong>Upsell candidates</strong>
                                          <ul className="sales-agent-trace-list">
                                            {traceUpsells.map((item) => (
                                              <li key={asString(item.variant_id)}>
                                                <span>{asString(item.label)}</span>
                                                <small>${formatMoney(asString(item.unit_price))}</small>
                                              </li>
                                            ))}
                                          </ul>
                                        </div>
                                      ) : null}
                                      {traceOfferSteps.length ? (
                                        <div className="sales-agent-trace-block">
                                          <strong>Offer ladder</strong>
                                          <ul className="sales-agent-trace-list">
                                            {traceOfferSteps.map((item) => (
                                              <li key={asString(item.offer_id)}>
                                                <span>
                                                  {asString(item.label)}
                                                  {asString(traceOfferPolicy.selected_offer_id) === asString(item.offer_id) ? ' · selected' : ''}
                                                </span>
                                                <small>
                                                  ${formatMoney(asString(item.unit_price))}
                                                  {asString(item.discount_percent) ? ` · ${asString(item.discount_percent)}% off` : ''}
                                                </small>
                                              </li>
                                            ))}
                                          </ul>
                                        </div>
                                      ) : null}
                                    </div>
                                  ) : (
                                    <p className="admin-muted">No warehouse trace has been captured for this conversation yet.</p>
                                  )}
                                </section>

                                <section className="sales-agent-side-card">
                                  <h4>Linked draft order</h4>
                                  {linkedOrder ? (
                                    <>
                                      <p className="admin-muted">
                                        {linkedOrder.order_number} · {linkedOrder.status} · ${formatMoney(linkedOrder.total_amount)}
                                      </p>
                                      <ul className="sales-agent-order-lines">
                                        {linkedOrder.lines.map((line) => (
                                          <li key={line.sales_order_item_id}>
                                            <strong>{line.label}</strong>
                                            <span>{formatQuantity(line.quantity)} × ${formatMoney(line.unit_price)}</span>
                                          </li>
                                        ))}
                                      </ul>
                                      <div className="sales-agent-side-actions">
                                        {linkedOrder.status === 'draft' ? (
                                          <button type="button" onClick={() => onConfirmOrder(linkedOrder.sales_order_id)}>
                                            Confirm Draft Order
                                          </button>
                                        ) : null}
                                        <Link href={`/sales?q=${linkedOrder.order_number}`} className="button-link secondary">
                                          Open in Sales
                                        </Link>
                                      </div>
                                    </>
                                  ) : (
                                    <p className="admin-muted">No draft order has been created from this conversation yet.</p>
                                  )}
                                </section>
                              </aside>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="workspace-empty">
            <h4>No recent conversations</h4>
            <p>Inbound WhatsApp conversations will appear here once the tenant channel starts receiving customer messages.</p>
          </div>
        )}
      </WorkspacePanel>

      <WorkspacePanel
        title="Agent-created draft orders"
        description="These orders were created by the sales agent and still need a human confirmation step."
      >
        {orders.length ? (
          <div className="sales-agent-order-queue">
            {orders.map((order) => (
              <article key={order.sales_order_id} className="sales-agent-side-card">
                <div className="sales-agent-order-head">
                  <div>
                    <strong>{order.order_number}</strong>
                    <p className="admin-muted">{order.customer_name} · {order.status}</p>
                  </div>
                  <span>${formatMoney(order.total_amount)}</span>
                </div>
                <ul className="sales-agent-order-lines">
                  {order.lines.map((line) => (
                    <li key={line.sales_order_item_id}>
                      <strong>{line.label}</strong>
                      <span>{formatQuantity(line.quantity)} × ${formatMoney(line.unit_price)}</span>
                    </li>
                  ))}
                </ul>
                <div className="sales-agent-side-actions">
                  {order.status === 'draft' ? (
                    <button type="button" onClick={() => onConfirmOrder(order.sales_order_id)}>
                      Confirm one by one
                    </button>
                  ) : null}
                  <Link href={`/sales?q=${order.order_number}`} className="button-link secondary">
                    Open in Sales
                  </Link>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="workspace-empty">
            <h4>No pending agent orders</h4>
            <p>When the sales agent prepares draft orders from conversations, they will queue here for manual confirmation.</p>
          </div>
        )}
      </WorkspacePanel>
    </div>
  );
}
