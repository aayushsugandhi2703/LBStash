/** A lead sentence in pieces: plain text, a figure in bold, or a figure in bold red (`bad`). */
export type LeadPart = string | { b: string; bad?: boolean };

export const leadText = (parts: readonly LeadPart[]): string => parts.map((p) => (typeof p === 'string' ? p : p.b)).join('');
