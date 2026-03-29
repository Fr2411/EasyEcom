'use client';

import Link from 'next/link';
import { ArrowRight, Bot, Boxes, ChartColumnIncreasing, MessageSquareText, PackageCheck, ShoppingCart, Sparkles } from 'lucide-react';
import { PublicSiteChrome } from '@/components/marketing/public-site-chrome';

const problems = [
  {
    title: 'Too many customer messages',
    body: 'You spend hours replying manually — and still miss customers.',
  },
  {
    title: 'Lost sales due to stock mistakes',
    body: 'You sell products that are already out of stock.',
  },
  {
    title: 'No clear view of your business',
    body: 'Orders, inventory, and customers are scattered everywhere.',
  },
  {
    title: 'Growth creates more problems',
    body: 'More orders = more confusion, not more profit.',
  },
];

const solutions = [
  {
    title: 'AI Sales Assistant',
    body: 'Reply instantly to customer messages and handle conversations 24/7 — without hiring extra staff.',
    icon: Bot,
  },
  {
    title: 'Inventory Management',
    body: 'Keep your stock accurate and updated so you never lose a sale again.',
    icon: Boxes,
  },
  {
    title: 'Order & Sales Tracking',
    body: 'Track every order from inquiry to delivery in one place.',
    icon: ShoppingCart,
  },
  {
    title: 'Business Dashboard',
    body: 'See exactly how your business is performing — in real time.',
    icon: ChartColumnIncreasing,
  },
];

const aiSellingPoints = [
  'Instantly replies to customer inquiries',
  'Suggests products based on customer needs',
  'Handles repetitive questions automatically',
  'Helps convert conversations into real orders',
];

const setupSteps = [
  {
    title: 'Set up your products',
    body: 'Add your items and basic business info.',
  },
  {
    title: 'Start receiving customer inquiries',
    body: 'Manage conversations and orders in one place.',
  },
  {
    title: 'Let EasyEcom handle the rest',
    body: 'Track inventory, manage sales, and grow smoothly.',
  },
];

const benefits = [
  'Handle more customers without extra staff',
  'Never miss a sales opportunity',
  'Keep your operations organized',
  'Make smarter decisions with real data',
  'Save time every day',
];

const pricingPreview = [
  {
    title: 'Free Plan',
    body: 'Start small and explore the platform',
    points: ['Limited products', 'Limited AI conversations'],
  },
  {
    title: 'Growth Plan',
    body: 'For growing businesses',
    points: ['More products', 'AI-powered automation', 'Full access to core features'],
  },
  {
    title: 'Scale Plan',
    body: 'For serious sellers',
    points: ['Advanced automation', 'Higher limits', 'Full business control'],
  },
];

function HeroMockup() {
  return (
    <div className="hero-mockup" aria-label="EasyEcom product preview">
      <section className="hero-chat-panel">
        <div className="hero-panel-head">
          <span className="hero-panel-kicker">Customer chat</span>
          <strong>WhatsApp inquiry</strong>
        </div>
        <div className="hero-chat-thread">
          <article className="hero-bubble customer">
            <span className="hero-bubble-label">Customer</span>
            <p>Do you have the black travel bag in stock?</p>
          </article>
          <article className="hero-bubble ai">
            <span className="hero-bubble-label">EasyEcom AI</span>
            <p>Yes — the black travel bag is available. I can place your order now for 2 pieces.</p>
          </article>
          <article className="hero-bubble system">
            <span className="hero-bubble-label">Suggested order</span>
            <p>Travel Bag / Black / Qty 2 staged from conversation.</p>
          </article>
        </div>
      </section>

      <section className="hero-dashboard-panel">
        <div className="hero-panel-head">
          <span className="hero-panel-kicker">Operations</span>
          <strong>Order created</strong>
        </div>
        <div className="hero-order-card">
          <div className="hero-order-row">
            <span>Customer</span>
            <strong>Sarah Ahmed</strong>
          </div>
          <div className="hero-order-row">
            <span>Order</span>
            <strong>#SO-24018</strong>
          </div>
          <div className="hero-order-row">
            <span>Status</span>
            <strong>Draft ready</strong>
          </div>
          <div className="hero-order-row">
            <span>Inventory</span>
            <strong>12 units available</strong>
          </div>
        </div>
        <div className="hero-dashboard-grid">
          <article className="hero-mini-stat">
            <PackageCheck size={18} aria-hidden="true" />
            <div>
              <span>Inventory</span>
              <strong>Accurate stock</strong>
            </div>
          </article>
          <article className="hero-mini-stat">
            <MessageSquareText size={18} aria-hidden="true" />
            <div>
              <span>Reply speed</span>
              <strong>Instant AI response</strong>
            </div>
          </article>
        </div>
      </section>
    </div>
  );
}

