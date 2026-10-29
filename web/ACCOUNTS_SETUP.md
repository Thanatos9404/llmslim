# Accounts: founder setup guide

This guide turns on accounts (sign-in and sign-up with email and password, Google, GitHub and
passkeys) for www.llmslim.app. The code is already merged into the site; until the variables below
are set, the site builds and runs normally and the accounts pages say accounts are not available yet.

Everything comes from environment variables. Nothing secret is in the repository. Do the steps in
this order:

1. [Generate the secrets](#1-generate-the-secrets)
2. [Create the database (Neon, through the Vercel Marketplace)](#2-database-neon-through-the-vercel-marketplace)
3. [Set up email (Resend)](#3-email-resend)
4. [Create the Google OAuth client](#4-google-sign-in)
5. [Create the GitHub OAuth app](#5-github-sign-in)
6. [Set the Vercel environment variables](#6-vercel-environment-variables)
7. [Deploy and check](#7-deploy-and-check)

The URLs used throughout:

| | Production | Vercel previews | Local development |
| --- | --- | --- | --- |
| Site origin (`BETTER_AUTH_URL`) | `https://www.llmslim.app` | the preview's own URL (automatic) | `http://localhost:3000` |
| Google redirect URI | `https://www.llmslim.app/api/auth/callback/google` | not supported (see below) | `http://localhost:3000/api/auth/callback/google` |
| GitHub callback URL | `https://www.llmslim.app/api/auth/callback/github` | not supported (see below) | `http://localhost:3000/api/auth/callback/github` |
| Passkey relying party ID | `llmslim.app` (covers www and the apex) | the preview host | `localhost` |

Google and GitHub do not accept wildcard redirect URIs, and every preview has a different host, so
Google and GitHub sign-in are for production and local development only. Leave their variables unset
for Preview: the buttons are then hidden on previews, which still offer email and passkeys when a
preview database is configured.

## 1. Generate the secrets

You need one auth secret per environment (production and, if you use it, preview). Run this once per
secret on your own machine and keep the output in your password manager:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
```

(`openssl rand -base64 32` works too.) The secret must be at least 32 characters; production refuses
to start the accounts API with a shorter one.

Also generate a password for the database app role (step 2) the same way:

```bash
node -e "console.log(require('crypto').randomBytes(24).toString('base64url'))"
```

## 2. Database: Neon, through the Vercel Marketplace

### 2.1 Create the database

1. Vercel dashboard → your team → **Storage** → **Create Database** (or go to
   vercel.com/marketplace/neon and click **Install**).
2. Choose **Neon** → **Continue**. In **Install Neon** choose **Create New Neon Account** (Vercel
   manages the billing) → **Continue**.
3. **Configuration and Plan**: pick the region closest to the project's function region (Vercel
   project → **Settings** → **Functions** → **Function Region**; the default is Washington, D.C.,
   `iad1`, which matches Neon `aws-us-east-1`). Leave **Auth** and **Realtime** off: the site runs
   Better Auth itself. Pick the **Free** plan, name the database `llmslim-accounts`, accept and create.
4. On the database page: **Connect Project** → choose the website project →
   - Environments: tick **Production** only. (Do not give previews the production database.)
   - **Create database branch for deployment**: leave **Preview** and **Production** unticked. A Neon
     branch copies its parent's data, so preview branches would hold copies of real users.
   - **Custom Prefix**: enter `NEON`. The integration's variables then start with `NEON_` (for example
     `NEON_DATABASE_URL_UNPOOLED`) and do not collide with the `DATABASE_URL` you set in step 6,
     which uses the least-privilege role below instead of the owner.
   - **Connect**.

TLS: Neon only accepts TLS connections, and the app additionally forces certificate and host-name
verification for every non-local database host, whatever the URL says.

### 2.2 Create the tables (migrations)

Migrations live in `web/drizzle/` and run with the owner role over the direct (unpooled) connection.
On your machine, from the `web/` folder:

1. Copy the owner's direct URL: Vercel → **Storage** → `llmslim-accounts` → the connection
   details (**Show secret**) → `NEON_DATABASE_URL_UNPOOLED`. Or, in the Neon console, the project's
   **Connect** button with **Connection pooling** switched off. The host has no `-pooler`.
2. Run (PowerShell):

   ```powershell
   $env:DATABASE_URL_UNPOOLED = "postgresql://neondb_owner:...@ep-....aws.neon.tech/neondb?sslmode=require"
   npm ci
   npm run db:migrate
   Remove-Item Env:DATABASE_URL_UNPOOLED
   ```

   or in bash: `DATABASE_URL_UNPOOLED="postgresql://..." npm run db:migrate`.

Run `npm run db:migrate` again after any future pull request that adds a file to `web/drizzle/`,
before (or right after) that deployment goes live.

### 2.3 Least-privilege app role

The running site should not use the owner role. Create a role that can only read and write the
accounts tables, and cannot change the schema or edit the audit trail:

1. Neon console (Vercel → **Storage** → `llmslim-accounts` → **Open in Neon**) → **SQL Editor**,
   database `neondb`.
2. Run, with the password you generated in step 1 (create the role with SQL, not with the console's
   **Roles** page: console-created roles are members of `neon_superuser`):

   ```sql
   CREATE ROLE llmslim_app WITH LOGIN PASSWORD 'PASTE_THE_GENERATED_PASSWORD';
   GRANT CONNECT ON DATABASE neondb TO llmslim_app;
   GRANT USAGE ON SCHEMA public TO llmslim_app;
   GRANT SELECT, INSERT, UPDATE, DELETE ON "user", session, account, verification, passkey, rate_limit TO llmslim_app;
   -- The audit trail can be written and pruned, never edited.
   GRANT SELECT, INSERT, DELETE ON auth_event TO llmslim_app;
   ```

   If a later migration adds a table, the pull request will say which `GRANT` to run.
3. Build the app's connection string from the **pooled** host (the one with `-pooler` in
   `NEON_DATABASE_URL`):

   ```
   postgresql://llmslim_app:PASSWORD@ep-XXXX-pooler.REGION.aws.neon.tech/neondb?sslmode=require&channel_binding=require
   ```

   This is the production `DATABASE_URL` in step 6.

Why `pg` with a pool: on Vercel Fluid compute, Neon and Vercel recommend a standard TCP driver with
a connection pool, registered with `attachDatabasePool` so idle connections close before an instance
is suspended. Better Auth also needs interactive transactions (sign-up, password reset with session
revocation), which Neon's HTTP driver does not provide.

## 3. Email: Resend

Email verification and password reset need an email provider. Without one, production keeps
email/password sign-up and password reset switched off (existing passwords still work, and Google,
GitHub and passkeys are unaffected).

1. resend.com → sign up or sign in → **Domains** → **Add Domain** → `llmslim.app` → choose a region
   → **Add**.
2. Add the DNS records Resend shows (an MX and a TXT record on the `send` subdomain for SPF, and a
   `resend._domainkey` TXT record for DKIM). If the domain uses Vercel DNS: Vercel → **Domains** →
   `llmslim.app` → **DNS Records** → add each one exactly as shown. Adding a DMARC record
   (`_dmarc` TXT `v=DMARC1; p=none;`) is recommended.
3. Back in Resend → **Verify DNS Records**, and wait until the domain shows **Verified**.
4. **API Keys** → **Create API Key** → name `llmslim-web-production`, permission **Sending access**,
   domain `llmslim.app` → **Add**. Copy the key now: it is shown once.
5. The sender will be `LLMSlim <accounts@llmslim.app>` (`AUTH_EMAIL_FROM`). Any address on the
   verified domain works; it does not need a mailbox, but replies to account-deletion notices go
   there, so point it at an inbox you read if you can.

## 4. Google sign-in

Scopes: `openid`, `email`, `profile` only. These are non-sensitive scopes, so no Google security
review is needed.

1. console.cloud.google.com → project picker → **New Project** → name `llmslim-web` → **Create**,
   and select it.
2. **Google Auth Platform** (search for it, or console.developers.google.com/auth) → **Get started**:
   - App information: app name `LLMSlim`, user support email: your address → **Next**.
   - Audience: **External** → **Next**.
   - Contact information: your address → **Next** → agree → **Create**.
3. **Branding**: application home page `https://www.llmslim.app`, privacy policy
   `https://www.llmslim.app/privacy`, terms of service `https://www.llmslim.app/terms`, authorised
   domain `llmslim.app` → **Save**.
4. **Data Access** → **Add or remove scopes** → tick `openid`, `.../auth/userinfo.email` and
   `.../auth/userinfo.profile` → **Update** → **Save**.
5. **Audience** → **Publish app** → confirm, so any Google account can sign in (in "Testing" only
   listed test users can).
6. **Clients** → **Create client** → application type **Web application** → name
   `LLMSlim web (production)`:
   - Authorised JavaScript origins: `https://www.llmslim.app` and `https://llmslim.app`
   - Authorised redirect URIs: `https://www.llmslim.app/api/auth/callback/google`
   - **Create**. Copy the client ID and the client secret now (the secret is shown in full only once;
     download the JSON if offered).
7. For local development, create a second client the same way, named `LLMSlim web (local)`, with
   origin `http://localhost:3000` and redirect URI `http://localhost:3000/api/auth/callback/google`.
   Keep its secret in your local `.env.local` only.

Changes in the Google console can take from five minutes to a few hours to apply.

## 5. GitHub sign-in

Scope: `user:email` only (requested by the site at sign-in; nothing to configure in the app). The site
signs in with the account's **primary** email and only if GitHub reports it as verified.

1. github.com → your avatar → **Settings** → **Developer settings** (bottom of the left sidebar) →
   **OAuth Apps** → **New OAuth app**.
2. Application name `LLMSlim`; homepage URL `https://www.llmslim.app`; authorization callback URL
   `https://www.llmslim.app/api/auth/callback/github`; leave **Enable Device Flow** unticked →
   **Register application**.
3. Copy the **Client ID**. Click **Generate a new client secret** and copy it now (it is shown once).
   Optionally upload the LLMSlim logo.
4. For local development, register a second OAuth app, `LLMSlim (local)`, with homepage
   `http://localhost:3000` and callback `http://localhost:3000/api/auth/callback/github`. (A GitHub
   OAuth app has a single callback URL, so production and local need separate apps.)

## 6. Vercel environment variables

Vercel → the website project → **Settings** → **Environment Variables** → **Add New**. For each row,
tick only the environments listed, and switch on **Sensitive** for secrets (they can then never be
read back, only replaced). Changes apply to the next deployment.

| Variable | Production | Preview | Development | Notes |
| --- | --- | --- | --- | --- |
| `DATABASE_URL` | the `llmslim_app` pooled URL from 2.3 (Sensitive) | unset, or a separate preview database | unset | Without it, accounts answer 503 and the pages say they are unavailable. |
| `BETTER_AUTH_SECRET` | secret from step 1 (Sensitive) | a different secret, only if Preview has a database | unset | 32+ characters. |
| `BETTER_AUTH_URL` | `https://www.llmslim.app` | unset (the preview URL is used) | unset | |
| `GOOGLE_CLIENT_ID` | production client ID | unset | unset | The button shows only when both Google variables are set. |
| `GOOGLE_CLIENT_SECRET` | production client secret (Sensitive) | unset | unset | |
| `GITHUB_CLIENT_ID` | production client ID | unset | unset | The button shows only when both GitHub variables are set. |
| `GITHUB_CLIENT_SECRET` | production client secret (Sensitive) | unset | unset | |
| `RESEND_API_KEY` | key from step 3 (Sensitive) | optional, a separate key | unset | |
| `AUTH_EMAIL_FROM` | `LLMSlim <accounts@llmslim.app>` | same, if Preview has a key | unset | |
| `PASSKEY_RP_ID` | optional: `llmslim.app` (already the default) | unset | unset | Changing it later invalidates existing passkeys. |

Never set `AUTH_DEV_MAIL`, `AUTH_DEV_MAIL_DIR` or `AUTH_BREACHED_PASSWORD_CHECK` in Vercel: they are
for local tests and are ignored on Vercel anyway.

`npm run build` needs none of these, so preview and CI builds keep working without them.

## 7. Deploy and check

After the variables are saved, redeploy production (Vercel → **Deployments** → the latest production
deployment → **⋯** → **Redeploy**), then:

1. `https://www.llmslim.app/api/auth/ok` returns `{"ok":true}` (a 503 means `DATABASE_URL` or
   `BETTER_AUTH_SECRET` is missing).
2. `/sign-up`: create an account with a real address, receive the confirmation email, follow the
   link, sign in.
3. `/account`: add a passkey, sign out, and sign in with the passkey (also try the email field's
   autofill, which offers passkeys in Chrome, Safari and Edge).
4. Sign out and use **Continue with Google** and **Continue with GitHub** with the same email address:
   each should land on the same account, connected under **Ways to sign in**.
5. In Neon's SQL editor, `select type, method, created_at from auth_event order by created_at desc
   limit 20;` shows the events, with no emails, passwords, tokens or raw IP addresses.

## Local development

```bash
cd web
npm ci
npm run db:local            # terminal 1: an in-memory Postgres (PGlite) on 127.0.0.1:5433, no Docker
cp .env.example .env.local  # terminal 2; the defaults point at that database
npm run db:migrate:local    # creates the tables from web/drizzle
npm run dev                 # http://localhost:3000/sign-up
```

Verification and reset links are printed in the `npm run dev` log. To try Google or GitHub locally,
put the local client IDs and secrets from steps 4.7 and 5.4 in `.env.local`. A local Postgres works
too: set `DATABASE_URL` to it. Tests: `npm test` (unit, in-process PGlite) and `npm run build &&
npm run test:e2e` (Playwright; needs a database at `E2E_DATABASE_URL`, default the `db:local` one).

## Decisions and behaviour worth knowing

- **Passkey-only sign-up is not offered.** New accounts start with a verified email (email and
  password, Google or GitHub); a passkey is added from the account page afterwards. This keeps every
  account tied to a verified email that can recover it, and keeps passkey registration behind a
  signed-in, recent session.
- **Recent sign-in for sensitive changes.** Adding a passkey, disconnecting Google or GitHub, setting a
  first password, and deleting an account without a password need a sign-in in the last 30 minutes;
  the page links to a quick re-sign-in otherwise. Deleting an account with a password asks for it.
- **Sessions** last 7 days and slide forward with use (refreshed at most daily). Changing or
  resetting a password signs out every other session.
- **What is stored**: name, email, email-verified flag, Google or GitHub avatar URL, scrypt password
  hash (email accounts), provider account IDs, passkey public keys, sessions (token, expiry, browser
  user agent) and the audit trail. OAuth access, refresh and ID tokens are discarded at sign-in.
  Session rows keep no IP address; the audit trail keeps only a keyed hash of it, and its rows older
  than 180 days are deleted automatically.
- **Account linking**: Google or GitHub attach to an existing account only when the provider says the
  email is verified and the existing account's email is verified too.

## Operations

- **Rotating `BETTER_AUTH_SECRET`** signs everyone out and invalidates outstanding email links. Rotate
  it if it may have leaked; set the new value as Sensitive and redeploy.
- **Rotating the database password**: `ALTER ROLE llmslim_app WITH PASSWORD '...';` in the SQL editor,
  update `DATABASE_URL` in Vercel, redeploy.
- **Rotating OAuth or Resend secrets**: create the new secret at the provider, update Vercel,
  redeploy, then delete the old secret at the provider.
- **Rate limits** are stored in the `rate_limit` table and need no maintenance. To unblock someone
  early, delete their rows (keys are hashed, so clear by time window:
  `delete from rate_limit where window_start > extract(epoch from now() - interval '1 hour') * 1000;`).
