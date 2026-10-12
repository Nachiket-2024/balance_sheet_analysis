import * as React from "react"
import { type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"
import { cn } from "../styles/classNames"
import { Loader2 } from "lucide-react"
import { buttonVariants } from "./button-variants"

interface ButtonProps
  extends React.ComponentProps<"button">,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  loading?: boolean
}

function Button({ className, variant, size, asChild = false, loading = false, disabled, children, ...props }: ButtonProps) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      disabled={disabled || loading}
      {...props}
    >
      {asChild ? (
        children
      ) : (
        <>
          {loading ? <Loader2 className="animate-spin" /> : null}
          {children}
        </>
      )}
    </Comp>
  )
}

export { Button }
export type { ButtonProps }
