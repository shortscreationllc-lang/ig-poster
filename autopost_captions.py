#!/usr/bin/env python3
"""
Caption writer for the auto-poster. Runs on Joseph's Mac (launchd, hourly).

For every approved personal video in HQ that has a transcript but no caption yet:
  1. asks Claude (headless `claude -p`, no tools) for a caption, following
     caption_playbook.md and only the CTA offers in cta_offers.json,
  2. checks it against hard rules (no dashes, hashtag cap, length, a real CTA
     keyword, no number that isn't in the transcript) and retries once with the
     problems listed,
  3. saves captions/<dropbox id>.json, commits and pushes, so the GitHub poster
     has it before the video's posting day.

The script does the git work itself; Claude only writes text.
Usage: autopost_captions.py [--rewrite-all] [--only <dropbox id>] [--dry]
"""
import argparse, datetime, json, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HQ = Path.home() / "ShortsCreation/Code/shortscreation-platform"
CAPTIONS = ROOT / "captions"
PLAYBOOK = ROOT / "caption_playbook.md"
OFFERS = ROOT / "cta_offers.json"
CLAUDE = str(Path.home() / ".local/bin/claude")
MODEL = os.getenv("CAPTION_MODEL", "claude-opus-5-5")
STATUS = Path.home() / ".claude/launchd-tasks/status/autopost-captions.json"
os.environ["PATH"] = f"{Path.home()}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"


def rules():
    cfg = json.loads((ROOT / "autopost_config.json").read_text())
    return cfg.get("captions", {"max_hashtags": 5, "max_chars": 2200, "first_line_max": 125})


def sh(cmd, cwd=ROOT, timeout=300):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def inputs():
    r = sh(["npx", "tsx", "scripts/autopost-caption-inputs.ts", "Joseph Borroto"], cwd=HQ, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f"HQ export failed: {r.stderr[-300:]}")
    return json.loads(r.stdout)


WHISPER = "/opt/homebrew/bin/whisper-cli"
WHISPER_MODEL = Path.home() / "Documents/Claude/video-analyzer/models/ggml-small.bin"
TX_CACHE = ROOT / ".transcripts"


def load_dropbox_env():
    for line in (HQ / ".env").read_text().splitlines():
        m = re.match(r"^(DROPBOX_[A-Z_]+)=(.*)$", line.strip())
        if m:
            os.environ.setdefault(m[1], m[2].strip().strip('"'))


def transcribe(link, cache_key):
    """Local Whisper for videos HQ doesn't know about (AI edits dropped straight in the queue)."""
    TX_CACHE.mkdir(exist_ok=True)
    txt = TX_CACHE / f"{cache_key}.txt"
    if txt.exists():
        return txt.read_text()
    wav = TX_CACHE / f"{cache_key}.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", link, "-ar", "16000", "-ac", "1", str(wav)],
                   check=True, timeout=600)
    subprocess.run([WHISPER, "-m", str(WHISPER_MODEL), "-l", "en", "-nt", "-otxt", "-of", str(TX_CACHE / cache_key),
                    "-f", str(wav)], check=True, capture_output=True, timeout=900)
    wav.unlink()
    return txt.read_text()


def queue_inputs(known_ids):
    """Videos sitting in the auto-post queue that HQ has no record of."""
    sys.path.insert(0, str(ROOT))
    load_dropbox_env()
    import autopost
    cfg = json.loads((ROOT / "autopost_config.json").read_text())
    dbx = autopost.Dropbox()
    out = []
    for v in dbx.videos(cfg["queue_folder"]):
        if v["id"] in known_ids:
            continue
        dur = (v.get("media_info") or {}).get("metadata", {}).get("duration")
        out.append({"dropboxId": v["id"], "title": v["name"], "path": v["path_display"],
                    "durationSec": round(dur / 1000) if dur else None, "idea": None,
                    "_link": lambda p=v["path_display"]: dbx.temp_link(p)})
    return out


def key(dropbox_id):
    return dropbox_id.replace("id:", "")


def numbers(text):
    return set(re.findall(r"\d[\d,.]*", text.replace(",", "")))


def check(c, video, offers, lim):
    problems = []
    cap = c.get("caption", "").strip()
    tags = c.get("hashtags", [])
    full = f"{cap}\n\n{' '.join(tags)}"
    if not cap:
        return ["empty caption"]
    if re.search("[—–]", full) or " - " in cap:
        problems.append("contains a dash; Joseph never uses dashes")
    if len(tags) > lim["max_hashtags"]:
        problems.append(f"{len(tags)} hashtags; max is {lim['max_hashtags']}")
    if any(not t.startswith("#") or " " in t for t in tags):
        problems.append("every hashtag must start with # and have no spaces")
    if len(full) > lim["max_chars"]:
        problems.append(f"{len(full)} characters; max {lim['max_chars']}")
    if len(cap) > lim.get("body_max_chars", 280):
        problems.append(f"caption is {len(cap)} characters before hashtags; his short captions win, keep it under {lim.get('body_max_chars', 280)}")
    first = cap.splitlines()[0]
    if first.rstrip().endswith("?"):
        problems.append("first line is a question; open with a statement")
    if len(first) > lim["first_line_max"]:
        problems.append(f"first line is {len(first)} characters; keep it under {lim['first_line_max']} so it shows before 'more'")
    kw = (c.get("cta_keyword") or "").strip()
    allowed = {o["keyword"].upper(): o for o in offers}
    if kw:
        if kw.upper() not in allowed:
            problems.append(f"CTA keyword {kw} is not one of the live offers: {', '.join(allowed)}")
        elif kw.upper() not in cap.upper():
            problems.append(f"CTA keyword {kw} is not actually in the caption")
    elif not c.get("cta_type"):
        problems.append("no CTA")
    # nothing invented: every number in the caption must come from the transcript or the offer
    source = numbers(video["transcript"]) | {n for o in offers for n in numbers(o.get("what_they_get", ""))}
    made_up = [n for n in numbers(cap) if n not in source and n.rstrip(".") not in source]
    if made_up:
        problems.append(f"numbers not said in the video: {', '.join(made_up)} (never invent stats)")
    return problems


