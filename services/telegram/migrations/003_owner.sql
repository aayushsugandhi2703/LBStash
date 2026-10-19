-- The one Telegram account allowed to link this bot: a username (lower case, no @) or a numeric id. Pairing is refused for anyone else.
ALTER TABLE telegram_bots ADD COLUMN owner_tg text CHECK (owner_tg IS NULL OR length(owner_tg) BETWEEN 1 AND 64);
