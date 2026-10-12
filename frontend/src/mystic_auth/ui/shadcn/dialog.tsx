import * as React from "react";
import { cn } from "@/ui/styles/classNames";
import { XIcon } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";

import { Button } from "@/ui/shadcn/button";
import { isToastInteractionActive } from "@/ui/toaster/toasterInstance";

let lastPointerDownElement: Element | null = null;
if (typeof document !== "undefined") {
  document.addEventListener("pointerdown", (event) => {
    if (event.target instanceof Element) lastPointerDownElement = event.target;
  }, true);
}

function focusableControl(element: Element | null | undefined): HTMLElement | null {
  if (!element) return null;
  const closest = element.closest<HTMLElement>("button,a,input,select,textarea,[tabindex]");
  return closest ?? element.querySelector<HTMLElement>("button,a,input,select,textarea,[tabindex]");
}

function Dialog({
  onOpenChange,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Root>) {
  return (
    <DialogPrimitive.Root
      data-slot="dialog"
      {...props}
      onOpenChange={(open) => {
        if (!open && isToastInteractionActive()) return;
        onOpenChange?.(open);
      }}
    />
  );
}

function DialogTrigger({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Trigger>) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />;
}

function DialogPortal({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Portal>) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />;
}

function DialogClose({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Close>) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />;
}

function DialogOverlay({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      data-slot="dialog-overlay"
      className={cn(
        "fixed inset-0 z-[1400] bg-black/45 backdrop-blur-[2px] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0",
        className,
      )}
      {...props}
    />
  );
}

function DialogContent({
  className,
  overlayClassName,
  children,
  showCloseButton = true,
  closeLabel = "Close",
  returnFocusElement,
  returnFocusFallback,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & {
  showCloseButton?: boolean;
  /** Extra classes for the backdrop, e.g. this app's blurred brand-tinted overlay (see ConfirmDialog). */
  overlayClassName?: string;
  /** Translated aria-label/sr-only text for the close button (this app's dialogs pass t("closeDialog")). */
  closeLabel?: string;
  /** Explicit trigger for controlled dialogs whose opening click is followed
   * by a state-driven render before Radix captures activeElement. */
  returnFocusElement?: HTMLElement | null;
  /** Resolves a replacement trigger when a query refresh replaced the node. */
  returnFocusFallback?: () => HTMLElement | null;
}) {
  const returnFocusRef = React.useRef<HTMLElement | null>(null);
  const handleOpenAutoFocus: React.ComponentProps<typeof DialogPrimitive.Content>["onOpenAutoFocus"] = (event) => {
    const activeElement = document.activeElement;
    if (activeElement instanceof HTMLElement) {
      // TooltipTrigger wraps icon buttons in a span. Depending on whether
      // the click landed on that wrapper or the button, activeElement can be
      // the non-focusable span. Keep the actual control as the return target.
      returnFocusRef.current = focusableControl(returnFocusElement)
        ?? focusableControl(activeElement)
        ?? (activeElement === document.body ? focusableControl(lastPointerDownElement) : activeElement);
    }
    props.onOpenAutoFocus?.(event);
  };
  const handleCloseAutoFocus: React.ComponentProps<typeof DialogPrimitive.Content>["onCloseAutoFocus"] = (event) => {
    props.onCloseAutoFocus?.(event);
    const returnFocusTarget = returnFocusRef.current?.isConnected
      ? returnFocusRef.current
      : returnFocusFallback?.();
    if (!event.defaultPrevented && returnFocusTarget?.isConnected) {
      event.preventDefault();
      returnFocusTarget.focus();
    }
  };
  const isToastInteraction = (target: EventTarget | null) =>
    target instanceof HTMLElement && !!target.closest(".app-toaster");
  const handlePointerDownOutside: React.ComponentProps<
    typeof DialogPrimitive.Content
  >["onPointerDownOutside"] = (event) => {
    if (isToastInteraction(event.target)) event.preventDefault();
    props.onPointerDownOutside?.(event);
  };
  const handleInteractOutside: React.ComponentProps<
    typeof DialogPrimitive.Content
  >["onInteractOutside"] = (event) => {
    if (isToastInteraction(event.target)) event.preventDefault();
    props.onInteractOutside?.(event);
  };

  return (
    <DialogPortal data-slot="dialog-portal">
      <DialogOverlay className={overlayClassName} />
      {/* Flexbox centering, not the old fixed top/left-50% + translate-[-50%]:
          that transform's -50% is computed against the content's own
          (often odd-numbered) rendered size, so it lands on a half-device-
          pixel offset more often than not - every edge but the one that
          happens to round "up" then renders as a blurred/missing hairline
          border, which a browser zoom (forcing a full re-rasterize at a
          different scale) can accidentally land back on a whole pixel and
          "fix". Centering via layout instead of a transform means the
          browser positions the box on a whole pixel to begin with, so
          borders render crisp on every edge at any zoom level. */}
      <div className="fixed inset-0 z-[1400] flex items-center justify-center p-3 sm:p-4">
        <DialogPrimitive.Content
          data-slot="dialog-content"
          className={cn(
            "relative grid w-full max-w-[calc(100vw-1.5rem)] max-h-[calc(100svh-1.5rem)] gap-0 overflow-auto rounded-card border border-brand-border bg-bg-canvas p-5 shadow-dialog ring-1 ring-black/5 duration-200 outline-none data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 dark:ring-white/5 sm:max-w-lg sm:p-6",
            className,
          )}
          {...props}
          onOpenAutoFocus={handleOpenAutoFocus}
          onCloseAutoFocus={handleCloseAutoFocus}
          onPointerDownOutside={handlePointerDownOutside}
          onInteractOutside={handleInteractOutside}
        >
          {children}
          {showCloseButton && (
            <DialogPrimitive.Close
              data-slot="dialog-close"
              aria-label={closeLabel}
              className="absolute top-3 right-3 z-20 inline-flex size-8 items-center justify-center rounded-md border border-border-strong bg-bg-surface text-fg-muted ring-offset-background transition-[background-color,border-color,color,box-shadow] hover:border-[var(--brand-500)] hover:bg-brand-tile-subtle hover:text-brand-fg hover:shadow-card-hover focus:ring-2 focus:ring-[var(--brand-500)] focus:ring-offset-2 focus:outline-hidden disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4"
            >
              <XIcon />
              <span className="sr-only">{closeLabel}</span>
            </DialogPrimitive.Close>
          )}
        </DialogPrimitive.Content>
      </div>
    </DialogPortal>
  );
}

function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-header"
      className={cn(
        "flex flex-col gap-2 text-center sm:text-left border-b border-brand-border pb-4",
        className,
      )}
      {...props}
    />
  );
}

function DialogFooter({
  className,
  showCloseButton = false,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  showCloseButton?: boolean;
}) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        "flex flex-col-reverse gap-2 sm:flex-row sm:justify-end",
        className,
      )}
      {...props}
    >
      {children}
      {showCloseButton && (
        <DialogPrimitive.Close asChild>
          <Button variant="outline">Close</Button>
        </DialogPrimitive.Close>
      )}
    </div>
  );
}

function DialogTitle({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn(
        "text-lg leading-tight font-semibold tracking-tight",
        className,
      )}
      {...props}
    />
  );
}

function DialogDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
};