def prompt(video, offers, feedback=None):
    p = [PLAYBOOK.read_text(),
         "\n## Live CTA offers (use ONLY these keywords; pick the one that fits the video)\n",
         json.dumps(offers, indent=2),
         "\n## The video\n",
         f"File: {video['title']} ({video.get('durationSec') or '?'} s)",
         f"Planned idea: {json.dumps(video['idea'])}" if video.get("idea") else "",
         f"Transcript (what Joseph actually says):\n{video['transcript']}",
         "\n## Output\nReply with ONLY a JSON object, no prose, no code fence:",
         '{"caption": "...", "hashtags": ["#a", "#b"], "cta_type": "comment|dm|follow|save|share",'
         ' "cta_keyword": "KEYWORD or empty", "search_keywords": ["..."], "why": "one sentence"}']
    if feedback:
        p.append("\n## Your last draft broke these rules. Fix every one:\n- " + "\n- ".join(feedback))
    return "\n".join(x for x in p if x)


def ask_claude(text):
    r = sh([CLAUDE, "-p", text, "--model", MODEL, "--output-format", "json", "--max-turns", "1"], timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"claude failed: {(r.stderr or r.stdout)[-300:]}")
    result = json.loads(r.stdout).get("result", "")
    m = re.search(r"\{.*\}", result, re.S)
    if not m:
        raise RuntimeError(f"no JSON in reply: {result[:200]}")
    return json.loads(m.group(0))


def write_one(video, offers, lim):
    feedback, c = None, None
    for attempt in (1, 2, 3):
        c = ask_claude(prompt(video, offers, feedback))
        feedback = check(c, video, offers, lim)
        if not feedback:
            break
    c.update({"video": video["title"], "written_by": f"{MODEL} via autopost_captions.py",
              "written_at": datetime.datetime.now().isoformat(timespec="seconds"),
              "open_problems": feedback or []})
    return c


def status(result, summary):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({"task": "autopost-captions", "finishedAt": datetime.datetime.now().astimezone().isoformat(),
                                  "result": result, "summary": summary[-1200:]}, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rewrite-all", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--dry", action="store_true", help="print captions, save nothing")
    a = ap.parse_args()
    lim, offers = rules(), json.loads(OFFERS.read_text())
    if not a.dry:
        sh(["git", "pull", "--rebase", "-q"])
    hq = inputs()
    todo = [v for v in hq + queue_inputs({v["dropboxId"] for v in hq})
            if (a.rewrite_all or not (CAPTIONS / f"{key(v['dropboxId'])}.json").exists())
            and (not a.only or key(v["dropboxId"]) == key(a.only))]
    if not todo:
        status("ok", "no new approved videos need captions")
        print("nothing to caption")
        return 0
    written, flagged = [], []
    for v in todo:
        try:
            if "transcript" not in v:
                v["transcript"] = transcribe(v.pop("_link")(), key(v["dropboxId"]))
            c = write_one(v, offers, lim)
        except Exception as e:
            flagged.append(f"{v['title']}: {e}")
            continue
        if c["open_problems"]:
            flagged.append(f"{v['title']}: {'; '.join(c['open_problems'])}")
        print(f"\n=== {v['title']} ===\n{c['caption']}\n\n{' '.join(c['hashtags'])}\n[{c.get('why', '')}]")
        if not a.dry:
            CAPTIONS.mkdir(exist_ok=True)
            (CAPTIONS / f"{key(v['dropboxId'])}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n")
            written.append(v["title"])
    if written and not a.dry:
        sh(["git", "add", "captions"])
        sh(["git", "commit", "-q", "-m", f"captions: {', '.join(written)[:180]}"])
        for _ in range(3):
            if sh(["git", "pull", "--rebase", "-q"]).returncode == 0 and sh(["git", "push", "-q"]).returncode == 0:
                break
            time.sleep(5)
        else:
            flagged.append("git push failed; captions are saved locally only")
    summary = f"captioned {len(written)}: {', '.join(written)}" + (f" | problems: {' / '.join(flagged)}" if flagged else "")
    status("fail" if flagged else "ok", summary)
    print("\n" + summary)
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
