"use client";

import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-all duration-150 disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon/60 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-950 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-neon text-ink-950 hover:bg-neon-300 active:bg-neon-400 shadow-[0_10px_30px_-18px_rgba(157,255,0,0.8)]",
        secondary: "border border-white/10 bg-white/[0.04] text-chalk-100 hover:bg-white/[0.08]",
        ghost: "text-chalk-300 hover:bg-white/[0.05] hover:text-chalk-100",
        outline: "border border-neon/30 text-neon hover:bg-neon/10",
        danger: "bg-signal-danger/15 text-signal-danger border border-signal-danger/30 hover:bg-signal-danger/25",
        subtle: "bg-ink-700 text-chalk-100 hover:bg-ink-600",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-4",
        lg: "h-12 px-6 text-[15px]",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  },
);
Button.displayName = "Button";

export { buttonVariants };
