import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-control text-sm font-medium ring-offset-[var(--medaid-bg)] transition-colors duration-150 ease-standard focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--medaid-accent)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-brand text-brand-contrast hover:bg-brand-hover",
        destructive: "bg-[var(--risk-emergency-solid)] text-white hover:brightness-110",
        outline: "border border-[var(--medaid-border)] bg-[var(--medaid-surface)] text-[var(--medaid-ink-soft)] hover:bg-[var(--medaid-surface-muted)]",
        secondary: "bg-[var(--medaid-surface-muted)] text-[var(--medaid-ink)] hover:bg-[var(--medaid-border)]",
        ghost: "text-[var(--medaid-ink-soft)] hover:bg-[var(--medaid-surface-muted)] hover:text-[var(--medaid-ink)]",
        link: "text-[var(--medaid-accent-strong)] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-control px-3",
        lg: "h-11 rounded-control px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
