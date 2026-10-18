export type RagSource = {
  chunk_id: string;
  document_id: string;
  title: string | null;
  content: string;
  score: number;
  rank: number | null;
};

export type RagStage = "classify" | "retrieve" | "check_ambiguity" | "generate";

export type RagStreamEvent =
  | { type: "stage"; stage: RagStage }
  | {
      type: "meta";
      conversation_id: string;
      sources: RagSource[];
      query_type: string;
      needs_clarification: boolean;
      mode: "answer" | "clarify" | "fallback";
      confidence: "high" | "medium" | "low" | "fallback";
      model: string;
    }
  | { type: "token"; content: string }
  | { type: "error"; error: string }
  | { type: "done"; took_ms?: number };

/** Retrieval metadata persisted on each assistant message as a `data-rag-meta` part. */
export type RagMeta = {
  sources: RagSource[];
  queryType: string;
  confidence: "high" | "medium" | "low" | "fallback";
  mode: "answer" | "clarify" | "fallback";
  model: string;
  tookMs?: number;
};
