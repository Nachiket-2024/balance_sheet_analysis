import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';

import { useAuthStore } from '@/store/authStore';
import { Authorized } from '@/authorization/Authorized';
import { IfCan } from '@/authorization/IfCan';

const initialAuthState = useAuthStore.getState();

function seed(options?: { isAuthenticated?: boolean | null; permissions?: string[] }) {
  useAuthStore.setState(initialAuthState, true);
  if (options?.isAuthenticated !== undefined && options.isAuthenticated !== null) {
    useAuthStore.getState().setAuthenticated(options.isAuthenticated);
    if (options.isAuthenticated) {
      useAuthStore.getState().setProfile({
        name: 'Test User', email: 'test@example.com', role: 'user',
        permissions: options.permissions ?? [], has_password: true,
      });
    }
  }
}

function renderWithAuth(ui: ReactNode) {
  return render(ui);
}

describe('Authorized', () => {
  beforeEach(() => {
    seed();
  });

  it('renders children when the user has the permission', () => {
    seed({ isAuthenticated: true, permissions: ['users:read'] });
    renderWithAuth(
      <Authorized permission="users:read">
        <div>Secret Content</div>
      </Authorized>
    );

    expect(screen.getByText('Secret Content')).toBeInTheDocument();
  });

  it('renders null (no fallback given) when the user lacks the permission', () => {
    seed({ isAuthenticated: true, permissions: [] });
    const { container } = renderWithAuth(
      <Authorized permission="users:read">
        <div>Secret Content</div>
      </Authorized>
    );

    expect(screen.queryByText('Secret Content')).toBeNull();
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the fallback when the user lacks the permission and a fallback is given', () => {
    seed({ isAuthenticated: true, permissions: [] });
    renderWithAuth(
      <Authorized permission="users:read" fallback={<div>Access Denied</div>}>
        <div>Secret Content</div>
      </Authorized>
    );

    expect(screen.getByText('Access Denied')).toBeInTheDocument();
    expect(screen.queryByText('Secret Content')).toBeNull();
  });

  it('renders nothing at all while authentication status is still loading : not children, not fallback', () => {
    seed({ isAuthenticated: null });
    const { container } = renderWithAuth(
      <Authorized permission="users:read" fallback={<div>Access Denied</div>}>
        <div>Secret Content</div>
      </Authorized>
    );

    expect(screen.queryByText('Secret Content')).toBeNull();
    expect(screen.queryByText('Access Denied')).toBeNull();
    expect(container).toBeEmptyDOMElement();
  });

  it('respects the resourceType prop being passed through without changing the result', () => {
    seed({ isAuthenticated: true, permissions: ['documents:view'] });
    renderWithAuth(
      <Authorized permission="documents:view" resourceType="documents">
        <div>Secret Content</div>
      </Authorized>
    );

    expect(screen.getByText('Secret Content')).toBeInTheDocument();
  });
});

describe('IfCan', () => {
  beforeEach(() => {
    seed();
  });

  it('renders children when the action is allowed', () => {
    seed({ isAuthenticated: true, permissions: ['documents:view'] });
    renderWithAuth(
      <IfCan action="documents:view">
        <div>Document Viewer</div>
      </IfCan>
    );

    expect(screen.getByText('Document Viewer')).toBeInTheDocument();
  });

  it('renders fallback when the action is denied', () => {
    seed({ isAuthenticated: true, permissions: [] });
    renderWithAuth(
      <IfCan action="documents:view" fallback={<div>No Access</div>}>
        <div>Document Viewer</div>
      </IfCan>
    );

    expect(screen.getByText('No Access')).toBeInTheDocument();
    expect(screen.queryByText('Document Viewer')).toBeNull();
  });

  it('renders nothing while loading', () => {
    seed({ isAuthenticated: null });
    const { container } = renderWithAuth(
      <IfCan action="documents:view" fallback={<div>No Access</div>}>
        <div>Document Viewer</div>
      </IfCan>
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('accepts an optional resourceType prop', () => {
    seed({ isAuthenticated: true, permissions: ['documents:view'] });
    renderWithAuth(
      <IfCan action="documents:view" resourceType="documents">
        <div>Document Viewer</div>
      </IfCan>
    );

    expect(screen.getByText('Document Viewer')).toBeInTheDocument();
  });
});
