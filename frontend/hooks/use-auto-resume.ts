"use client";

import type { UseChatHelpers } from "@ai-sdk/react";
import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/lib/types";

export type UseAutoResumeParams = {
  autoResume: boolean;
  chatId: string;
  initialMessages: ChatMessage[];
  resumeStream: UseChatHelpers<ChatMessage>["resumeStream"];
};

/**
 * If a chat was left mid-answer (last stored message is the user's), try to
 * resume the in-flight stream once. Requires REDIS_URL for resumable streams.
 */
export function useAutoResume({
  autoResume,
  chatId,
  initialMessages,
  resumeStream,
}: UseAutoResumeParams) {
  const resumedChatId = useRef<string | null>(null);

  useEffect(() => {
    if (!autoResume || resumedChatId.current === chatId) {
      return;
    }
    resumedChatId.current = chatId;

    if (initialMessages.at(-1)?.role === "user") {
      resumeStream();
    }
  }, [autoResume, chatId, initialMessages, resumeStream]);
}
