import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';

import FormAlert from '@/ui/FormAlert';

function renderAlert(status: 'error' | 'success', children: React.ReactNode) {
  return render(
    <ChakraProvider value={defaultSystem}>
      <FormAlert status={status}>{children}</FormAlert>
    </ChakraProvider>
  );
}

describe('FormAlert', () => {
  it('renders its children as the alert content', () => {
    renderAlert('error', 'Something went wrong');

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('renders the Chakra alert root for error status', () => {
    const { container } = renderAlert('error', 'Something went wrong');

    expect(container.querySelector('.chakra-alert__root')).toBeInTheDocument();
  });

  it('renders success content distinctly from error content', () => {
    renderAlert('success', 'Saved successfully');

    expect(screen.getByText('Saved successfully')).toBeInTheDocument();
  });
});
