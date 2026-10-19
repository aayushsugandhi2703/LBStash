/** The address the iPhone uses to reach the server (PHONE_URL), for the Setup guide. Not a secret and not used for sign-in. */
export const dynamic = 'force-dynamic';

export function GET(): Response {
  return Response.json({ url: process.env.PHONE_URL ?? null });
}
