"use client";

import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { create } from "zustand";

import { cn } from "@/lib/utils";

type ToastTone = "success" | "error" | "info";

interface ToastItem {
  id: string;
  title: string;
  description?: string;
  tone: ToastTone;
}

interface ToastStore {
  items: ToastItem[];
  push: (item: Omit<ToastItem, "id">) => void;
  dismiss: (id: string) => void;
}

export const useToastStore = create<ToastStore>((set) => ({
  items: [],
  push: (item) => {
    const id = Math.random().toString(36).slice(2);
    set((state) => ({ items: [...state.items.slice(-3), { ...item, id }] }));
    setTimeout(() => {
      set((state) => ({ items: state.items.filter((entry) => entry.id !== id) }));
    }, 4800);
  },
  dismiss: (id) => set((state) => ({ items: state.items.filter((entry) => entry.id !== id) })),
}));

export function toast(tone: ToastTone, title: string, description?: string) {
  useToastStore.getState().push({ tone, title, description });
}

const toneStyles: Record<ToastTone, { icon: typeof Info; className: string }> = {
  success: { icon: CheckCircle2, className: "text-signal-success" },
  error: { icon: AlertTriangle, className: "text-signal-danger" },
  info: { icon: Info, className: "text-signal-info" },
};

export function Toaster() {
  const items = useToastStore((state) => state.items);
  const dismiss = useToastStore((state) => state.dismiss);

  return (
    <div className="pointer-events-none fixed bottom-4 end-4 z-[80] flex w-[min(92vw,360px)] flex-col gap-2">
      {items.map((item) => {
        const Icon = toneStyles[item.tone].icon;
        return (
          <div
            key={item.id}
            role="status"
            className="pointer-events-auto flex items-start gap-3 rounded-2xl border border-white/10 bg-ink-800/95 p-3.5 shadow-[0_24px_60px_-20px_rgba(0,0,0,0.9)] backdrop-blur animate-fade-up"
          >
            <Icon className={cn("mt-0.5 size-4", toneStyles[item.tone].className)} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-chalk-100">{item.title}</p>
              {item.description ? <p className="mt-0.5 text-xs text-chalk-500">{item.description}</p> : null}
            </div>
            <button
              type="button"
              onClick={() => dismiss(item.id)}
              className="rounded p-1 text-chalk-500 hover:text-chalk-100"
              aria-label="Dismiss"
            >
              <X className="size-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
