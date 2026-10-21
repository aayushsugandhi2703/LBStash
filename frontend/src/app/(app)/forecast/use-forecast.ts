import { useMemo } from 'react';
import type { z } from 'zod';
import type { BudgetsRes, DashboardRes, RecurringRes, ReportDailyRes } from '@/contracts';
import { errorText, useApi } from '@/lib/api';
import { useToday } from '@/lib/me';
import { categoryRows, flexibleLines, forecast, forecastChart, forecastInput, limitsById, repeatsLeft } from '@/features/forecast';
import type { PlanResponse } from '@/features/plan';

type Budgets = z.infer<typeof BudgetsRes>;
type Recurring = z.infer<typeof RecurringRes>;

/** Everything the three Forecast tabs show, once all five endpoints have answered. */
function buildModel(
  d: ReportDailyRes | undefined, plan: PlanResponse | undefined, budgets: Budgets | undefined, recurring: Recurring | undefined,
  dash: DashboardRes | undefined, today: string | undefined,
) {
  if (!d || !plan || !budgets || !recurring || !dash || !today) return null;
  const left = repeatsLeft(recurring.items, today, d.daysInMonth - d.dayOfMonth);
  const input = forecastInput({ daily: d, planLines: plan.lines, spentSoFarMinor: dash.balance.spent, availableMinor: dash.balance.available, repeatsLeftMinor: left.totalMinor });
  const f = forecast(input);
  const rows = categoryRows(flexibleLines(plan.lines, d.fixedCategories), limitsById(budgets.items), d.dayOfMonth, d.daysInMonth);
  return { input, f, left, rows, chart: forecastChart(input, f) };
}
export type Model = NonNullable<ReturnType<typeof buildModel>>;

/** The forecast model for the page, its month, and a message plus retry when a request failed. SWR shares the requests between tabs. */
export function useForecast() {
  const today = useToday();
  const daily = useApi<ReportDailyRes>('/reports/daily');
  const month = daily.data?.month ?? today?.month ?? null;
  const plan = useApi<PlanResponse>(month ? `/plans/${month}` : null);
  const budgets = useApi<Budgets>(month ? `/budgets?month=${month}` : null);
  const recurring = useApi<Recurring>('/recurring');
  const dash = useApi<DashboardRes>('/dashboard');

  const model = useMemo(
    () => buildModel(daily.data, plan.data, budgets.data, recurring.data, dash.data, today?.today),
    [daily.data, plan.data, budgets.data, recurring.data, dash.data, today?.today],
  );

  const error = daily.error ?? plan.error ?? budgets.error ?? recurring.error ?? dash.error;
  const retry = () => { void daily.mutate(); void plan.mutate(); void budgets.mutate(); void recurring.mutate(); void dash.mutate(); };
  return { month, model, errorMessage: error ? errorText(error, 'Could not load the forecast.') : null, retry };
}
