import Link from 'next/link';
import { EasyEcomLogo } from '@/components/branding/easy-ecom-logo';

const FOOTER_GROUPS = [
  {
    title: 'Product',
    links: [
      { href: '/#features', label: 'Features' },
      { href: '/pricing', label: 'Pricing' },
    ],
  },
  {
    title: 'Company',
    links: [
      { href: '/about', label: 'About' },
      { href: '/contact', label: 'Contact' },
    ],
  },
  {
    title: 'Account',
    links: [
      { href: '/login', label: 'Login' },
      { href: '/signup', label: 'Sign Up' },
    ],
  },
  {
    title: 'Legal',
    links: [
      { href: '/terms', label: 'Terms' },
      { href: '/privacy', label: 'Privacy' },
    ],
  },
];

export function PublicFooter() {
  return (
    <footer className="marketing-footer-shell">
      <div className="marketing-footer">
        <div className="marketing-footer-brand">
          <Link href="/" className="marketing-brand" aria-label="EasyEcom home">
            <EasyEcomLogo className="easyecom-logo" imageClassName="easyecom-logo-image" />
            <div>
              <strong>EasyEcom</strong>
              <span>Business operating system</span>
            </div>
          </Link>
        </div>
        <div className="marketing-footer-grid">
          {FOOTER_GROUPS.map((group) => (
            <section key={group.title} className="marketing-footer-group" aria-label={group.title}>
              <h2>{group.title}</h2>
              <ul>
                {group.links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href}>{link.label}</Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </footer>
  );
}
