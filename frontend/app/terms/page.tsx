import type { Metadata } from 'next';
import { LegalPageShell } from '@/components/legal/legal-page-shell';

export const metadata: Metadata = {
  title: 'Terms | EasyEcom',
  description: 'Terms governing the use of the EasyEcom platform.',
};

const effectiveDate = 'March 29, 2026';
const contactEmail = 'support@easy-ecom.online';

export default function TermsPage() {
  return (
    <LegalPageShell
      eyebrow="EasyEcom Terms"
      title="Terms of Use"
      lead="These Terms of Use govern access to and use of the EasyEcom platform, including AI-assisted selling, inventory, sales, returns, billing, and related operational workflows."
      effectiveDate={effectiveDate}
      contactEmail={contactEmail}
      links={[
        { href: '/terms', label: 'Terms' },
        { href: '/privacy', label: 'Privacy' },
        { href: '/data-deletion', label: 'Data Deletion' },
      ]}
    >
      <h2>1. Platform Use</h2>
      <p>
        EasyEcom is provided for business use. You are responsible for keeping your account credentials secure and for all
        activity that happens under your tenant workspace.
      </p>

      <h2>2. Subscription and Billing</h2>
      <p>
        Paid plans are billed through hosted subscription flows. EasyEcom does not store card data. Access to paid
        features depends on verified subscription state and payment events.
      </p>

      <h2>3. Customer and Business Data</h2>
      <p>
        You remain responsible for the accuracy, lawfulness, and rights associated with the business and customer data you
        place into the platform.
      </p>

      <h2>4. AI-Assisted Features</h2>
      <p>
        AI-assisted responses and recommendations are designed to support your workflows, but you remain responsible for the
        final business decisions and customer communications sent from your workspace.
      </p>

      <h2>5. Service Changes</h2>
      <p>
        We may improve, modify, or discontinue parts of the platform over time. Where practical, material changes will be
        reflected in updated product or legal documentation.
      </p>

      <h2>6. Contact</h2>
      <p>
        Questions about these terms can be sent to <a href={`mailto:${contactEmail}`}>{contactEmail}</a>.
      </p>
    </LegalPageShell>
  );
}
