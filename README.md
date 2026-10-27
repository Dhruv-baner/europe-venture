# The Funding Dashboard

Everything on the page is computed from one file: `rounds.json`.
To update the dashboard, add or change rows in `rounds.json` and push. Vercel redeploys on its own.

## Files
- `rounds.json`: the data (one object per funding round).
- `europe-map.json`: fixed map geometry. Does not change.
- `lib.js`: data preparation, filters, search and chart maths.
- `FundingDashboard.jsx`: the page.
- `main.jsx`, `index.html`, `vite.config.js`, `package.json`: project setup.

## A row in rounds.json
```
{ "id": 1537, "name": "Company", "month": "2026-11", "country": "France",
  "amount": 12000000, "round": "Series A", "investors": "Fund A, Fund B",
  "category": "Fintech", "sub": "Payments", "blurb": "One-line description",
  "url": "https://source-link" }
```
- `amount` is in GBP (blank or null if undisclosed).
- `month` is `YYYY-MM`. The page shows the latest year in the file, with a year switch when more than one year is present.
- `category` and `sub` must come from the taxonomy (see `SUB_ORDER` in `lib.js`).
- Other fields in the file (`desc`, `sector`, `use`, `conf`, ...) are ignored by the page.

## Run locally
```
npm install
npm run dev
```
