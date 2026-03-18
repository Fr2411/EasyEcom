import type { Metadata } from 'next';
import { LegalPageShell } from '@/components/legal/legal-page-shell';

export const metadata: Metadata = {
  title: 'Data Deletion Instructions | EasyEcom',
  description: 'Data deletion instructions for EasyEcom platform users and customer data requests.',
};

const effectiveDate = 'March 18, 2026';
const contactEmail = 'support@easy-ecom.online';

export default function DataDeletionPage() {
  return (
    <LegalPageShell
      title="Data Deletion Instructions"
      lead="This page explains how EasyEcom users and tenant businesses can request deletion of account or customer-related data processed through the EasyEcom platform."
      effectiveDate={effectiveDate}
      contactEmail={contactEmail}
      links={[
        { href: '/privacy', label: 'Privacy Policy' },
        { href: '/data-deletion', label: 'Data Deletion' },
      ]}
    >
      <h2>1. How to Request Deletion</h2>
      <p>
        To request deletion of personal data associated with EasyEcom, send an email to{' '}
        <a href={`mailto:${contactEmail}`}>{contactEmail}</a> with the subject line <strong>Data Deletion Request</strong>.
      </p>

      <h2>2. Information to Include</h2>
      <p>To help us locate the correct records, include as much of the following as applicable:</p>
      <ul>
        <li>your full name;</li>
        <li>your email address;</li>
        <li>your phone number;</li>
        <li>the business or tenant name associated with the request;</li>
        <li>relevant customer or account identifiers, if known;</li>
        <li>a description of the data you want deleted.</li>
      </ul>

      <h2>3. Verification</h2>
      <p>
        We may request additional information to verify identity or confirm authority before processing a deletion request.
        This is required to protect account security and prevent unauthorized deletion.
      </p>

      <h2>4. Tenant-Controlled Data</h2>
      <p>
        EasyEcom is a multi-tenant business platform. If the requested data belongs to a customer record managed by one of
        our tenant businesses, the relevant tenant may need to review or authorize the request before deletion can be
        completed. In such cases, we may coordinate with that tenant as part of the request process.
      </p>

      <h2>5. What Happens After a Request</h2>
      <p>After verification, we will review the request and either:</p>
      <ul>
        <li>delete the eligible data;</li>
        <li>anonymize the eligible data where deletion is not operationally appropriate;</li>
        <li>retain limited records where retention is required for legal, regulatory, security, fraud prevention, tax, accounting, or audit obligations.</li>
      </ul>

      <h2>6. Response Timing</h2>
      <p>
        We aim to acknowledge deletion requests promptly and respond within a commercially reasonable period, subject to
        verification, system constraints, and applicable legal obligations.
      </p>

      <h2>7. Messaging and AI Records</h2>
      <p>
        If a request involves messaging or AI-assisted communication records, we will review the associated data stored in
        EasyEcom systems and process eligible deletion or anonymization in line with tenant obligations and audit
        requirements.
      </p>

      <h2>8. Contact</h2>
      <p>
        For all deletion-related requests, contact <a href={`mailto:${contactEmail}`}>{contactEmail}</a>.
      </p>
    </LegalPageShell>
  );
}
