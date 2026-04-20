import type { Metadata } from 'next';
import { LegalPageShell } from '@/components/legal/legal-page-shell';

export const metadata: Metadata = {
  title: 'Privacy Policy | EasyEcom',
  description: 'Privacy Policy for EasyEcom commerce operations platform.',
};

const effectiveDate = 'March 18, 2026';
const contactEmail = 'support@easy-ecom.online';

export default function PrivacyPage() {
  return (
    <LegalPageShell
      title="Privacy Policy"
      lead="This Privacy Policy explains how EasyEcom collects, uses, stores, and protects information when businesses use the EasyEcom platform, including inventory, sales, warehouse, and reporting features."
      effectiveDate={effectiveDate}
      contactEmail={contactEmail}
      links={[
        { href: '/privacy', label: 'Privacy Policy' },
        { href: '/data-deletion', label: 'Data Deletion' },
      ]}
    >
        <h2>1. Who We Are</h2>
        <p>
          EasyEcom provides software for commerce operations, including catalog management, inventory tracking, purchase
          and sales workflows, customer management, and reporting.
        </p>

        <h2>2. Information We Collect</h2>
        <p>Depending on how the platform is used, we may collect and process the following categories of information:</p>
        <ul>
          <li>Business account details such as business name, contact information, tax or registration details, and billing data.</li>
          <li>User account details such as names, email addresses, roles, login activity, and account preferences.</li>
          <li>Customer and transaction data such as customer names, phone numbers, email addresses, order history, returns, and payment-related records.</li>
          <li>Catalog, pricing, warehouse, and inventory data including products, variants, stock movements, purchase entries, and sales entries.</li>
          <li>Communication data such as support inquiries submitted through the website or support channels.</li>
          <li>Technical and usage data such as IP address, browser type, device information, request logs, diagnostics, and security events.</li>
        </ul>

        <h2>3. How We Use Information</h2>
        <p>We use information to operate, secure, improve, and support the EasyEcom platform, including to:</p>
        <ul>
          <li>create and manage tenant accounts and user access;</li>
          <li>support inventory, catalog, procurement, sales, returns, finance visibility, and reporting workflows;</li>
          <li>process and store customer communication records and support requests;</li>
          <li>monitor system performance, detect fraud or abuse, and maintain platform security;</li>
          <li>comply with legal obligations, resolve disputes, and enforce platform terms.</li>
        </ul>

        <h2>4. Legal Bases and Business Use</h2>
        <p>
          Where applicable, we process information on the basis of contract performance, legitimate business interests,
          compliance with legal obligations, consent where required, and other lawful bases permitted by applicable data
          protection law.
        </p>

        <h2>5. How We Share Information</h2>
        <p>We do not sell personal information. We may share information only as necessary with:</p>
        <ul>
          <li>cloud, hosting, analytics, communication, and infrastructure providers that support operation of the platform;</li>
          <li>service providers that help us deliver security, storage, and support functions;</li>
          <li>law enforcement, regulators, courts, or other parties where disclosure is required by law or to protect rights and safety;</li>
          <li>successors or counterparties involved in a merger, acquisition, financing, or business transfer, subject to appropriate safeguards.</li>
        </ul>

        <h2>6. Data Retention</h2>
        <p>
          We retain information for as long as reasonably necessary to provide services, maintain auditability, support
          tenant operations, comply with legal and financial obligations, resolve disputes, and enforce agreements.
          Retention periods may vary based on the type of data and the tenant&apos;s configuration.
        </p>

        <h2>7. Security</h2>
        <p>
          We use administrative, technical, and organizational safeguards designed to protect information against
          unauthorized access, loss, misuse, or alteration. No system can guarantee absolute security, but we aim to apply
          reasonable and industry-aligned safeguards appropriate to the nature of the data we process.
        </p>

        <h2>8. International Processing</h2>
        <p>
          Information may be processed or stored in countries other than the one in which it was collected. Where required,
          we take steps intended to ensure an appropriate level of protection for cross-border data transfers.
        </p>

        <h2>9. Your Rights and Choices</h2>
        <p>Depending on applicable law, individuals may have rights to request access, correction, deletion, restriction, or portability of personal data, or to object to certain processing.</p>
        <p>
          Where EasyEcom acts as a service provider or processor for a tenant business, requests relating to end-customer
          data may need to be directed to the relevant tenant first. We may assist tenants in responding to such requests
          where appropriate.
        </p>

        <h2>10. Children&apos;s Privacy</h2>
        <p>
          EasyEcom is intended for business use and is not directed to children. We do not knowingly collect personal data
          from children in a manner that requires parental consent under applicable law.
        </p>

        <h2>11. Changes to This Policy</h2>
        <p>
          We may update this Privacy Policy from time to time. The updated version will be posted on this page with a
          revised effective date. Material changes may also be communicated through the platform or other appropriate means.
        </p>

        <h2>12. Contact</h2>
        <p>
          For privacy-related questions, requests, or complaints, contact us at <a href={`mailto:${contactEmail}`}>{contactEmail}</a>.
        </p>
    </LegalPageShell>
  );
}
