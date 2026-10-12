import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import FormAlert from '@/ui/feedback/FormAlert';

function renderAlert(status: 'error' | 'success', children: React.ReactNode) {
  return render(<FormAlert status={status}>{children}</FormAlert>);
}

describe('FormAlert', () => {
  it('renders its children as the alert content', () => {
    renderAlert('error', 'Something went wrong');

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('renders an alert role for error status', () => {
    renderAlert('error', 'Something went wrong');

    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('renders success content distinctly from error content', () => {
    renderAlert('success', 'Saved successfully');

    expect(screen.getByText('Saved successfully')).toBeInTheDocument();
  });
});
