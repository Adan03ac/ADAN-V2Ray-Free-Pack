"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Toaster } from "@/components/ui/toast";
import { useUiStore } from "@/lib/store";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 20_000,
            retry: (failureCount, error) => {
              const status = (error as { status?: number }).status ?? 0;
              if (status === 401 || status === 403 || status === 404) return false;
              return failureCount < 2;
            },
            refetchOnWindowFocus: false,
          },
        },
      }),
  );
  const language = useUiStore((state) => state.language);

  useEffect(() => {
    const root = document.documentElement;
    root.lang = language;
    root.dir = language === "fa" ? "rtl" : "ltr";
  }, [language]);

  return (
    <QueryClientProvider client={client}>
      {children}
      <Toaster />
    </QueryClientProvider>
  );
}
