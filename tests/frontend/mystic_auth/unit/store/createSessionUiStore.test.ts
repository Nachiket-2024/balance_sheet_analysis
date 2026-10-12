import { describe, it, expect } from 'vitest';

import { createSessionUiStore, resetAllSessionUiStores } from '@/store/createSessionUiStore';

describe('createSessionUiStore', () => {
  it('starts at the given initial values', () => {
    const useStore = createSessionUiStore({ tab: 'profile', count: 0 });

    expect(useStore.getState().tab).toBe('profile');
    expect(useStore.getState().count).toBe(0);
  });

  it('update() merges a partial patch without touching other fields', () => {
    const useStore = createSessionUiStore({ tab: 'profile', count: 0 });

    useStore.getState().update({ tab: 'appearance' });

    expect(useStore.getState().tab).toBe('appearance');
    expect(useStore.getState().count).toBe(0);
  });

  it('survives being read again later (module-singleton semantics, not per-render state)', () => {
    const useStore = createSessionUiStore({ tab: 'profile' });
    useStore.getState().update({ tab: 'danger' });

    // A fresh call to getState() (standing in for a page component
    // remounting after in-app navigation away and back) still sees the
    // updated value, unlike a component's own useState which would have
    // reset to the initializer on remount.
    expect(useStore.getState().tab).toBe('danger');
  });

  it('resetAllSessionUiStores() restores every created store to its own initial values', () => {
    const storeA = createSessionUiStore({ tab: 'profile' });
    const storeB = createSessionUiStore({ scope: 'mine' });
    storeA.getState().update({ tab: 'danger' });
    storeB.getState().update({ scope: 'all' });

    resetAllSessionUiStores();

    expect(storeA.getState().tab).toBe('profile');
    expect(storeB.getState().scope).toBe('mine');
  });

  it('resetAllSessionUiStores() keeps update() itself intact (merge, not replace)', () => {
    const useStore = createSessionUiStore({ tab: 'profile' });

    resetAllSessionUiStores();

    expect(typeof useStore.getState().update).toBe('function');
    useStore.getState().update({ tab: 'password' });
    expect(useStore.getState().tab).toBe('password');
  });
});
