---
name: Image2
description: "帮助您用自然语言生成图片，并通过 Tokenlane 的 gpt-image-2 图片 API 在 Codex Desktop 里直接显示结果。适用于“生成图片”、“用 tokenlane 画图”、“gpt-image-2 出图”、“image-2 作图”等请求。"
---

# Image2

Use this skill when the user wants image generation through Tokenlane. The goal is to call Tokenlane's OpenAI-compatible Images API, save returned `b64_json` images as local files, and display those files directly in Codex Desktop.

## Rules

- Always use the Tokenlane Images API endpoint: `https://api.tokenlane.tech/v1/images/generations`.
- Always use `gpt-image-2` as the actual API model. If the user says `image-2`, `gpt-image-1`, `gpt-image-1.5`, or any other model, still call `gpt-image-2`.
- Use the bundled script from the active skill directory: `scripts/generate_image.py`.
- Default size is `1024x1024`.
- Natural size mapping:
  - Square/default/方图/正方形: `1024x1024`
  - Landscape/横图/宽图: `1536x1024`
  - Portrait/竖图/海报: `1024x1536`
  - `auto` is also accepted when explicitly requested.
- If the user asks for multiple images, pass `--count N`. The script allows `1` to `4`; use `4` if the user asks for more than 4.
- Do not print or expose API keys, Authorization headers, raw `b64_json`, or secrets.
- Do not use `/v1/responses` or image editing endpoints for image generation. Use the bundled script.
- The script prefers system `curl` for the HTTPS request because some Cloudflare configurations reject Python's default `urllib` client signature. It falls back to `urllib` only when `curl` is unavailable.

## Workflow

1. Extract the final image prompt from the user's request.
2. Infer `--size` and `--count` from natural language.
3. Run the bundled script:

```bash
python3 /path/to/Image2/scripts/generate_image.py \
  --prompt "IMAGE PROMPT HERE" \
  --size 1024x1024 \
  --count 1
```

4. Parse the JSON printed by the script.
5. Prefer `output_paths`. Display each image with absolute-path Markdown:

```markdown
![generated image](/absolute/path/to/generated-1.png)
![generated image](/absolute/path/to/generated-2.png)
```

6. If only `output_path` is present, display that single file.
7. Keep the final response short. Do not explain Base64 unless the user asks.

## API key discovery

The script uses this order:

1. `TOKENLANE_API_KEY`
2. `IMAGE2_API_KEY`
3. `~/.codex/Image2/api_key`
4. `~/.codex/Image2/config.json` field `api_key`
5. `~/.codex/auth.json` field `OPENAI_API_KEY`, but only if `~/.codex/config.toml` contains `api.tokenlane.tech`

If no source is available, tell the user to configure the key outside the chat. On macOS Desktop, terminal `export` often does not reach an already running Codex app, so the most reliable local setup is a private key file:

```bash
mkdir -p ~/.codex/Image2
printf '%s' 'YOUR_TOKENLANE_KEY' > ~/.codex/Image2/api_key
chmod 600 ~/.codex/Image2/api_key
```

## Failure handling

- Missing key: ask the user to configure `~/.codex/Image2/api_key` or `TOKENLANE_API_KEY`.
- HTTP 401/403: tell the user the Tokenlane key or permissions need checking.
- HTTP 429: tell the user Tokenlane image generation is rate limited and to retry later.
- HTTP 503: tell the user Tokenlane image generation is temporarily unavailable and to retry later.
- For other failures, show the script's short stderr message only; do not expose secrets or raw response bodies.
