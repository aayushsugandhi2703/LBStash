-- telegram service schema ("telegram"), forward-only. Every table with user data: SELECT bt.enable_rls('table');

-- Per-user settings (Reveal, idle days, digest hour, after-tag). Lives apart from the link so the gateway's GET /settings
-- works before a bot is saved or linked, and a PATCH survives unlink / re-link.
CREATE TABLE telegram_settings (
  user_id uuid PRIMARY KEY,
  allow_reveal boolean NOT NULL DEFAULT true,
  session_idle_days int NOT NULL DEFAULT 30 CHECK (session_idle_days BETWEEN 1 AND 90),
  digest_hour int NOT NULL DEFAULT 21 CHECK (digest_hour BETWEEN 0 AND 23),
  after_tag text NOT NULL DEFAULT 'edit' CHECK (after_tag IN ('edit', 'delete')),
  updated_at timestamptz NOT NULL DEFAULT now()
);
SELECT bt.enable_rls('telegram_settings');

-- The user's own bot: token encrypted (AES-256-GCM, aad = user id), webhook secrets stored only as hashes.
-- `path_hash` finds the owner from the webhook path; `header_hash` is checked against X-Telegram-Bot-Api-Secret-Token.
CREATE TABLE telegram_bots (
  user_id uuid PRIMARY KEY,
  token_enc bytea NOT NULL,
  bot_username text,
  path_hash text NOT NULL UNIQUE,
  header_hash text NOT NULL,
  tz text NOT NULL DEFAULT 'Asia/Kolkata',
  last_update_id bigint,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
SELECT bt.enable_rls('telegram_bots');

CREATE TABLE telegram_links (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL UNIQUE,
  telegram_user_id bigint NOT NULL UNIQUE,
  chat_id bigint NOT NULL,
  tg_username text,
  linked_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz,
  -- /signin: waiting for the authenticator code until this time
  signin_until timestamptz,
  signin_fail_count int NOT NULL DEFAULT 0,
  signin_fail_since timestamptz,
  signin_paused_until timestamptz,
  -- "＋ New tag": the next plain message is the tag for this prompt (about 2 minutes)
  awaiting_prompt_id uuid,
  awaiting_until timestamptz,
  awaiting_msg_id bigint
);
SELECT bt.enable_rls('telegram_links');

CREATE TABLE telegram_pairings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  code_hash text NOT NULL,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX telegram_pairings_user ON telegram_pairings (user_id);
SELECT bt.enable_rls('telegram_pairings');

CREATE TABLE telegram_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  link_id uuid NOT NULL REFERENCES telegram_links (id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  ended_at timestamptz,
  end_reason text CHECK (end_reason IN ('signout', 'idle', 'web', 'unlink', 'replaced'))
);
-- one open session per link
CREATE UNIQUE INDEX telegram_sessions_open ON telegram_sessions (link_id) WHERE ended_at IS NULL;
SELECT bt.enable_rls('telegram_sessions');

-- One row per message (tag prompt, alert / nudge, digest). `transaction_id` is a ledger id (no foreign key across services).
CREATE TABLE telegram_prompts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  seq bigserial NOT NULL,
  user_id uuid NOT NULL,
  link_id uuid NOT NULL REFERENCES telegram_links (id) ON DELETE CASCADE,
  transaction_id uuid,
  kind text NOT NULL CHECK (kind IN ('tag', 'alert', 'digest')),
  status text NOT NULL CHECK (status IN ('queued', 'held', 'sent', 'tagged', 'auto_tagged', 'expired', 'failed')),
  -- one prompt per transaction / alert / unparsed message / digest day
  dedupe_key text NOT NULL,
  direction text CHECK (direction IN ('debit', 'credit')),
  occurred_at timestamptz,
  message_id bigint,
  -- opaque callback token: callback_data is `<token>:<action>`, resolved here, never raw data
  token text NOT NULL UNIQUE,
  -- the category buttons shown on this message: [{ "id": uuid, "name": text }]
  choices jsonb,
  category_name text,
  resolved_via text CHECK (resolved_via IN ('telegram', 'web', 'rule')),
  -- alert / nudge / digest content that holds no bank detail (category name, level, pct, counts)
  meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- the prompt was re-sent by Start / Next and shows a "Next" button
  nav boolean NOT NULL DEFAULT false,
  plan_answer text CHECK (plan_answer IN ('yes', 'no')),
  revealed_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz,
  resolved_at timestamptz,
  UNIQUE (user_id, dedupe_key)
);
CREATE INDEX telegram_prompts_queue ON telegram_prompts (link_id, status, seq);
CREATE INDEX telegram_prompts_tx ON telegram_prompts (transaction_id) WHERE transaction_id IS NOT NULL;
SELECT bt.enable_rls('telegram_prompts');
