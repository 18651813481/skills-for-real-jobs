---
name: codex-config-fixer
description: "修复客户贴来的 Codex config.toml，尤其是 Windows 沙盒配置、缺失 Tokenlane 中转 provider、reconnecting、Mac/Windows Codex 安装配置，输出可直接复制的 config.toml 和 auth.json。"
---

# Codex Config Fixer

Use this skill when the user asks to fix a customer's Codex `config.toml`, generate a copyable Codex config for Mac or Windows, troubleshoot `reconnecting` when other users can reach Tokenlane, or replace invalid Windows sandbox settings such as `[windows] sandbox = "elevated"`.

## Output rules

- Reply in concise Chinese.
- Give copyable content only; do not write a long tutorial.
- Start with the target path and say to replace the whole `config.toml`.
- Then provide the `auth.json` path and JSON placeholder.
- Never ask for or print a real customer API key.
- Use this placeholder exactly: `这里换成他的中转 API Key`.
- If the input contains `[windows] sandbox = "elevated"`, explicitly say to delete it.
- Do not include `[windows] sandbox = "elevated"` in the repaired config.

## Defaults

- Fixed gateway:
  - `base_url = "https://tokenlane.tech"`
- Fixed provider:
  - `model_provider = "OpenAI"`
  - `[model_providers.OpenAI]`
  - `name = "OpenAI"`
  - `wire_api = "responses"`
  - `requires_openai_auth = true`
- Always replace the customer's original `model` with `gpt-5.5` to avoid old-model routing conflicts.
- Always use `model_reasoning_effort = "medium"`.
- Always include:
  - `review_model = "gpt-5.5"`
  - `disable_response_storage = true`
  - `network_access = "enabled"`
  - `model_context_window = 1000000`
  - `model_auto_compact_token_limit = 900000`

## OS detection

Treat the customer as Windows if any of these are present:

- A path like `C:\Users\...`
- A path like `\\?\C:\Users\...`
- A TOML section `[windows]`
- The user says Windows.

Treat the customer as Mac if any of these are present:

- A path like `/Users/...`
- The user says Mac or macOS.

When unsure, infer from the config paths. If still unknown, provide Windows first only if the pasted config contains `[windows]`; otherwise provide a generic `~/.codex` Mac/Linux style config.

## Windows config template

Include Windows sandbox fields at top level:

```toml
model_provider = "OpenAI"
model = "gpt-5.5"
review_model = "gpt-5.5"
model_reasoning_effort = "medium"
disable_response_storage = true
network_access = "enabled"
sandbox_mode = "danger-full-access"
windows_wsl_setup_acknowledged = true
model_context_window = 1000000
model_auto_compact_token_limit = 900000

[model_providers.OpenAI]
name = "OpenAI"
base_url = "https://tokenlane.tech"
wire_api = "responses"
requires_openai_auth = true
```

Then append preserved local sections from the customer's input.

Windows `auth.json`:

```json
{
  "OPENAI_API_KEY": "这里换成他的中转 API Key"
}
```

## Mac config template

Do not include Windows sandbox fields for Mac.

```toml
model_provider = "OpenAI"
model = "gpt-5.5"
review_model = "gpt-5.5"
model_reasoning_effort = "medium"
disable_response_storage = true
network_access = "enabled"
model_context_window = 1000000
model_auto_compact_token_limit = 900000

[model_providers.OpenAI]
name = "OpenAI"
base_url = "https://tokenlane.tech"
wire_api = "responses"
requires_openai_auth = true
```

Then append preserved local sections from the customer's input.

Mac `auth.json`:

```json
{
  "OPENAI_API_KEY": "这里换成他的中转 API Key"
}
```

## Preserve local sections

Copy these sections from the customer's input exactly, including their body lines:

- `[marketplaces.openai-bundled]`
- `[plugins."browser-use@openai-bundled"]`
- Any `[projects...]` section.

Do not preserve:

- `[windows]`
- Existing incomplete `[model_providers.OpenAI]`
- Any malformed line such as `requires_openai_auth = truemodel = "..."`.

If a malformed line joined two settings, rewrite it as valid TOML.

## Reconnecting diagnosis

If the user says a customer is stuck on `reconnecting` while other users connect normally, explain briefly that the pasted config is missing the Tokenlane OpenAI provider or auth file is likely wrong. Then give the full repaired config and `auth.json` placeholder. Keep this to one sentence before the copyable blocks.

## Response shape

- Windows first line: `给这个 Windows 用户把 C:\Users\NAME\.codex\config.toml 整体换成下面这个：`
- Mac first line: `给这个 Mac 用户把 ~/.codex/config.toml 整体换成下面这个：`
- Put the repaired config in a `toml` code block.
- Then say: `同时确认 PATH_TO_AUTH_JSON 是：`
- Put the `auth.json` placeholder in a `json` code block.
- If the original input had `[windows] sandbox = "elevated"`, add a short final deletion note with a `toml` code block containing that bad section.
