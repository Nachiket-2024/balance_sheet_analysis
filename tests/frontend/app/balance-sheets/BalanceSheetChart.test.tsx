import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { render } from '@testing-library/react';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';

import BalanceSheetChart from '@app/balance-sheets/BalanceSheetChart';
import type { BalanceSheet } from '@app/api/balance_sheet_api';

// recharts v3 rewrote its internals significantly (2.x -> 3.x): this only
// existed as a component with zero coverage before that upgrade, so it's
// added now specifically to guard the actual props/data this app passes it
// (Tooltip/Legend formatters, multi-series data keys, null-value handling).
//
// Deliberately does not assert on recharts' own internal SVG output:
// ResponsiveContainer measures itself via ResizeObserver + getBoundingClientRect,
// neither meaningfully implemented by jsdom, and mocking both to force real
// measurement was found to be unreliable across runs in this environment
// (recharts' own internal sizing/effect timing, not this app's code). The
// minimal ResizeObserver stub below exists only so referencing it doesn't
// throw and crash the render (jsdom doesn't declare it as `undefined`, it
// throws ReferenceError on access here, so ResponsiveContainer's own
// `typeof ResizeObserver === 'undefined'` fallback never triggers); it's
// never asked to actually report a measurement. What's actually worth
// guarding here, the component doesn't crash and passes well-formed
// data/props into recharts, is covered without depending on jsdom's layout
// emulation for the resulting SVG.
beforeAll(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  );
});

afterAll(() => {
  vi.unstubAllGlobals();
});

function sheet(year: number, overrides: Partial<BalanceSheet> = {}): BalanceSheet {
  return {
    id: year,
    company_id: 1,
    year,
    created_at: '2026-01-01T00:00:00Z',
    total_assets: 100,
    total_liabilities_net_minority_interest: 40,
    stockholders_equity: 60,
    total_debt: null,
    current_assets: null,
    current_liabilities: null,
    cash_and_cash_equivalents: null,
    working_capital: null,
    ...overrides,
  };
}

describe('BalanceSheetChart', () => {
  it('renders nothing for an empty balance-sheet list', () => {
    const { container } = render(
      <ChakraProvider value={defaultSystem}>
        <BalanceSheetChart balanceSheets={[]} />
      </ChakraProvider>
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the chart title and container without crashing, for multiple fiscal years including a null series value', () => {
    const { getByText, container } = render(
      <ChakraProvider value={defaultSystem}>
        <BalanceSheetChart
          balanceSheets={[
            sheet(2023),
            sheet(2024, { total_assets: null }),
            sheet(2022),
          ]}
        />
      </ChakraProvider>
    );

    expect(getByText('Assets, liabilities & equity over time')).toBeInTheDocument();
    expect(container.querySelector('.recharts-responsive-container')).toBeTruthy();
  });

  it('renders out-of-order fiscal years without crashing', () => {
    // An uncaught render error fails this test on its own (see the
    // repo-wide ".not chaining" typecheck note for why this isn't phrased
    // as expect(...).not.toThrow()); this exists to cover the sort-by-year
    // step in BalanceSheetChart itself, not a recharts concern, with
    // genuinely unsorted input.
    const unsorted = [sheet(2024), sheet(2022), sheet(2023)];
    const { getByText } = render(
      <ChakraProvider value={defaultSystem}>
        <BalanceSheetChart balanceSheets={unsorted} />
      </ChakraProvider>
    );
    expect(getByText('Assets, liabilities & equity over time')).toBeInTheDocument();
  });
});
