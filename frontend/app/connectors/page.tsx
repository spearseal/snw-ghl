'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function ConnectorsRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/?panel=connectors');
  }, [router]);
  return null;
}
