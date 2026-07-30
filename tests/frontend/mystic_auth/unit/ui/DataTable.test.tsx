import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';

import DataTable, { type DataTableColumn } from '@/ui/DataTable';

interface Row {
  id: number;
  name: string;
}

const columns: DataTableColumn<Row>[] = [
  { key: 'id', header: 'ID', render: (row) => row.id },
  { key: 'name', header: 'Name', render: (row) => row.name },
];

function renderTable(props: Partial<React.ComponentProps<typeof DataTable<Row>>> = {}) {
  return render(
    <ChakraProvider value={defaultSystem}>
      <DataTable columns={columns} rows={[]} rowKey={(row) => row.id} {...props} />
    </ChakraProvider>
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

  it('renders one row per item, using rowKey and each column render function', () => {
    renderTable({ rows: [{ id: 1, name: 'Alice' }, { id: 2, name: 'Bob' }] });

    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getAllByRole('row')).toHaveLength(3); // header + 2 rows
  });
});
