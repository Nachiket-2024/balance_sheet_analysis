import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import PasswordRulesChecklist from '@/auth/password_rules/PasswordRulesChecklist';

function renderChecklist(
  rules: Partial<React.ComponentProps<typeof PasswordRulesChecklist>['rules']> = {},
  pristine = false
) {
  return render(
      <PasswordRulesChecklist
        rules={{ lengthRule: false, upperRule: false, lowerRule: false, numberRule: false, ...rules }}
        pristine={pristine}
      />
  );
}

// Each rule renders as an icon (lucide "check" or "x"), not inline text,
// so assert on the icon next to the label instead of a leading character.
function expectRuleIcon(labelText: string, iconClass: 'lucide-check' | 'lucide-x') {
  const label = screen.getByText(labelText);
  const row = label.parentElement;
  expect(row?.querySelector(`svg.${iconClass}`)).toBeInTheDocument();
}

describe('PasswordRulesChecklist', () => {
  it('shows a failing (X) mark for every rule that has not passed', () => {
    renderChecklist();

    expectRuleIcon('At least 8 characters', 'lucide-x');
    expectRuleIcon('At least one uppercase letter', 'lucide-x');
    expectRuleIcon('At least one lowercase letter', 'lucide-x');
    expectRuleIcon('At least one number', 'lucide-x');
  });

  it('shows a passing (check) mark only for rules that have passed', () => {
    renderChecklist({ lengthRule: true, numberRule: true });

    expectRuleIcon('At least 8 characters', 'lucide-check');
    expectRuleIcon('At least one number', 'lucide-check');
    expectRuleIcon('At least one uppercase letter', 'lucide-x');
    expectRuleIcon('At least one lowercase letter', 'lucide-x');
  });

  it('shows all passing marks once every rule is satisfied', () => {
    renderChecklist({ lengthRule: true, upperRule: true, lowerRule: true, numberRule: true });

    expectRuleIcon('At least 8 characters', 'lucide-check');
    expectRuleIcon('At least one uppercase letter', 'lucide-check');
    expectRuleIcon('At least one lowercase letter', 'lucide-check');
    expectRuleIcon('At least one number', 'lucide-check');
  });

  it('shows a neutral mark for every rule when pristine, not a failing (X) mark', () => {
    renderChecklist({}, true);

    const label = screen.getByText('At least 8 characters');
    const row = label.parentElement;
    // .not.toBeInTheDocument() doesn't type-check here (see the ".not chaining"
    // note in docs/mystic_auth/testing/overview.md); toBeNull() is the equivalent.
    expect(row?.querySelector('svg.lucide-x')).toBeNull();
    expect(row?.querySelector('svg.lucide-check')).toBeNull();
    expect(row?.querySelector('svg.lucide-circle')).toBeInTheDocument();
  });

  it('announces updates to assistive tech via aria-live', () => {
    const { container } = renderChecklist();

    expect(container.querySelector('[aria-live="polite"]')).toBeInTheDocument();
  });
});
