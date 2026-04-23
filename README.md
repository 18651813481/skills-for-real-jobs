# 实用工作技能

这个仓库用于整理面向真实工作场景的 Codex Skills。每个技能都应该能解决一个具体工作任务，并尽量包含可直接安装或分发的压缩包。

## 目录分类

- `设计工作/`
  - 面向设计、图片生成、视觉素材、PPT 视觉资产等工作流。
- `科研工作/`
  - 预留分类，后续放置科研写作、科研绘图、论文、PPT、海报等相关技能。
- `output/`
  - 固定放置技能压缩包。以后上传或发布技能包，都放在这个目录，不再放到其他项目的 `output/` 目录。

## 已收录技能

### Image2

路径：

```text
设计工作/Image2
```

压缩包：

```text
output/Image2-skill.zip
```

用途：

- 在 Codex Desktop 里用自然语言生成图片。
- 固定调用 Tokenlane Images API：
  - `https://api.tokenlane.tech/v1/images/generations`
- 实际模型固定为：
  - `gpt-image-2`
- 生成后把图片保存到本地，并在 Codex Desktop 里用绝对路径 Markdown 直接显示。

主要能力：

- 支持默认方图、横图、竖图和 `auto` 尺寸。
- 支持一次生成 1 到 4 张图片。
- 自动读取 Tokenlane key。
- 优先使用 `curl` 请求 Tokenlane，避免部分 Cloudflare 场景下 Python `urllib` 被拦。
- 不输出 API key、Authorization header 或原始 `b64_json`。

## 安装方式

把技能目录复制到 Codex skills 目录：

```bash
mkdir -p ~/.codex/skills
cp -R "设计工作/Image2" ~/.codex/skills/Image2
```

如需使用压缩包分发，使用：

```text
output/Image2-skill.zip
```

## Tokenlane Key 配置

Image2 会按下面顺序读取 key：

1. `TOKENLANE_API_KEY`
2. `IMAGE2_API_KEY`
3. `~/.codex/Image2/api_key`
4. `~/.codex/Image2/config.json` 里的 `api_key`
5. `~/.codex/auth.json` 里的 `OPENAI_API_KEY`，但仅当 `~/.codex/config.toml` 包含 `api.tokenlane.tech`

推荐本地配置：

```bash
mkdir -p ~/.codex/Image2
printf '%s' 'YOUR_TOKENLANE_KEY' > ~/.codex/Image2/api_key
chmod 600 ~/.codex/Image2/api_key
```

## 上传前检查清单

每次上传或更新仓库前，都要检查：

- 中文 `README.md` 已同步更新，说明新增或修改的技能。
- 技能源码放在正确分类目录下。
- 技能压缩包放在 `output/` 目录下。
- 压缩包里不要包含 `.DS_Store`、`__pycache__` 或临时文件。
- 至少运行一次脚本语法检查或最小相关验证。
- 不提交 API key、配置文件、生成图片缓存或其他敏感信息。
