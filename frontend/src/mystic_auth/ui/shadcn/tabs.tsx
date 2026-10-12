"use client"

import * as React from "react"
import { type VariantProps } from "class-variance-authority"
import { cn } from "@/ui/styles/classNames"
import { Tabs as TabsPrimitive } from "radix-ui"
import { tabsListVariants } from "./tabs-variants"

function Tabs({
  className,
  orientation = "horizontal",
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      data-orientation={orientation}
      orientation={orientation}
      className={cn(
        "group/tabs flex gap-2 data-[orientation=horizontal]:flex-col",
        className
      )}
      {...props}
    />
  )
}

function TabsList({
  className,
  variant = "default",
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List> &
  VariantProps<typeof tabsListVariants>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      data-variant={variant}
      className={cn(tabsListVariants({ variant }), className)}
      {...props}
    />
  )
}

function TabsTrigger({
  className,
  tone = "default",
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger> & {
  /** Line-variant only: "destructive" recolors hover/active text and the
   * active underline red instead of brand (AccountSettingsPage's Danger
   * Zone tab). Mutually-exclusive data-[tone=...] selectors below, so
   * default and destructive styling never both match at once - no
   * specificity/order fight between them, just each vs. the plain
   * data-[state=active]:text-foreground/hover:text-foreground base
   * (still needs !important, see the comment below). */
  tone?: "default" | "destructive"
}) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      data-tone={tone}
      className={cn(
        // cursor-pointer: native <button> defaults to cursor:default, not a
        // hand pointer (Button.tsx sets this explicitly for the same
        // reason; TabsTrigger never did).
        // Keep focus accessible through the ring/outline, but never animate
        // the trigger's transparent border into a light visible edge when a
        // pointer click changes tabs. The UserAccessDialog uses the same
        // focus treatment without a border flash; shared TabsTrigger must do
        // the same for Account Settings, Audit Log, and other tab strips.
        "relative inline-flex h-[calc(100%-1px)] flex-1 items-center justify-center gap-1.5 rounded-md border border-transparent px-2 py-1 text-sm font-medium whitespace-nowrap text-foreground/60 transition-all cursor-pointer group-data-[orientation=vertical]/tabs:w-full group-data-[orientation=vertical]/tabs:justify-start hover:text-foreground focus-visible:!border-transparent focus-visible:ring-0 focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-[-2px] disabled:pointer-events-none disabled:opacity-50 group-data-[variant=default]/tabs-list:data-[state=active]:shadow-sm group-data-[variant=line]/tabs-list:data-[state=active]:shadow-none dark:text-muted-foreground dark:hover:text-foreground [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        "group-data-[variant=line]/tabs-list:bg-transparent group-data-[variant=line]/tabs-list:data-[state=active]:bg-transparent dark:group-data-[variant=line]/tabs-list:data-[state=active]:border-transparent dark:group-data-[variant=line]/tabs-list:data-[state=active]:bg-transparent",
        // The base rounded-md above curls the active trigger's visible
        // border-bottom up at each end (bracket-like serifs) instead of a
        // clean straight line, since a "line" variant tab never shows a
        // filled/bordered background - only its bottom edge is ever drawn.
        "group-data-[variant=line]/tabs-list:rounded-b-none",
        // flex-1 (below) is right for the "default" pill variant and for
        // any vertical tab list (group-data-[orientation=vertical]/tabs:w-full
        // needs it to actually stretch), but every "line" variant list in
        // this app is horizontal and shrink-to-fit (TabsList's w-fit) - in
        // that container flex-1's flex-basis:0 hands each trigger an equal
        // share of the list's width regardless of its label length, so
        // "Legal" got padded out as wide as "Permissions" instead of sizing
        // to its own text. flex-none restores content-sized tabs there.
        "group-data-[variant=line]/tabs-list:flex-none",
        "data-[state=active]:bg-background data-[state=active]:text-foreground dark:data-[state=active]:border-input dark:data-[state=active]:bg-input/30 dark:data-[state=active]:text-foreground",
        // Brand/red tint on hover and the active line-variant tab, matching
        // the rest of the app's active-state color (see .project/design.md:
        // brand color is the product's identity, applies to active states
        // everywhere) - "destructive" tone (Danger Zone) gets red instead,
        // both on hover and once selected, so it never looks like a normal
        // tab. ! (important) throughout because these and the plain
        // hover:text-foreground/data-[state=active]:text-foreground above
        // have different modifier chains, so Tailwind doesn't treat them as
        // the same override target and won't dedupe them - which one wins
        // in the generated stylesheet isn't guaranteed by source order
        // here, so force every one of these explicitly.
        "group-data-[variant=line]/tabs-list:data-[tone=default]:hover:!text-[var(--brand-600)] dark:group-data-[variant=line]/tabs-list:data-[tone=default]:hover:!text-brand-fg",
        "group-data-[variant=line]/tabs-list:data-[tone=default]:data-[state=active]:!text-[var(--brand-700)] dark:group-data-[variant=line]/tabs-list:data-[tone=default]:data-[state=active]:!text-brand-fg",
        "group-data-[variant=line]/tabs-list:data-[tone=destructive]:hover:!text-red-500 dark:group-data-[variant=line]/tabs-list:data-[tone=destructive]:hover:!text-red-300",
        "group-data-[variant=line]/tabs-list:data-[tone=destructive]:data-[state=active]:!text-red-500 dark:group-data-[variant=line]/tabs-list:data-[tone=destructive]:data-[state=active]:!text-red-300",
        // Vertical/default-variant indicator only now (kept for a future
        // vertical or pill-style tab list, neither used today): an ::after
        // bar offset from the trigger's own box. The horizontal "line"
        // variant used to reuse this same offset ::after approach, but its
        // -5px/-bottom offset floated the bar below the trigger's own box
        // instead of sharing an edge with it, which (a) got clipped
        // entirely inside AccountSettingsPage's overflow-y-hidden TabsList
        // (barely 1-2px of room below the trigger there) and (b) even
        // where visible, never quite lined up with tabs-variants.ts's line
        // baseline (a 1px border-b on TabsList itself), reading as two
        // separate parallel lines instead of one. Replaced below with a
        // border-bottom directly on the trigger, which by construction
        // shares the exact same edge as its neighbors and as any border on
        // an ancestor - no offset math, no clipping risk.
        "after:absolute after:bg-foreground after:opacity-0 after:transition-opacity group-data-[orientation=horizontal]/tabs:after:inset-x-0 group-data-[orientation=horizontal]/tabs:after:bottom-[-5px] group-data-[orientation=horizontal]/tabs:after:h-0.5 group-data-[orientation=vertical]/tabs:after:inset-y-0 group-data-[orientation=vertical]/tabs:after:-right-1 group-data-[orientation=vertical]/tabs:after:w-0.5",
        // Line-variant horizontal indicator: the baseline itself lives on
        // TabsList (tabs-variants.ts), one continuous border-b under the
        // whole strip - putting it on each trigger instead (so the active
        // one's border could just "grow" in place) broke it into segments
        // with a visible gap between every tab. Only the active trigger
        // gets its own border-bottom here, 2px and colored, sitting flush
        // on top of that same baseline (tabs-variants.ts's pb-0 removes
        // the gap that would otherwise float it above/below by the
        // container's padding). ! (important): border utilities split by
        // side (border-b-*) vs. the all-sides `border border-transparent`
        // above aren't deduped by Tailwind either.
        "group-data-[variant=line]/tabs-list:data-[state=active]:!border-b-2",
        "group-data-[variant=line]/tabs-list:data-[tone=default]:data-[state=active]:!border-b-[var(--brand-600)] dark:group-data-[variant=line]/tabs-list:data-[tone=default]:data-[state=active]:!border-b-[var(--brand-400)]",
        "group-data-[variant=line]/tabs-list:data-[tone=destructive]:data-[state=active]:!border-b-red-500 dark:group-data-[variant=line]/tabs-list:data-[tone=destructive]:data-[state=active]:!border-b-red-300",
        className
      )}
      {...props}
    />
  )
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("flex-1 outline-none", className)}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent }
