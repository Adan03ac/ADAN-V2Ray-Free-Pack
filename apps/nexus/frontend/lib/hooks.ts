"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { AuthMe } from "@/lib/types";

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<AuthMe>("/auth/me"),
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useIsAdmin() {
  const me = useMe();
  return me.data?.user.role === "admin";
}

export function useDebounced<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
