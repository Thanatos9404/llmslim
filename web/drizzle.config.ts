import { defineConfig } from "drizzle-kit"

// Migrations run with the owner role over a direct (unpooled) connection; the app itself uses
// DATABASE_URL with a least-privilege role. See ACCOUNTS_SETUP.md.
export default defineConfig({
  dialect: "postgresql",
  schema: "./src/db/schema.ts",
  out: "./drizzle",
  dbCredentials: { url: process.env.DATABASE_URL_UNPOOLED || process.env.DATABASE_URL || "" },
  strict: true,
  verbose: true,
})
