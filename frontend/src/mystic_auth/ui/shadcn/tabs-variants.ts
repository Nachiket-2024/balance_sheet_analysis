import { cva } from "class-variance-authority"

// Split out of tabs.tsx so that file only exports components
// (react-refresh/only-export-components).
const tabsListVariants = cva(
  "group/tabs-list inline-flex w-fit items-center justify-center rounded-lg p-[3px] text-muted-foreground group-data-[orientation=horizontal]/tabs:h-9 group-data-[orientation=vertical]/tabs:h-fit group-data-[orientation=vertical]/tabs:flex-col data-[variant=line]:rounded-none",
  {
    variants: {
      variant: {
        default: "bg-muted",
        // One continuous baseline under the whole strip (horizontal only -
        // a vertical line list would want border-r instead, but nothing in
        // this app uses one yet). Tried putting this same border-b on each
        // TabsTrigger instead (so the active one's colored border-bottom
        // could just "grow" in place) - that broke the baseline into
        // disconnected segments with a visible gap between every tab
        // (each trigger is its own box, and TabsList's gap-5 sits between
        // them), which looked worse than the line-was-floating bug it
        // replaced. Baseline stays here, on the one continuous box;
        // TabsTrigger's active border-bottom (see tabs.tsx) overlays it.
        // pb-0 (overriding the shared p-[3px] above) is what makes that
        // overlay work: it puts every trigger's own bottom edge flush
        // against this same border, so the active trigger's thicker,
        // colored border-bottom sits exactly on this line instead of
        // floating above or below it by the padding amount.
        // border-strong (not border-card): border-card is a near-invisible
        // #dde1e8-on-white hairline in light mode - fine for a card edge
        // sitting next to whitespace, but too faint to read as a tab-strip
        // baseline that the active tab's border-bottom needs to visually
        // sit flush on top of. border-strong keeps solid contrast against
        // bg-surface in both modes.
        line: "gap-5 bg-transparent pb-0 group-data-[orientation=horizontal]/tabs:border-b group-data-[orientation=horizontal]/tabs:border-border-strong",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export { tabsListVariants }