export default function PublicLandingPage() {
  return (
    <PublicSiteChrome ctaLabel="Start Free" ctaHref="/login?mode=signup">
      <section className="marketing-hero landing-hero">
        <div className="landing-hero-grid">
          <div className="landing-copy">
            <h1>Turn customer chats into sales — automatically</h1>
            <p className="landing-subheadline">
              EasyEcom is your AI-powered sales and operations system.
              Reply instantly, manage inventory, and run your business — all from one platform.
            </p>
            <div className="landing-cta-row">
              <Link href="/login?mode=signup" className="button-link btn-primary">
                Start Free — No Credit Card
              </Link>
              <Link href="/#how-it-works" className="button-link secondary">
                See How It Works
              </Link>
            </div>
            <p className="landing-trust-line">
              Used by growing businesses to handle sales, inventory, and operations in one place.
            </p>
          </div>
          <HeroMockup />
        </div>
      </section>

      <section className="marketing-section landing-section" id="features">
        <div className="landing-section-heading">
          <p className="marketing-kicker">The problem</p>
          <h2>Running your business shouldn’t feel like chaos</h2>
          <p>Most small businesses struggle with the same problems:</p>
        </div>
        <div className="landing-problem-grid">
          {problems.map((problem, index) => (
            <article key={problem.title} className="landing-problem-card">
              <span className="landing-card-number">0{index + 1}</span>
              <h3>{problem.title}</h3>
              <p>{problem.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section landing-section landing-section-contrast">
        <div className="landing-section-heading">
          <p className="marketing-kicker">The solution</p>
          <h2>EasyEcom fixes this — automatically</h2>
          <p>One system to manage your entire business, powered by AI.</p>
        </div>
        <div className="landing-solution-grid">
          {solutions.map((solution) => {
            const Icon = solution.icon;
            return (
              <article key={solution.title} className="landing-solution-card">
                <div className="landing-solution-icon">
                  <Icon size={20} aria-hidden="true" />
                </div>
                <h3>{solution.title}</h3>
                <p>{solution.body}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section className="marketing-section landing-section">
        <div className="landing-ai-grid">
          <div className="landing-section-heading">
            <p className="marketing-kicker">AI selling</p>
            <h2>Your AI sales employee — working 24/7</h2>
            <p>Let AI handle conversations while you focus on growing your business.</p>
            <ul className="landing-check-list">
              {aiSellingPoints.map((point) => (
                <li key={point}>
                  <Sparkles size={16} aria-hidden="true" />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
          <aside className="landing-highlight-box">
            <p>You don’t need to hire more people to grow.</p>
            <strong>You just need better systems.</strong>
          </aside>
        </div>
      </section>

      <section className="marketing-section landing-section" id="how-it-works">
        <div className="landing-section-heading">
          <p className="marketing-kicker">How it works</p>
          <h2>Get started in minutes</h2>
        </div>
        <div className="landing-steps-grid">
          {setupSteps.map((step, index) => (
            <article key={step.title} className="landing-step-card">
              <span className="landing-step-badge">Step {index + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section landing-section landing-section-contrast">
        <div className="landing-section-heading">
          <p className="marketing-kicker">Benefits</p>
          <h2>Built for businesses that want to grow</h2>
        </div>
        <div className="landing-benefit-grid">
          {benefits.map((benefit) => (
            <article key={benefit} className="landing-benefit-card">
              <ArrowRight size={16} aria-hidden="true" />
              <span>{benefit}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section landing-section">
        <div className="landing-section-heading">
          <p className="marketing-kicker">Pricing</p>
          <h2>Simple pricing that grows with you</h2>
        </div>
        <div className="landing-pricing-grid">
          {pricingPreview.map((plan) => (
            <article key={plan.title} className="landing-pricing-card">
              <h3>{plan.title}</h3>
              <p>{plan.body}</p>
              <ul>
                {plan.points.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
        <div className="landing-section-actions">
          <Link href="/pricing" className="button-link secondary">
            View Full Pricing
          </Link>
        </div>
      </section>

      <section className="marketing-section landing-section">
        <div className="landing-final-cta">
          <div>
            <p className="marketing-kicker">Start today</p>
            <h2>Start building a smarter business today</h2>
            <p>No setup hassle. No risk. Start free and upgrade when you grow.</p>
          </div>
          <div className="landing-cta-row">
            <Link href="/login?mode=signup" className="button-link btn-primary">
              Start Free
            </Link>
            <Link href="/login" className="button-link secondary">
              Login
            </Link>
          </div>
        </div>
      </section>
    </PublicSiteChrome>
  );
}
