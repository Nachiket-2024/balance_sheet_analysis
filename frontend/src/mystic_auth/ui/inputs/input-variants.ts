import { cva } from "class-variance-authority"

// Split out of Input.tsx so that file only exports components
// (react-refresh/only-export-components).
const inputVariants = cva(
  "flex w-full min-w-0 rounded-md border border-border-strong bg-bg-surface px-3 text-base shadow-xs transition-colors outline-none selection:bg-primary selection:text-primary-foreground file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm hover:border-[var(--brand-500)] hover:bg-[var(--brand-100)] dark:hover:border-[var(--brand-400)] dark:hover:bg-[color-mix(in_srgb,var(--brand-solid)_16%,transparent)] focus-visible:border-brand-solid focus-visible:ring-[1px] focus-visible:ring-brand-solid aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40",
  {
    variants: {
      size: {
        sm: "h-8 py-1",
        md: "h-9 py-1",
        lg: "h-11 py-2 text-base",
      },
    },
    defaultVariants: {
      size: "md",
    },
  }
)

export { inputVariants }
