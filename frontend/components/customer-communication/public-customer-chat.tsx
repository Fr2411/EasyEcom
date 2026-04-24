'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Bot, RotateCcw, Send } from 'lucide-react';
import { sendPublicCustomerChatMessage } from '@/lib/api/public-customer-chat';
import type { CustomerMessage } from '@/types/customer-communication';

type ChatEntry = {
  id: string;
  role: 'customer' | 'assistant';
  text: string;
  occurred_at?: string | null;
};

function buildSenderId(channelKey: string) {
  const randomPart =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `web-${channelKey.slice(0, 18)}-${randomPart}`;
}

function messageEntry(message: CustomerMessage | null | undefined): ChatEntry | null {
  if (!message) return null;
  return {
    id: message.message_id,
    role: message.sender_role === 'assistant' ? 'assistant' : 'customer',
    text: message.message_text,
    occurred_at: message.occurred_at,
  };
}

export function PublicCustomerChat({ channelKey }: { channelKey: string }) {
  const storageKey = useMemo(() => `easyecom.public-chat.${channelKey}.sender`, [channelKey]);
  const contactKey = useMemo(() => `easyecom.public-chat.${channelKey}.contact`, [channelKey]);
  const [externalSenderId, setExternalSenderId] = useState('');
  const [senderName, setSenderName] = useState('');
  const [senderPhone, setSenderPhone] = useState('');
  const [messageText, setMessageText] = useState('');
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const storedSender = window.localStorage.getItem(storageKey);
    const nextSender = storedSender || buildSenderId(channelKey);
    if (!storedSender) {
      window.localStorage.setItem(storageKey, nextSender);
    }
    setExternalSenderId(nextSender);

    try {
      const contact = JSON.parse(window.localStorage.getItem(contactKey) || '{}') as {
        name?: string;
        phone?: string;
      };
      setSenderName(contact.name || '');
      setSenderPhone(contact.phone || '');
    } catch {
      setSenderName('');
      setSenderPhone('');
    }
  }, [channelKey, contactKey, storageKey]);

  useEffect(() => {
    window.localStorage.setItem(contactKey, JSON.stringify({ name: senderName, phone: senderPhone }));
  }, [contactKey, senderName, senderPhone]);

  function resetConversation() {
    const nextSender = buildSenderId(channelKey);
    window.localStorage.setItem(storageKey, nextSender);
    setExternalSenderId(nextSender);
    setMessages([]);
    setMessageText('');
    setError('');
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanText = messageText.trim();
    if (!cleanText || sending || !externalSenderId) return;

    const optimisticMessage: ChatEntry = {
      id: `local-${Date.now()}`,
      role: 'customer',
      text: cleanText,
      occurred_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, optimisticMessage]);
    setMessageText('');
    setSending(true);
    setError('');

    try {
      const payload = await sendPublicCustomerChatMessage(channelKey, {
        external_sender_id: externalSenderId,
        sender_name: senderName.trim(),
        sender_phone: senderPhone.trim(),
        sender_email: '',
        message_text: cleanText,
        provider_event_id: `${externalSenderId}-${Date.now()}`,
        metadata: { source: 'tenant_safe_web_chat' },
      });
      const inbound = messageEntry(payload.inbound_message);
      const outbound = messageEntry(payload.outbound_message);
      setMessages((current) => [
        ...current.filter((message) => message.id !== optimisticMessage.id),
        ...(inbound ? [inbound] : [optimisticMessage]),
        ...(outbound ? [outbound] : []),
      ]);
    } catch (sendError) {
      setMessages((current) => current.filter((message) => message.id !== optimisticMessage.id));
      setMessageText(cleanText);
      setError(sendError instanceof Error ? sendError.message : 'Unable to send message.');
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="customer-chat-page">
      <section className="customer-chat-shell" aria-label="Customer chat">
        <header className="customer-chat-header">
          <div className="customer-chat-brand">
            <span className="customer-chat-icon"><Bot size={19} aria-hidden="true" /></span>
            <div>
              <p>EasyEcom Assistant</p>
              <h1>Chat with the store</h1>
            </div>
          </div>
          <button type="button" className="customer-chat-icon-button" onClick={resetConversation} aria-label="Start a new conversation">
            <RotateCcw size={17} aria-hidden="true" />
          </button>
        </header>

        <div className="customer-chat-contact">
          <label>
            Name
            <input value={senderName} onChange={(event) => setSenderName(event.target.value)} autoComplete="name" />
          </label>
          <label>
            Phone
            <input value={senderPhone} onChange={(event) => setSenderPhone(event.target.value)} autoComplete="tel" inputMode="tel" />
          </label>
        </div>

        <div className="customer-chat-thread" aria-live="polite">
          {messages.length ? (
            messages.map((message) => (
              <article key={message.id} className={`customer-chat-bubble ${message.role}`}>
                <span>{message.role === 'assistant' ? 'Assistant' : 'You'}</span>
                <p>{message.text}</p>
              </article>
            ))
          ) : (
            <div className="customer-chat-empty">
              <strong>Start a conversation</strong>
              <span>Ask about price, stock, size, delivery, exchange, or product recommendations.</span>
            </div>
          )}
        </div>

        {error ? <p className="customer-chat-error">{error}</p> : null}

        <form className="customer-chat-compose" onSubmit={sendMessage}>
          <label className="sr-only" htmlFor="customer-chat-message">Message</label>
          <textarea
            id="customer-chat-message"
            rows={2}
            value={messageText}
            onChange={(event) => setMessageText(event.target.value)}
            placeholder="Type your message"
            disabled={sending}
          />
          <button type="submit" disabled={sending || !messageText.trim()} aria-label="Send message">
            <Send size={18} aria-hidden="true" />
          </button>
        </form>
      </section>
    </main>
  );
}
