"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useActiveChat } from "@/hooks/use-active-chat";
import type { ChatMessage } from "@/lib/types";
import { ChatHeader } from "./chat-header";
import { submitEditedMessage } from "./message-editor";
import { Messages } from "./messages";
import { MultimodalInput } from "./multimodal-input";

export function ChatShell() {
  const pathname = usePathname();
  const {
    chatId,
    messages,
    setMessages,
    sendMessage,
    status,
    stop,
    regenerate,
    input,
    setInput,
    visibilityType,
    isReadonly,
    isLoading,
    votes,
  } = useActiveChat();

  const [editingMessage, setEditingMessage] = useState<ChatMessage | null>(
    null
  );

  const stopRef = useRef(stop);
  stopRef.current = stop;

  const prevChatIdRef = useRef(chatId);
  useEffect(() => {
    if (prevChatIdRef.current !== chatId) {
      prevChatIdRef.current = chatId;
      stopRef.current();
      setEditingMessage(null);
    }
  }, [chatId]);

  const handleEditMessage = useCallback(
    (msg: ChatMessage) => {
      const text = msg.parts
        ?.filter((p) => p.type === "text")
        .map((p) => p.text)
        .join("");
      setInput(text ?? "");
      setEditingMessage(msg);
    },
    [setInput]
  );

  const handleCancelEdit = useCallback(() => {
    setEditingMessage(null);
    setInput("");
  }, [setInput]);

  const handleSendEditedMessage = useCallback(async () => {
    if (!editingMessage) {
      return;
    }

    const msg = editingMessage;
    setEditingMessage(null);
    await submitEditedMessage({
      message: msg,
      regenerate,
      setMessages,
      text: input,
    });
    setInput("");
  }, [editingMessage, input, regenerate, setInput, setMessages]);

  // Non-chat pages (e.g. the knowledge base) render as layout children instead
  if (pathname.startsWith("/knowledge")) {
    return null;
  }

  return (
    <div className="flex h-dvh w-full flex-row overflow-hidden">
      <div className="flex w-full min-w-0 flex-col bg-sidebar">
        <ChatHeader
          chatId={chatId}
          isReadonly={isReadonly}
          selectedVisibilityType={visibilityType}
        />

        <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden bg-background md:rounded-tl-xl md:border-t md:border-l md:border-border/70">
          <Messages
            chatId={chatId}
            isLoading={isLoading}
            isReadonly={isReadonly}
            messages={messages}
            onEditMessage={handleEditMessage}
            status={status}
            votes={votes}
          />

          <div className="sticky bottom-0 z-1 mx-auto flex w-full max-w-3xl gap-2 border-t-0 bg-gradient-to-t from-background via-background/95 to-transparent px-3 pt-6 pb-3 md:px-6 md:pb-5">
            {!isReadonly && (
              <MultimodalInput
                chatId={chatId}
                editingMessage={editingMessage}
                input={input}
                isLoading={isLoading}
                messages={messages}
                onCancelEdit={handleCancelEdit}
                selectedVisibilityType={visibilityType}
                sendMessage={
                  editingMessage ? handleSendEditedMessage : sendMessage
                }
                setInput={setInput}
                status={status}
                stop={stop}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
