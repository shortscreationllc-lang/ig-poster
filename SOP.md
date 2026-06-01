# Instagram Auto-Poster — SOP

> Automated daily Instagram poster for **@josephborroto**. Renders on-brand image cards + carousels and posts them on a schedule, zero daily effort. **Live and self-sustaining since 2026-05-31.** Runs entirely in the cloud — your computer does NOT need to be on.

---

## 1. What it does
- Auto-posts twice a day to **@josephborroto**: **8 AM ET** = single image card, **8 PM ET** = multi-slide carousel.
- Designs auto-rotate across **4 looks** (warm-black, navy, white, cream) so nothing repeats back-to-back.
- All CTAs are **follow-based** ("Follow @josephborroto for…") — never comment/DM, so no inbound to service.
- Keeps a **14-deep buffer** of pre-rendered posts per slot — never misses a day.
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

## 7b. Stories (LIVE since 2026-06-01)
Every morning, alongside the 8 AM feed post, it posts **2 stories**:
1. **Hook story** — a bold attention-grabber (from `story_bank.json` → `hooks`) to pull people into your stories. Rotates daily, alternates dark/navy.
2. **Reshare story** — the actual feed card of the day, framed in a 9:16 story with "Just posted → see it on my feed."

Files: `render_story.py` (draws the 9:16 stories), `post_stories.py` (posts them), `story_bank.json` (the hook lines — edit/add freely).
Limits (Instagram, not us): API stories are image or single video only — **no tappable post-link sticker, no polls, no music/trending audio**. The reshare drives people to your profile, just not auto-linked.
Add hooks: edit `story_bank.json` → `hooks` array, commit + push.

## 8. Roadmap — FUTURE: video posts
Currently images + carousels only. Next phase = **video / Reels** (possibly from the Dropbox video inventory). Notes for later:
- IG API posts video via `media_type=REELS` + a public `video_url` (same "must be a public link" rule — host the file, then publish).
- Same buffer + schedule + token-refresh architecture extends to video; add a video source + publish path in `daily_run.py`.
- Keep the same privacy rules.

## 9. Proof it's live (first real posts, 2026-05-31, @josephborroto)
- Single (manual): https://www.instagram.com/p/DZA9FMHlGcE/
- Single (auto/cloud): https://www.instagram.com/p/DZBAbL7IPo2/
- Carousel (auto/cloud): https://www.instagram.com/p/DZBCZz3iQWo/
