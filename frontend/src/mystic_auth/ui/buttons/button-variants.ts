import { cva } from "class-variance-authority"

// Split out of Button.tsx so that file only exports components
// (react-refresh/only-export-components: co-exporting a non-component const
// from a component file breaks Fast Refresh for that file).
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-md font-semibold whitespace-nowrap transition-all outline-none cursor-pointer focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4 duration-[var(--duration-hover)] ease-[var(--easing-hover)] active:translate-y-px",
  {
    variants: {
      variant: {
        // Default brand solid CTA. brand.800 hover (not the stock 90%
        // opacity darken): see BRAND_SOLID_HOVER_PROPS in the old
        // This shared variant file owns the hover treatment.
        brand: "border border-transparent bg-brand-solid text-brand-contrast shadow-[0_1px_2px_rgba(15,23,42,0.12),0_10px_18px_-14px_var(--brand-solid)] hover:bg-[var(--brand-800)] hover:shadow-[0_1px_2px_rgba(15,23,42,0.14),0_14px_24px_-16px_var(--brand-solid)]",
        // Plain neutral outline (no brand tint) - signup/reset "back"
        // style CTAs that used variant="outline" with no colorPalette.
        outline:
          "border border-border-strong bg-bg-surface shadow-xs hover:border-brand-border hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:hover:bg-input/50",
        ghost: "hover:bg-accent hover:text-accent-foreground dark:hover:bg-accent/50",
        // Brand-tinted outline secondary action. See old
        // BRAND_OUTLINE_HOVER_PROPS: fills solid on hover, not just a
        // lightened tint, or the hover state read as barely different.
        "brand-outline":
          "border text-brand-fg border-brand-border bg-transparent hover:bg-[var(--brand-600)] hover:border-[var(--brand-600)] hover:text-white",
        // Same "fills solid, don't just lighten" fix as brand-outline, for
        // destructive solid actions (ConfirmDialog's confirm button).
        destructive: "bg-[var(--red-500)] text-white hover:bg-[var(--red-700)]",
        // Destructive outline (e.g. ActionChipGroup's off-state destructive
        // chips). Transparent at rest, solid red only on hover.
        "destructive-outline":
          "border text-fg-error border-[var(--red-400)] bg-transparent hover:bg-[var(--red-500)] hover:border-[var(--red-500)] hover:text-white dark:border-[var(--red-400)] dark:hover:bg-[var(--red-600)] dark:hover:border-[var(--red-600)]",
        // Non-destructive counterpart to destructive-outline: same .400
        // border weight, for outline controls that need equal visual
        // weight next to a destructive one beside them.
        "brand-tinted-outline":
          "border text-brand-fg border-[var(--brand-400)] bg-transparent hover:bg-[var(--brand-600)] hover:border-[var(--brand-600)] hover:text-white dark:border-[var(--brand-400)] dark:hover:bg-[var(--brand-700)] dark:hover:border-[var(--brand-700)]",
        // Dialog secondary actions (Cancel/Close) and filter-bar
        // secondary buttons. Light gray fill with a border at rest, one
        // step darker on hover - no heavy solid fill. Dark mode uses its
        // own step (gray-700 -> gray-800, not gray-600) since the shared
        // gray scale isn't redefined per-theme and gray-600 would read
        // lighter than gray-700 against a dark surface.
        secondary:
          "border border-border-strong bg-bg-surface text-fg-default shadow-xs hover:bg-bg-card-head hover:border-[var(--gray-500)] dark:bg-[var(--gray-800)] dark:text-fg-default dark:hover:bg-[var(--gray-700)] dark:hover:border-[var(--gray-500)]",
        // Navbar/ControlCluster icon-only controls (FontSizeControl,
        // LanguageToggle, ThemeToggle) plus the command-palette trigger.
        icon: "border border-border-strong bg-bg-canvas text-fg-default hover:border-[var(--brand-500)] hover:bg-[var(--brand-100)] hover:text-[var(--brand-700)] dark:hover:border-[var(--brand-400)] dark:hover:bg-[color-mix(in_srgb,var(--brand-solid)_16%,transparent)] dark:hover:text-brand-fg",
        // Small brand-tinted inline actions (UserPoliciesDialog's
        // "Expand all"/"Collapse all").
        "brand-subtle":
          "border border-[var(--brand-500)] bg-[var(--brand-200)] text-[var(--brand-800)] hover:bg-[var(--brand-300)] hover:border-[var(--brand-600)] dark:border-[var(--brand-600)] dark:bg-[var(--brand-800)] dark:text-[var(--brand-100)] dark:hover:bg-[var(--brand-900)] dark:hover:border-[var(--brand-700)]",
        // Dialog close-trigger (the X in a dialog corner).
        "close-trigger":
          "border border-[var(--gray-500)] bg-[var(--gray-200)] text-[var(--gray-700)] rounded-md hover:bg-[var(--gray-600)] hover:border-[var(--gray-700)] hover:text-white dark:text-[var(--gray-100)] dark:border-[var(--gray-500)] dark:bg-[var(--gray-700)] dark:hover:bg-[var(--gray-300)] dark:hover:border-[var(--gray-300)] dark:hover:text-[var(--gray-900)]",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        "2xs": "h-6 gap-1 rounded-md px-1.5 text-xs has-[>svg]:px-1 [&_svg:not([class*='size-'])]:size-3",
        xs: "h-7 gap-1 rounded-md px-2 text-xs has-[>svg]:px-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 gap-1.5 rounded-md px-3 text-sm has-[>svg]:px-2.5",
        md: "h-9 px-4 py-2 text-sm has-[>svg]:px-3",
        lg: "h-11 rounded-md px-6 text-base has-[>svg]:px-5",
        "icon-xs": "size-6 rounded-md [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-8 rounded-md",
        icon: "size-9 rounded-md",
      },
    },
    defaultVariants: {
      variant: "brand",
      size: "md",
    },
  }
)

export { buttonVariants }
