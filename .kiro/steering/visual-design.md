---
inclusion: fileMatch
fileMatchPattern: "web/**"
---
# Visual design system

Look: a calm, professional research tool (think a clean analytics dashboard), not a default HTML page.

## Base
- One global stylesheet `web/src/styles/base.css`, imported once in `main.tsx` after `palette.css`.
- Font: system UI stack `-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif` (bundled/system only, no web font requests). Numbers use `font-variant-numeric: tabular-nums`.
- Body: margin 0, background `--surface`, text `--ink`, 16px, line-height 1.55.
- Content column: max-width 1080px, centered, 24px side padding (16px under 600px).
- `main:focus { outline: none; }` (focus is moved there programmatically; real controls keep visible `--focus` rings).

## Tokens (add to palette.css, keep WCAG AA)
- `--surface: #F6F8FB` page background, `--card: #FFFFFF`, `--border: #E3E8EF`, `--muted: #5B6573` secondary text, `--accent-soft: #E8F1FB`.
- Radius 12px for cards, 8px for buttons/badges. Shadow `0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.08)`.
- Spacing scale: 4, 8, 12, 16, 24, 32, 48.

## Type scale
- h1 32px/700, h2 22px/650, h3 17px/600, body 16px, small 14px `--muted`.
- Headings use `--ink`, letter-spacing -0.01em.

## Layout pieces
- Header: white bar with bottom border, product name "Research Gap Index" on the left, nav links on the right; active link = accent text + 2px underline. Collapses to a wrapped row on phones.
- Sample-data banner: slim pill-style strip above the header, `--accent-soft` background, small text.
- Content sections sit in cards (`--card`, border, radius, shadow, 24px padding).
- Home: hero card with h1, one-line question, and the top finding as a big stat (range in large tabular numbers) plus a primary button "Explore all diseases".
- Tables: full width, header row `--surface`, 12px cell padding, row borders `--border`, numbers right-aligned.
- Links: `--accent`, underline on hover only (inline body links stay underlined for accessibility).
- Buttons: primary = accent background, white text, 8px radius, 10px 16px padding.
- Footer: muted small text, top border, sources as inline links separated by " · ".

## Rules
- Keep every accessibility behaviour and test passing; restyle only, do not change copy, data flow or markup semantics unless needed for layout.
- Charts and map keep the existing palette variables.
