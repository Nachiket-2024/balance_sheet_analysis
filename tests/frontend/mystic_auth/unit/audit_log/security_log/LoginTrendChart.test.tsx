import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';

import LoginTrendChart from '@/audit_log/security_log/LoginTrendChart';
import type { LoginTrendPoint } from '@/api/audit_api';

function renderChart(data: LoginTrendPoint[] | undefined, overrides?: { isLoading?: boolean; isError?: boolean }) {
  return render(
    <ChakraProvider value={defaultSystem}>
      <LoginTrendChart data={data} isLoading={overrides?.isLoading ?? false} isError={overrides?.isError ?? false} />
    </ChakraProvider>
  );
}

const SPARSE_DATA: LoginTrendPoint[] = [
  { date: '2026-01-01', success: 0, failure: 0 },
  { date: '2026-01-02', success: 1, failure: 0 },
];

describe('LoginTrendChart', () => {
  it('renders 0/half/max as three distinct y-axis labels even when the busiest day only has one event', () => {
    // Regression guard: niceMax(1) used to return 1, and the middle tick
    // (scaleMax / 2, rounded) rounded 0.5 up to 1 too - "1" appeared twice
    // (top and middle), reading as a broken/duplicated axis instead of a
    // real midpoint, exactly what happens right after your very first login
    // when there's nothing else in the last 14 days to compare against.
    renderChart(SPARSE_DATA);

    const axisLabels = screen.getAllByText(/^[0-9]+$/).map((el) => el.textContent);
    const uniqueLabels = new Set(axisLabels);

    expect(axisLabels).toHaveLength(3);
    expect(uniqueLabels.size).toBe(3);
    expect(axisLabels.sort()).toEqual(['0', '1', '2']);
  });

  it('renders nothing when there is no data', () => {
    const { container } = renderChart([]);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when data is undefined', () => {
    const { container } = renderChart(undefined);
    expect(container).toBeEmptyDOMElement();
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
});
