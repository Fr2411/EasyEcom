import type { Metadata } from 'next';
import { PublicCustomerChat } from '@/components/customer-communication/public-customer-chat';

export const metadata: Metadata = {
  title: 'Store Chat | EasyEcom',
  description: 'Customer chat powered by EasyEcom.',
  robots: {
    index: false,
    follow: false,
  },
};

export default function CustomerChatPage({
  params,
}: {
  params: { channelKey: string };
}) {
  return <PublicCustomerChat channelKey={params.channelKey} />;
}
