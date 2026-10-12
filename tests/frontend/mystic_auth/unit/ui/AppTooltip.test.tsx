// Regression coverage for the bug behind "toggles merge into the
// background in the Permissions tab" (UserAccessDialog): AppTooltip used to
// pass its child straight to Radix's TooltipTrigger asChild, which clones
// the trigger's own data-state (tooltip open/closed) directly onto whatever
// element it wraps. A plain button doesn't care, but a Radix Switch also
// uses data-state for its own meaning (checked/unchecked) - the tooltip's
// state silently clobbered it, so every switch with a tooltip got stuck at
// data-state="closed", which matches none of Switch's data-[state=...]
// color rules and renders as a colorless/transparent circle. Fixed by
// wrapping the child in a neutral span (AppTooltip.tsx) so the tooltip
// stamps its own state on that span instead of on the switch.
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import AppTooltip from '@/ui/feedback/AppTooltip';
import { Switch } from '@/ui/shadcn/switch';

describe('AppTooltip', () => {
  it("renders children unwrapped, with the child's own data-state intact, when content is falsy", () => {
    render(
      <AppTooltip content={undefined}>
        <Switch checked aria-label="on" />
      </AppTooltip>
    );

    expect(screen.getByRole('switch')).toHaveAttribute('data-state', 'checked');
  });

  it("never overwrites a wrapped Switch's own data-state (checked) with the tooltip's own data-state", () => {
    render(
      <AppTooltip content="Some hint">
        <Switch checked aria-label="on" />
      </AppTooltip>
    );

    // Before the fix, asChild's clone stamped the tooltip's own
    // data-state="closed" straight onto the switch button, so this
    // attribute read "closed" instead of "checked" even though the switch
    // itself was on - the exact bug that made it render colorless.
    expect(screen.getByRole('switch')).toHaveAttribute('data-state', 'checked');
  });

  it("never overwrites a wrapped Switch's own data-state (unchecked) with the tooltip's own data-state", () => {
    render(
      <AppTooltip content="Some hint">
        <Switch checked={false} aria-label="off" />
      </AppTooltip>
    );

    expect(screen.getByRole('switch')).toHaveAttribute('data-state', 'unchecked');
  });

  it('still shows the tooltip content on hover, so the wrapping span does not break the tooltip itself', async () => {
    const user = userEvent.setup();
    render(
      <AppTooltip content="Some hint" openDelay={0}>
        <Switch checked aria-label="on" />
      </AppTooltip>
    );

    await user.hover(screen.getByRole('switch'));

    expect(await screen.findAllByText('Some hint')).not.toHaveLength(0);
  });

  it('uses a measurable trigger wrapper so floating UI can anchor the tooltip', () => {
    render(
      <AppTooltip content="Some hint">
        <button type="button">Hover me</button>
      </AppTooltip>
    );

    const trigger = screen.getByText('Hover me').parentElement;

    expect(trigger).toHaveClass('inline-flex');
    expect(trigger).not.toHaveClass('contents');
  });
});
