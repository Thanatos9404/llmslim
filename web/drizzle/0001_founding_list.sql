CREATE TABLE "founding_list" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" text,
	"email" text NOT NULL,
	"plan" text NOT NULL,
	"currency" text NOT NULL,
	"billing" text NOT NULL,
	"use_case" text,
	"source" text NOT NULL,
	"status" text DEFAULT 'pending' NOT NULL,
	"token_hash" text,
	"token_expires_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"confirmed_at" timestamp with time zone,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "founding_list_plan_check" CHECK ("founding_list"."plan" in ('free', 'pro', 'team', 'business')),
	CONSTRAINT "founding_list_currency_check" CHECK ("founding_list"."currency" in ('inr', 'usd')),
	CONSTRAINT "founding_list_billing_check" CHECK ("founding_list"."billing" in ('monthly', 'annual')),
	CONSTRAINT "founding_list_status_check" CHECK ("founding_list"."status" in ('pending', 'confirmed', 'unsubscribed')),
	CONSTRAINT "founding_list_email_check" CHECK (char_length("founding_list"."email") <= 254),
	CONSTRAINT "founding_list_use_case_check" CHECK (char_length("founding_list"."use_case") <= 280),
	CONSTRAINT "founding_list_source_check" CHECK ("founding_list"."source" ~ '^[a-z0-9_-]{1,40}$')
);
--> statement-breakpoint
ALTER TABLE "founding_list" ADD CONSTRAINT "founding_list_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE UNIQUE INDEX "founding_list_email_idx" ON "founding_list" USING btree ("email");--> statement-breakpoint
CREATE UNIQUE INDEX "founding_list_token_hash_idx" ON "founding_list" USING btree ("token_hash");--> statement-breakpoint
CREATE INDEX "founding_list_user_id_idx" ON "founding_list" USING btree ("user_id");