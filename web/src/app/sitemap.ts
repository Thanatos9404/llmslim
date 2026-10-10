import { MetadataRoute } from "next";
import { ARTICLES_REGISTRY } from "@/data/articles";
import { BENCHMARK_SUITES } from "@/data/benchmarks";
import { releases } from "@/data/changelog";
import { DOCS_REGISTRY } from "@/data/docs";
import { INTEGRATIONS_REGISTRY } from "@/data/integrations";
import { absoluteUrl, contentDate } from "@/lib/seo";

type Entry = MetadataRoute.Sitemap[number];

// lastModified comes from the content's own dates. Where a page has none it is omitted rather than
// stamped with the build time, which would tell crawlers every page changes on every deploy.
function entry(path: string, priority: number, changeFrequency: Entry["changeFrequency"], modified?: Date): Entry {
  return { url: absoluteUrl(path), priority, changeFrequency, ...(modified ? { lastModified: modified } : {}) };
}

const latest = (dates: Array<Date | undefined>) => dates.filter((date): date is Date => !!date).sort((a, b) => b.getTime() - a.getTime())[0];

export default function sitemap(): MetadataRoute.Sitemap {
  const docs = Object.values(DOCS_REGISTRY);
  const articles = Object.values(ARTICLES_REGISTRY);
  const lastRelease = latest(releases.map((release) => contentDate(release.date)));
  const lastDoc = latest(docs.map((doc) => contentDate(doc.lastUpdated)));
  const lastArticle = latest(articles.map((article) => contentDate(article.lastUpdated)));

  return [
    entry("/", 1.0, "weekly", lastRelease),
    entry("/docs", 0.9, "weekly", lastDoc),
    entry("/playground", 0.9, "monthly"),
    entry("/platform", 0.9, "monthly"),
    entry("/integrations", 0.9, "monthly"),
    entry("/benchmarks", 0.85, "monthly"),
    entry("/articles", 0.8, "monthly", lastArticle),
    entry("/changelog", 0.7, "monthly", lastRelease),
    entry("/privacy", 0.3, "yearly"),
    ...docs.map((doc) => entry(`/docs/${doc.slug}`, 0.8, "monthly", contentDate(doc.lastUpdated))),
    ...Object.keys(INTEGRATIONS_REGISTRY).map((slug) => entry(`/integrations/${slug}`, 0.8, "monthly")),
    ...Object.keys(BENCHMARK_SUITES).map((slug) => entry(`/benchmarks/${slug}`, 0.75, "monthly")),
    ...articles.map((article) => entry(`/articles/${article.slug}`, 0.7, "yearly", contentDate(article.lastUpdated))),
  ];
}
