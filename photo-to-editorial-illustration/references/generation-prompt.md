# Photo Abstraction — Image Prompt

## Assembly Contract

Resolve four source-dependent values:

- `{KEEP_ELEMENTS}` from content distillation;
- `{DROP_INFORMATION}` from content distillation;
- `{APPLICABLE_REPRESENTATION}` from only the retained Human, Animal, Architecture, Vegetation, Furniture / Objects, and Environmental Field categories;
- `{WATERCOLOR_ELIGIBILITY}` from explicitly retained distant continuous fields, or an empty value when none are eligible.

Insert the Abstraction Prompt Fragment and Visual Prompt Fragment from [style-media-grammar.md](style-media-grammar.md) into `{ABSTRACTION_KERNEL}` and `{VISUAL_KERNEL}` exactly as written. Use the Watercolor Eligibility Prompt Fragment only when applicable. Replace every placeholder once and send only the completed Image-Facing Template to the model.

Insert the Illustration Safety Margin Prompt Fragment from [layout-grammar.md](layout-grammar.md) into `{LAYOUT_KERNEL}` exactly as written.

## Human Prompt Fragment

Use this complete fragment for every retained human, followed by one applicable expression signal from [face-policy.md](face-policy.md):

```text
FIGURE
Use the source for pose, gesture, action, interaction, and weight-bearing logic.
Reconstruct each person as a natural, elegant couture editorial figure with approximately 8-head proportions, a moderately small head, natural neck, simplified torso, anatomically plausible limbs, simplified hands and feet, and a redesigned fashion silhouette.
Do not use small-head exaggeration, extreme leg elongation, extreme torso lengthening, distorted anatomy, or photographed body-contour tracing.

FACE
Use a standardized high-fashion editorial face. Completely ignore photographed facial features, face shape, facial proportions, and likeness.

HUMAN MEDIA — EXCLUSIVE
Render every retained human only with selective soft brush-pen contours, large connected marker color masses, a few directional marker strokes, sparse fine-marker internal structure, and clean paper white.
Use marker color masses, not transparent wash, to establish skin, hair, garments, hands, legs, and human form.
Do not apply watercolor wash, transparent glaze, diluted color fill, wet-on-wet edges, watercolor blooms, granulation, watercolor paper texture, or watercolor tonal modeling to any human.
Compress garment patterns into one dominant connected garment mass with only a few large graphic accents.

HUMAN OUTER CONTOUR — BRUSH-PEN ONLY
Construct the redesigned human silhouette from gesture, direction, and large fashion masses.
Use only a few long, open, pressure-sensitive soft brush-pen strokes for the primary outer contour.
Keep the contour selective, confident, thick-to-thin, tapered, intentionally incomplete, and visibly departed from the photographed perimeter.
Do not continuously outline the complete head, torso, garment, arms, hands, legs, or feet.

FINE MARKER — STRUCTURE ONLY
Use fine-marker lines only for a small amount of internal structure: major joint direction, garment flow, essential overlap, and a few identity-bearing garment directions.
Fine-marker lines must not become the primary human outer contour, close every form, or connect into a complete outlined figure.
Do not use dense correction lines, fragmented micro-contours, or anatomical tracing.

Let large connected marker color masses establish the primary human form. Use contour to select and energize important edges rather than enclosing every color mass. Contour and color may slightly misregister.
```

## Image-Facing Template

```text
OBJECTIVE
Transform the uploaded photo into a sophisticated minimal mid-century European couture fashion editorial illustration.

KEEP / DROP
Keep only:
{KEEP_ELEMENTS}

Omit or merge:
{DROP_INFORMATION}

{APPLICABLE_REPRESENTATION}

ABSTRACTION
{ABSTRACTION_KERNEL}

VISUAL LANGUAGE
{VISUAL_KERNEL}

{WATERCOLOR_ELIGIBILITY}

{LAYOUT_KERNEL}

OUTPUT
Create one transformed illustration only, using the same aspect ratio as the source image, on continuous warm-white paper.

Return a single finished illustration with no text or presentation elements.
```
