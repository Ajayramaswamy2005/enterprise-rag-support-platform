/**
 * Answers come from the FastAPI RAG backend (see lib/rag). The frontend only
 * calls an LLM directly to name new chats, and only when a key is configured.
 */
export const titleModel = {
  gatewayOrder: ["groq"],
  id: "openai/gpt-oss-20b",
};
