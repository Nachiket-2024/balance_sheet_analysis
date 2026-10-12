import * as React from "react"
import { cn } from "@/ui/styles/classNames"
import { XIcon } from "lucide-react"
import { Dialog as SheetPrimitive } from "radix-ui"

/** Right-edge sliding panel, built on the same Radix Dialog primitive as
 * dialog.tsx (a modal with its own focus trap/Escape handling/overlay) but
 * positioned and animated as a fixed-width strip pinned to the viewport's
 * right edge instead of centered - the shape the Audit Log's event-details
 * drawer needs (design/audit-log.html's "Right-side drawer opened by row
 * click"). Kept as its own file rather than a variant prop on Dialog: the
 * two share no className, and forcing one component to branch between
 * "centered card" and "edge panel" layouts would make Dialog.tsx harder to
 * read for its far more common callers. */
function Sheet({
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Root>) {
  return <SheetPrimitive.Root data-slot="sheet" {...props} />
}

function SheetPortal({
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Portal>) {
  return <SheetPrimitive.Portal data-slot="sheet-portal" {...props} />
}

function SheetOverlay({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Overlay>) {
  return (
    <SheetPrimitive.Overlay
      data-slot="sheet-overlay"
      className={cn(
        "fixed inset-0 z-[1400] bg-black/50 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0",
        className
      )}
      {...props}
    />
  )
}

function SheetContent({
  className,
  children,
  showCloseButton = true,
  closeLabel = "Close",
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Content> & {
  showCloseButton?: boolean
  closeLabel?: string
}) {
  const returnFocusRef = React.useRef<HTMLElement | null>(null);
  const handleOpenAutoFocus: React.ComponentProps<typeof SheetPrimitive.Content>["onOpenAutoFocus"] = (event) => {
    const activeElement = document.activeElement;
    if (activeElement instanceof HTMLElement) returnFocusRef.current = activeElement;
    props.onOpenAutoFocus?.(event);
  };
  const handleCloseAutoFocus: React.ComponentProps<typeof SheetPrimitive.Content>["onCloseAutoFocus"] = (event) => {
    props.onCloseAutoFocus?.(event);
    if (!event.defaultPrevented && returnFocusRef.current?.isConnected) {
      event.preventDefault();
      returnFocusRef.current.focus();
    }
  };
  return (
    <SheetPortal>
      <SheetOverlay />
      <SheetPrimitive.Content
        data-slot="sheet-content"
        className={cn(
          "fixed inset-y-0 right-0 z-[1400] flex h-full w-full max-w-[calc(100vw-0.75rem)] flex-col gap-0 overflow-hidden border-l border-brand-border bg-bg-canvas shadow-dialog outline-none sm:max-w-xl md:max-w-2xl lg:max-w-3xl",
          "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right data-[state=open]:duration-300 data-[state=closed]:duration-200",
          className
        )}
        {...props}
        onOpenAutoFocus={handleOpenAutoFocus}
        onCloseAutoFocus={handleCloseAutoFocus}
      >
        {children}
        {showCloseButton && (
          <SheetPrimitive.Close
            data-slot="sheet-close"
            aria-label={closeLabel}
            className="absolute top-4 right-4 rounded-xs opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:outline-hidden disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4"
          >
            <XIcon />
            <span className="sr-only">{closeLabel}</span>
          </SheetPrimitive.Close>
        )}
      </SheetPrimitive.Content>
    </SheetPortal>
  )
}

function SheetHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-header"
      className={cn("flex flex-col gap-1 border-b border-brand-border px-6 py-4 bg-bg-canvas", className)}
      {...props}
    />
  )
}

function SheetTitle({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Title>) {
  return (
    <SheetPrimitive.Title
      data-slot="sheet-title"
      className={cn("text-lg font-semibold pr-8", className)}
      {...props}
    />
  )
}

function SheetDescription({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Description>) {
  return (
    <SheetPrimitive.Description
      data-slot="sheet-description"
      className={cn("text-sm text-fg-muted", className)}
      {...props}
    />
  )
}

export { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle }
