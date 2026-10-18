import { z } from "zod";

/** Keep in sync with MAX_MESSAGE_LENGTH in the composer. */
export const MAX_MESSAGE_LENGTH = 4000;

const textPartSchema = z.object({
  text: z.string().min(1).max(MAX_MESSAGE_LENGTH),
  type: z.enum(["text"]),
});

const userMessageSchema = z.object({
  id: z.uuid(),
  parts: z.array(textPartSchema).min(1),
  role: z.enum(["user"]),
});

export const postRequestBodySchema = z.object({
  id: z.uuid(),
  message: userMessageSchema,
  selectedVisibilityType: z.enum(["public", "private"]),
});

export type PostRequestBody = z.infer<typeof postRequestBodySchema>;
