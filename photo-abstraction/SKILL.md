---
name: photo-abstraction
description: Use when a user wants to transform one photograph containing people, animals, landscapes, architecture, plants, or objects into a minimal mid-century European couture editorial composition with the faithful source photo above a generated illustration panel.
---

# Photo Abstraction

Require exactly one source photograph. Request it when it is missing.

Use this fixed sequence:

**SOURCE PHOTO → SOURCE PREFLIGHT → CONTENT DISTILLATION → ONE ILLUSTRATION GENERATION → ILLUSTRATION EVALUATION → 2–3 WORD TITLE → DETERMINISTIC COMPOSITION → FINAL IMAGE**

## Prepare the Source

1. Create a fresh internal work directory for the run and reserve a new `.png` path inside it for normalized output.
2. Run [prepare_source_image.py](scripts/prepare_source_image.py) with the provided photo and normalized-output path. JPG/JPEG, PNG, and static WebP pass through unchanged. MPO and HEIC/HEIF use only their primary image and are normalized to a verified single-frame RGB PNG. APNG, animated WebP, GIF, files over 50 MiB, images over 100 MP, and images with an edge over 20,000 px are unsupported.
3. Read the returned JSON. Use `runtime_source` for content inspection, use `runtime_source` for generation attachment, and use `runtime_source` for composition. Keep `original_source` only for traceability.
4. If HEIC/HEIF reports that `pillow-heif` is unavailable, run [setup_image_runtime.py](scripts/setup_image_runtime.py) with `--inspect`. When the runtime is ready, rerun preflight with the reported Python path. When installation is required, pause for explicit user approval before running `--approve-install`, then rerun preflight with the installed runtime.
5. If source preflight fails, report the error and stop before content selection or image generation.

## Generate the Illustration

1. Use [content-abstraction-grammar.md](references/content-abstraction-grammar.md) to resolve `KEEP_ELEMENTS` and `DROP_INFORMATION` from the source.
2. Use [element-abstraction-grammar.md](references/element-abstraction-grammar.md) to define how each retained element is simplified. Compile only categories actually retained by content distillation; do not send absent Human, Animal, Architecture, Vegetation, Furniture / Objects, or Environmental Field rules.
3. For every retained human, apply [geometry-grammar.md](references/geometry-grammar.md) and [face-policy.md](references/face-policy.md), then use the Human Prompt Fragment in [generation-prompt.md](references/generation-prompt.md).
4. For every retained animal, use the Animal Prompt Fragment in [element-abstraction-grammar.md](references/element-abstraction-grammar.md).
5. Use the Abstraction Prompt Fragment and Visual Prompt Fragment from [style-media-grammar.md](references/style-media-grammar.md) exactly as written. Add its Watercolor Eligibility Prompt Fragment only for explicitly retained distant continuous environmental fields; humans and animals are never eligible.
6. Assemble [generation-prompt.md](references/generation-prompt.md) by replacing every placeholder once.
7. Send the assembled prompt and source photograph in one image-transformation call.

Set `APPLICABLE_REPRESENTATION` from retained categories only:

- retained human: Human Prompt Fragment, with one short Face Policy expression signal only when applicable;
- retained animal: Animal Prompt Fragment;
- retained architecture, vegetation, furniture / objects, ground, wall, water, or sky: only the matching element instructions;
- absent category: no fragment.

When a human is the Anchor, merge retained environmental facts into one coherent subordinate support.

The model returns one illustration at the source aspect ratio on continuous warm-white paper. The source photograph remains an input and is not reproduced inside the generated image.

## Evaluate the Illustration

Read [quality-guardrails.md](references/quality-guardrails.md) after generation. Continue only when the illustration passes every applicable check. Report a failed check instead of initiating an automatic generation retry.

## Compose and Return

1. Create one quiet, source-grounded English title containing exactly 2–3 words.
2. Run [compose_editorial.py](scripts/compose_editorial.py) with `runtime_source`, generated illustration, title, and output path.
3. Return the compositor output as the final image.

The compositor is the sole owner of final presentation. Its packaged script and assets define that contract.
