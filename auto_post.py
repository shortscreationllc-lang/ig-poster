#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(command, **kwargs):
    return subprocess.check_output(command, cwd=ROOT, text=True, **kwargs).strip()


def main():
    parser = argparse.ArgumentParser(description="Create, upload, and publish one Instagram tip post.")
    parser.add_argument("--index", type=int, default=None, help="Post bank index to use.")
    parser.add_argument("--dry-run", action="store_true", help="Create and upload, but do not publish.")
    args = parser.parse_args()

    create_cmd = [str(ROOT / "create_post_asset.py")]
    if args.index is not None:
        create_cmd += ["--index", str(args.index)]
    package = json.loads(run(create_cmd))

    image_url = run([str(ROOT / "upload_image.py"), package["image_path"]])
    caption = Path(package["caption_path"]).read_text()
    alt_text = Path(package["alt_path"]).read_text()

    if args.dry_run:
        print(json.dumps({
            "headline": package["headline"],
            "image_path": package["image_path"],
            "image_url": image_url,
            "caption_path": package["caption_path"],
            "alt_path": package["alt_path"],
            "would_publish": False,
        }, indent=2))
        return 0

    subprocess.check_call([
        str(ROOT / "ig_post.py"),
        "--image-url", image_url,
        "--caption", caption,
        "--alt-text", alt_text,
    ], cwd=ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
