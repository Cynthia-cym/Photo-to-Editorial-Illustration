# Photo-to-Editorial-Illustration

An installable Codex Skill that transforms one source photograph into a clean vertical editorial composition: the original photo remains intact above a restrained, source-derived illustration panel with a short English title.

## Install

Ask Codex:

> Install the `photo-to-editorial-illustration` skill from `https://github.com/Cynthia-cym/Photo-to-Editorial-Illustration/tree/main/photo-to-editorial-illustration`.

Or use the bundled Codex Skill installer:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo Cynthia-cym/Photo-to-Editorial-Illustration \
  --path photo-to-editorial-illustration
```

Open a new Codex task after installation so the Skill is discovered.

## Use

Attach exactly one photograph and ask Codex to transform it with the `photo-to-editorial-illustration` Skill. The workflow accepts JPG/JPEG, PNG, static WebP, MPO, and HEIC/HEIF source images. It performs one image-transformation generation and then assembles the final layout deterministically.

Python 3.10 or newer is required. The Skill includes a small setup helper for its pinned Pillow and HEIC dependencies; installation is requested only when the active runtime needs them.

## Included

- the `photo-to-editorial-illustration` Skill instructions;
- the active prompt and abstraction references;
- source preflight and deterministic compositor scripts;
- the packaged Noto Sans font and its SIL Open Font License.

No Plugin is required. The Skill uses Codex's installed and authorized image-generation capability.

## Privacy and licensing

Source photos and generated outputs stay in the user's runtime workspace and are not part of this repository.

The Skill code and documentation are licensed under the MIT License. The bundled Noto Sans font remains licensed under the SIL Open Font License 1.1 in `photo-to-editorial-illustration/assets/fonts/OFL.txt`.
