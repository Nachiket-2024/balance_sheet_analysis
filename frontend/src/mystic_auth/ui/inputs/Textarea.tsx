import * as React from "react"
import { cn } from "../styles/classNames"

// Same border/hover/focus treatment as ui/inputs/Input.tsx so a form mixing
// both reads as one consistent field style.
const Textarea = React.forwardRef<HTMLTextAreaElement, React.ComponentProps<"textarea">>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        data-slot="textarea"
        className={cn(
          "flex field-sizing-content min-h-16 w-full rounded-md border border-border-strong bg-bg-surface px-3 py-2 text-base shadow-xs transition-colors outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50 md:text-sm hover:border-[var(--brand-500)] hover:bg-[var(--brand-100)] dark:hover:border-[var(--brand-400)] dark:hover:bg-[color-mix(in_srgb,var(--brand-solid)_16%,transparent)] focus-visible:border-brand-solid focus-visible:ring-[1px] focus-visible:ring-brand-solid aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40",
          className
        )}
        {...props}
      />
    )
  }
)
Textarea.displayName = "Textarea"

export { Textarea }
