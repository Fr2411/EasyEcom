import Image from 'next/image';

const DEFAULT_LOGO_SRC = '/branding/easy-ecom-logo.png';
const DEFAULT_LOGO_WIDTH = 903;
const DEFAULT_LOGO_HEIGHT = 301;

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

  return (
    <Image
      alt={title}
      className={imageClassName ?? className}
      height={DEFAULT_LOGO_HEIGHT}
      priority
      src={resolvedSrc}
      unoptimized
      width={DEFAULT_LOGO_WIDTH}
    />
  );
}
