"use client";

import { ChevronDownIcon } from "lucide-react";
import { useState } from "react";
import type { RagMeta, RagSource } from "@/lib/rag/types";
import { cn } from "@/lib/utils";

const CONFIDENCE_STYLES: Record<
  RagMeta["confidence"],
  { label: string; className: string }
> = {
  fallback: {
    className: "bg-signal-soft text-signal",
    label: "Not in knowledge base",
  },
  high: {
    className: "bg-grounded-soft text-grounded",
    label: "Well grounded",
  },
  low: {
    className: "bg-caution-soft text-caution",
    label: "Weak grounding",
  },
  medium: {
    className: "bg-muted text-foreground/80",
    label: "Grounded",
  },
};

/** Cross-encoder scores are unbounded logits; squash them for a relevance bar. */
function relevance(score: number) {
  return 1 / (1 + Math.exp(-score / 2));
}

function formatDuration(ms?: number) {
  if (ms === undefined) {
    return null;
  }
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

function SourceCard({ source, index }: { source: RagSource; index: number }) {
  const [open, setOpen] = useState(false);
  const pct = Math.round(relevance(source.score) * 100);

  return (
    <li
      className="card-in"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <button
        aria-expanded={open}
        className={cn(
          "group/source flex w-full flex-col gap-2 rounded-md border border-border/70 bg-card px-3 py-2.5 text-left shadow-[var(--shadow-card)] transition-all duration-200",
          "hover:-translate-y-px hover:border-foreground/20 hover:shadow-[var(--shadow-float)]",
          open && "border-foreground/20"
        )}
        onClick={() => setOpen((v) => !v)}
        type="button"
      >
        <span className="flex w-full items-center gap-2">
          <span className="font-label flex h-5 min-w-5 items-center justify-center rounded-sm bg-signal-soft px-1 text-signal">
            {index + 1}
          </span>
          <span className="min-w-0 flex-1 truncate font-medium text-[12.5px] text-foreground">
            {source.title || "Untitled document"}
          </span>
          <ChevronDownIcon
            className={cn(
              "size-3.5 shrink-0 text-muted-foreground transition-transform duration-200",
              open && "rotate-180"
            )}
          />
        </span>
        <span
          className={cn(
            "text-[12px] text-muted-foreground leading-relaxed",
            open ? "whitespace-pre-wrap" : "line-clamp-2"
          )}
        >
          {source.content}
        </span>
        <span className="flex w-full items-center gap-2">
          <span className="h-[3px] flex-1 overflow-hidden rounded-full bg-muted">
            <span
              className="block h-full rounded-full bg-foreground/50"
              style={{ width: `${pct}%` }}
            />
          </span>
          <span className="font-label text-muted-foreground/80">
            {pct}% match
          </span>
        </span>
      </button>
    </li>
  );
}

export function RagAnswerMeta({ meta }: { meta: RagMeta }) {
  const confidence = CONFIDENCE_STYLES[meta.confidence];
  const showSources = meta.mode === "answer" && meta.sources.length > 0;
  const duration = formatDuration(meta.tookMs);

  return (
    <div className="flex flex-col gap-2.5" data-testid="rag-meta">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span
          className={cn(
            "font-label rounded-sm px-1.5 py-0.5",
            meta.mode === "clarify"
              ? "bg-caution-soft text-caution"
              : confidence.className
          )}
        >
          {meta.mode === "clarify" ? "Needs detail" : confidence.label}
        </span>
        <span className="font-label text-muted-foreground/80">
          {meta.queryType}
        </span>
        {showSources && (
          <span className="font-label text-muted-foreground/80">
            {meta.sources.length} source{meta.sources.length === 1 ? "" : "s"}
          </span>
        )}
        {duration && (
          <span className="font-label text-muted-foreground/60">{duration}</span>
        )}
      </div>

      {showSources && (
        <ol className="grid gap-2 sm:grid-cols-2">
          {meta.sources.map((source, index) => (
            <SourceCard
              index={index}
              key={source.chunk_id}
              source={source}
            />
          ))}
        </ol>
      )}
    </div>
  );
}
