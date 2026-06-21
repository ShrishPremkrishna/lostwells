# Lost Wells of Appalachia — UI Design Spec
# Agent-parsable. Framework-agnostic. Implement exactly as written.

---

## 1. IDENTITY

**Project name:** The Lost Wells of Appalachia
**Product type:** Investigative geospatial tool for government agencies and environmental researchers
**Core interaction:** Find an unknown well on a map → investigate it → get a funded path to plug it
**Aesthetic direction:** Topographic field survey meets modern intelligence dashboard. Worn, analog, authoritative — but fast and precise. Not a climate startup. Not a data viz tool. Something closer to a war room built inside an old geological survey office.

---

## 2. COLOR SYSTEM

All colors are mathematically derived from the base gray #CFCFCF.

### Grays (base and neutrals)

```
--color-base:        #CFCFCF   /* Base gray — borders, dividers, inactive UI */
--color-surface-1:   #F5F5F5   /* Lightest surface — main app background */
--color-surface-2:   #E8E8E8   /* Card and panel backgrounds */
--color-surface-3:   #CFCFCF   /* Dividers, input borders, subtle strokes */
--color-mid:         #A8A8A8   /* Secondary text, placeholders, disabled states */
--color-text-body:   #3D3D3D   /* Primary body text */
--color-text-head:   #1A1A1A   /* Headlines, labels, high-emphasis text */
--color-ink:         #0D0D0D   /* Near-black for maximum contrast */
```

### Greens (accent — muted olive-to-forest range, NOT neon)

```
--color-accent-light:  #D4E8DA   /* Very light green — selected well highlight wash */
--color-accent-soft:   #7AAE8A   /* Soft green — tags, badges, secondary actions */
--color-accent:        #4A7C59   /* Primary accent — active states, buttons, map pins */
--color-accent-deep:   #2E5C3E   /* Deep green — hover, pressed, high-emphasis accent */
--color-accent-ink:    #1A3D29   /* Darkest green — text on light green backgrounds */
```

### Semantic colors

```
--color-danger:    #8B3A3A   /* Error, high-risk wells */
--color-warning:   #8B6914   /* Medium-risk, caution states */
--color-success:   #2E5C3E   /* Same as accent-deep — confirmed, resolved */
--color-info:      #3A5F8B   /* Informational, neutral data points */
```

### Usage rules

