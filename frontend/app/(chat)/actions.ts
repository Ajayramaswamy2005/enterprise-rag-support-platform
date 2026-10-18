"use server";

import { generateText, type UIMessage } from "ai";
import { auth } from "@/app/(auth)/auth";
import type { VisibilityType } from "@/components/chat/visibility-selector";
import { titleModel } from "@/lib/ai/models";
import { titlePrompt } from "@/lib/ai/prompts";
import { getTitleModel } from "@/lib/ai/providers";
import {
  deleteMessagesByChatIdAfterTimestamp,
  getChatById,
  getMessageById,
  updateChatVisibilityById,
} from "@/lib/db/queries";
import { getTextFromMessage } from "@/lib/utils";

export async function generateTitleFromUserMessage({
  message,
}: {
  message: UIMessage;
}) {
  const messageText = getTextFromMessage(message);
  const fallbackTitle = deriveTitle(messageText);

  // Titles are cosmetic: without an LLM key on the frontend, derive one locally
  if (!process.env.GROQ_API_KEY && !process.env.AI_GATEWAY_API_KEY) {
    return fallbackTitle;
  }

  try {
    const { text } = await generateText({
      instructions: titlePrompt,
      model: getTitleModel() as any,
      prompt: messageText,
      providerOptions: {
        gateway: { order: titleModel.gatewayOrder },
      },
    });
    const title = text
      .replace(/^[#*"\s]+/, "")
      .replace(/["]+$/, "")
      .trim();
    return title || fallbackTitle;
  } catch {
    return fallbackTitle;
  }
}

function deriveTitle(text: string) {
  const firstLine = text.trim().split("\n")[0].replace(/[?!.]+$/, "");
  if (!firstLine) {
    return "New conversation";
  }
  return firstLine.length > 48 ? `${firstLine.slice(0, 45).trimEnd()}…` : firstLine;
}

export async function deleteTrailingMessages({ id }: { id: string }) {
  const session = await auth();
  if (!session?.user?.id) {
    throw new Error("Unauthorized");
  }

  const [message] = await getMessageById({ id });
  if (!message) {
    throw new Error("Message not found");
  }

  const chat = await getChatById({ id: message.chatId });
  if (!chat || chat.userId !== session.user.id) {
    throw new Error("Unauthorized");
  }

  await deleteMessagesByChatIdAfterTimestamp({
    chatId: message.chatId,
    timestamp: message.createdAt,
  });
}

export async function updateChatVisibility({
  chatId,
  visibility,
}: {
  chatId: string;
  visibility: VisibilityType;
}) {
  const session = await auth();
  if (!session?.user?.id) {
    throw new Error("Unauthorized");
  }

  const chat = await getChatById({ id: chatId });
  if (!chat || chat.userId !== session.user.id) {
    throw new Error("Unauthorized");
  }

  await updateChatVisibilityById({ chatId, visibility });
}
