import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import PasswordStrengthPanel from '@/auth/password_rules/PasswordStrengthPanel';
import { checkPasswordRules } from '@/auth/password_rules/passwordRules';

function renderPanel(password: string, label: string, pristine = false) {
  return render(
      <PasswordStrengthPanel
        password={password}
        label={label}
        rules={checkPasswordRules(password)}
        pristine={pristine}
      />
  );
}

// Same-styled segments get an identical generated className, so comparing
// classNames (instead of reading CSS vars, which jsdom won't resolve)
// tells us how many of the 4 segments are filled.
function segmentClasses(container: HTMLElement): string[] {
  // The ShieldCheck icon is also aria-hidden; narrow to the element with 4 children.
  const candidates = Array.from(container.querySelectorAll('[aria-hidden="true"]'));
  const row = candidates.find((el) => el.children.length === 4) as HTMLElement;
  return Array.from(row.children).map((el) => (el as HTMLElement).className);
}

describe('PasswordStrengthPanel', () => {
  it('fills zero segments (all share the unfilled class) and shows the muted "-" label for an empty password', () => {
    const { container } = renderPanel('', 'Strength: -');

    const classes = segmentClasses(container);
    expect(classes).toHaveLength(4);
    expect(new Set(classes).size).toBe(1); // all 4 identical -> none filled

    const label = screen.getByText('Strength: -');
    expect(label).toBeInTheDocument();
  });

  it('fills exactly 2 segments and shows red "Weak" for a password passing 2 rules', () => {
    // length + lower only = 2 rules -> Weak (<=2)
    const { container } = renderPanel('aaaaaaaa', 'Strength: Weak');

    const classes = segmentClasses(container);
    expect(classes.slice(0, 2).every((c) => c === classes[0])).toBe(true);
    expect(classes[2] === classes[0]).toBe(false); // unfilled segments differ from filled ones
    expect(classes[2]).toBe(classes[3]);

    expect(screen.getByText('Strength: Weak')).toBeInTheDocument();
  });

  it('fills exactly 3 segments and shows orange "Medium" for a password passing 3 rules', () => {
    // length + upper + lower = 3 rules -> Medium
    const { container } = renderPanel('Aaaaaaaa', 'Strength: Medium');

    const classes = segmentClasses(container);
    expect(classes.slice(0, 3).every((c) => c === classes[0])).toBe(true);
    expect(classes[3] === classes[0]).toBe(false);

    expect(screen.getByText('Strength: Medium')).toBeInTheDocument();
  });

  it('fills all 4 segments and shows green "Strong" once every rule passes', () => {
    const { container } = renderPanel('Aaaaaaaa1', 'Strength: Strong');

    const classes = segmentClasses(container);
    expect(new Set(classes).size).toBe(1); // all 4 filled -> identical class

    expect(screen.getByText('Strength: Strong')).toBeInTheDocument();
  });

  it('renders the rules checklist alongside the strength bar', () => {
    renderPanel('Aaaaaaaa1', 'Strength: Strong');

    expect(screen.getByText('At least 8 characters')).toBeInTheDocument();
    expect(screen.getByText('At least one uppercase letter')).toBeInTheDocument();
    expect(screen.getByText('At least one lowercase letter')).toBeInTheDocument();
    expect(screen.getByText('At least one number')).toBeInTheDocument();
  });
});
