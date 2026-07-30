import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';

import LoadingState from '@/ui/LoadingState';

describe('LoadingState', () => {
  it('renders the given message', () => {
    render(
      <ChakraProvider value={defaultSystem}>
        <LoadingState message="Loading users..." />
      </ChakraProvider>
    );

    expect(screen.getByText('Loading users...')).toBeInTheDocument();
  });

  it('renders different styling for fullScreen vs. container-sized (h/bg props differ)', () => {
    // Chakra v3 resolves style props (h, bg, py) to atomic CSS classes rather
    // than inline styles, so the only DOM-observable signal that fullScreen
    // actually changed anything is the generated className itself.
    const { container: fullScreenContainer } = render(
      <ChakraProvider value={defaultSystem}>
        <LoadingState message="Loading..." fullScreen />
      </ChakraProvider>
    );
    const { container: containerSized } = render(
      <ChakraProvider value={defaultSystem}>
        <LoadingState message="Loading..." />
      </ChakraProvider>
    );

    const fullScreenFlex = fullScreenContainer.firstElementChild as HTMLElement;
    const defaultFlex = containerSized.firstElementChild as HTMLElement;
    expect(fullScreenFlex.className === defaultFlex.className).toBe(false);
  });
});
