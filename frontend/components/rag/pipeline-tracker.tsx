"use client";

import { useEffect, useState } from "react";
import { useDataStream } from "@/components/chat/data-stream-provider";
import type { RagStage } from "@/lib/rag/types";
import { cn } from "@/lib/utils";

const STEPS: { stage: RagStage; label: string; detail: string }[] = [
  {
    detail: "Labelling the question to pick the right shelf",
    label: "Classify",
    stage: "classify",
  },
  {
    detail: "BM25 + dense vectors, fused with RRF, re-ranked by a cross-encoder",
    label: "Retrieve",
    stage: "retrieve",
  },
  {
    detail: "Checking the question is specific enough to answer",
    label: "Verify",
    stage: "check_ambiguity",
  },
  {
    detail: "Composing a grounded answer with citations",
    label: "Compose",
    stage: "generate",
  },
];

const COLD_START_HINT_MS = 7000;

/**
 * Live view of the backend's LangGraph pipeline, driven by the transient
 * `data-rag-stage` events streamed from /chat/stream.
 */
export function PipelineTracker() {
  const { ragStage } = useDataStream();
  const [showColdStart, setShowColdStart] = useState(false);

  useEffect(() => {
    if (ragStage) {
      setShowColdStart(false);
      return;
    }
    const timer = setTimeout(() => setShowColdStart(true), COLD_START_HINT_MS);
    return () => clearTimeout(timer);
  }, [ragStage]);

  const activeIndex = ragStage
    ? STEPS.findIndex((s) => s.stage === ragStage)
    : -1;
  const active = activeIndex >= 0 ? STEPS[activeIndex] : null;

  return (
    <div
      aria-live="polite"
      className="flex w-full max-w-md flex-col gap-2.5 py-1"
      data-testid="pipeline-tracker"
    >
      <ol className="flex items-center">
        {STEPS.map((step, index) => {
          const isDone = index < activeIndex;
          const isActive = index === activeIndex;
          return (
            <li
              className={cn("flex items-center", index > 0 && "flex-1")}
              key={step.stage}
            >
              {index > 0 && (
                <span className="relative mx-1.5 h-px flex-1 bg-border">
                  {index <= activeIndex && (
                    <span className="stage-sweep absolute inset-0 bg-foreground/60" />
                  )}
                </span>
              )}
              <span className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "size-2 rounded-full border transition-colors duration-300",
                    isDone && "border-foreground/70 bg-foreground/70",
                    isActive && "stage-active border-signal bg-signal",
                    !isDone && !isActive && "border-border bg-transparent"
                  )}
                />
                <span
                  className={cn(
                    "font-label transition-colors duration-300",
                    isActive ? "text-foreground" : "text-muted-foreground/70"
                  )}
                >
                  {step.label}
                </span>
              </span>
            </li>
          );
        })}
      </ol>
      <p className="text-[12.5px] text-muted-foreground leading-snug">
        {active
          ? active.detail
          : showColdStart
            ? "Waking the knowledge backend — free-tier services can take a minute or two after a quiet spell. Your question will be answered once it's up."
            : "Connecting to the knowledge backend…"}
      </p>
    </div>
  );
}
