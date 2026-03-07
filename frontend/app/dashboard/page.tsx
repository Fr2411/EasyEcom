'use client';

import { useEffect, useState } from 'react';
import { apiGet, SessionUser } from '../../lib/api';

export default function DashboardPage() {
  const [data, setData] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem('easy_ecom_user');
    if (!raw) return;
    const user = JSON.parse(raw) as SessionUser;
    apiGet<Record<string, number>>('/dashboard/summary', user).then(setData).catch(() => setData(null));
  }, []);

  return (
    <div>
      <h1>Business Health Dashboard</h1>
      {!data ? <p>Loading...</p> : Object.entries(data).map(([k, v]) => <p key={k}>{k}: {v}</p>)}
    </div>
  );
}
