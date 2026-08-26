import { readFileSync } from "fs";
import { join } from "path";

const KNOWLEDGE_BASE_PATH = join(__dirname, "..", "knowledge", "shokogi-knowledge-base.md");
const EXAMPLE_REPLIES_PATH = join(__dirname, "..", "knowledge", "example-replies.md");

function readIfExists(path: string): string {
  try {
    return readFileSync(path, "utf-8");
  } catch {
    return "";
  }
}

// Cached at process start - restart the server after editing the knowledge files.
export const knowledgeBaseContent = readIfExists(KNOWLEDGE_BASE_PATH);
export const exampleRepliesContent = readIfExists(EXAMPLE_REPLIES_PATH);
