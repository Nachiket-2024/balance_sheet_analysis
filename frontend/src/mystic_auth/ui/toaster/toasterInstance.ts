import type React from "react";

export type ToastType = "success" | "error" | "warning" | "info" | "loading";
export interface ToastAction { label: string; onClick: () => void; }
export interface ToastOptions {
  title: React.ReactNode;
  description?: React.ReactNode;
  type?: ToastType;
  duration?: number;
  action?: ToastAction;
}
export interface AppToast extends ToastOptions { id: number; exiting?: boolean; }

type Listener = () => void;
let nextId = 1;
let toasts: AppToast[] = [];
const listeners = new Set<Listener>();
const timers = new Map<number, ReturnType<typeof setTimeout>>();
const exitTimers = new Map<number, ReturnType<typeof setTimeout>>();
const actionToastIds = new Set<number>();

function notify() { listeners.forEach((listener) => listener()); }
export function subscribeToasts(listener: Listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
export function getToasts() { return toasts; }

function clearTimer(id: number) {
  const timer = timers.get(id);
  if (timer !== undefined) { clearTimeout(timer); timers.delete(id); }
}
function dismissToast(id: number) {
  clearTimer(id);
  const existing = toasts.find((toast) => toast.id === id);
  if (!existing || existing.exiting) return;
  toasts = toasts.map((toast) => toast.id === id ? { ...toast, exiting: true } : toast);
  notify();
  exitTimers.set(id, setTimeout(() => {
    exitTimers.delete(id);
    toasts = toasts.filter((toast) => toast.id !== id);
    notify();
  }, 180));
}
function armAutoDismiss(id: number, duration: number | undefined) {
  if (duration === Infinity) return;
  const lifetime = duration ?? 5000;
  if (lifetime > 0) timers.set(id, setTimeout(() => dismissToast(id), lifetime));
}

export const toaster = {
  create(options: ToastOptions) {
    actionToastIds.forEach((toastId) => dismissToast(toastId));
    actionToastIds.clear();
    const id = nextId++;
    const toast: AppToast = { ...options, id, type: options.type ?? "success" };
    toasts = [...toasts, toast];
    notify();
    armAutoDismiss(id, toast.duration);
    return id;
  },
  beginAction(id: string | number) {
    const numericId = Number(id);
    const existing = toasts.find((toast) => toast.id === numericId);
    if (!existing) return;
    actionToastIds.add(numericId);
    toaster.update(numericId, {
      title: existing.title,
      description: existing.description,
      type: "loading",
      duration: 15000,
      action: undefined,
    });
  },
  update(id: string | number, options: ToastOptions) {
    const numericId = Number(id);
    const existing = toasts.find((toast) => toast.id === numericId);
    if (!existing) return numericId;
    clearTimer(numericId);
    const updated: AppToast = { ...existing, ...options, id: numericId, type: options.type ?? "success" };
    toasts = toasts.map((toast) => (toast.id === numericId ? updated : toast));
    notify();
    armAutoDismiss(numericId, updated.duration);
    return numericId;
  },
  dismiss(id?: string | number) {
    if (id === undefined) {
      timers.forEach((_timer, toastId) => clearTimer(toastId));
      exitTimers.forEach((timer) => clearTimeout(timer));
      exitTimers.clear();
      if (toasts.length > 0) {
        toasts = toasts.map((toast) => ({ ...toast, exiting: true }));
        notify();
        toasts.forEach((toast) => {
          exitTimers.set(toast.id, setTimeout(() => {
            exitTimers.delete(toast.id);
            toasts = toasts.filter((current) => current.id !== toast.id);
            notify();
          }, 180));
        });
      }
      return;
    }
    actionToastIds.delete(Number(id));
    dismissToast(Number(id));
  },
  remove(id?: string | number) { this.dismiss(id); },
};

let toastInteractionUntil = 0;
export function markToastInteraction() { toastInteractionUntil = Date.now() + 1000; }
export function isToastInteractionActive() { return Date.now() < toastInteractionUntil; }
