export const MAX_TAG_LENGTH = 32;

type TagResult = { ok: true; tag: string } | { ok: false; error: string };

/** Stored form of a typed tag: lowercase, trimmed, spaces collapsed, leading '#' dropped (README 3.3). */
export function parseTag(raw: string): TagResult {
  const t = raw.normalize('NFKC').trim().replace(/^#+/, '').trim().toLowerCase().replace(/\s+/g, ' ');
  if (!t) return { ok: false, error: 'A tag cannot be empty' };
  if (t.length > MAX_TAG_LENGTH) return { ok: false, error: `A tag can be at most ${MAX_TAG_LENGTH} characters` };
  if (!/^[\p{L}\p{N}][\p{L}\p{N} _&'./+-]*$/u.test(t)) return { ok: false, error: 'A tag can use letters, numbers and simple punctuation' };
  return { ok: true, tag: t };
}

/** "bank charges" → "Bank charges". */
export const displayTag = (name: string): string => (name ? name.charAt(0).toUpperCase() + name.slice(1) : name);
