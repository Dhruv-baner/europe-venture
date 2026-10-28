// A tiny pass-through on your own site: it fetches the newsletter's public RSS feed and returns it unchanged.
// Why: Substack refuses requests from GitHub's servers, but usually accepts requests from Vercel's.
// The address it fetches is fixed (it cannot be used to fetch anything else), and results are cached for 10 minutes.
const FEED = 'https://scalingeurope.substack.com/feed';

export default async function handler(req, res) {
  try {
    const upstream = await fetch(FEED, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        Accept: 'application/rss+xml, application/xml;q=0.9, */*;q=0.5',
      },
    });
    const body = await upstream.text();
    if (!upstream.ok) {
      res.setHeader('Cache-Control', 'no-store');
      return res.status(502).send(`upstream status ${upstream.status}`);
    }
    res.setHeader('Content-Type', 'application/xml; charset=utf-8');
    res.setHeader('Cache-Control', 's-maxage=600, stale-while-revalidate=3600');
    return res.status(200).send(body);
  } catch (e) {
    res.setHeader('Cache-Control', 'no-store');
    return res.status(502).send('upstream error: ' + e.message);
  }
}
