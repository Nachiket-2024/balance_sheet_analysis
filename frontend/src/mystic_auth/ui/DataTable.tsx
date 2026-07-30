import React from "react";
import { Skeleton, Table, EmptyState } from "@chakra-ui/react";

import FormAlert from "./FormAlert";

export interface DataTableColumn<T> {
    key: string;
    header: string;
    render: (row: T) => React.ReactNode;
    /** Right-aligns numeric/action columns. */
    align?: "start" | "center" | "end";
}

interface DataTableProps<T> {
    columns: DataTableColumn<T>[];
    rows: T[] | undefined;
    rowKey: (row: T) => string | number;
    isLoading?: boolean;
    isError?: boolean;
    errorMessage?: string;
    emptyMessage?: string;
    /** Rows of skeleton placeholders shown while isLoading, mirrors the
     * shape of the real table rather than swapping to a spinner, so the
     * layout doesn't jump once data arrives. */
    skeletonRowCount?: number;
}

/**
 * Generic table with a shared loading/error/empty treatment, so every admin
 * list page (Users, Policies, Audit Log) doesn't reimplement the same three
 * conditional branches around a bare Chakra Table.
 */
function DataTable<T>({
    columns,
    rows,
    rowKey,
    isLoading,
    isError,
    errorMessage = "Failed to load data",
    emptyMessage = "No data available",
    skeletonRowCount = 5,
}: DataTableProps<T>) {
    if (isLoading) {
        return (
            <Table.ScrollArea borderWidth="1px" borderColor="border.default" rounded="lg">
                <Table.Root size="sm">
                    <Table.Header>
                        <Table.Row>
                            {columns.map((col) => (
                                <Table.ColumnHeader key={col.key} textAlign={col.align}>
                                    {col.header}
                                </Table.ColumnHeader>
                            ))}
                        </Table.Row>
                    </Table.Header>
                    <Table.Body>
                        {Array.from({ length: skeletonRowCount }).map((_, rowIndex) => (
                            <Table.Row key={rowIndex}>
                                {columns.map((col) => (
                                    <Table.Cell key={col.key}>
                                        <Skeleton height="16px" />
                                    </Table.Cell>
                                ))}
                            </Table.Row>
                        ))}
                    </Table.Body>
                </Table.Root>
            </Table.ScrollArea>
        );
    }

    if (isError) {
        return <FormAlert status="error">{errorMessage}</FormAlert>;
    }

    if (!rows || rows.length === 0) {
        return (
            <EmptyState.Root size="sm">
                <EmptyState.Content>
                    <EmptyState.Title>{emptyMessage}</EmptyState.Title>
                </EmptyState.Content>
            </EmptyState.Root>
        );
    }

    return (
        <Table.ScrollArea borderWidth="1px" borderColor="border.default" rounded="lg">
            <Table.Root size="sm" striped>
                <Table.Header>
                    <Table.Row>
                        {columns.map((col) => (
                            <Table.ColumnHeader key={col.key} textAlign={col.align}>
                                {col.header}
                            </Table.ColumnHeader>
                        ))}
                    </Table.Row>
                </Table.Header>
                <Table.Body>
                    {rows.map((row) => (
                        <Table.Row key={rowKey(row)}>
                            {columns.map((col) => (
                                <Table.Cell key={col.key} textAlign={col.align}>
                                    {col.render(row)}
                                </Table.Cell>
                            ))}
                        </Table.Row>
                    ))}
                </Table.Body>
            </Table.Root>
        </Table.ScrollArea>
    );
}

export default DataTable;
