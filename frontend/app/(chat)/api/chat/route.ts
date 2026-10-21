import { ipAddress } from "@vercel/functions";
import {
  createUIMessageStream,
  createUIMessageStreamResponse,
  generateId,
} from "ai";
import { checkBotId } from "botid/server";
import { after } from "next/server";
import { createResumableStreamContext } from "resumable-stream";
import { auth, type UserType } from "@/app/(auth)/auth";
import { entitlementsByUserType } from "@/lib/ai/entitlements";
import {
  createStreamId,
  deleteChatById,
  getChatById,
  getMessageCountByUserId,
  getMessagesByChatId,
  saveChat,
  saveMessages,
  updateChatTitleById,
} from "@/lib/db/queries";
import { ChatbotError } from "@/lib/errors";
import {
  BackendError,
  backendFetch,
  parseRagStream,
  readBackendError,
} from "@/lib/rag/backend";
import type { RagMeta } from "@/lib/rag/types";
import { checkIpRateLimit } from "@/lib/ratelimit";
import type { ChatMessage } from "@/lib/types";
import { convertToUIMessages, generateUUID } from "@/lib/utils";
import { generateTitleFromUserMessage } from "../../actions";
import { type PostRequestBody, postRequestBodySchema } from "./schema";

export const maxDuration = 300;

/** Number of prior turns forwarded to the backend as conversational memory. */
const HISTORY_TURNS = 12;
/**
 * A sleeping free-tier Render service can take a minute or two to wake up, and
 * Render answers 502/503 or holds the connection while it does. Each attempt
 * waits this long for response headers; attempts repeat until the budget runs out.
 */
const BACKEND_ATTEMPT_TIMEOUT_MS = 60_000;
const BACKEND_WAKE_BUDGET_MS = 180_000;
const BACKEND_RETRY_DELAY_MS = 3000;
const RETRYABLE_STATUSES = new Set([502, 503, 504]);

async function openBackendStream(
  body: string,
  signal: AbortSignal
): Promise<Response & { body: ReadableStream<Uint8Array> }> {
  const deadline = Date.now() + BACKEND_WAKE_BUDGET_MS;
  while (true) {
    try {
      // biome-ignore lint/performance/noAwaitInLoops: retries must run one after another
      const response = await backendFetch("/chat/stream", {
        body,
        method: "POST",
        signal,
        timeoutMs: Math.min(BACKEND_ATTEMPT_TIMEOUT_MS, deadline - Date.now()),
      });
      if (response.ok && response.body) {
        return response as Response & { body: ReadableStream<Uint8Array> };
      }
      throw new BackendError(await readBackendError(response), response.status);
    } catch (error) {
      const retryable =
        error instanceof BackendError && RETRYABLE_STATUSES.has(error.status);
      if (
        !retryable ||
        signal.aborted ||
        Date.now() + BACKEND_RETRY_DELAY_MS >= deadline
      ) {
        throw error;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, BACKEND_RETRY_DELAY_MS));
  }
}

function getStreamContext() {
  try {
    return createResumableStreamContext({ waitUntil: after });
  } catch {
    return null;
  }
}

export { getStreamContext };

function toBackendMessages(messages: ChatMessage[]) {
  return messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({
      content: m.parts
        .filter((p) => p.type === "text")
        .map((p) => p.text)
        .join("\n")
        .trim(),
      role: m.role,
    }))
    .filter((m) => m.content.length > 0)
    .slice(-HISTORY_TURNS);
}

