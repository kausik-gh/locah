# Prebuilt template intake — `infra/templates/inbound/`

**Status: idle. No export has been provided yet.** Nothing in the pipeline runs
until a founder drops an export into this folder. This directory and its contract
exist so that when that happens, the translation work has a defined starting
point — it is not a blocker for any other work.

Governing spec: **Document 12 §12.8** (Prebuilt Template Ingestion — Option A) and
**Document 10 §11.3–§11.4** (amended 2026-09-01).

---

## What this pipeline does (Option A)

It **translates a design reference into the platform's existing structured
system**. It never renders external markup.

```
infra/templates/inbound/<slug>/        <- founder drops an export here
   -> a human/tooling pass extracts design decisions
   -> emits:
        (a) a WebsiteTheme definition   -> website_versions.theme JSONB
        (b) 0..N new layout variants     -> added to an existing
                                            website_section_types.allowed_variants
   -> checked in under infra/templates/translated/<slug>/ (created on first use)
   -> new variants land as a reviewed migration + section-registry change
```

What is extracted:

| Extract | Target |
|---|---|
| Colour palette | `theme.colors.*` (within the allowed design-token surface) |
| Type choices (families, scale, weights) | `theme.typography.*` |
| Spacing rhythm / density | `theme.spacing.*` |
| Section composition & ordering | mapping onto the **13 existing** `SectionType`s |
| A distinct section layout | a new entry in that `SectionType`'s `allowed_variants` |

What is **never** taken from an export:

- raw HTML, CSS, or JavaScript into any rendering path;
- external URLs as content or asset values (assets are imported and referenced by Asset ID);
- new `SectionType`s invented to fit the export (see "Flag-back rule" below);
- any platform mechanic (cart, checkout, nav semantics, confirmation) — those are fixed code.

---

## Intake shape

Drop a single folder named for the template, `kebab-case`:

```
infra/templates/inbound/<slug>/
   source/            required  the export as received (HTML/CSS/assets, a ZIP, a Figma export, screenshots — whatever the founder has)
   NOTES.md           required  founder's intent in prose: which businesses this is for,
                                what they like about it, anything that must survive translation,
                                anything that must NOT be copied (fonts they don't have a licence for, etc.)
   reference/         optional  extra screenshots, a live URL captured to PDF, brand guide
```

Minimum viable drop: `source/` + a one-paragraph `NOTES.md`. Everything else is a bonus.

`source/` contents are **inputs for a human/tooling extraction pass only**. They are
not deployed, not served, and not committed to any app package. This folder is
`.gitignore`d for everything except `README.md`, `.gitignore`, and any `NOTES.md`
— see the note below before committing a real export (licensing / size).

---

## Flag-back rule

If an export contains a section or interaction the current **13** `SectionType`s
cannot represent, **stop and flag it** as a schema/architecture decision — do not
invent a new `SectionType` unilaterally. New section types and new layout-variant
families are shown as a diff/migration before they are applied, per the standing
discipline. Record the flagged item in `<slug>/NOTES.md` under a `## Flagged` heading.

---

## The 13 section types a translation must map onto

`about`, `classes_section`, `contact`, `cta_band`, `enquiry_form`, `gallery`,
`hero`, `location_list`, `menu_section`, `offerings_list`, `plans_section`,
`rooms_section`, `text_block`.

(Authoritative source: `website_section_types` table; in-process bootstrap subset
in `python/core/platform_core/website/section_registry.py`.)
