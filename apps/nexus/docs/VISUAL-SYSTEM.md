# Visual system

The approved reference is a neon operational console: near-black canvas, one saturated accent
surface, a right-hand live rail, dense-but-quiet cards, sparklines and a contribution grid. The
implementation keeps that grammar but re-interprets it for connectivity intelligence.

## Tokens

| Role | Value | Usage |
| --- | --- | --- |
| Canvas | `#080A0B` | App background, with two low-opacity radial ambience layers (violet top-right, neon top-left) |
| Panel | `#111416` | Sidebar, topbar, hero-adjacent surfaces |
| Card | `#171B1D` | Data cards, tables, drawers |
| Primary neon | `#9DFF00` | Active nav pill, primary buttons, key metrics, growth line, reachable state |
| Secondary violet | `#8B5CF6` | Latency line, secondary emphasis, atmospheric light only |
| Text primary | `#F3F5F4` | Headings, values |
| Text secondary | `#919B98` | Hints, labels, meta |
| Semantic | `#34D399` `#FBBF24` `#F87171` `#60A5FA` | success / warning / danger / info |

Borders are `rgba(255,255,255,0.05–0.08)`; glow is limited to the hero card and active navigation.

## Type

- **Space Grotesk** — geometric UI sans (`--font-sans`).
- **JetBrains Mono** — hosts, ports, latency, fingerprints, IDs, logs, run numbers.
- **Vazirmatn** — applied automatically under `[dir="rtl"]` for Persian.
- Scale: 9–10 px uppercase tracked labels, 11–13 px UI copy, 15–18 px card titles, 26–68 px metrics.

## Layout

- Fixed 256 px sidebar (desktop) → overlay drawer (mobile), grouped operations / intelligence / platform.
- Sticky topbar: page title with live dot, last-run context, global search, 7/30/90 window
  selector, alerts popover, account menu.
- Content max-width 1560 px, 3xl card radius, 12-column grid.
- Overview mirrors the reference: neon hero with concentric arcs + coverage ring on the left, live
  source rail and activity feed on the right, KPI strip beneath, chart grid, run table.

## Component rules

- Active navigation is a filled neon pill with dark glyphs — the single strongest affordance.
- One accent per card: neon for growth/health, violet for latency/secondary series, greys for
  distribution tracks.
- Charts always render an honest empty state when there is no telemetry.
- Every control performs a real action; there are no decorative toggles. Unimplemented features are
  labelled in place (Cloudflare, end-to-end verification, country filters).
- Motion: 150–400 ms transitions, one entrance fade, no looping decoration except a status pulse.

## Accessibility

- Focus rings (`2px` neon at 60–75%) on every interactive element.
- Status is never conveyed by colour alone: pills carry text labels.
- Tables scroll horizontally on narrow screens with minimum widths rather than compressing to
  unreadable text.
- Contrast: primary text on canvas ≈ 17:1, secondary ≈ 5.5:1, dark text on neon ≈ 13:1.
- Language switch changes `lang` and `dir` on `<html>`; layout uses logical properties
  (`ms-*`, `me-*`, `start-*`, `end-*`) so RTL mirrors without bespoke CSS.
