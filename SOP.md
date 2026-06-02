# Instagram Auto-Poster — SOP

> Automated daily Instagram poster for **@josephborroto**. Renders on-brand image cards + carousels + stories and posts them on a schedule, zero daily effort. **Live and self-sustaining since 2026-05-31.** Runs entirely in the cloud — your computer does NOT need to be on.
>
> 📘 **Full system + reusable client playbook:** [`docs/IG-Autoposter-Playbook.md`](docs/IG-Autoposter-Playbook.md) (also saved to Obsidian/Drive for future clients).

---

## 1. What it does
- **Feed: 3 posts/day (ET)** — ~8:37 AM single card (mixed format), ~12:37 PM single card, ~7:37 PM carousel.
- **Stories: 1/day** — ~8:40 AM, a few minutes after the morning feed post.
- Single cards rotate **mixed formats** (tip / quote / myth / versus / value / stat / checklist / statement).
- Designs auto-rotate across **4 looks** (dark / midnight / light / cream) so nothing repeats back-to-back.
- All CTAs are **follow-based** ("Follow @josephborroto for…") — never comment/DM, so no inbound to service.
- Keeps a **14-deep buffer** of pre-rendered posts per slot — never misses a day; auto-recovers a dropped cron (catch-up).
- A **cross-channel de-dup guard** ensures a story and a feed post never show the same content.
- Instagram token **refreshes itself weekly** — nothing expires.

## 2. Does my computer need to be on?
**No.** Posting happens on GitHub's servers (GitHub Actions). Your Mac is only needed when *editing* the system (content, design, schedule) with Claude.

## 3. Where it lives
- **GitHub repo:** `shortscreationllc-lang/ig-poster` (public) — code, content, schedule, and image hosting.
- **Local copy (edits only):** `/Users/josephborroto/Downloads/instagram-api-poster/`
- **GitHub account:** `shortscreationllc-lang` (shortscreationllc@gmail.com)

## 4. Content rules (PRIVACY — important)
Never put client-identifying info in posts: no client/editor counts, no client names or niches, no specific client results/numbers (e.g. "1.4M views," "$1,600 retainer," "Miami realtor"). Allowed: generic short-form/editing/content-strategy education + normal industry info. Only share results if strong AND fully anonymized; when in doubt, leave it out.

## 5. The pieces
| File | What it is |
|---|---|
| `post_bank.json` | Single-card posts (30). |
| `carousel_bank.json` | Carousels (12). |
| `render_card.py` | Draws images — League Spartan font, orange `#F87C11`, 4 palettes. |
| `daily_run.py` | Engine: picks post, fills buffer, posts to IG, advances rotation. |
| `state.json` | Tracks what's next so nothing repeats. |
| `queue/` | Pre-rendered buffer ("never miss a day" stockpile). |
| `.github/workflows/daily-post.yml` | The 8AM/8PM schedule. |
| `.github/workflows/refresh-token.yml` | Weekly IG token refresh (Mondays). |

## 6. How to…
- **Add posts:** add entries to `post_bank.json` / `carousel_bank.json` (keep privacy rules), commit + push. Buffer auto-picks them up.
- **Change times:** edit the cron + hour gate in `daily-post.yml`.
- **Post now / preview:** GitHub → Actions → "Daily Instagram Post" → Run workflow → pick `slot` am/pm; `dry_run=yes` previews without posting.
- **Missed day:** manually run the workflow (buffer always has content ready).

## 7. Secrets (encrypted in repo, never in files)
- `IG_USER_ID`, `IG_ACCESS_TOKEN` (auto-refreshed weekly).
- `GH_PAT` — **no-expiry** fine-grained token named "IG Post" (scoped to ig-poster, Secrets + Contents). Keeps refresh self-sustaining.
- Old classic setup token (`ghp_…`) is unused — delete at github.com/settings/tokens → "Tokens (classic)". Must be done in the browser; cannot be revoked via API.

## 7b. Stories (LIVE since 2026-06-01; reworked to 1/day)
**One story a day**, ~8:40 AM (a few minutes after the morning feed post). It posts a
**story sequence** from `story_bank.json` → `sequences` (a hook→fix pair, a multi-slide
series, or a single statement/quote). Rotates daily; morning uses the cream "bone" palette.
- Stories are **live-only** — posted only in their window, never back-filled.
- The cross-channel de-dup guard means a story never repeats that day's feed content.
- The old "reshare the feed card" story was **removed** (redundant / could grab a mismatch).

Files: `render_story.py` (draws the 9:16 stories), `post_stories.py` (posts them),
`story_bank.json` (the sequences — edit/add freely).
Limits (Instagram, not us): API stories are image or single video only — **no tappable
post-link sticker, no polls, no music/trending audio**.
Add/edit: change `story_bank.json` → `sequences`, commit + push.

## 8. Roadmap — FUTURE: video posts
Currently images + carousels only. Next phase = **video / Reels** (possibly from the Dropbox video inventory). Notes for later:
- IG API posts video via `media_type=REELS` + a public `video_url` (same "must be a public link" rule — host the file, then publish).
- Same buffer + schedule + token-refresh architecture extends to video; add a video source + publish path in `daily_run.py`.
- Keep the same privacy rules.

## 9. Proof it's live (first real posts, 2026-05-31, @josephborroto)
- Single (manual): https://www.instagram.com/p/DZA9FMHlGcE/
- Single (auto/cloud): https://www.instagram.com/p/DZBAbL7IPo2/
- Carousel (auto/cloud): https://www.instagram.com/p/DZBCZz3iQWo/
