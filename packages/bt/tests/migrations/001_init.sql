CREATE TABLE notes (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, body text NOT NULL);
SELECT bt.enable_rls('notes');
CREATE TABLE audit (id bigserial PRIMARY KEY, user_id uuid NOT NULL, action text NOT NULL);
SELECT bt.enable_rls('audit');
REVOKE UPDATE, DELETE ON audit FROM CURRENT_USER;
