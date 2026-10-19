-- recurring service schema ("recurring"), forward-only.
CREATE TABLE recurring_rules (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL,
  name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
  note            text CHECK (note IS NULL OR length(note) <= 120),
  -- ledger category id (another service's row: no foreign key across schemas)
  category_id     uuid NOT NULL,
  amount_minor    bigint NOT NULL CHECK (amount_minor > 0),
  kind            text NOT NULL CHECK (kind IN ('monthly', 'weekly', 'yearly')),
  day_of_month    smallint CHECK (day_of_month BETWEEN 1 AND 31),
  weekday         smallint CHECK (weekday BETWEEN 0 AND 6),
  month_of_year   smallint CHECK (month_of_year BETWEEN 1 AND 12),
  next_due        date NOT NULL,
  -- last occurrence handled (handed to the ledger, or skipped by the user); next_due is always after it
  last_handled_due date,
  paused          boolean NOT NULL DEFAULT false,
  ends_on         date,
  match_hint      text CHECK (match_hint IS NULL OR length(match_hint) <= 100),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CHECK (
    (kind = 'monthly' AND day_of_month IS NOT NULL AND weekday IS NULL AND month_of_year IS NULL) OR
    (kind = 'weekly'  AND weekday IS NOT NULL AND day_of_month IS NULL AND month_of_year IS NULL) OR
    (kind = 'yearly'  AND day_of_month IS NOT NULL AND month_of_year IS NOT NULL AND weekday IS NULL)
  )
);
CREATE INDEX recurring_rules_user ON recurring_rules (user_id, next_due);
-- the cron scan: due, running rules across all users
CREATE INDEX recurring_rules_due ON recurring_rules (next_due) WHERE NOT paused;
SELECT bt.enable_rls('recurring_rules');
