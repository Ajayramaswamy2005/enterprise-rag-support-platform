import { createOpenAI } from "@ai-sdk/openai";
import { customProvider, gateway } from "ai";
import { isTestEnvironment } from "../constants";
import { titleModel } from "./models";

const groq = createOpenAI({
  apiKey: process.env.GROQ_API_KEY,
  baseURL: "https://api.groq.com/openai/v1",
});

const testProvider = isTestEnvironment
  ? (() => {
      const { titleModel: mockTitleModel } = require("./models.mock");
      return customProvider({
        languageModels: { "title-model": mockTitleModel },
      });
    })()
  : null;

export function getTitleModel() {
  if (testProvider) {
    return testProvider.languageModel("title-model");
  }

  if (process.env.GROQ_API_KEY) {
    return groq.chat(titleModel.id);
  }

  return gateway.languageModel(titleModel.id);
}
