/** Landing page for the Telegram "Open Google Pay" button: Telegram buttons only open web links, so this hands the phone to the app. */
export const dynamic = 'force-dynamic';

const PAGE = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Google Pay</title>
<style>body{font:16px system-ui,sans-serif;margin:0;min-height:100vh;display:grid;place-items:center;background:#111;color:#eee}a{display:block;margin:12px 0;padding:14px 22px;border-radius:10px;background:#2a2a2a;color:#fff;text-align:center;text-decoration:none}</style></head>
<body><div><a id="open" href="gpay://">Open Google Pay</a><a href="https://pay.google.com/">Open on the web</a></div>
<script>
var ua = navigator.userAgent;
var app = /Android/.test(ua) ? 'intent://#Intent;package=com.google.android.apps.nbu.paisa.user;end' : 'gpay://';
document.getElementById('open').href = app;
window.location.href = app;
</script></body></html>`;

export function GET(): Response {
  return new Response(PAGE, { headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' } });
}
