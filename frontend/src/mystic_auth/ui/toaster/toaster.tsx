import { createPortal } from "react-dom";
import { useSyncExternalStore } from "react";
import { CircleCheckIcon, InfoIcon, Loader2Icon, OctagonXIcon, TriangleAlertIcon, XIcon } from "lucide-react";

import { getToasts, markToastInteraction, subscribeToasts, toaster, type AppToast } from "./toasterInstance";

const icons = { success: CircleCheckIcon, error: OctagonXIcon, warning: TriangleAlertIcon, info: InfoIcon, loading: Loader2Icon };
const toastStyles = { success: "app-toast-success", error: "app-toast-error", warning: "app-toast-warning", info: "app-toast-info", loading: "app-toast-loading" };

function Toast({ toast }: { toast: AppToast }) {
  const type = toast.type ?? "success";
  const Icon = icons[type];
  return (
    <div className={`app-toast ${toastStyles[type]} ${toast.exiting ? "app-toast-exiting" : ""}`} role={type === "error" ? "alert" : "status"} aria-live={type === "error" ? "assertive" : "polite"}>
      <Icon className={`app-toast-icon ${type === "loading" ? "app-toast-spinner" : ""}`} aria-hidden="true" />
      <div className="app-toast-content">
        <div className="app-toast-title">{toast.title}</div>
        {toast.description !== undefined && <div className="app-toast-description">{toast.description}</div>}
      </div>
      {toast.action && (
        <button type="button" className="app-toast-action !bg-transparent !text-inherit" onClick={(event) => {
          event.stopPropagation();
          markToastInteraction();
          toaster.beginAction(toast.id);
          toast.action?.onClick();
        }}>{toast.action.label}</button>
      )}
      <button type="button" className="app-toast-close" aria-label="Dismiss notification" onClick={() => toaster.dismiss(toast.id)}>
        <XIcon aria-hidden="true" />
      </button>
    </div>
  );
}

/** CSP-safe toast renderer. All styling is shipped in the app stylesheet; no
 * runtime <style> injection or third-party inline CSS is required. */
export const Toaster = () => {
  const toastList = useSyncExternalStore(subscribeToasts, getToasts, getToasts);
  // aria-live on the portal root is intentional: Radix Dialog's modal
  // isolation preserves live regions while hiding the rest of the page.
  // Without it, an open dialog marks this global portal aria-hidden and
  // makes visible Undo actions inaccessible to assistive technology.
  return createPortal(
    <div className="app-toaster" role="region" aria-label="Notifications" aria-live="polite">
      {toastList.map((toast) => <Toast key={toast.id} toast={toast} />)}
    </div>,
    document.body,
  );
};
