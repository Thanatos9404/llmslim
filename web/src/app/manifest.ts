import { MetadataRoute } from "next";
import { siteConfig } from "@/config/site";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: siteConfig.title,
    short_name: siteConfig.shortName,
    description: siteConfig.description,
    start_url: "/",
    display: "standalone",
    background_color: "#030508",
    theme_color: "#030508",
    icons: [
      {
        src: "/llmslim_logo.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/llmslim_brand_id.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
  };
}
