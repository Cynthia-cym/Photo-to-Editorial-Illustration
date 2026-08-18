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
  <a href="#overview">Overview</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#what-it-preserves">What it preserves</a> ·
  <a href="#privacy">Privacy</a>
</p>

<p align="center">
  <img src="docs/preview/hero.png" alt="Three fictional photographs paired with their marker-led editorial illustrations" width="100%">
</p>

## Overview

An installable Codex Skill that transforms one source photograph into a clean editorial composition. Landscape and square photos stack above the illustration; portrait photos sit beside it. The original photo remains intact, and the deterministic footer uses two quiet English lines.

## Quick Start

### 1. Install

```bash
npx skills add https://github.com/Cynthia-cym/Photo-to-Editorial-Illustration \
  --skill photo-to-editorial-illustration
```

### 2. Start a new Codex task

Open a new Codex task after installation so the Skill is discovered.

### 3. Transform a photo

Attach exactly one photograph and ask Codex:

> Use `$photo-to-editorial-illustration` to transform this photo.

The Skill accepts JPG/JPEG, PNG, static WebP, MPO, and HEIC/HEIF sources containing people, animals, landscapes, architecture, plants, or objects.

## How it works

| Step | What happens |
| --- | --- |
| **1. Validate** | Preflight checks the source format, orientation, dimensions, and frame count without altering the photograph. |
| **2. Illustrate** | One image-transformation generation distills the source into marker masses, selective brush-pen contours, restrained environmental wash, and generous negative space. |
| **3. Compose** | A deterministic compositor preserves the original photo, places the complete illustration image, matches its paper color, and adds a two-line Caveat footer. |

## What it preserves

- the original photograph as the visual anchor;
- human pose, interaction, and identity-bearing facial structure;
- animal species, silhouette, markings, and relationship to people;
- architecture and scene-defining geometry;
- a restrained palette derived from the source;
- a single-generation, zero-retry illustration workflow.

The illustration language is marker-led and editorial: connected color masses establish form, pressure-sensitive contours remain selective and open, and watercolor is reserved for eligible environmental fields rather than people or animals.

## Output

The final artwork is an orientation-aware editorial composition containing:

1. the unchanged source photograph;
2. a source-derived illustration on a matching paper-color canvas;
3. a 2–4 word English title;
4. a natural 4–8 word English subtitle.

## Requirements

- Codex with an installed and authorized image-generation capability;
- Python 3.10 or newer;
- Pillow and HEIC support when required by the source format.

The included setup helper installs only the pinned runtime dependencies needed by the preflight and compositor scripts. No Plugin is required.

## Included

- the `photo-to-editorial-illustration` Skill instructions;
- active prompt and abstraction references;
- source preflight and deterministic compositor scripts;
- the packaged Caveat Regular font and its SIL Open Font License.

## Privacy

Source photos and generated outputs remain in the user's runtime workspace. They are not uploaded to or included in this repository.

## License

The Skill code and documentation are licensed under the [MIT License](LICENSE). The bundled Caveat Regular font remains licensed under the SIL Open Font License 1.1 in `photo-to-editorial-illustration/assets/fonts/OFL.txt`.
