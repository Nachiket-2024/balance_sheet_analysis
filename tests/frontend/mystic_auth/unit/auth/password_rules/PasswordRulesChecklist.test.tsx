import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';

import PasswordRulesChecklist from '@/auth/password_rules/PasswordRulesChecklist';

function renderChecklist(rules: Partial<React.ComponentProps<typeof PasswordRulesChecklist>['rules']> = {}) {
  return render(
    <ChakraProvider value={defaultSystem}>
      <PasswordRulesChecklist
        rules={{ lengthRule: false, upperRule: false, lowerRule: false, numberRule: false, ...rules }}
      />
    </ChakraProvider>
  );
}

describe('PasswordRulesChecklist', () => {
  it('shows a failing (✗) mark for every rule that has not passed', () => {
    renderChecklist();

    expect(screen.getByText(/✗ At least 8 characters/)).toBeInTheDocument();
    expect(screen.getByText(/✗ At least one uppercase letter/)).toBeInTheDocument();
    expect(screen.getByText(/✗ At least one lowercase letter/)).toBeInTheDocument();
    expect(screen.getByText(/✗ At least one number/)).toBeInTheDocument();
  });

  it('shows a passing (✓) mark only for rules that have passed', () => {
    renderChecklist({ lengthRule: true, numberRule: true });

    expect(screen.getByText(/✓ At least 8 characters/)).toBeInTheDocument();
    expect(screen.getByText(/✓ At least one number/)).toBeInTheDocument();
    expect(screen.getByText(/✗ At least one uppercase letter/)).toBeInTheDocument();
    expect(screen.getByText(/✗ At least one lowercase letter/)).toBeInTheDocument();
  });

  it('shows all passing marks once every rule is satisfied', () => {
    renderChecklist({ lengthRule: true, upperRule: true, lowerRule: true, numberRule: true });

    expect(screen.getByText(/✓ At least 8 characters/)).toBeInTheDocument();
    expect(screen.getByText(/✓ At least one uppercase letter/)).toBeInTheDocument();
    expect(screen.getByText(/✓ At least one lowercase letter/)).toBeInTheDocument();
    expect(screen.getByText(/✓ At least one number/)).toBeInTheDocument();
  });

  it('announces updates to assistive tech via aria-live', () => {
    const { container } = renderChecklist();

    expect(container.querySelector('[aria-live="polite"]')).toBeInTheDocument();
  });
});
