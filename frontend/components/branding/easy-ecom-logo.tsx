import Image from 'next/image';

const DEFAULT_LOGO_SRC = '/branding/easy-ecom-logo.svg';
const DEFAULT_LOGO_WIDTH = 690;
const DEFAULT_LOGO_HEIGHT = 184;
const DEFAULT_LOGO_VIEWBOX = '40 22 690 184';

type EasyEcomLogoProps = {
  className?: string;
  imageClassName?: string;
  src?: string;
  title?: string;
};

export function EasyEcomLogo({
  className,
  imageClassName,
  src,
  title = 'Easy-Ecom'
}: EasyEcomLogoProps) {
  const resolvedSrc = src ?? DEFAULT_LOGO_SRC;

  if (resolvedSrc) {
    return (
      <Image
        alt={title}
        className={imageClassName ?? className}
        height={DEFAULT_LOGO_HEIGHT}
        priority
        src={resolvedSrc}
        width={DEFAULT_LOGO_WIDTH}
      />
    );
  }

  return (
    <svg
      aria-label={title}
      className={className}
      role="img"
      viewBox={DEFAULT_LOGO_VIEWBOX}
      xmlns="http://www.w3.org/2000/svg"
    >
      <title>{title}</title>
      <defs>
        <linearGradient id="easy-ecom-logo-gradient" x1="110" y1="40" x2="640" y2="180" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#0d63d8" />
          <stop offset="52%" stopColor="#1688ff" />
          <stop offset="100%" stopColor="#56c1ff" />
        </linearGradient>
        <filter
          id="easy-ecom-logo-glow"
          x="-8%"
          y="-18%"
          width="116%"
          height="136%"
          colorInterpolationFilters="sRGB"
        >
          <feGaussianBlur in="SourceGraphic" result="blur" stdDeviation="11" />
          <feComponentTransfer in="blur" result="glow">
            <feFuncA type="linear" slope="0.5" />
          </feComponentTransfer>
          <feMerge>
            <feMergeNode in="glow" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <g id="easy-ecom-logo-mark">
        <g fill="none" stroke="url(#easy-ecom-logo-gradient)" strokeLinecap="round" strokeLinejoin="round">
          <path d="M58 76h72l30 104h246" strokeWidth="20" />
          <path d="M132 100h24v40h-24zm52-20h24v60h-24zm52-12h24v72h-24zm52-26h24v98h-24z" fill="url(#easy-ecom-logo-gradient)" strokeWidth="8" />
          <path d="M124 152h212l28-102" strokeWidth="18" />
          <path d="M130 92c84 0 154-18 212-58" strokeWidth="11" />
          <path d="m332 46 58-16-16 58" strokeWidth="11" />
          <circle cx="190" cy="200" r="16" fill="url(#easy-ecom-logo-gradient)" strokeWidth="8" />
          <circle cx="332" cy="200" r="16" fill="url(#easy-ecom-logo-gradient)" strokeWidth="8" />
        </g>
        <text
          fill="url(#easy-ecom-logo-gradient)"
          fontFamily="Inter, sans-serif"
          fontSize="96"
          fontWeight="800"
          letterSpacing="-0.05em"
          x="438"
          y="146"
        >
          Easy-Ecom
        </text>
      </g>
      <use href="#easy-ecom-logo-mark" filter="url(#easy-ecom-logo-glow)" opacity="0.9" />
      <use href="#easy-ecom-logo-mark" />
    </svg>
  );
}
