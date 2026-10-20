'use client';
import { useEffect, useState } from 'react';
import type { z } from 'zod';
import { dateKey, monthProgress, TZ } from '@/common';
import type { MeDto } from '@/contracts';
import { useApi } from './api';

type Me = z.infer<typeof MeDto>;

/** The signed-in user and the header counts (`GET /me`, composed by the gateway). */
export const useMe = () => useApi<Me>('/me');

export interface Today { tz: string; month: string; day: number; days: number; today: string }

/** "Today" in the user's zone, known only after mount so server HTML and the first client render agree. */
export function useToday(): Today | null {
  const tz = useMe().data?.timezone ?? TZ;
  const [t, setT] = useState<Today | null>(null);
  useEffect(() => {
    const now = new Date();
    const p = monthProgress(now, tz);
    setT({ tz, month: p.month, day: p.day, days: p.days, today: dateKey(now, tz) });
  }, [tz]);
  return t;
}