export async function POST(request: Request) {
  let requestBody: PostRequestBody;

  try {
    const json = await request.json();
    requestBody = postRequestBodySchema.parse(json);
  } catch {
    return new ChatbotError("bad_request:api").toResponse();
  }

  try {
    const { id, message, selectedVisibilityType } = requestBody;

    const [botIdResult, session] = await Promise.all([
      checkBotId().catch(() => null),
      auth(),
    ]);

    if (botIdResult?.isBot) {
      return new ChatbotError("forbidden:api").toResponse();
    }

    if (!session?.user) {
      return new ChatbotError("unauthorized:chat").toResponse();
    }

    await checkIpRateLimit(ipAddress(request));

    const userType: UserType = session.user.type;

    const messageCount = await getMessageCountByUserId({
      differenceInHours: 1,
      id: session.user.id,
    });

    if (messageCount > entitlementsByUserType[userType].maxMessagesPerHour) {
      return new ChatbotError("rate_limit:chat").toResponse();
    }

    const chat = await getChatById({ id });
    let titlePromise: Promise<string> | null = null;
    let history: ChatMessage[] = [];

    if (chat) {
      if (chat.userId !== session.user.id) {
        return new ChatbotError("forbidden:chat").toResponse();
      }
      history = convertToUIMessages(await getMessagesByChatId({ id }));
    } else {
      await saveChat({
        id,
        title: "New chat",
        userId: session.user.id,
        visibility: selectedVisibilityType,
      });
      titlePromise = generateTitleFromUserMessage({ message });
    }

    // Regenerating re-sends a user message that is already stored
    const alreadySaved = history.some((m) => m.id === message.id);
    if (alreadySaved) {
      history = history.filter((m) => m.id !== message.id);
    } else {
      await saveMessages({
        messages: [
          {
            attachments: [],
            chatId: id,
            createdAt: new Date(),
            id: message.id,
            parts: message.parts,
            role: "user",
          },
        ],
      });
    }

    const backendMessages = toBackendMessages([
      ...history,
      message as ChatMessage,
    ]);

    const stream = createUIMessageStream<ChatMessage>({
      execute: async ({ writer }) => {
        writer.write({ type: "start" });

        const response = await openBackendStream(
          JSON.stringify({
            conversation_id: id,
            messages: backendMessages,
          }),
          request.signal
        );

        const textId = generateUUID();
        let textStarted = false;
        let meta: RagMeta | null = null;

        for await (const event of parseRagStream(response.body)) {
          if (event.type === "stage") {
            writer.write({
              data: { stage: event.stage },
              transient: true,
              type: "data-rag-stage",
            });
          } else if (event.type === "meta") {
            meta = {
              confidence: event.confidence,
              mode: event.mode,
              model: event.model,
              queryType: event.query_type,
              sources: event.sources,
            };
            writer.write({ data: meta, id: "rag-meta", type: "data-rag-meta" });
          } else if (event.type === "token") {
            if (!textStarted) {
              writer.write({ id: textId, type: "text-start" });
              textStarted = true;
            }
            writer.write({
              delta: event.content,
              id: textId,
              type: "text-delta",
            });
          } else if (event.type === "error") {
            writer.write({ errorText: event.error, type: "error" });
          } else if (event.type === "done" && meta) {
            // Re-emit with the same id so the persisted part includes latency
            writer.write({
              data: { ...meta, tookMs: event.took_ms },
              id: "rag-meta",
              type: "data-rag-meta",
            });
          }
        }

        if (textStarted) {
          writer.write({ id: textId, type: "text-end" });
        }

        if (titlePromise) {
          try {
            const title = await titlePromise;
            writer.write({ data: title, type: "data-chat-title" });
            await updateChatTitleById({ chatId: id, title });
          } catch {
            /* non-fatal */
          }
        }

        writer.write({ type: "finish" });
      },
      generateId: generateUUID,
      onEnd: async ({ messages: finishedMessages }) => {
        const toSave = finishedMessages.filter(
          (m) => m.role === "assistant" && m.parts.length > 0
        );
        if (toSave.length === 0) {
          return;
        }
        await saveMessages({
          messages: toSave.map((currentMessage) => ({
            attachments: [],
            chatId: id,
            createdAt: new Date(),
            id: currentMessage.id,
            parts: currentMessage.parts,
            role: currentMessage.role,
          })),
        });
      },
      onError: (error) => {
        if (error instanceof BackendError) {
          return error.message;
        }
        console.error("Chat stream error:", error);
        return "Something went wrong while generating the answer.";
      },
    });

    return createUIMessageStreamResponse({
      async consumeSseStream({ stream: sseStream }) {
        if (!process.env.REDIS_URL) {
          return;
        }
        try {
          const streamContext = getStreamContext();
          if (streamContext) {
            const streamId = generateId();
            await createStreamId({ chatId: id, streamId });
            await streamContext.createNewResumableStream(
              streamId,
              () => sseStream
            );
          }
        } catch {
          /* non-critical */
        }
      },
      stream,
    });
  } catch (error) {
    if (error instanceof ChatbotError) {
      return error.toResponse();
    }

    console.error("Unhandled error in chat API:", error);
    return new ChatbotError("offline:chat").toResponse();
  }
}

export async function DELETE(request: Request) {
  const { searchParams } = new URL(request.url);
  const id = searchParams.get("id");

  if (!id) {
    return new ChatbotError("bad_request:api").toResponse();
  }

  const session = await auth();

  if (!session?.user) {
    return new ChatbotError("unauthorized:chat").toResponse();
  }

  const chat = await getChatById({ id });

  if (chat?.userId !== session.user.id) {
    return new ChatbotError("forbidden:chat").toResponse();
  }

  const deletedChat = await deleteChatById({ id });

  return Response.json(deletedChat, { status: 200 });
}
