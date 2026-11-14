"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  className,
  children,
  side = "center",
}: {
  className?: string;
  children: React.ReactNode;
  side?: "center" | "right";
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink-950/80 backdrop-blur-sm data-[state=closed]:animate-out data-[state=open]:animate-in" />
      <DialogPrimitive.Content
        className={cn(
          "fixed z-50 border border-white/[0.07] bg-ink-850 shadow-[0_40px_120px_-40px_rgba(0,0,0,0.9)] focus:outline-none",
          side === "center" &&
            "left-1/2 top-1/2 w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-3xl p-6",
          side === "right" &&
            "inset-y-0 right-0 w-full max-w-xl overflow-y-auto rounded-l-3xl border-y-0 border-r-0 p-6",
          className,
        )}
      >
        {children}
        <DialogPrimitive.Close
          className="absolute end-4 top-4 rounded-lg p-1.5 text-chalk-500 transition-colors hover:bg-white/5 hover:text-chalk-100"
          aria-label="Close"
        >
          <X className="size-4" />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function DialogHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("mb-5 space-y-1 pe-8", className)}>{children}</div>;
}

export function DialogTitle({ children }: { children: React.ReactNode }) {
  return <DialogPrimitive.Title className="text-lg font-medium text-chalk-100">{children}</DialogPrimitive.Title>;
}

export function DialogDescription({ children }: { children: React.ReactNode }) {
  return <DialogPrimitive.Description className="text-xs text-chalk-500">{children}</DialogPrimitive.Description>;
}
