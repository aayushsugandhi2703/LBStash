-- ingest service schema ("ingest"), forward-only. Every table with user data: SELECT lbstash.enable_rls('table');

-- Devices: one row per phone/Shortcut. The ingest token is shown once; only its sha256 is stored (README 15.3).
CREATE TABLE devices (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                 uuid NOT NULL,
  name                    text NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
  token_hash              text NOT NULL UNIQUE,
  -- masked token for display ("ledg_live_8f3a…b605"); not enough to use or guess the token
  token_hint              text NOT NULL,
  -- the owner's IANA zone, taken from the request that made the token: times written in a bank message are local
  tz                      text NOT NULL DEFAULT 'Asia/Kolkata',
  -- optional sender allow-list (normalised ids such as HDFCBK); empty = accept every sender
  allowed_senders         text[] NOT NULL DEFAULT '{}',
  created_at              timestamptz NOT NULL DEFAULT now(),
  rotated_at              timestamptz,
  last_seen_at            timestamptz,
  last_delay_seconds      integer CHECK (last_delay_seconds IS NULL OR last_delay_seconds >= 0),
  last_test_at            timestamptz,
  last_test_source        text CHECK (last_test_source IN ('device', 'web')),
  last_test_delay_seconds integer CHECK (last_test_delay_seconds IS NULL OR last_test_delay_seconds >= 0),
  last_test_amount_minor  bigint CHECK (last_test_amount_minor IS NULL OR last_test_amount_minor > 0),
  revoked_at              timestamptz
);
CREATE INDEX devices_user_idx ON devices (user_id, created_at DESC);
SELECT lbstash.enable_rls('devices');

-- Ingest events: the nonce transactions for replay protection. No message text, no payload hash, no amounts.
CREATE TABLE ingest_events (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid NOT NULL,
  device_id      uuid NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
  nonce          text NOT NULL,
  received_at    timestamptz NOT NULL DEFAULT now(),
  outcome        text NOT NULL DEFAULT 'received'
                 CHECK (outcome IN ('received', 'created', 'duplicate', 'linked_manual', 'linked_recurring', 'replaced_unaccounted',
                                    'reversed_original', 'saved_as_credit', 'test', 'unparsed')),
  transaction_id uuid,
  UNIQUE (device_id, nonce)
);
CREATE INDEX ingest_events_user_outcome_idx ON ingest_events (user_id, outcome, received_at DESC);
CREATE INDEX ingest_events_received_idx ON ingest_events (received_at);
SELECT lbstash.enable_rls('ingest_events');

-- Messages the parser could not read: encrypted (AES-256-GCM, aad = user id), masked before encryption, 30 days at most.
CREATE TABLE unparsed_messages (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL,
  device_id   uuid NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
  body_enc    bytea NOT NULL,
  reason      text NOT NULL CHECK (reason IN ('no_amount', 'direction_unclear', 'unreadable')),
  received_at timestamptz NOT NULL,
  status      text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'dismissed', 'expired')),
  expires_at  timestamptz NOT NULL DEFAULT now() + interval '30 days',
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX unparsed_user_status_idx ON unparsed_messages (user_id, status, received_at DESC);
CREATE INDEX unparsed_expires_idx ON unparsed_messages (expires_at);
SELECT lbstash.enable_rls('unparsed_messages');
