-- planning service schema ("planning"), forward-only. Every table with user data: SELECT lbstash.enable_rls('table');
-- Category ids point into the transactions's categories: no foreign key across services; names are fetched from the transactions.

CREATE TABLE planning_settings (
  user_id uuid PRIMARY KEY,
  alert_level int NOT NULL DEFAULT 80 CHECK (alert_level IN (70, 80, 90)),
  warn_on_pace boolean NOT NULL DEFAULT true,
  -- last time zone seen on a request for this user; names the budget period when an event does not carry one
  tz text,
  updated_at timestamptz NOT NULL DEFAULT now()
);
SELECT lbstash.enable_rls('planning_settings');

CREATE TABLE plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  month text NOT NULL CHECK (month ~ '^\d{4}-(0[1-9]|1[0-2])$'),
  total_minor bigint NOT NULL DEFAULT 0 CHECK (total_minor >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, month)
);
SELECT lbstash.enable_rls('plans');

CREATE TABLE plan_lines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  plan_id uuid NOT NULL REFERENCES plans (id) ON DELETE CASCADE,
  category_id uuid NOT NULL,
  allocated_minor bigint NOT NULL CHECK (allocated_minor >= 0),
  position int NOT NULL DEFAULT 0,
  UNIQUE (plan_id, category_id)
);
CREATE INDEX plan_lines_plan ON plan_lines (plan_id, position);
SELECT lbstash.enable_rls('plan_lines');

-- One row per credit already added to a plan total: makes the internal endpoint and the credit.added event safe together.
CREATE TABLE plan_credits (
  user_id uuid NOT NULL,
  transaction_id uuid NOT NULL,
  month text NOT NULL,
  amount_minor bigint NOT NULL CHECK (amount_minor > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, transaction_id)
);
SELECT lbstash.enable_rls('plan_credits');

CREATE TABLE budgets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  category_id uuid NOT NULL,
  limit_minor bigint NOT NULL CHECK (limit_minor > 0),
  period text NOT NULL DEFAULT 'monthly' CHECK (period = 'monthly'),
  warn_pct int CHECK (warn_pct BETWEEN 50 AND 99),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, category_id)
);
SELECT lbstash.enable_rls('budgets');

CREATE TABLE alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  budget_id uuid NOT NULL REFERENCES budgets (id) ON DELETE CASCADE,
  period_key text NOT NULL,
  level text NOT NULL CHECK (level IN ('alert', 'exceeded')),
  pct int NOT NULL,
  -- the category's name when the alert fired (a notification is a snapshot; reading alerts never calls the transactions)
  category_name text NOT NULL,
  sent_at timestamptz NOT NULL DEFAULT now(),
  read_at timestamptz,
  UNIQUE (budget_id, period_key, level)
);
CREATE INDEX alerts_user_sent ON alerts (user_id, sent_at DESC);
SELECT lbstash.enable_rls('alerts');
