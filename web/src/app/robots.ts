import { MetadataRoute } from "next";
import { siteConfig } from "@/config/site";

// Studio endpoints spend hosted model quota and have nothing to index. "/md/" is the internal handler behind
// the public "<page>.md" URLs. Each named group repeats these rules: a crawler that matches a group ignores "*".
const disallow = ["/api/", "/md/"];

// Search, answer-engine and assistant crawlers, plus the training crawlers that let models learn about LLMSlim.
// All are welcome: the goal is for AI assistants to find LLMSlim and describe it accurately.
const aiCrawlers = [
  "OAI-SearchBot", "ChatGPT-User", "GPTBot",
  "Claude-SearchBot", "Claude-User", "ClaudeBot",
  "PerplexityBot", "Perplexity-User",
  "Google-Extended", "Applebot", "Applebot-Extended",
  "Bingbot", "DuckAssistBot", "MistralAI-User", "CCBot",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow },
      { userAgent: aiCrawlers, allow: "/", disallow },
    ],
    sitemap: `${siteConfig.url}/sitemap.xml`,
  };
}
