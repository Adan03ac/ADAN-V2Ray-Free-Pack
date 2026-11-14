"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Language } from "@/lib/i18n";

type Range = 7 | 30 | 90;

interface UiState {
  language: Language;
  range: Range;
  sidebarOpen: boolean;
  setLanguage: (language: Language) => void;
  setRange: (range: Range) => void;
  setSidebarOpen: (open: boolean) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      language: "en",
      range: 7,
      sidebarOpen: false,
      setLanguage: (language) => set({ language }),
      setRange: (range) => set({ range }),
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
    }),
    { name: "nexus-ui", partialize: (state) => ({ language: state.language, range: state.range }) },
  ),
);
