<h1 align="center">Photo to Editorial Illustration</h1>

<p align="center">
  <a href="https://www.skills.sh/cynthia-cym/photo-to-editorial-illustration/photo-to-editorial-illustration"><img src="https://skills.sh/b/cynthia-cym/photo-to-editorial-illustration" alt="skills.sh"></a>
  <a href="https://github.com/Cynthia-cym/Photo-to-Editorial-Illustration/releases"><img src="https://img.shields.io/github/v/release/Cynthia-cym/Photo-to-Editorial-Illustration?display_name=tag&style=flat" alt="GitHub release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.10-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Codex-Skill-111111" alt="Codex Skill">
</p>

<p align="center"><b>Keep the photograph. Reimagine its visual memory.</b></p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#use">Use</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#what-it-preserves">What it preserves</a> ·
  <a href="#privacy">Privacy</a>
</p>

<p align="center">
  <img src="docs/preview/hero.png" alt="Three fictional photographs paired with their marker-led editorial illustrations" width="100%">
</p>

An installable Codex Skill that transforms one source photograph into a clean vertical editorial composition. The original photo remains intact above a restrained, source-derived fashion illustration with a short English title and a deterministic final layout.

## Install

```bash
npx skills add https://github.com/Cynthia-cym/Photo-to-Editorial-Illustration \
  --skill photo-to-editorial-illustration
```

Open a new Codex task after installation so the Skill is discovered.

## Use

Attach exactly one photograph and ask Codex:

> Use `$photo-to-editorial-illustration` to transform this photo.

The Skill accepts JPG/JPEG, PNG, static WebP, MPO, and HEIC/HEIF sources containing people, animals, landscapes, architecture, plants, or objects.

## How it works

| Step | What happens |
| --- | --- |
| **1. Validate** | Preflight checks the source format, orientation, dimensions, and frame count without altering the photograph. |
| **2. Illustrate** | One image-transformation generation distills the source into marker masses, selective brush-pen contours, restrained environmental wash, and generous negative space. |
| **3. Compose** | A deterministic compositor preserves the original photo, places the illustration, adds a short title and source-derived palette, and exports the final vertical artwork. |

## What it preserves

- the original photograph as the visual anchor;
- human pose, interaction, and identity-bearing facial structure;
- animal species, silhouette, markings, and relationship to people;
- architecture and scene-defining geometry;
- a restrained palette derived from the source;
- a single-generation, zero-retry illustration workflow.

The illustration language is marker-led and editorial: connected color masses establish form, pressure-sensitive contours remain selective and open, and watercolor is reserved for eligible environmental fields rather than people or animals.

## Output

The final artwork is a vertical editorial composition containing:

1. the unchanged source photograph;
2. a source-derived illustration panel;
3. a concise two- or three-word English title;
4. four restrained palette swatches.

## Requirements

- Codex with an installed and authorized image-generation capability;
- Python 3.10 or newer;
- Pillow and HEIC support when required by the source format.

The included setup helper installs only the pinned runtime dependencies needed by the preflight and compositor scripts. No Plugin is required.

## Included

- the `photo-to-editorial-illustration` Skill instructions;
- active prompt and abstraction references;
- source preflight and deterministic compositor scripts;
- the packaged Noto Sans font and its SIL Open Font License.

## Privacy

Source photos and generated outputs remain in the user's runtime workspace. They are not uploaded to or included in this repository.

## License

The Skill code and documentation are licensed under the [MIT License](LICENSE). The bundled Noto Sans font remains licensed under the SIL Open Font License 1.1 in `photo-to-editorial-illustration/assets/fonts/OFL.txt`.
