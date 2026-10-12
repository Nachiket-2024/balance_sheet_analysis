import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import DataTable, { type DataTableColumn } from '@/ui/DataTable/DataTable';

interface Row {
  id: number;
  name: string;
}

const columns: DataTableColumn<Row>[] = [
  { key: 'id', header: 'ID', render: (row) => row.id },
  { key: 'name', header: 'Name', render: (row) => row.name },
  // A real interactive control inside a cell (like UsersTable's Role
  // select); row-click-to-select must not fire underneath it.
  { key: 'action', header: 'Action', render: () => <button>Row action</button> },
];

function renderTable(props: Partial<React.ComponentProps<typeof DataTable<Row>>> = {}) {
  return render(
      <DataTable columns={columns} rows={[]} rowKey={(row) => row.id} {...props} />
  );
}

describe('DataTable', () => {
  it('renders skeleton placeholders while loading, not the rows or empty state', () => {
    renderTable({ isLoading: true, rows: [{ id: 1, name: 'Alice' }] });

    expect(screen.queryByText('Alice')).toBeNull();
    expect(screen.getByText('ID')).toBeInTheDocument();
  });

  it('renders the error message when isError is true, even if rows are present', () => {
    renderTable({ isError: true, errorMessage: 'Could not load rows', rows: [{ id: 1, name: 'Alice' }] });

    expect(screen.getByText('Could not load rows')).toBeInTheDocument();
    expect(screen.queryByText('Alice')).toBeNull();
  });

  it('falls back to the default error message when none is provided', () => {
    renderTable({ isError: true });

    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
  });

  it('renders the empty state when rows is an empty array', () => {
    renderTable({ rows: [] });

    expect(screen.getByText('No data available')).toBeInTheDocument();
  });

  it('renders the empty state when rows is undefined', () => {
    renderTable({ rows: undefined });

    expect(screen.getByText('No data available')).toBeInTheDocument();
  });

  it('renders a custom empty message when provided', () => {
    renderTable({ rows: [], emptyMessage: 'Nothing here yet' });

    expect(screen.getByText('Nothing here yet')).toBeInTheDocument();
  });

  it('exposes sortable header state and handles keyboard sorting', () => {
    const onSortChange = vi.fn();
    const sortableColumns: DataTableColumn<Row>[] = [
      { key: 'id', header: 'ID', sortable: true, render: (row) => row.id },
      { key: 'name', header: 'Name', render: (row) => row.name },
    ];

    render(
      <DataTable
        columns={sortableColumns}
        rows={[{ id: 1, name: 'Alice' }]}
        rowKey={(row) => row.id}
        sort={{ key: 'id', direction: 'desc' }}
        onSortChange={onSortChange}
      />
    );

    const idHeader = screen.getByRole('columnheader', { name: /ID/ });
    const nameHeader = screen.getByRole('columnheader', { name: 'Name' });
    expect(idHeader).toHaveAttribute('aria-sort', 'descending');
    expect(nameHeader).not.toHaveAttribute('aria-sort');

    fireEvent.keyDown(idHeader, { key: 'Enter' });
    fireEvent.keyDown(idHeader, { key: ' ' });
    fireEvent.keyDown(idHeader, { key: 'Escape' });

    expect(onSortChange).toHaveBeenCalledTimes(2);
    expect(onSortChange).toHaveBeenCalledWith('id');
  });

  it('renders selection, row-number, alignment, truncation, and row-click header cells', () => {
    renderTable({
      columns: [
        { key: 'name', header: 'A long name', truncate: true, align: 'end', render: (row) => row.name },
      ],
      rows: [{ id: 1, name: 'Alice' }],
      startIndex: 10,
      selectable: true,
      selectedKeys: new Set(),
      onSelectionChange: vi.fn(),
      onRowClick: vi.fn(),
    });

    expect(screen.getByRole('checkbox', { name: /select all rows/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: '#' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /A long name/ })).toHaveClass('text-right');
  });

  it('renders one row per item, using rowKey and each column render function', () => {
    renderTable({ rows: [{ id: 1, name: 'Alice' }, { id: 2, name: 'Bob' }] });

    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getAllByRole('row')).toHaveLength(3); // header + 2 rows
  });

  // Row-click-to-select: opt-in via `rowClickSelects` (e.g. BulkActionToolbar's
  // "Select mode" button). While active, clicking anywhere in a selectable
  // row toggles it, but a click on a real control inside the row (a button,
  // a select) should keep doing its own thing instead.
  describe('row-click-to-select', () => {
    function renderSelectable(selectedKeys: ReadonlySet<number> = new Set(), rowClickSelects = true) {
      const onSelectionChange = vi.fn();
      const utils = render(
          <DataTable
            columns={columns}
            rows={[{ id: 1, name: 'Alice' }]}
            rowKey={(row) => row.id}
            selectable
            rowClickSelects={rowClickSelects}
            selectedKeys={selectedKeys}
            onSelectionChange={onSelectionChange}
          />
      );
      return { ...utils, onSelectionChange };
    }

    it('toggles selection when clicking plain row content, not just the checkbox', async () => {
      const user = userEvent.setup();
      const { onSelectionChange } = renderSelectable();

      await user.click(screen.getByText('Alice'));

      // onSelectionChange is called with the functional form, computing the
      // next set off latest state rather than a render-time snapshot (see DataTableSelection.ts).
      expect(onSelectionChange).toHaveBeenCalledTimes(1);
      const updater = onSelectionChange.mock.calls[0][0] as (prev: ReadonlySet<number>) => Set<number>;
      expect(updater(new Set())).toEqual(new Set([1]));
    });

    it('does not toggle selection when the click starts on a button inside the row', async () => {
      const user = userEvent.setup();
      const { onSelectionChange } = renderSelectable();

      await user.click(screen.getByRole('button', { name: 'Row action' }));

      expect(onSelectionChange).toHaveBeenCalledTimes(0);
    });

    it('does not toggle on row-content clicks while rowClickSelects is off (the default)', async () => {
      const user = userEvent.setup();
      const { onSelectionChange } = renderSelectable(new Set(), false);

      await user.click(screen.getByText('Alice'));

      expect(onSelectionChange).toHaveBeenCalledTimes(0);
    });

    it('does not double-toggle when clicking the checkbox itself', async () => {
      const user = userEvent.setup();
      const { onSelectionChange } = renderSelectable();

      await user.click(screen.getByRole('checkbox', { name: /select row/i }));

      expect(onSelectionChange).toHaveBeenCalledTimes(1);
      const updater = onSelectionChange.mock.calls[0][0] as (prev: ReadonlySet<number>) => Set<number>;
      expect(updater(new Set())).toEqual(new Set([1]));
    });
  });

  describe('onRowClick', () => {
    it('calls onRowClick with the clicked row when a row is clicked', async () => {
      const user = userEvent.setup();
      const onRowClick = vi.fn();
      renderTable({ rows: [{ id: 1, name: 'Alice' }], onRowClick });

      await user.click(screen.getByText('Alice'));

      expect(onRowClick).toHaveBeenCalledWith({ id: 1, name: 'Alice' });
    });

    it('opens the row from keyboard focus with Enter or Space', async () => {
      const user = userEvent.setup();
      const onRowClick = vi.fn();
      renderTable({ rows: [{ id: 1, name: 'Alice' }], onRowClick });
      const row = screen.getAllByRole('row')[1];

      row.focus();
      await user.keyboard('{Enter}');
      await user.keyboard(' ');

      expect(onRowClick).toHaveBeenCalledTimes(2);
      expect(row).toHaveAttribute('tabindex', '0');
    });

    it('does not call onRowClick when the click starts on an interactive control inside the row', async () => {
      const user = userEvent.setup();
      const onRowClick = vi.fn();
      renderTable({ rows: [{ id: 1, name: 'Alice' }], onRowClick });

      await user.click(screen.getByRole('button', { name: 'Row action' }));

      expect(onRowClick).not.toHaveBeenCalled();
    });

    it('renders a chevron hint column only when onRowClick is set', () => {
      const { rerender } = renderTable({ rows: [{ id: 1, name: 'Alice' }] });
      expect(document.querySelector('.lucide-chevron-right')).toBeNull();

      rerender(<DataTable columns={columns} rows={[{ id: 1, name: 'Alice' }]} rowKey={(row) => row.id} onRowClick={() => {}} />);
      expect(document.querySelector('.lucide-chevron-right')).not.toBeNull();
    });

    it('applies semantic row emphasis to every cell without replacing the row content', () => {
      renderTable({
        rows: [{ id: 1, name: 'Denied' }],
        getRowClassName: () => 'audit-row-denied',
      });

      const row = screen.getAllByRole('row')[1];
      expect(row.querySelectorAll('.audit-row-denied')).toHaveLength(3);
      expect(screen.getByText('Denied')).toBeInTheDocument();
    });
  });
});
