import type { Metadata } from "next";
import { KnowledgeBase } from "@/components/rag/knowledge-base";

export const metadata: Metadata = {
  title: "Knowledge base",
};

export default function Page() {
  return <KnowledgeBase />;
}
