import * as React from "react"
import { type VariantProps } from "class-variance-authority"
import { cn } from "../styles/classNames"
import { inputVariants } from "./input-variants"

interface InputProps extends Omit<React.ComponentProps<"input">, "size">, VariantProps<typeof inputVariants> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, type, size, ...props }, ref) => {
  return (
    <input
      ref={ref}
      type={type}
      data-slot="input"
      className={cn(inputVariants({ size, className }))}
      {...props}
    />
  )
})
Input.displayName = "Input"

export { Input }
export type { InputProps }
