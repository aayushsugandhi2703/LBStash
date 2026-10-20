-- transactions service schema ("transactions"), forward-only. Every table with user data: SELECT lbstash.enable_rls('table');
-- Money is bigint paise; `amount_minor > 0` with `type` carrying the direction. Balance is never stored: it is derived on read.

CREATE TABLE transactions_settings (
  user_id uuid PRIMARY KEY,
  opening_balance_minor bigint NOT NULL DEFAULT 0,
  reconcile_grace_hours int NOT NULL DEFAULT 6 CHECK (reconcile_grace_hours BETWEEN 0 AND 72),
  -- time (written in the message, or the moment of a manual check) of the newest bank balance used so far:
  -- older, out-of-order messages may not supply a balance (README 3.6)
  last_balance_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now()
);
SELECT lbstash.enable_rls('transactions_settings');

CREATE TABLE categories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  name text NOT NULL CHECK (name = lower(name) AND length(name) BETWEEN 1 AND 32),
  archived boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  -- target of the composite foreign keys below: a row can never point at another user's category
  UNIQUE (user_id, id)
);
CREATE UNIQUE INDEX categories_user_name ON categories (user_id, lower(name));
SELECT lbstash.enable_rls('categories');

CREATE TABLE transactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  type text NOT NULL CHECK (type IN ('debit', 'credit')),
  amount_minor bigint NOT NULL CHECK (amount_minor > 0),
  occurred_at timestamptz NOT NULL,
  payee text,
  -- normalised payee (lbstash.common.payee_key): what payee memory and keyword rules match on
  payee_key text,
  description text,
  reference text,
  account_last4 text,
  category_id uuid,
  source text NOT NULL CHECK (source IN ('captured', 'recurring', 'manual', 'unaccounted')),
  status text NOT NULL CHECK (status IN ('pending', 'confirmed', 'reversed')),
  dedupe_key text NOT NULL,
  recurring_id uuid,
  -- recurring rows: payee/keyword a captured debit must match to be merged into this post
  match_hint text,
  device_id uuid,
  captured_at timestamptz,
  weak_parse boolean NOT NULL DEFAULT false,
  classified_by text CHECK (classified_by IN ('memory', 'rule', 'user', 'recurring')),
  rule_pattern text,
  -- a hand-added credit / recurring post that a bank message has already been merged into
  linked boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, dedupe_key),
  -- deleting a category that has transactions is blocked: reassign or archive instead
  FOREIGN KEY (user_id, category_id) REFERENCES categories (user_id, id) ON DELETE RESTRICT
);
CREATE INDEX transactions_user_time ON transactions (user_id, occurred_at DESC, id DESC);
CREATE INDEX transactions_user_category_time ON transactions (user_id, category_id, occurred_at);
CREATE INDEX transactions_user_pending ON transactions (user_id, occurred_at) WHERE status = 'pending';
CREATE INDEX transactions_user_reference ON transactions (user_id, reference) WHERE reference IS NOT NULL;
CREATE INDEX transactions_user_payee ON transactions (user_id, payee_key) WHERE status = 'pending' AND payee_key IS NOT NULL;
SELECT lbstash.enable_rls('transactions');

-- Other dedupe keys that resolve to an existing row (a bank message merged into a hand-added credit, a recurring post,
-- an Unaccounted entry, or a reversed original), so a re-sent message is a `duplicate` instead of being merged twice.
CREATE TABLE tx_links (
  user_id uuid NOT NULL,
  dedupe_key text NOT NULL,
  transaction_id uuid NOT NULL REFERENCES transactions (id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, dedupe_key)
);
CREATE INDEX tx_links_tx ON tx_links (transaction_id);
SELECT lbstash.enable_rls('tx_links');

CREATE TABLE tag_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  category_id uuid NOT NULL,
  kind text NOT NULL CHECK (kind IN ('keyword', 'payee')),
  pattern text NOT NULL CHECK (pattern <> ''),
  hits int NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, kind, pattern),
  FOREIGN KEY (user_id, category_id) REFERENCES categories (user_id, id) ON DELETE CASCADE
);
SELECT lbstash.enable_rls('tag_rules');

CREATE TABLE balance_checks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  bank_balance_minor bigint NOT NULL,
  transactions_balance_minor bigint NOT NULL,
  gap_minor bigint NOT NULL,
  source text NOT NULL CHECK (source IN ('message', 'manual')),
  status text NOT NULL CHECK (status IN ('open', 'booked', 'resolved', 'ignored')),
  checked_at timestamptz NOT NULL,
  as_of timestamptz NOT NULL,
  transaction_id uuid REFERENCES transactions (id) ON DELETE SET NULL
);
CREATE INDEX balance_checks_user_time ON balance_checks (user_id, checked_at DESC);
-- one open check per user: a newer check supersedes the older one
CREATE UNIQUE INDEX balance_checks_one_open ON balance_checks (user_id) WHERE status = 'open';
SELECT lbstash.enable_rls('balance_checks');
