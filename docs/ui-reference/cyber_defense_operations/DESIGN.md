---
name: Cyber Defense Operations
colors:
  surface: '#0e131e'
  surface-dim: '#0e131e'
  surface-bright: '#343946'
  surface-container-lowest: '#090e19'
  surface-container-low: '#171b27'
  surface-container: '#1b1f2b'
  surface-container-high: '#252a36'
  surface-container-highest: '#303541'
  on-surface: '#dee2f2'
  on-surface-variant: '#bcc8d0'
  inverse-surface: '#dee2f2'
  inverse-on-surface: '#2b303c'
  outline: '#86929a'
  outline-variant: '#3d484f'
  surface-tint: '#6dd2ff'
  primary: '#96dcff'
  on-primary: '#003547'
  primary-container: '#00c6ff'
  on-primary-container: '#004f67'
  inverse-primary: '#006685'
  secondary: '#a9c7ff'
  on-secondary: '#003063'
  secondary-container: '#3c90ff'
  on-secondary-container: '#002957'
  tertiary: '#28f280'
  on-tertiary: '#003918'
  tertiary-container: '#00d36c'
  on-tertiary-container: '#005427'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#bfe9ff'
  primary-fixed-dim: '#6dd2ff'
  on-primary-fixed: '#001f2a'
  on-primary-fixed-variant: '#004d65'
  secondary-fixed: '#d6e3ff'
  secondary-fixed-dim: '#a9c7ff'
  on-secondary-fixed: '#001b3d'
  on-secondary-fixed-variant: '#00468c'
  tertiary-fixed: '#62ff96'
  tertiary-fixed-dim: '#00e475'
  on-tertiary-fixed: '#00210b'
  on-tertiary-fixed-variant: '#005226'
  background: '#0e131e'
  on-background: '#dee2f2'
  surface-variant: '#303541'
typography:
  display-lg:
    fontFamily: Space Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.03em
  headline-xl:
    fontFamily: Space Grotesk
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Space Grotesk
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
  title-sm:
    fontFamily: Space Grotesk
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.05em
  code-inline:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-desktop: 2rem
  space-2xs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
  space-2xl: 2rem
  space-3xl: 3rem
---

## Brand & Style

This design system delivers an elite, enterprise-grade Security Operations Center (SOC) and cyber-telemetry experience. Drawing direct inspiration from resilient cyber-sentinel iconography—typified by fortified horn circuits, luminous topological nexus points, and hyper-precise node routing—the interface balances technical authority with immediate situational awareness. 

The aesthetic is firmly rooted in **Tactical Dark High-Contrast Futurism**: deep obsidian and midnight-navy canvases layered with precision hairline borders, neon cybernetic signal accents, and crisp luminescent typography. The interface must evoke absolute vigilance, cryptographic security, and unwavering command. Visual density is calibrated for high information throughput, mission-critical response times, and uninterrupted operational clarity under high-pressure triage conditions.

## Colors

The palette establishes an immersion-first operational hierarchy:

- **Canvas & Surface Tiering**:
  - `Base Canvas`: `#0B101B` (Ultra-deep midnight obsidian) provides infinite spatial depth, preventing eye fatigue during continuous monitoring.
  - `Card / Surface Container`: `#131B2E` (Structured slate navy) serves as elevated telemetry clusters and monitoring units.
  - `Interactive / Hover Container`: `#1A243D` provides discrete optical response without blowing out contrast.
  - `Structural Borders`: `#1E293B` provides clean mechanical separation; critical telemetry cards feature high-frequency highlights of `rgba(0, 198, 255, 0.25)`.

- **Operational Signals & Accents**:
  - `Primary (Electric Cyan)`: `#00C6FF` drives active states, focused nodes, telemetry metrics, and primary navigational beacons.
  - `Secondary (Signal Royal Blue)`: `#0084FF` powers corporate branding elements, selected row backgrounds (`rgba(0, 132, 255, 0.12)`), and multi-tier network pipelines.
  - `Tertiary / Node Vital (Emerald Cyber-Green)`: `#00E676` directly replicates the central nexus core from the visual mark, serving as real-time active status, nominal defense postures, and secured route indicators.
  - `Threat Warning / Critical Alerts`: Reserve `#FF3B30` for breach vectors, and `#FFB300` for warning throttles.

## Typography

The typography uses a tri-font structure purpose-built for tactical SecOps:

1. **Space Grotesk** commands display titles and card module headers. Its sharp, engineered glyph geometry injects technological momentum while aligning with the geometric curves and horns of the brand mark.
2. **Inter** manages body copy, multi-line incident logs, and system explanations, providing neutral, distortion-free legibility across dense dashboard layouts.
3. **JetBrains Mono** governs telemetry data points, IP routing tables, node latency readouts, and tactical tags. The fixed-pitch alignment prevents layout shifting during real-time data streaming.

