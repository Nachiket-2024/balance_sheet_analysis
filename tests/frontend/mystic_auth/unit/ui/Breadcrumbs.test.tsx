import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import type { ReactNode } from 'react';

import Breadcrumbs from '@/ui/navigation/Breadcrumbs';

function renderBreadcrumbs(children: ReactNode) {
  return render(
      <MemoryRouter>{children}</MemoryRouter>
  );
}

describe('Breadcrumbs', () => {
  it('renders nothing for an empty items list', () => {
    const { container } = renderBreadcrumbs(<Breadcrumbs items={[]} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('renders a single item as the current page, with no separator', () => {
    const { container } = renderBreadcrumbs(<Breadcrumbs items={[{ label: 'Dashboard' }]} />);

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(container.querySelector('a')).toBeNull();
  });

  it('renders every non-last item with a `to` as a link, and the last item as plain current text', () => {
    renderBreadcrumbs(
      <Breadcrumbs
        items={[
          { label: 'Users', to: '/users' },
          { label: 'Jane Doe' },
        ]}
      />
    );

    const link = screen.getByRole('link', { name: 'Users' });
    expect(link.tagName).toBe('A');
    expect(link).toHaveAttribute('href', '/users');
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('Jane Doe').tagName).toBe('SPAN');
  });

  it('renders the last item as current text even when it sets `to`', () => {
    const { container } = renderBreadcrumbs(
      <Breadcrumbs items={[{ label: 'Users', to: '/users' }, { label: 'Jane Doe', to: '/users/jane' }]} />
    );

    expect(container.querySelectorAll('a')).toHaveLength(1);
    expect(screen.getByText('Jane Doe').tagName).toBe('SPAN');
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
  });

  it('renders a non-last item with no `to` as plain text rather than a broken link', () => {
    const { container } = renderBreadcrumbs(<Breadcrumbs items={[{ label: 'Users' }, { label: 'Jane Doe' }]} />);

    expect(container.querySelector('a')).toBeNull();
    expect(screen.getByText('Users')).toBeInTheDocument();
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
  });
});
