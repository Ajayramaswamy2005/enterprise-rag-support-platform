"use client";

import { motion } from "framer-motion";
import { ArrowRightIcon } from "lucide-react";
import Link from "next/link";
import { useBackendHealth, useKnowledge } from "@/hooks/use-knowledge";

const ease = [0.22, 1, 0.36, 1] as const;

function KnowledgeStatus() {
  const { data: health } = useBackendHealth();
  const { data, error } = useKnowledge();

  if (health?.status === "unconfigured") {
    return (
      <span className="text-signal">
        Backend not connected — set BACKEND_API_URL
      </span>
    );
  }
  if (health?.status === "offline" || error) {
    return <span className="text-caution">Knowledge backend is offline</span>;
  }
  if (!data?.stats) {
    return <span className="opacity-60">Checking the shelves…</span>;
  }
  if (data.stats.documents === 0) {
    return (
      <Link
        className="pointer-events-auto inline-flex items-center gap-1 text-signal underline-offset-4 hover:underline"
        href="/knowledge"
      >
        Knowledge base is empty — add documents
        <ArrowRightIcon className="size-3" />
      </Link>
    );
  }
  return (
    <Link
      className="pointer-events-auto underline-offset-4 hover:text-foreground hover:underline"
      href="/knowledge"
    >
      {data.stats.documents} document{data.stats.documents === 1 ? "" : "s"}
      {" · "}
      {data.stats.sparse_chunks} passages indexed
    </Link>
  );
}

export const Greeting = () => (
  <div className="flex max-w-xl flex-col items-center px-6" key="overview">
    <motion.span
      animate={{ opacity: 1 }}
      className="font-label mb-5 flex items-center gap-2 text-muted-foreground"
      initial={{ opacity: 0 }}
      transition={{ delay: 0.2, duration: 0.5 }}
    >
      <span className="size-1.5 rounded-full bg-signal" />
      Support desk
    </motion.span>
    <motion.h1
      animate={{ opacity: 1, y: 0 }}
      className="font-display text-balance text-center text-[44px] leading-[1.02] text-foreground md:text-[60px]"
      initial={{ opacity: 0, y: 12 }}
      transition={{ delay: 0.3, duration: 0.6, ease }}
    >
      What needs <em className="text-signal">answering</em> today?
    </motion.h1>
    <motion.p
      animate={{ opacity: 1, y: 0 }}
      className="mt-4 max-w-md text-balance text-center text-[14px] text-muted-foreground leading-relaxed"
      initial={{ opacity: 0, y: 10 }}
      transition={{ delay: 0.45, duration: 0.6, ease }}
    >
      Every answer is retrieved from your knowledge base, re-ranked for
      relevance, and cited — never made up.
    </motion.p>
    <motion.div
      animate={{ opacity: 1 }}
      className="font-label mt-5 text-muted-foreground"
      initial={{ opacity: 0 }}
      transition={{ delay: 0.65, duration: 0.5 }}
    >
      <KnowledgeStatus />
    </motion.div>
  </div>
);
