"use client";

import useSWR from "swr";

export type KnowledgeDocument = {
  id: string;
  title: string;
  content: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type KnowledgeStats = {
  documents: number;
  sparse_chunks: number;
  vectors: number | null;
};

type KnowledgeResponse = {
  items: KnowledgeDocument[];
  total: number;
  stats: KnowledgeStats | null;
};

export type BackendHealth = {
  status: "healthy" | "degraded" | "offline" | "unconfigured";
  components: Record<string, string>;
  version?: string;
};

const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

async function jsonFetcher<T>(url: string): Promise<T> {
  const res = await fetch(url);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.error ?? `Request failed (${res.status})`);
  }
  return body as T;
}

export const KNOWLEDGE_KEY = `${base}/api/knowledge?limit=200`;

export function useKnowledge() {
  return useSWR<KnowledgeResponse>(KNOWLEDGE_KEY, jsonFetcher, {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });
}

export function useBackendHealth() {
  return useSWR<BackendHealth>(`${base}/api/backend-health`, jsonFetcher, {
    refreshInterval: 60_000,
    revalidateOnFocus: true,
  });
}
