"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { api, ApiError } from "./api";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: api.me, retry: false, staleTime: 10 * 60_000 });
}

export function useLogout() {
  const qc = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: api.logout,
    onSettled: () => {
      qc.clear();
      router.replace("/login");
      toast.success("Signed out");
    },
  });
}

export function useStations() {
  return useQuery({ queryKey: ["stations"], queryFn: () => api.stations(), staleTime: 60 * 60_000 });
}

export function useCurrent() {
  return useQuery({ queryKey: ["current"], queryFn: api.current });
}

export function usePreferences(enabled = true) {
  return useQuery({ queryKey: ["preferences"], queryFn: api.preferences, enabled, retry: false });
}

export function useActiveModel() {
  return useQuery({ queryKey: ["model", "active"], queryFn: api.activeModel });
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.fieldMessage ?? e.message;
  return "Something went wrong.";
}
