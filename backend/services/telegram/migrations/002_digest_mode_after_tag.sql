-- Settings align with the UI: digest Off / Daily / Twice a day, and after-tag Keep it / One line / Delete it.
ALTER TABLE telegram_settings ADD COLUMN digest_mode text NOT NULL DEFAULT 'daily' CHECK (digest_mode IN ('off', 'daily', 'twice'));
ALTER TABLE telegram_settings DROP CONSTRAINT telegram_settings_after_tag_check;
UPDATE telegram_settings SET after_tag = 'line' WHERE after_tag = 'edit';
ALTER TABLE telegram_settings ALTER COLUMN after_tag SET DEFAULT 'line';
ALTER TABLE telegram_settings ADD CONSTRAINT telegram_settings_after_tag_check CHECK (after_tag IN ('keep', 'line', 'delete'));
