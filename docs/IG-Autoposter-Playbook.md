---
title: Instagram Auto-Poster — System Playbook
tags: [automation, instagram, social-media, client-systems, playbook]
status: live
created: 2026-06-01
reusable_template: true
---

# Instagram Auto-Poster — System Playbook

> Cloud-based daily Instagram auto-poster. Renders on-brand image cards, carousels, and
> stories and publishes them on a schedule with zero daily effort. Runs entirely on
> GitHub's servers — **the client's computer does not need to be on.**
> Built for **@josephborroto**; written to be **reused as a template for future clients.**

---

## 1. What it does (current, live)

**Feed posts — 3×/day (America/New_York):**
| Time | Post |
|---|---|
| ~8:37 AM | single image card (mixed format) |
| ~12:37 PM | single image card (mixed format) |
| ~7:37 PM | multi-slide **carousel** |

**Stories — 1×/day:**
| Time | Story |
|---|---|
| ~8:40 AM | story sequence (a few min after the morning feed post) |

- Single cards rotate **mixed formats**: tip, quote, myth-vs-truth, this-vs-that, value, stat, checklist, statement.
- Designs auto-rotate looks (dark / midnight / light / cream-"bone") so nothing repeats back-to-back.
- All CTAs are **follow-based** ("Follow @… for…") — never comment/DM.
- A **14-deep pre-rendered buffer** per slot guarantees there's always something to post.
- Instagram token **auto-refreshes weekly** — nothing expires.

> [!note] One story/day, never repetitive
> Stories were dialed from 2/day → 1/day (morning) because two looked repetitive.
> Stories are **live-only**: they post only inside their window and are never back-filled.

---

## 2. Reliability — why it won't miss or double-post

GitHub cron is **best-effort** (often late, occasionally dropped). These layers make the
system resilient regardless:

- **Catch-up** (`plan_slots.py`): every run also posts any earlier *feed* slot missed
  today — a dropped cron is recovered by the next run, not lost.
- **Once-per-day guard**: completion is tracked in `state.json` → `daily[YYYYMMDD]`,
  written only **after a successful post** (so a failure retries; a success never repeats).
- **Push trigger**: any push to `main` triggers a real run on GitHub's runner (push
  events are reliable, unlike cron). `paths-ignore` excludes the bot's own commits so it
  can't loop. Great for "post it now" + deploys.
- **Concurrency serialization**: two crons in the same window can't double-post — the
  second waits, re-syncs state, sees the slot done, and skips.
- **Self-heal**: anything in post history is treated as posted even if the queue manifest
  diverged — prevents re-posting an already-posted item.
- **Fault-tolerant rendering**: a content item the renderer chokes on is skipped, not
  crashed — a bad entry can never block the whole run.
- **No self-duplication**: the queue never holds the same bank entry twice (fixed a case
  where carousel queue depth `14` > carousel count `12` queued some entries twice).
- **Cross-channel de-dup** (`content_dedup.py`): a story and a feed post can **never show
  the same line** (shared quotes, lists, "5 hook formulas," etc. are skipped).

> [!warning] Run exactly ONE poster per Instagram account
> The biggest real-world failure mode is a **second automation** posting to the same
> account (an old repo, a duplicate Action, a Zapier/Make/Buffer flow). That shows up as
> duplicate/near-duplicate posts even though this repo is correct. Audit for stray posters
> and disable them. (We hit this: an older `ig-images` repo was double-posting.)

---

## 3. Architecture / files

| File | Role |
|---|---|
| `daily_run.py` | Feed engine: build buffer, pick post, publish to IG, advance rotation, de-dup |
| `post_stories.py` | Story engine: render + publish the day's story sequence |
| `plan_slots.py` | Scheduler brain: which slots to run now (catch-up + once-per-day) |
| `content_dedup.py` | Cross-channel de-dup (post vs story never share content) |
| `render_card.py` / `render_story.py` | Draw the images (League Spartan, orange `#F87C11`, 4 palettes) |
| `post_bank.json` (30) / `content_bank.json` (20) / `quote_bank.json` (11) | Single-card content |
| `carousel_bank.json` (12) | Carousels |
| `story_bank.json` (14) | Story sequences (hook→fix, series, single) |
| `state.json` | Rotation pointers, post history, daily-done flags, de-dup memory |
| `queue/` + `queue/manifest.json` | Pre-rendered buffer ("never miss a day") |
| `.github/workflows/daily-post.yml` | Schedule + catch-up + posting job |
| `.github/workflows/refresh-token.yml` | Weekly IG token refresh (Mondays) |
| `threads_post.py` | *(optional, dormant)* Threads cross-post for feed posts |

**Image hosting:** the repo serves its own rendered images from `queue/` via
`raw.githubusercontent.com/<repo>/<branch>/…`. **The repo must be public** for Instagram
to fetch them (or swap in another public image host).

---

## 4. Set up for a NEW client (reusable steps)

