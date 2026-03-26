# LavanLabs Kanban — Branding Guideline

Dark-mode dashboard inspired by premium fintech/crypto UIs. Deep black canvas
with colorful card accents and generous inner padding.

---

## Color Palette

### Background Layers
| Token         | Hex       | Usage                              |
|---------------|-----------|-------------------------------------|
| `bg-base`     | `#0d0d0d` | Page background — near-black        |
| `bg-surface`  | `#161616` | Cards, nav, panels                  |
| `bg-raised`   | `#1e1e1e` | Elevated cards, inputs, inner cells |
| `bg-overlay`  | `#0a0a0a` | Modal backdrops, deep wells         |

### Text
| Token          | Hex       | Usage                    |
|----------------|-----------|--------------------------|
| `text-primary` | `#f5f5f5` | Headings, primary text   |
| `text-body`    | `#9a9a9a` | Body copy, descriptions  |
| `text-muted`   | `#5a5a5a` | Labels, meta, hints      |

### Accent — Agent Cards (Brighter, inspired by crypto/fintech UI)
| Agent   | Card BG   | Text Accent | Border        | Gradient Banner               |
|---------|-----------|-------------|---------------|---------------------------------|
| Alfred  | `#8a6a28` | `#f5e8c0`   | `#a07830`     | `#d4a840 → #a07828` (amber)     |
| Vio     | `#3d3466` | `#d4ccf8`   | `#4e4580`     | `#8878d0 → #6050b0` (lavender)  |
| Neo     | `#1e5c4a` | `#b8ead8`   | `#2a7360`     | `#48c0a0 → #2a9070` (sage)      |
| Zeo     | `#1e4060` | `#b8ddf0`   | `#2a5580`     | `#58a8d8 → #3080b0` (sky blue)  |
| Seo     | `#8c4a38` | `#f5ccc0`   | `#a05840`     | `#e07050 → #b85840` (coral)     |

### Status Colors
| Status        | Color       | Badge BG                     | Badge Text  |
|---------------|-------------|------------------------------|-------------|
| Todo          | `#b0b0b0`  | `rgba(0,0,0,0.3)`            | `#c0c0c0`   |
| In Progress   | `#818cf8`  | `rgba(99,102,241,0.25)`       | `#c5c8ff`   |
| Testing       | `#f0d878`  | `rgba(224,184,80,0.25)`       | `#f0d878`   |
| Review        | `#d4ccf8`  | `rgba(155,140,224,0.25)`      | `#d4ccf8`   |
| Done          | `#a0f0d8`  | `rgba(92,200,168,0.25)`       | `#a0f0d8`   |

### Semantic
| Purpose    | Color     | Usage                         |
|------------|-----------|-------------------------------|
| Primary    | `#6366f1` | Active nav buttons, links     |
| Success    | `#5cc8b4` | Toast success, done states    |
| Danger     | `#e07a5f` | Toast error, coral accents    |
| Warn       | `#e8c46a` | Testing, caution, gold        |

### Feature Accent Cards (bold, saturated — crypto/fintech inspired)
| Name         | Background | Text      | Usage                     |
|--------------|------------|-----------|---------------------------|
| Blue-Violet  | `#818cf8`  | `#ffffff` | Primary actions, active    |
| Amber/Ochre  | `#d4a840`  | `#1a1a1a` | Highlights, warnings       |
| Coral/Orange | `#e07050`  | `#1a1a1a` | Attention, alerts          |
| Sage Green   | `#48c0a0`  | `#1a1a1a` | Success, positive states   |
| Lavender     | `#8878d0`  | `#ffffff` | Reviews, secondary accent  |
| Sky Blue     | `#58a8d8`  | `#1a1a1a` | Informational              |

---

## Typography

### Headings — Do Hyeon
- Google Fonts: `Do Hyeon`, sans-serif
- Weight: 400 only (single-weight font)
- Usage: Page titles, section headings, nav brand

### Body — Poppins
- Google Fonts: `Poppins`, sans-serif
- Weights used: 300 (light), 400 (regular), 500 (medium), 600 (semibold), 700 (bold)
- Usage: All body text, labels, buttons, badges, inputs

### Mono — System
- `ui-monospace, SFMono-Regular, monospace`
- Usage: Point values, model names, code snippets

### Scale
| Element               | Font     | Size    | Weight       |
|-----------------------|----------|---------|-------------- |
| Nav brand             | Do Hyeon | 28px    | 400          |
| Page title (h1)       | Do Hyeon | 26px    | 400          |
| Section heading (h2)  | Do Hyeon | 20px    | 400          |
| Card title            | Poppins  | 14px    | 600          |
| Body text             | Poppins  | 13px    | 400          |
| Small / labels        | Poppins  | 11px    | 500          |
| Micro / meta          | Poppins  | 10px    | 500          |

---

## Layout & Spacing

### Border Radius
| Component           | Radius |
|---------------------|--------|
| Cards, panels       | 16px   |
| Buttons             | 12px   |
| Badges / pills      | 999px  |
| Inputs              | 12px   |
| Progress bars       | 999px  |

### Spacing
- Card padding: 16–20px
- Card gap: 12px (kanban columns), 16–24px (grid views)
- Section margin-bottom: 24px

### Shadows
- Cards: `0 4px 24px rgba(0,0,0,0.4)`
- Elevated (modals): `0 8px 40px rgba(0,0,0,0.6)`
- Active nav buttons: colored glow matching primary
- Drop glow: animated gradient glow on card placement

---

## Micro Animations

### Card Drop Glow
When a story card is dropped into a new column, it pulses with a gradient
glow (agent-colored) that fades out over ~1s. CSS keyframe `drop-glow`.

### Hover States
- Cards: `brightness(1.08)` on hover
- Buttons: `brightness(1.1)` on hover
- Nav items: smooth color transition `150ms`

### Transitions
- All interactive elements: `transition-all 150ms ease`
- Kanban column highlight on drag-over: border color shift `200ms`

---

## Component Patterns

### Navigation Bar
- Height: ~72px, sits at the top, bg-surface
- Brand on the left (Do Hyeon, 28px)
- Button group on the right, pill-shaped toggles
- Active button: solid primary fill with subtle glow
- Inactive button: raised background, muted text

### Story Cards (Kanban)
- Colored background per assigned agent
- Rounded 16px, subtle border matching agent color
- Title first, then summary (1-line), then project/feature labels
- Progress bar: thin, rounded, accent-colored
- Footer: agent avatar + name, comment count, point badge

### Agent Cards
- Profile banner gradient (agent-colored), thin
- Large circular avatar with zoomed face
- Name (large), alias, role
- Grid stats: active tasks + model
- Story list underneath

---

## Do's and Don'ts

DO:
- Use generous padding inside cards (min 16px)
- Keep the background truly dark (#0d0d0d) — let cards pop
- Use colorful agent backgrounds on cards for visual identity
- Add micro animations for feedback (hover, drop, transitions)

DON'T:
- Use bright saturated backgrounds for large areas
- Put more than 1 line of summary on a kanban card
- Use outline-only buttons (use filled buttons)
- Mix heading fonts (Do Hyeon for headings only, never body)
- Use pure white (#ffffff) for backgrounds — keep everything tinted dark
