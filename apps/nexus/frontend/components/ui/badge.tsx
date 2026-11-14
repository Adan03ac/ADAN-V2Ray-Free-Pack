import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium leading-5",
  {
    variants: {
      tone: {
        neutral: "border-white/10 bg-white/[0.04] text-chalk-300",
        neon: "border-neon/25 bg-neon/10 text-neon",
        violet: "border-violet/30 bg-violet/10 text-violet-400",
        success: "border-signal-success/25 bg-signal-success/10 text-signal-success",
        warning: "border-signal-warning/25 bg-signal-warning/10 text-signal-warning",
        danger: "border-signal-danger/25 bg-signal-danger/10 text-signal-danger",
        info: "border-signal-info/25 bg-signal-info/10 text-signal-info",
        muted: "border-transparent bg-white/[0.03] text-chalk-500",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export { badgeVariants };
