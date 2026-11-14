import * as React from "react";

import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        "h-10 w-full rounded-xl border border-white/[0.08] bg-ink-950/60 px-3 text-sm text-chalk-100 placeholder:text-chalk-500 transition-colors focus-visible:border-neon/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon/20 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "min-h-[84px] w-full rounded-xl border border-white/[0.08] bg-ink-950/60 px-3 py-2 text-sm text-chalk-100 placeholder:text-chalk-500 transition-colors focus-visible:border-neon/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon/20",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

export function Select({ className, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-10 w-full appearance-none rounded-xl border border-white/[0.08] bg-ink-950/60 px-3 text-sm text-chalk-100 transition-colors focus-visible:border-neon/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon/20",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}
