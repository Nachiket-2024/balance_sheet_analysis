import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import TimeRangeControl from '@/ui/filters/TimeRangeControl';
import { DEFAULT_TIME_RANGE_STATE } from '@/audit_log/auditLogListConfig';

describe('TimeRangeControl', () => {
  it('shows the default 14-day preset label and no reset button when nothing is picked', () => {
    render(<TimeRangeControl value={DEFAULT_TIME_RANGE_STATE} onChange={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Time range' })).toHaveTextContent('Last 14 days');
    expect(screen.queryByRole('button', { name: 'Reset time range' })).toBeNull();
  });

  it('picking a preset calls onChange with that preset and clears any custom dates', async () => {
    const onChange = vi.fn();
    render(<TimeRangeControl value={DEFAULT_TIME_RANGE_STATE} onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: 'Time range' }));
    await userEvent.click(screen.getByRole('button', { name: 'Last 30 days' }));
    expect(onChange).toHaveBeenCalledWith({ range: '30', customFrom: '', customTo: '' });
  });

  it('shows a reset (x) button once the range is off its 14-day default, which resets to the default', async () => {
    const onChange = vi.fn();
    render(<TimeRangeControl value={{ range: '30', customFrom: '', customTo: '' }} onChange={onChange} />);
    expect(screen.getByText('Last 30 days')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Reset time range' }));
    expect(onChange).toHaveBeenCalledWith({ range: '14', customFrom: '', customTo: '' });
  });

  it('applying a custom range calls onChange with range "custom" and the picked dates', async () => {
    const onChange = vi.fn();
    render(<TimeRangeControl value={DEFAULT_TIME_RANGE_STATE} onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: 'Time range' }));

    const fromInput = screen.getByLabelText('From');
    const toInput = screen.getByLabelText('To');
    await userEvent.clear(fromInput);
    await userEvent.type(fromInput, '2026-01-01');
    await userEvent.clear(toInput);
    await userEvent.type(toInput, '2026-01-07');
    await userEvent.click(screen.getByRole('button', { name: 'Apply custom range' }));

    expect(onChange).toHaveBeenCalledWith({ range: 'custom', customFrom: '2026-01-01', customTo: '2026-01-07' });
  });
});
