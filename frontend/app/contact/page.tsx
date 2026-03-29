import type { Metadata } from 'next';
import { PublicSiteChrome } from '@/components/marketing/public-site-chrome';

export const metadata: Metadata = {
  title: 'Contact | EasyEcom',
  description: 'Contact EasyEcom for product, sales, or support questions.',
};

const contactEmail = 'support@easy-ecom.online';

export default function ContactPage() {
  return (
    <PublicSiteChrome>
      <section className="marketing-section compact-public-page">
        <div className="landing-section-heading">
          <p className="marketing-kicker">Contact</p>
          <h1>Talk to the EasyEcom team</h1>
          <p>
            If you have questions about the platform, pricing, onboarding, or support, reach out and we will guide you from
            there.
          </p>
        </div>
        <div className="marketing-copy-card">
          <div className="contact-detail-grid">
            <article>
              <h2>Email</h2>
              <p><a href={`mailto:${contactEmail}`}>{contactEmail}</a></p>
            </article>
            <article>
              <h2>Product</h2>
              <p>Questions about AI selling, inventory, billing, or how EasyEcom fits your workflow.</p>
            </article>
            <article>
              <h2>Support</h2>
              <p>Need help with setup, plan access, or operations? Contact us and include your business name.</p>
            </article>
          </div>
        </div>
      </section>
    </PublicSiteChrome>
  );
}
