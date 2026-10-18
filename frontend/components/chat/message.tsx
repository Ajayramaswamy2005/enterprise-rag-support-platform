"use client";
import type { Vote } from "@/lib/db/schema";
import type { ChatMessage } from "@/lib/types";
import { cn, sanitizeText } from "@/lib/utils";
import { MessageContent, MessageResponse } from "../ai-elements/message";
import { BrandMark } from "../rag/brand-mark";
import { PipelineTracker } from "../rag/pipeline-tracker";
import { RagAnswerMeta } from "../rag/source-cards";
import { MessageActions } from "./message-actions";

const PurePreviewMessage = ({
  chatId,
  message,
  vote,
  isLoading,
  isReadonly,
  onEdit,
}: {
  chatId: string;
  message: ChatMessage;
  vote: Vote | undefined;
  isLoading: boolean;
  isReadonly: boolean;
  onEdit?: (message: ChatMessage) => void;
}) => {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";

  const hasAnyContent = message.parts?.some(
    (part) => part.type === "text" && part.text?.trim().length > 0
  );
  const isThinking = isAssistant && isLoading && !hasAnyContent;

  const parts = message.parts?.map((part, index) => {
    const { type } = part;
    const key = `message-${message.id}-part-${index}`;

    if (type === "data-rag-meta") {
      // Rendered after the answer text, below
      return null;
    }

    if (type === "text") {
      return (
        <MessageContent
          className={cn("text-[14px] leading-[1.7]", {
            "w-fit max-w-[min(85%,60ch)] overflow-hidden break-words rounded-lg rounded-br-sm bg-primary px-3.5 py-2 text-primary-foreground shadow-[var(--shadow-card)] [&_a]:text-primary-foreground [&_code]:text-primary-foreground":
              message.role === "user",
          })}
          data-testid="message-content"
          key={key}
        >
          <MessageResponse>{sanitizeText(part.text)}</MessageResponse>
        </MessageContent>
      );
    }

    return null;
  });

  const actions = !isReadonly && (
    <MessageActions
      chatId={chatId}
      isLoading={isLoading}
      key={`action-${message.id}`}
      message={message}
      onEdit={onEdit ? () => onEdit(message) : undefined}
      vote={vote}
    />
  );

  const ragMeta = message.parts.find((part) => part.type === "data-rag-meta");

  const content = isThinking ? (
    <PipelineTracker />
  ) : (
    <>
      {parts}
      {isAssistant && !isLoading && !hasAnyContent && (
        <p className="text-[13px] text-muted-foreground italic">
          No answer was generated. The backend may have hit an error — try
          sending the question again.
        </p>
      )}
      {isAssistant && ragMeta && !isLoading && (
        <RagAnswerMeta meta={ragMeta.data} />
      )}
      {actions}
    </>
  );

  return (
    <div
      className={cn(
        "group/message w-full",
        !isAssistant && "animate-[fade-up_0.25s_cubic-bezier(0.22,1,0.36,1)]"
      )}
      data-role={message.role}
      data-testid={`message-${message.role}`}
    >
      <div
        className={cn(
          isUser ? "flex flex-col items-end gap-2" : "flex items-start gap-3"
        )}
      >
        {isAssistant && (
          <div className="flex h-[calc(14px*1.7)] shrink-0 items-center">
            <BrandMark size={24} />
          </div>
        )}
        {isAssistant ? (
          <div className="flex min-w-0 flex-1 flex-col gap-2">{content}</div>
        ) : (
          content
        )}
      </div>
    </div>
  );
};

export const PreviewMessage = PurePreviewMessage;

export const ThinkingMessage = () => (
  <div
    className="group/message w-full"
    data-role="assistant"
    data-testid="message-assistant-loading"
  >
    <div className="flex items-start gap-3">
      <div className="flex h-[calc(14px*1.7)] shrink-0 items-center">
        <BrandMark size={24} />
      </div>

      <PipelineTracker />
    </div>
  </div>
);