- NEVER use --color-accent as a background for large surfaces. Buttons and icons only.
- --color-surface-1 is the app shell background. Always.
- Text on --color-surface-2 uses --color-text-body minimum. Never --color-mid on a card.
- --color-base (#CFCFCF) is for borders and dividers only. Never as a text color.
- Map overlay panels use --color-ink at 85% opacity as background with white text. This gives the "field notes on dark glass" effect.

---

## 3. TYPOGRAPHY

### Typefaces

```
--font-display:  'Playfair Display', Georgia, serif
--font-body:     'Inter', system-ui, sans-serif
--font-mono:     'JetBrains Mono', 'Courier New', monospace
```

**Playfair Display** — used for well names, section headers, the project title, and the dossier headline. Carries the aged, editorial weight. Never use below 18px.

**Inter** — used for everything functional: labels, stats, filter controls, button text, body copy, coordinates. Clean and fast.

**JetBrains Mono** — used for coordinates, IDs, raw data values, API outputs, and the live agent feed. Makes data feel like data.

### Type scale

```
--text-xs:    11px / 1.4  Inter, uppercase, letter-spacing 0.08em — eyebrows and labels
--text-sm:    13px / 1.5  Inter — secondary text, metadata
--text-base:  15px / 1.6  Inter — body, descriptions, sidebar well list items
--text-md:    18px / 1.4  Inter medium — stat values, filter headers
--text-lg:    24px / 1.3  Playfair Display — well name in dossier, section titles
--text-xl:    32px / 1.2  Playfair Display — page-level headers
--text-2xl:   48px / 1.1  Playfair Display — hero stats, impact numbers
```

### Typography rules

- Section labels above content blocks: Inter, --text-xs, uppercase, --color-mid, letter-spacing 0.08em. Always. This is the "field survey form" touch.
- Well names: Playfair Display, --text-lg, --color-text-head.
- Coordinates: JetBrains Mono, --text-sm, --color-mid.
- Stats (e.g. "320,000 wells"): number in Playfair Display --text-2xl, unit label in Inter --text-sm beneath it.
- Never mix Playfair and Inter in the same line of text.

---

## 4. LAYOUT

### App shell structure

```
+--------------------------------------------------+
|  TOPBAR (48px fixed)                             |
+----------------+---------------------------------+
|                |                                 |
|   WELL LIST    |         MAP CANVAS              |
|   PANEL        |         (full bleed)            |
|   (320px)      |                                 |
|   collapsible  |    +------------------------+   |
|                |    |  DOSSIER PANEL         |   |
|                |    |  (slides in from right)|   |
|                |    |  (420px wide)          |   |
+----------------+---------------------------------+
|  STATUS BAR (32px fixed)                         |
+--------------------------------------------------+
```

### Topbar (48px, fixed)

- Background: --color-ink
- Left: project wordmark in Playfair Display, 18px, white
- Center: map style toggle (see Map Controls below)
- Right: region selector, well count badge
- No drop shadow. A 1px bottom border in --color-accent at 40% opacity instead.

### Well List Panel (320px, left)

- Background: --color-surface-2
- Right border: 1px solid --color-base
- NOT a full sidebar in the traditional sense. It can collapse to 0px with a pull tab remaining.
- Panel has three sections stacked vertically:

**Filter Bar (top, collapsible)**
- Label: "FILTER WELLS" in --text-xs uppercase --color-mid
- Filters are pill toggles, not dropdowns. One row per category.
- Active filter pill: background --color-accent, text white
- Inactive pill: background --color-surface-3, text --color-text-body, border 1px --color-base
- Filter categories: Water Risk / School Proximity / Residential Proximity / Environmental Justice / Funding Eligible / Corporate Traceable

**Well Count (below filters)**
- "[N] wells found" in Inter --text-sm --color-mid
- Updates live as filters change

**Well List (scrollable, fills remaining height)**
- Each well is a card: 72px tall, full width, no border-radius (zero — this is intentional)
- Card background: --color-surface-2 default, --color-accent-light when selected
- Left edge: 3px solid accent color coded by risk (--color-danger / --color-warning / --color-accent)
- Card contents:
  - Line 1: Well ID or auto-name in Inter --text-base --color-text-head
  - Line 2: County, State in Inter --text-sm --color-mid
  - Line 3: Top risk factor (e.g. "0.2mi from elementary school") in Inter --text-xs --color-warning or --color-danger
- No hover animation. Background shifts to --color-surface-3 on hover, that's it.
- Clicking a card: selects the well, flies map to it, opens dossier panel

### Map Canvas (fills remaining space)

- Map is always full bleed. No padding around it.
- Default style: custom muted topographic style (see Map Controls)
- Well markers: circles, not pins. 10px diameter. Color by risk tier. --color-danger / --color-warning / --color-accent. 2px white stroke.
- Selected well marker: 16px, same color, white stroke, subtle pulse animation (1 pulse, not looping)
- Clustering: wells closer than [threshold] merge into a count bubble. Bubble style: --color-ink background, white Inter --text-sm, white stroke.

**Map Controls (bottom center of map, floating)**
- A pill-shaped toggle, not a button bar
- Options: TOPO / SATELLITE / HYBRID
- Background: --color-ink at 90% opacity
- Text: Inter --text-xs uppercase white
- Active option: --color-accent background
- Position: fixed to bottom center of map canvas, 24px from bottom edge

**Attribution (bottom right of map)**
- Standard map attribution, Inter --text-xs --color-mid

### Dossier Panel (420px, slides in from right over map)

- Triggered by selecting a well in the list or clicking a marker
- Background: --color-surface-1
- Left border: 1px solid --color-base
- NOT a modal. Sits flush against the right edge. Map is still visible and pannable behind it.
- Has its own internal scroll
- Close: X button top right, 32px, --color-mid

**Dossier panel sections in order:**

**1. Well Header**
- Well name/ID: Playfair Display --text-lg --color-text-head
- Coordinates: JetBrains Mono --text-sm --color-mid
- Risk badge: pill, right-aligned, colored by tier
- Thin 1px --color-base divider beneath

**2. Map thumbnail**
- 100% width, 160px tall
- Shows a static satellite crop centered on the well
- Overlaid with a crosshair at the well location
- "CANDIDATE WELL — UNCONFIRMED" watermark text in Inter --text-xs --color-mid uppercase, bottom left

**3. Quick stats row**
- 3–4 stat blocks in a row
- Each: number in Playfair Display --text-md, label in Inter --text-xs uppercase --color-mid below
- Stats: nearest school distance / nearest water source / population within 1mi / estimated methane (labeled "MODELED ESTIMATE")

**4. Risk factors**
- Section label: "RISK FACTORS" in --text-xs uppercase --color-mid
- List of factors, each a row: icon (simple SVG, --color-warning or --color-danger) + description in Inter --text-sm
- No bullets. Icon + text only.

**5. Funding pathway**
- Section label: "PLUGGING PATHWAY" in --text-xs uppercase --color-mid
- One of three states shown as a tag:
  - FEDERAL ELIGIBLE — --color-accent background, white text
  - CORPORATE LIABILITY — --color-info background, white text
  - CARBON CREDIT — --color-accent-soft background, --color-accent-ink text
- Below the tag: one sentence describing the specific pathway in Inter --text-sm --color-text-body

**6. Investigate button**
- Full width, 48px tall
- Background: --color-accent
- Text: "RUN INVESTIGATION" Inter --text-sm uppercase white letter-spacing 0.06em
- No border-radius. Square corners. This is intentional.
- On click: button text changes to "INVESTIGATING..." and the agent feed appears below

**7. Agent feed (appears after investigation triggered)**
- Background: --color-ink
- Text: JetBrains Mono --text-xs, white, 1.6 line height
- Lines appear one at a time as agents report back
- Each line prefixed with a timestamp: "09:42:13 >"
- Example lines:
  - "Querying EPA SDWIS water records..."
  - "Municipal water source found — 0.31 miles NW"
  - "Searching corporate registry: Appalachian Oil Co."
  - "Company dissolved — 1987. Successor: Mountain Energy LLC"
  - "Flagging for corporate liability pathway"
- When complete: a green "INVESTIGATION COMPLETE" line appears
- Feed is scrollable, max 240px tall

---

## 5. INTERACTION PATTERNS

### Well selection flow
1. User clicks well in list OR clicks marker on map
2. Map flies to well (smooth animation, 600ms)
3. Selected marker pulses once
4. Dossier panel slides in from right (240ms ease-out)
5. List item highlights with --color-accent-light background

### Filter interaction
1. User toggles a filter pill
2. Well list updates immediately (no loading state if pre-filtered client-side)
3. Map markers update to show only matching wells
4. Well count badge updates
5. No confirmation needed. Filters are reversible.

### Investigation flow
1. User clicks "RUN INVESTIGATION"
2. Button becomes disabled, text becomes "INVESTIGATING..."
3. Agent feed panel expands below button (height animates open, 200ms)
4. Lines appear in feed as results come in
5. On completion: button becomes "VIEW FULL REPORT" linking to a full-page dossier
6. Pathway tag may update if investigation changes the recommendation

### Map style toggle
1. User clicks TOPO / SATELLITE / HYBRID pill
2. Map style transitions with a crossfade (300ms)
3. Active option updates immediately

---

## 6. COMPONENT RULES

### Borders and radius
- **Zero border-radius everywhere except filter pills and badges.**
- Filter pills: 999px radius (fully rounded)
- Risk/status badges: 4px radius
- Everything else: 0px. Cards, buttons, panels, inputs. This is the hardest rule and the most important one for avoiding the AI-generated look.

### Shadows
- No drop shadows on panels or cards. Use borders instead.
- One exception: the dossier panel has a single box-shadow: `-4px 0 24px rgba(0,0,0,0.12)` on its left edge to separate it from the map. That's the only shadow in the entire UI.

### Buttons
- One button style: full-width, square corners, --color-accent background, white text, Inter uppercase, letter-spacing 0.06em
- Hover: --color-accent-deep background
- Disabled: --color-surface-3 background, --color-mid text
- No ghost buttons. No outlined buttons. One style, used consistently.

### Dividers
- 1px solid --color-base
- No decorative dividers. Only use where content sections genuinely need separation.

### Empty states
- If no wells match filters: center-aligned in the list panel, Inter --text-sm --color-mid, "No wells match these filters." Nothing else. No illustration.
- If investigation returns no data for a field: "No data found" in JetBrains Mono --text-xs --color-mid inline.

### Loading states
- Skeleton screens for initial well list load: gray rectangles at --color-surface-3, no animation (no shimmer — shimmer looks AI-generated)
- Investigation feed is its own loading state — no spinner needed

---

## 7. MOTION

Less is more. Three animations only:

**1. Dossier panel slide-in**
- `transform: translateX(100%) → translateX(0)`
- Duration: 240ms
- Easing: cubic-bezier(0.16, 1, 0.3, 1) — fast out, no bounce

**2. Map fly-to on well selection**
- Handled by map library (Mapbox/MapLibre fitBounds or flyTo)
- Duration: 600ms
- Use the library's default easing

**3. Agent feed line appearance**
- Each new line: `opacity: 0 → 1`, `transform: translateY(4px) → translateY(0)`
- Duration: 120ms per line
- No delay between lines beyond the actual agent response time

**Everything else: no animation.** No hover transitions on cards beyond instant background color change. No page transitions. No loading spinners.

Honor `prefers-reduced-motion`: if set, disable all three animations entirely.

---

## 8. SPACING SYSTEM

Base unit: 4px. All spacing is a multiple of 4.

```
--space-1:   4px
--space-2:   8px
--space-3:   12px
--space-4:   16px
--space-5:   20px
--space-6:   24px
--space-8:   32px
--space-10:  40px
--space-12:  48px
--space-16:  64px
```

Panel internal padding: --space-6 (24px) on all sides
Card internal padding: --space-4 (16px) horizontal, --space-3 (12px) vertical
Section label margin-bottom: --space-2 (8px)
Between dossier sections: --space-6 (24px) with a 1px --color-base divider

---

## 9. ICONOGRAPHY

- Use a single icon library throughout. Recommended: Lucide (MIT license, consistent stroke width)
- Icon size: 16px for inline, 20px for standalone
- Icon color: always inherits from parent text color. Never hardcoded.
- No filled icons. Stroke-only throughout. This matches the cartographic aesthetic.
- Icons used: MapPin, Droplets, School, Users, AlertTriangle, CheckCircle, Search, ChevronLeft, X, Layers (map toggle)

---

## 10. STATUS BAR (32px, fixed bottom)

- Background: --color-ink
- Text: Inter --text-xs white
- Left: "N wells loaded · Last updated [timestamp]"
- Right: data source attribution "USGS · LBNL · EPA · Census"
- Serves as a trust signal — shows where data comes from at all times

---

## 11. WHAT TO AVOID

These are the patterns that make a UI look AI-generated. Do not use any of them:

- Gradient backgrounds or gradient buttons
- Cards with rounded corners (8px+ radius)
- Drop shadows on cards
- Glassmorphism (backdrop-filter blur on panels, except the map overlay controls where it's justified)
- Animated shimmer loading skeletons
- Emoji in UI copy
- Any shade of blue as a primary accent
- Heroicons filled variants
- `font-weight: 300` anywhere
- Centered body text in information-dense sections
- Decorative dividers (dots, dashes, ornaments)
- The color combination of white background + blue accent + gray text (default Tailwind/shadcn look)

---

## 12. RESPONSIVE BEHAVIOR

**Desktop (1280px+):** Full three-column layout as described above.

**Tablet (768px–1279px):**
- Well list panel collapses to icon-only strip by default, expands on tap
- Dossier panel takes 60% of screen width

**Mobile (below 768px):**
- Map is full screen
- Well list is a bottom sheet (slides up from bottom, 50% screen height)
- Dossier panel is a full-screen modal slide-up
- Map controls move to bottom right corner

---

## 13. IMPLEMENTATION NOTES FOR AGENTS

- CSS custom properties (variables) are the source of truth. Never hardcode a hex value outside of the variable declarations.
- The zero border-radius rule is enforced at the component level. Set `border-radius: 0` explicitly on all interactive elements. Do not rely on browser defaults.
- The agent feed must use a monospace font. Do not substitute.
- The dossier panel sits OVER the map (position: fixed or absolute, right: 0), not beside it. The map does not shrink when the panel opens.
- Well list panel collapse should use CSS transform translateX, not display:none, so the animation is smooth.
- All color usage must reference CSS variables, not hardcoded values, so theming remains consistent.
- The "CANDIDATE WELL — UNCONFIRMED" watermark must appear on every map thumbnail. This is a data integrity requirement, not a design choice.
- Methane estimates must always be labeled "MODELED ESTIMATE" in the UI. Same requirement.