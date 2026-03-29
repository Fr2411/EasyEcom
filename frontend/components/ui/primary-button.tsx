import type { ButtonHTMLAttributes, AnchorHTMLAttributes, ReactNode } from 'react';
import Link from 'next/link';

type SharedProps = {
  children: ReactNode;
  className?: string;
};

type ButtonProps = SharedProps & ButtonHTMLAttributes<HTMLButtonElement> & { href?: undefined };
type LinkProps = SharedProps & AnchorHTMLAttributes<HTMLAnchorElement> & { href: string };

export function PrimaryButton(props: ButtonProps | LinkProps) {
  if ('href' in props && props.href) {
    const { href, children, className = '', ...rest } = props;
    return (
      <Link href={href} className={`button-link btn-primary ${className}`.trim()} {...rest}>
        {children}
      </Link>
    );
  }

  const { children, className = '', ...rest } = props as ButtonProps;
  return (
    <button className={`btn-primary ${className}`.trim()} {...rest}>
      {children}
    </button>
  );
}
