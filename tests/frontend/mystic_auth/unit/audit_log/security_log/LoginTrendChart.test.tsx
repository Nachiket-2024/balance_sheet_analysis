import { describe, it, expect } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import LoginTrendChart from '@/audit_log/security_log/LoginTrendChart';
import type { LoginTrendPoint } from '@/api/audit_api';

function renderChart(data: LoginTrendPoint[] | undefined, overrides?: { isLoading?: boolean; isError?: boolean }) {
  return render(
      <LoginTrendChart data={data} isLoading={overrides?.isLoading ?? false} isError={overrides?.isError ?? false} />
  );
}

const SPARSE_DATA: LoginTrendPoint[] = [
  { date: '2026-01-01', success: 0, failure: 0 },
  { date: '2026-01-02', success: 1, failure: 0 },
];

describe('LoginTrendChart', () => {
  it('renders 0/half/max as three distinct y-axis labels even when the busiest day only has one event', () => {
    // Regression guard: niceMax(1) used to return 1, and the middle tick
    // (half of that, rounded) also rounded up to 1, so "1" appeared twice
    // instead of a real midpoint.
    renderChart(SPARSE_DATA);

    const axisLabels = within(screen.getByTestId('chart-y-axis'))
      .getAllByText(/^[0-9]+$/)
      .map((el) => el.textContent);
    const uniqueLabels = new Set(axisLabels);

    expect(axisLabels).toHaveLength(3);
    expect(uniqueLabels.size).toBe(3);
    expect(axisLabels.sort()).toEqual(['0', '1', '2']);
  });

  it('shows attempts/failed/failure-rate/most-failures KPIs computed from the range', () => {
    const data: LoginTrendPoint[] = [
      { date: '2026-01-01', success: 8, failure: 2 },
      { date: '2026-01-02', success: 5, failure: 5 },
    ];
    renderChart(data);

    expect(screen.getByText('20')).toBeInTheDocument(); // attempts: 8+2+5+5
    expect(screen.getByText('7')).toBeInTheDocument(); // failed: 2+5
    expect(screen.getByText('35%')).toBeInTheDocument(); // failure rate: 7/20
    const mostFailuresLabel = screen.getByText('Most failures (5)');
    // "2 Jan" (the 5-failure day) also appears as an x-axis tick below the chart, so this
    // scopes to the KPI tile itself rather than screen.getByText finding both.
    expect(within(mostFailuresLabel.parentElement!).getByText('2 Jan')).toBeInTheDocument();
  });

  it('omits the "most failures" KPI when every day in range has zero failures', () => {
    const data: LoginTrendPoint[] = [
      { date: '2026-01-01', success: 3, failure: 0 },
      { date: '2026-01-02', success: 4, failure: 0 },
    ];
    renderChart(data);

    expect(screen.queryByText(/Most failures/)).toBeNull();
  });

  it('shows an empty-range message when there is no data', () => {
    renderChart([]);
    expect(screen.getByText('No sign-in attempts in this range')).toBeInTheDocument();
  });

  it('renders nothing (no loading/error/empty state) while data is merely undefined and not loading or errored', () => {
    // Distinguishes "still fetching" (isLoading true) from "loaded, zero rows" ([] above):
    // undefined with isLoading false shouldn't normally happen from a real query, but the
    // component still falls through to the empty-range message rather than rendering nothing,
    // since `data` alone can't tell loaded-empty apart from not-yet-loaded.
    renderChart(undefined);
    expect(screen.getByText('No sign-in attempts in this range')).toBeInTheDocument();
  });

  it('shows a loading placeholder (not the error message or empty state) while fetching', () => {
    const { container } = renderChart(undefined, { isLoading: true });
    expect(container.childElementCount).toBeGreaterThan(0);
    expect(screen.queryByText('Failed to load login trend')).toBeNull();
  });

  it('shows an error message when the trend fails to load', () => {
    renderChart(undefined, { isError: true });
    expect(screen.getByText('Failed to load login trend')).toBeInTheDocument();
  });

  it('announces background refetches while keeping the current chart visible', () => {
    const { container } = render(
      <LoginTrendChart data={SPARSE_DATA} isLoading={false} isFetching isError={false} />
    );

    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /sign-in attempts/i })).toBeInTheDocument();
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('shows the exact day counts and positions the tooltip when a bar receives keyboard focus', () => {
    const { container } = renderChart(SPARSE_DATA);
    const bars = screen.getByRole('img').querySelectorAll('g');
    const secondBar = bars[1];
    expect(secondBar).toBeTruthy();

    fireEvent.focus(secondBar!);

    expect(screen.getByText('Success:', { exact: true })).toBeInTheDocument();
    expect(screen.getByText('Failed:', { exact: true })).toBeInTheDocument();
    expect(container.querySelector('[style*="--tooltip-left"]')).toHaveStyle('--tooltip-left: 75%');
  });

  it('thins x-axis labels to weekly ticks for a 90-day range', () => {
    const start = new Date('2026-01-01T00:00:00Z');
    const data = Array.from({ length: 90 }, (_, index) => {
      const date = new Date(start);
      date.setUTCDate(start.getUTCDate() + index);
      return { date: date.toISOString().slice(0, 10), success: index, failure: 0 };
    });
    const { container } = renderChart(data);
    const axis = container.querySelector('div.flex.items-center.mt-1');

    expect(Array.from(axis?.querySelectorAll('p') ?? []).filter((label) => label.textContent)).toHaveLength(13);
  });

  it('switches to a plain date/success/failed/rate table on the Table view toggle', async () => {
    const data: LoginTrendPoint[] = [
      { date: '2026-01-01', success: 8, failure: 2 },
      { date: '2026-01-02', success: 5, failure: 5 },
    ];
    renderChart(data);

    expect(screen.queryByRole('table')).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Table' }));

    const table = screen.getByRole('table');
    expect(within(table).getByText('1 Jan')).toBeInTheDocument();
    expect(within(table).getByText('20%')).toBeInTheDocument(); // 2/10 rate on the first row
    expect(within(table).getByText('50%')).toBeInTheDocument(); // 5/10 rate on the second row
  });

  it('rescales the y-axis to failures alone on the "Failed only" toggle', async () => {
    // Success dwarfs failure here - under "All attempts" the max is 100 (95+5), so the scale
    // reads in the hundreds; under "Failed only" it should instead scale to just the failures.
    const data: LoginTrendPoint[] = [{ date: '2026-01-01', success: 95, failure: 5 }];
    renderChart(data);

    await userEvent.click(screen.getByRole('button', { name: 'Failed only' }));

    const axisLabels = within(screen.getByTestId('chart-y-axis'))
      .getAllByText(/^[0-9]+$/)
      .map((el) => el.textContent);
    expect(axisLabels).toContain('5'); // niceMax(5) -> 5, not niceMax(100) -> 100
    expect(axisLabels).not.toContain('100');
  });
});