1. **Copy this repo** to a new GitHub repo for the client. Make it **public** (image hosting).
2. **Meta / Instagram app** → get `IG_USER_ID` and a long-lived `IG_ACCESS_TOKEN`
   (scopes: `instagram_business_content_publish` + basic). Add both as repo **Secrets**.
3. **`GH_PAT`** — a fine-grained, no-expiry PAT scoped to the new repo (Secrets + Contents).
   Powers the weekly token auto-refresh. Add as a Secret.
4. **Brand the content**: set the IG handle in captions/CTAs; fill the content banks
   (respect the Privacy rules below). Designs/fonts in `render_card.py` if rebranding.
5. **Enable Actions.** The cron + catch-up + token refresh run hands-off from there.
6. **One poster per account** — never leave a second automation pointed at the same handle.
7. *(Optional)* Threads cross-post: add `THREADS_USER_ID` + `THREADS_ACCESS_TOKEN`
   Secrets (separate Threads token — the IG one does **not** work). Feed posts only.

### Secrets summary
| Secret | Purpose |
|---|---|
| `IG_USER_ID` | Instagram business account id |
| `IG_ACCESS_TOKEN` | Long-lived IG token (auto-refreshed weekly) |
| `GH_PAT` | Fine-grained PAT so the refresh can update the token Secret |
| `THREADS_USER_ID` / `THREADS_ACCESS_TOKEN` | *(optional)* Threads cross-post |

---

## 5. Content rules (PRIVACY — important)

Never put client-identifying info in posts: no client/editor counts, client names or
niches, or specific client results/numbers. Allowed: generic short-form / editing /
content-strategy education + normal industry info. Share results only if strong **and**
fully anonymized. When in doubt, leave it out.

---

## 6. How to…

- **Post now / preview:** GitHub → **Actions → "Daily Instagram Post" → Run workflow**
  (blank = catch-up plan; `slot=` forces one; `dry_run=yes` previews without posting).
  Or just push any code/content change to `main`.
- **Add content:** add entries to the relevant bank JSON, commit + push. The buffer picks
  them up automatically (and de-dup keeps posts ≠ stories).
- **Change schedule / story slots:** edit `SLOTS` in `plan_slots.py` (start hour, feed
  slot, story on/off) and the cron list in `daily-post.yml`.
- **Missed a slot:** it self-recovers (feed) via catch-up, or run the workflow manually.

---

## 6b. On-time firing — cron-job.org trigger (free)

GitHub `schedule` (cron) is best-effort and often late. The fix: a free, punctual
external scheduler (**cron-job.org**) calls GitHub's API at the exact minute —
`workflow_dispatch` runs start within seconds (unlike `schedule`). GitHub's own crons
stay as a silent fallback.

**1. Fine-grained PAT (least privilege):** GitHub → Settings → Developer settings →
Fine-grained tokens. Resource owner `shortscreationllc-lang`; repo access **only
`ig-poster`**; permission **Actions: Read and write** (only that). Copy `github_pat_…`.

**2. cron-job.org job (free account):**
- URL: `https://api.github.com/repos/shortscreationllc-lang/ig-poster/actions/workflows/daily-post.yml/dispatches`
- Method: `POST`
- Headers: `Accept: application/vnd.github+json` · `Authorization: Bearer github_pat_…`
  · `X-GitHub-Api-Version: 2022-11-28` · `User-Agent: ig-poster-cron`
- Body: `{"ref":"main"}`
- **Schedule (the magic):** Timezone **America/New_York**, Minute **37**, Hours **8, 12, 19**,
  every day → fires 8:37a / 12:37p / 7:37p ET, auto-handling EDT/EST. One schedule, no UTC math.
- Test run → expect **HTTP 204** + a run appears in GitHub Actions. Enable failure emails.

The morning story rides the 8:37 trigger automatically (plan logic attaches it).

## 7. Known gotchas & lessons

- **GitHub cron is unreliable** — never depend on it alone. Catch-up + the push trigger are
  the safety nets. (Confirmed working: an afternoon story fired automatically once stable.)
- **One account = one poster.** Duplicate posts almost always mean a second automation.
- **IG token expires every 60 days** — the weekly refresh keeps it alive *as long as
  `GH_PAT` stays valid*. Put a reminder to renew the PAT before it expires.
- **Repo must be public** (or use another public image host) for IG to fetch images.
- **Queue depth vs bank size**: if a buffer is deeper than the bank is large, guard against
  queuing the same entry twice (now handled by unique-source de-dup).

---

## 8. Status / change log

- **2026-05-31** — went live (@josephborroto): 2 feed posts/day + stories.
- **2026-06-01** — reworked to current state:
  - 3 feed posts/day (8a/12p/7p) + 1 morning story.
  - Catch-up scheduling, state-based once-per-day guard, push trigger, concurrency.
  - Self-heal, fault-tolerant rendering, no-self-duplication.
  - Cross-channel de-dup (post ≠ story).
  - Removed the redundant story "reshare."
  - Threads cross-post built but dormant (needs Threads token).
  - Identified an external duplicate source (old `ig-images` repo) to disable.
