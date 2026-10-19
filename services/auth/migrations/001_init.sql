-- auth service schema ("auth"), forward-only. Every table with user data: SELECT bt.enable_rls('table');

-- ---------------------------------------------------------------------------------------------
-- users: one row per account. Secrets are encrypted (TOTP, AES-256-GCM with the user id as AAD)
-- or hashed (password, Argon2id). `last_totp_step` makes an authenticator code usable once.
-- ---------------------------------------------------------------------------------------------
CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL CHECK (email = lower(email) AND length(email) BETWEEN 3 AND 254),
  password_hash text NOT NULL,
  name text CHECK (name IS NULL OR length(name) BETWEEN 1 AND 80),
  timezone text NOT NULL DEFAULT 'Asia/Kolkata',
  totp_secret_enc bytea,
  totp_pending_enc bytea,
  totp_enabled_at timestamptz,
  last_totp_step bigint,
  -- set when the authenticator is enabled AND a recovery set exists; until then sessions are setup-limited
  setup_completed_at timestamptz,
  pending_email text,
  delete_after timestamptz,
  password_changed_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_email_key ON users (email);
CREATE INDEX users_delete_after ON users (delete_after) WHERE delete_after IS NOT NULL;
SELECT bt.enable_rls('users', 'id');

-- ---------------------------------------------------------------------------------------------
-- sessions: one row per signed-in browser. `family_id` ties the session to its refresh tokens; revoking
-- the family (sign out, reuse detection, password change) ends it everywhere at once.
-- ---------------------------------------------------------------------------------------------
CREATE TABLE sessions (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  family_id uuid NOT NULL,
  device text NOT NULL DEFAULT 'Unknown browser',
  ip text,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_used_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  revoked_reason text
);
CREATE INDEX sessions_user ON sessions (user_id, created_at DESC);
CREATE INDEX sessions_family ON sessions (family_id);
SELECT bt.enable_rls('sessions');

-- Every refresh token ever issued for a session, hashed. A token that was already rotated and is shown again
-- means it was copied: the whole family is revoked.
CREATE TABLE refresh_tokens (
  token_hash text PRIMARY KEY,
  session_id uuid NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  used_at timestamptz,
  expires_at timestamptz NOT NULL
);
CREATE INDEX refresh_tokens_session ON refresh_tokens (session_id);
SELECT bt.enable_rls('refresh_tokens');

-- ---------------------------------------------------------------------------------------------
-- auth_factors: passkeys (public key, credential id, counter) and recovery codes (hash, used_at).
-- ---------------------------------------------------------------------------------------------
CREATE TABLE auth_factors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('passkey', 'recovery_code')),
  label text,
  public_key bytea,
  credential_id text,
  counter bigint NOT NULL DEFAULT 0,
  transports jsonb,
  code_hash text,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_used_at timestamptz,
  used_at timestamptz,
  revoked_at timestamptz,
  CHECK ((kind = 'passkey' AND public_key IS NOT NULL AND credential_id IS NOT NULL)
      OR (kind = 'recovery_code' AND code_hash IS NOT NULL))
);
CREATE UNIQUE INDEX auth_factors_credential ON auth_factors (credential_id) WHERE credential_id IS NOT NULL;
CREATE UNIQUE INDEX auth_factors_code ON auth_factors (user_id, code_hash) WHERE code_hash IS NOT NULL;
CREATE INDEX auth_factors_user ON auth_factors (user_id, kind);
SELECT bt.enable_rls('auth_factors');

-- ---------------------------------------------------------------------------------------------
-- challenges: short-lived single-use server-side state of a multi-step flow. Tokens are stored hashed.
--   login            password accepted, second step pending (token = twoFactorToken)
--   reset            recovery code accepted, new password pending
--   passkey_register WebAuthn registration challenge (no token)
-- ---------------------------------------------------------------------------------------------
CREATE TABLE challenges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('login', 'reset', 'passkey_register')),
  token_hash text UNIQUE,
  attempts int NOT NULL DEFAULT 0,
  -- reset: the recovery code accepted in step 1, used up in step 2
  factor_id uuid,
  webauthn_challenge text,
  ip text,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  used_at timestamptz
);
CREATE INDEX challenges_user ON challenges (user_id, kind);
CREATE INDEX challenges_expires ON challenges (expires_at);
SELECT bt.enable_rls('challenges');

-- Confirmation links for "change my e-mail" (hashed, single use).
CREATE TABLE email_changes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  new_email text NOT NULL,
  token_hash text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  used_at timestamptz
);
CREATE INDEX email_changes_user ON email_changes (user_id);
SELECT bt.enable_rls('email_changes');

-- ---------------------------------------------------------------------------------------------
-- login_throttle: persisted progressive lockout per (email, ip) and per second-step. Keys are hashes, so no
-- e-mail address or ip is stored here. Not user data (it must work for e-mails that do not exist), so no RLS.
-- ---------------------------------------------------------------------------------------------
CREATE TABLE login_throttle (
  key_hash text PRIMARY KEY,
  failures int NOT NULL DEFAULT 0,
  locked_until timestamptz,
  last_failure_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------------------------
-- audit_log: append-only. UPDATE and DELETE are revoked AND a trigger raises, so neither a bug nor a
-- privileged session can quietly rewrite history. No amounts, payees or message text ever go in `meta`.
-- The only exception is account deletion (hard delete): purge_user_audit(), which refuses to run for a user
-- that still exists.
-- ---------------------------------------------------------------------------------------------
CREATE TABLE audit_log (
  id bigserial PRIMARY KEY,
  user_id uuid NOT NULL,
  device_id uuid,
  action text NOT NULL CHECK (length(action) BETWEEN 1 AND 64),
  ip text,
  meta jsonb,
  at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_user ON audit_log (user_id, id DESC);
SELECT bt.enable_rls('audit_log');

CREATE FUNCTION audit_log_guard() RETURNS trigger LANGUAGE plpgsql AS $f$
BEGIN
  IF TG_OP = 'DELETE' AND current_setting('auth.purging_user', true) = OLD.user_id::text THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'audit_log is append-only' USING ERRCODE = 'insufficient_privilege';
END $f$;

CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_guard();
CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION audit_log_guard();

CREATE FUNCTION purge_user_audit(uid uuid) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, auth AS $f$
DECLARE n bigint;
BEGIN
  IF current_setting('app.system', true) IS DISTINCT FROM 'on' THEN
    RAISE EXCEPTION 'purge_user_audit is for the retention job only' USING ERRCODE = 'insufficient_privilege';
  END IF;
  IF EXISTS (SELECT 1 FROM auth.users WHERE id = uid) THEN
    RAISE EXCEPTION 'account still exists' USING ERRCODE = 'insufficient_privilege';
  END IF;
  EXECUTE format('GRANT DELETE ON auth.audit_log TO %I', current_user);
  PERFORM set_config('auth.purging_user', uid::text, true);
  DELETE FROM auth.audit_log WHERE user_id = uid;
  GET DIAGNOSTICS n = ROW_COUNT;
  PERFORM set_config('auth.purging_user', '', true);
  EXECUTE format('REVOKE DELETE ON auth.audit_log FROM %I', current_user);
  RETURN n;
END $f$;
REVOKE ALL ON FUNCTION purge_user_audit(uuid) FROM PUBLIC;

REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM CURRENT_USER;
