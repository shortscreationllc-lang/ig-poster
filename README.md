# Instagram API Poster

Local tool for publishing Joseph's posts to `@josephborroto` through the official Instagram Graph API.

## What This Does

- Checks that the Instagram API token works.
- Creates an Instagram media container.
- Waits for Meta to finish processing it.
- Publishes the container to the account.
- Supports single-image feed posts first.

## What You Need

Create a config file:

```bash
cp /Users/josephborroto/Downloads/instagram-api-poster/.env.example /Users/josephborroto/Downloads/instagram-api-poster/.env
```

Fill in:

```bash
IG_USER_ID="your_instagram_professional_account_id"
IG_ACCESS_TOKEN="your_long_lived_access_token"
GRAPH_VERSION="v25.0"
IG_API_HOST="graph.instagram.com"
```

The token needs publishing access for the Instagram professional account.

## Important Media Rule

The Instagram API needs a public, direct `image_url`. A normal local file path will not work.

Good:

```text
https://example.com/my-photo.jpg
```

Not good:

```text
/Users/josephborroto/Desktop/photo.jpg
```

## Check Connection

```bash
/Users/josephborroto/Downloads/instagram-api-poster/ig_check.py
```

## Dry Run

```bash
/Users/josephborroto/Downloads/instagram-api-poster/ig_post.py \
  --image-url "https://example.com/photo.jpg" \
  --caption "Test caption" \
  --alt-text "Test image" \
  --dry-run
```

## Real Post

```bash
/Users/josephborroto/Downloads/instagram-api-poster/ig_post.py \
  --image-url "https://example.com/photo.jpg" \
  --caption "Your caption here" \
  --alt-text "Alt text here"
```

## Fully Automatic Post

This creates the image, writes the caption, uploads the image to a public host, then publishes it:

```bash
/Users/josephborroto/Downloads/instagram-api-poster/auto_post.py
```

One-time image hosting setup is required because Instagram cannot publish a local Mac file.

Recommended:

```bash
IMAGE_HOST="cloudinary"
CLOUDINARY_CLOUD_NAME="your_cloud_name"
CLOUDINARY_UPLOAD_PRESET="your_unsigned_upload_preset"
```

Dropbox alternative:

```bash
IMAGE_HOST="dropbox"
DROPBOX_ACCESS_TOKEN="your_dropbox_api_token"
DROPBOX_FOLDER="/Instagram Auto Posts"
```

Generate only the image/caption package:

```bash
/Users/josephborroto/Downloads/instagram-api-poster/create_post_asset.py
```

Test the full flow without publishing:

```bash
/Users/josephborroto/Downloads/instagram-api-poster/auto_post.py --dry-run
```
