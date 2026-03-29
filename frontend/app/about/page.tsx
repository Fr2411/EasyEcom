import type { Metadata } from 'next';
import Link from 'next/link';
import { PublicLayout } from '@/components/layout/public-layout';

export const metadata: Metadata = {
  title: 'About | EasyEcom',
  description: 'Learn what EasyEcom is building for growing businesses.',
};

export default function AboutPage() {
  return (
    <PublicLayout>
      <section className="marketing-section compact-public-page">
        <div className="landing-section-heading">
          <p className="marketing-kicker">About</p>
          <h1>EasyEcom helps growing businesses sell faster and operate with less chaos.</h1>
          <p>
            We build one system for customer conversations, inventory, sales, and daily operations so business owners do not
            need to stitch together separate tools just to keep up.
          </p>
        </div>
        <div className="marketing-copy-card">
          <p>
            EasyEcom is designed for businesses that want to reply faster, keep stock accurate, and run their operations from
            one clear platform. The product combines AI-assisted selling with practical operational control so growth does not
            create more confusion.
          </p>
          <p>
            Our focus is simple: help businesses turn customer chats into sales while keeping inventory, orders, and decision
            making organized.
          </p>
          <p>
            <Link href="/signup" className="button-link btn-primary">Start Free</Link>
          </p>
        </div>
      </section>
    </PublicLayout>
  );
}
