import { ArrowRight, Boxes, ChartColumnIncreasing, MessageSquareText, PackageCheck, ShoppingCart, Sparkles } from 'lucide-react';
import type { Metadata } from 'next';
import { CTASection } from '@/components/marketing/cta-section';
import { FeatureGrid } from '@/components/marketing/feature-grid';
import { HeroSection } from '@/components/marketing/hero-section';
import { PricingPreview } from '@/components/marketing/pricing-preview';
import { ProblemCards } from '@/components/marketing/problem-cards';
import { PublicLayout } from '@/components/layout/public-layout';
import { PrimaryButton } from '@/components/ui/primary-button';
import { SecondaryButton } from '@/components/ui/secondary-button';

export const metadata: Metadata = {
  title: 'EasyEcom | Run Commerce Operations In One Place',
  description: 'EasyEcom is your sales and operations platform for managing inventory, orders, returns, and reporting in one place.',
  openGraph: {
    title: 'EasyEcom | Run Commerce Operations In One Place',
    description: 'Manage inventory, orders, and business operations from one platform.',
  },
};

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
    title: 'Customer Management',
    body: 'Track customer history and keep service decisions tied to real order activity.',
    icon: MessageSquareText,
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

const operationsPoints = [
  'Track catalog, stock, and warehouses in one place',
  'Create and manage sales, purchases, and returns',
  'Review finance and reports with tenant-safe access',
  'Keep daily operations auditable and consistent',
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
    points: ['Limited products', 'Core commerce workspace'],
  },
  {
    title: 'Growth Plan',
    body: 'For growing businesses',
    points: ['More products', 'Automation', 'Full access to core features'],
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
        <div className="hero-window-bar" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <div className="hero-panel-head">
          <span className="hero-panel-kicker">Sales desk</span>
          <strong>New order request</strong>
        </div>
        <div className="hero-code-chip-row" aria-label="Workflow state">
          <span>[ inquiry ]</span>
          <span>[ order draft ]</span>
          <span>[ draft order ]</span>
        </div>
        <div className="hero-chat-thread">
          <article className="hero-bubble customer">
            <span className="hero-bubble-label">Customer</span>
            <p>Do you have the black travel bag in stock?</p>
          </article>
          <article className="hero-bubble ai">
            <span className="hero-bubble-label">Sales team</span>
            <p>Yes — the black travel bag is available. I can place your order now for 2 pieces.</p>
          </article>
          <article className="hero-bubble system">
            <span className="hero-bubble-label">Suggested order</span>
            <p>Travel Bag / Black / Qty 2 staged from conversation.</p>
          </article>
        </div>
      </section>

      <section className="hero-dashboard-panel">
        <div className="hero-window-bar" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <div className="hero-panel-head">
          <span className="hero-panel-kicker">Operations</span>
          <strong>Order created</strong>
        </div>
        <div className="hero-metric-strip">
          <article>
            <span>Response time</span>
            <strong>12 sec</strong>
          </article>
          <article>
            <span>Stock status</span>
            <strong>In sync</strong>
          </article>
          <article>
            <span>Order value</span>
            <strong>$120</strong>
          </article>
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
              <span>Order cycle</span>
              <strong>Fast team workflow</strong>
            </div>
          </article>
        </div>
        <div className="hero-chart-card">
          <div className="hero-chart-head">
            <span>Conversation to order</span>
            <strong>Today</strong>
          </div>
          <div className="hero-chart-bars" aria-hidden="true">
            <span style={{ height: '42%' }} />
            <span style={{ height: '58%' }} />
            <span style={{ height: '49%' }} />
            <span style={{ height: '74%' }} />
            <span style={{ height: '68%' }} />
            <span style={{ height: '84%' }} />
          </div>
        </div>
      </section>
    </div>
  );
}

export default function PublicLandingPage() {
  return (
    <PublicLayout ctaLabel="Start Free" ctaHref="/signup">
      <HeroSection
        title="Run your sales and operations in one workspace"
        description="EasyEcom helps you manage catalog, inventory, sales, purchases, returns, and reporting from one platform."
        trustLine="Used by growing businesses to handle sales, inventory, and operations in one place."
        actions={
          <>
            <PrimaryButton href="/signup">Start Free — No Credit Card</PrimaryButton>
            <SecondaryButton href="/#how-it-works">See How It Works</SecondaryButton>
          </>
        }
        visual={<HeroMockup />}
      />

      <section className="marketing-section landing-section" id="features">
        <div className="landing-section-heading">
          <p className="marketing-kicker">The problem</p>
          <h2>Running your business shouldn’t feel like chaos</h2>
          <p>Most small businesses struggle with the same problems:</p>
        </div>
        <ProblemCards items={problems} />
      </section>

      <section className="marketing-section landing-section landing-section-contrast">
        <div className="landing-section-heading">
          <p className="marketing-kicker">The solution</p>
          <h2>EasyEcom fixes this — automatically</h2>
          <p>One system to manage your entire business operations.</p>
        </div>
        <FeatureGrid items={solutions} />
      </section>

      <section className="marketing-section landing-section">
        <div className="landing-ai-grid">
          <div className="landing-section-heading">
            <p className="marketing-kicker">Operations</p>
            <h2>Keep the core business running cleanly</h2>
            <p>Use one workspace to execute day-to-day commerce workflows without disconnected tools.</p>
            <ul className="landing-check-list">
              {operationsPoints.map((point) => (
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
        <PricingPreview plans={pricingPreview} />
        <div className="landing-section-actions">
          <SecondaryButton href="/pricing">View Full Pricing</SecondaryButton>
        </div>
      </section>

      <CTASection
        title="Start building a smarter business today"
        description="No setup hassle. No risk. Start free and upgrade when you grow."
        actions={
          <>
            <PrimaryButton href="/signup">Start Free</PrimaryButton>
            <SecondaryButton href="/login">Login</SecondaryButton>
          </>
        }
      />
    </PublicLayout>
  );
}
