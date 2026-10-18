import type { UIMessage } from "ai";
import { z } from "zod";
import type { RagMeta, RagStage } from "./rag/types";

export const messageMetadataSchema = z.object({
  createdAt: z.string(),
});

export type MessageMetadata = z.infer<typeof messageMetadataSchema>;

export type WaitingStatusData = {
  phase: "waiting" | "still-waiting" | "health" | "thinking";
  message: string;
  modelId: string;
  modelName: string;
};

export type CustomUIDataTypes = {
  "chat-title": string;
  "waiting-status": WaitingStatusData;
  "rag-stage": { stage: RagStage };
  "rag-meta": RagMeta;
};

export type ChatMessage = UIMessage<MessageMetadata, CustomUIDataTypes>;

export type Attachment = {
  name: string;
  url: string;
  contentType: string;
};
