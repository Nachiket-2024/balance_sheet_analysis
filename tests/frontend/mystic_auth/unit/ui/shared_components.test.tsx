import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';

import Badge from '@/ui/badges/Badge';
import { Button } from '@/ui/buttons/Button';
import Card from '@/ui/cards/Card';
import FilterPanel from '@/ui/cards/FilterPanel';
import CardStatTile from '@/ui/cards/StatTile';
import CollapsibleSection from '@/ui/display/CollapsibleSection';
import DisplayStatTile from '@/ui/display/StatTile';
import FormAlert from '@/ui/feedback/FormAlert';
import LoadingState from '@/ui/feedback/LoadingState';
import PasswordInput from '@/ui/inputs/PasswordInput';
import { Input } from '@/ui/inputs/Input';
import { Textarea } from '@/ui/inputs/Textarea';
import AuthInlineLink from '@/ui/links/AuthInlineLink';
import Breadcrumbs from '@/ui/navigation/Breadcrumbs';
import PageContainer from '@/ui/navigation/PageContainer';
import SectionHeading from '@/ui/navigation/SectionHeading';

describe('shared UI components', () => {
  it('renders badges, buttons, cards, inputs, and links with their public behavior', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <MemoryRouter>
        <Badge colorPalette="red" variant="solid" size="lg">Danger</Badge>
        <Button loading onClick={onClick}>Save</Button>
        <Card as="article">Card content</Card>
        <FilterPanel>Filters</FilterPanel>
        <Input aria-label="Name" size="sm" defaultValue="Ada" />
        <Textarea aria-label="Notes" defaultValue="Hello" />
        <PasswordInput aria-label="Password" />
        <AuthInlineLink to="/help">Help</AuthInlineLink>
      </MemoryRouter>
    );

    expect(screen.getByText('Danger')).toHaveClass('bg-red-600');
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    expect(screen.getByText('Card content')).toBeInTheDocument();
    expect(screen.getByText('Filters')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Name' })).toHaveValue('Ada');
    expect(screen.getByRole('textbox', { name: 'Notes' })).toHaveValue('Hello');
    const password = screen.getByLabelText('Password');
    expect(password).toHaveAttribute('type', 'password');
    await user.click(screen.getByRole('button', { name: /show password/i }));
    expect(password).toHaveAttribute('type', 'text');
    expect(screen.getByRole('link', { name: 'Help' })).toHaveAttribute('href', '/help');
  });

  it.each(['error', 'success', 'warning'] as const)('renders %s form alerts', (status) => {
    render(<FormAlert status={status} size="lg" id={`${status}-alert`}>Message</FormAlert>);
    expect(screen.getByRole('alert')).toHaveAttribute('id', `${status}-alert`);
  });

  it('renders loading states and both stat tile modes', async () => {
    const onClick = vi.fn();
    render(
      <>
        <LoadingState message="Loading data" fullScreen />
        <CardStatTile icon="•" label="Total" value={1234} isLoading={false} dotColor="red" />
        <CardStatTile icon="•" label="Failed" value={undefined} isLoading={false} isError />
        <CardStatTile icon="•" label="Clickable" value={5} isLoading={false} onClick={onClick} pressed ariaLabel="Clickable stat" />
        <DisplayStatTile label="Users" value={12} isLoading={false} onClick={onClick} />
        <DisplayStatTile label="Loading" value={12} isLoading />
      </>
    );

    expect(screen.getByText('Loading data')).toBeInTheDocument();
    expect(screen.getByText('1234')).toBeInTheDocument();
    expect(screen.getByText('–')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Clickable stat' }));
    expect(onClick).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Filter: Users' })).toBeInTheDocument();
  });

  it('supports collapsible sections, static sections, breadcrumbs, and page slots', async () => {
    const onToggle = vi.fn();
    const { rerender } = render(
      <MemoryRouter>
        <CollapsibleSection title="Details">Body</CollapsibleSection>
        <CollapsibleSection title="Static" staticOpen>Always here</CollapsibleSection>
        <CollapsibleSection title="Controlled" isOpen={false} onToggle={onToggle}>Hidden</CollapsibleSection>
        <Breadcrumbs items={[{ label: 'Home', to: '/' }, { label: 'Current' }]} />
        <PageContainer title="Users" breadcrumbs={[{ label: 'Home', to: '/' }, { label: 'Users' }]} description="Manage users" actions={<button>Export</button>} headerExtra={<div>Filters</div>}>Content</PageContainer>
        <SectionHeading level="subsection" as="h3">Section</SectionHeading>
      </MemoryRouter>
    );

    expect(screen.getByText('Body')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Details' }));
    expect(screen.queryByText('Body')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Controlled' }));
    expect(onToggle).toHaveBeenCalled();
    expect(screen.getAllByRole('link', { name: 'Home' })[0]).toHaveAttribute('href', '/');
    expect(screen.getByRole('heading', { name: 'Users' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Section' })).toHaveClass('text-base');

    rerender(<Breadcrumbs items={[]} />);
    expect(screen.queryByRole('navigation', { name: 'Breadcrumb' })).not.toBeInTheDocument();
  });
});