## Layout & Spacing

The interface runs on an ultra-compact 12-column modular fluid grid system tuned for mission-critical command centers. 

- **Density Standards**: Spacing uses a compact 4px base rhythm (`0.25rem`). Gaps between telemetry widgets prioritize information density over decorative white space, allowing operators to oversee firewalls, intrusion traces, and system resource telemetry without scrolling.
- **Breakpoints & Adaptation**:
  - `Desktop (>= 1280px)`: 12-column grid, 24px margins, sticky tactical telemetry rail and peripheral node graphs.
  - `Tablet (768px - 1279px)`: 6-column grid, 16px margins, modular cards collapse into stacked dual-column diagnostics.
  - `Mobile (< 768px)`: 4-column grid, 16px margins, real-time node graphs switch to horizontal scroll carousels with strict card virtualization.

## Elevation & Depth

Visual hierarchy does not rely on soft drop shadows, which dilute contrast in dark environments. Depth is established via **luminance stepping, micro-borders, and targeted optic glow**:

- **Ground Level (Canvas)**: `#0B101B` background with an optional subtle 32px CSS circuit dot matrix at 4% opacity.
- **Level 1 (Card & Module Shells)**: `#131B2E` surface paired with a 1px solid border (`#1E293B`).
- **Level 2 (Popovers, Modals & Flyouts)**: `#172138` with a 1px outline (`rgba(0, 198, 255, 0.4)`) and an ambient, low-spread back-glow: `0 0 24px rgba(0, 198, 255, 0.08)`.
- **Node Active Bloom**: Live nodes and critical status gauges project an authentic luminescent aura using multi-layered box shadows (`0 0 8px rgba(0, 230, 118, 0.4), 0 0 20px rgba(0, 230, 118, 0.15)`).

## Shapes

The design system employs **Soft Level 1** corner geometry (`0.25rem` / `4px` default radius) to project an architectural, fortified, and technical tool feel. 

- Primary cards, buttons, telemetry counters, and input fields use crisp `4px` radii.
- Pill badges and operational status dots (`border-radius: 9999px`) are reserved exclusively for live connection states, active pulse indicators, and severity tags to distinguish operational telemetry from structural containers.
- High-level modal windows and command sheets use `8px` (`0.5rem`) to maintain structural precision at scale.

## Components

### Buttons
- **Primary Cyber-Action**: Background gradient from `#0084FF` to `#00C6FF`, text `#0B101B` (bold weight), border `none`. Hover emits an electric glow: `0 0 16px rgba(0, 198, 255, 0.4)`.
- **Secondary / Ghost Terminal**: Background `transparent`, border `1px solid #1E293B`, text `#F8FAFC`. Hover transitions border to `#00C6FF` with background `rgba(0, 198, 255, 0.06)`.
- **Destructive Mitigate**: Background `rgba(255, 59, 48, 0.1)`, border `1px solid #FF3B30`, text `#FF3B30`.

### Chips & Status Badges
- Constructed with `JetBrains Mono` at `label-md`. 
- **Healthy Node**: Background `rgba(0, 230, 118, 0.08)`, border `1px solid rgba(0, 230, 118, 0.3)`, text `#00E676`, accompanied by an active pulsing green dot (`6px`).
- **Defending/Mitigating**: Background `rgba(0, 198, 255, 0.08)`, border `1px solid rgba(0, 198, 255, 0.3)`, text `#00C6FF`.

### Input Fields & Terminal Consoles
- Inputs rest on surface `#0D1424` with a 1px border of `#1E293B`.
- Text is rendered in `#F8FAFC` with placeholder `#64748B`.
- Active focus state introduces a crisp electric cyan border (`#00C6FF`) and an inset subtle glow (`inset 0 0 6px rgba(0, 198, 255, 0.15)`).

### SecOps Telemetry Cards
- Slate background `#131B2E` with 1px border `#1E293B`.
- Header bar features a subtle bottom divider (`#1A243D`), monospaced section coordinate markers (`SEC-01`, `NODE-LIVE`), and contextual action buttons.
- Supports an integrated real-time sparkline or live network mesh canvas at the bottom margin.

### Checkboxes & Switches
- Checkboxes are `16px x 16px` with `2px` border radius, bordered by `#334155`. When checked, filled with `#00C6FF` featuring a dark `#0B101B` checkmark vector.
- Toggle switches feature a deep track `#1E293B` and transition into `#0084FF` when engaged, carrying a glowing indicator handle.