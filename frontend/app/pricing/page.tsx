import type { Metadata } from 'next';
import { PricingPage } from '@/components/billing/pricing-page';

export const metadata: Metadata = {
  title: 'Pricing | EasyEcom',
  description: 'Compare the Free, Growth, and Scale plans for EasyEcom billing.',
};

export default function PricingRoutePage() {
  return <PricingPage />;
}
