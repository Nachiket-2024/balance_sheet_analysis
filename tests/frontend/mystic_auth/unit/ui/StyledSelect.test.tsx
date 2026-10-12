import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import StyledSelect from '@/ui/filters/StyledSelect';

const OPTIONS = [
  { value: '', label: 'All Roles' },
  { value: 'admin', label: 'Admin' },
  { value: 'user', label: 'User' },
];

function renderSelect(props: Partial<React.ComponentProps<typeof StyledSelect>> = {}) {
  const onChange = vi.fn();
  const utils = render(
      <StyledSelect
        value=""
        onChange={onChange}
        options={OPTIONS}
        ariaLabel="Filter by role"
        {...props}
      />
  );
  return { ...utils, onChange };
}

describe('StyledSelect', () => {
  it('shows the label of the option matching the current value', () => {
    renderSelect({ value: 'admin' });

    expect(screen.getByRole('combobox', { name: 'Filter by role' })).toHaveTextContent('Admin');
  });

  it('calls onChange with the picked option value when a new option is chosen', async () => {
    const { onChange } = renderSelect();

    await userEvent.click(screen.getByRole('combobox', { name: 'Filter by role' }));
    await userEvent.click(screen.getByRole('option', { name: 'Admin' }));

    expect(onChange).toHaveBeenCalledWith('admin');
  });

  it('disables the trigger and shows a loading placeholder while isLoading', () => {
    // A value matching no option, so Select.ValueText falls back to the
    // placeholder slot instead of an option's own label.
    renderSelect({ value: '__unset__', isLoading: true, placeholder: 'Pick one' });

    const trigger = screen.getByRole('combobox', { name: 'Filter by role' });
    expect(trigger).toHaveAttribute('data-disabled');
    expect(trigger).toHaveTextContent('Loading...');
  });

  it('disables the trigger when disabled is passed', () => {
    renderSelect({ disabled: true });

    expect(screen.getByRole('combobox', { name: 'Filter by role' })).toHaveAttribute('data-disabled');
  });

  it('gives the trigger a different class (brand-tint styling) once isActive is true', () => {
    const { rerender } = renderSelect({ value: 'admin', isActive: false });
    const trigger = () => screen.getByRole('combobox', { name: 'Filter by role' });
    const inactiveClassName = trigger().className;

    rerender(
        <StyledSelect
          value="admin"
          onChange={vi.fn()}
          options={OPTIONS}
          ariaLabel="Filter by role"
          isActive
        />
    );

    expect(trigger().className).not.toBe(inactiveClassName);
  });

  it('renders every option label in the open menu', async () => {
    renderSelect();

    await userEvent.click(screen.getByRole('combobox', { name: 'Filter by role' }));

    for (const option of OPTIONS) {
      expect(screen.getByRole('option', { name: option.label })).toBeInTheDocument();
    }
  });
});
