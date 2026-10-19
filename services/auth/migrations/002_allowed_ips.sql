-- Optional per-user list of addresses (IPv4/IPv6, or a CIDR range) the web app accepts. Empty = accepted from anywhere.
ALTER TABLE users ADD COLUMN allowed_ips text[] NOT NULL DEFAULT '{}' CHECK (cardinality(allowed_ips) <= 20);
