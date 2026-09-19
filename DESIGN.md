---
name: FirstWeek
description: A project handover with readable context and inspectable sources.
colors:
  pine: "#173c35"
  ink: "#18362f"
  muted: "#576b64"
  line: "#dce3df"
  ground: "#f2f5f2"
  action: "#d5ee85"
  action-hover: "#c6e475"
  action-ink: "#203523"
  sheet: "#ffffff"
  source-paper: "#f8faf6"
  note: "#f1f5ed"
  rail-text: "#edf3ec"
  focus: "#478372"
  error: "#923f32"
typography:
  body:
    fontFamily: "FirstWeek, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.55
  reading:
    fontFamily: "FirstWeek, Segoe UI, sans-serif"
    fontSize: "13px"
    lineHeight: 1.8
  label:
    fontFamily: "FirstWeek, Segoe UI, sans-serif"
    fontSize: "12px"
  small:
    fontFamily: "FirstWeek, Segoe UI, sans-serif"
    fontSize: "11px"
  section-title:
    fontFamily: "FirstWeek, Segoe UI, sans-serif"
    fontSize: "30px"
    fontWeight: 500
    lineHeight: 1.25
    letterSpacing: "-.025em"
rounded:
  compact: "6px"
  control: "7px"
  initial: "10px"
  inset: "12px"
  circle: "50%"
spacing:
  compact: "8px"
  related: "12px"
  row: "18px"
  inset: "22px"
  mobile-gutter: "23px"
  tablet-gutter: "28px"
  section-gap: "32px"
  desktop-gutter: "38px"
components:
  button-primary:
    backgroundColor: "{colors.action}"
    textColor: "{colors.action-ink}"
    rounded: "{rounded.control}"
    padding: "12px 18px"
  button-primary-hover:
    backgroundColor: "{colors.action-hover}"
  button-text:
    textColor: "{colors.ink}"
    padding: "0"
  button-icon:
    textColor: "{colors.ink}"
    width: "44px"
    height: "44px"
  field:
    backgroundColor: "{colors.sheet}"
    rounded: "{rounded.control}"
    padding: "13px"
  citation:
    backgroundColor: "{colors.note}"
    rounded: "{rounded.compact}"
    padding: "9px 10px"
  note:
    backgroundColor: "{colors.note}"
    rounded: "{rounded.inset}"
    padding: "22px"
---

# Design System: FirstWeek

## Overview

**Creative North Star: "The project handover board"**

FirstWeek uses deep pine navigation, pale mineral surroundings and white reading sheets to make project context feel settled and approachable. Plain humanist typography, compact source rows and fine dividers support reading. Lime identifies actions and small identity accents.

This is the system implemented by `frontend/src/firstweek/firstweek.css`, `Workspace.jsx`, `Login.jsx` and `Brand.jsx`, following direction seed `4e541dc4`. It applies to the FirstWeek workspace and login surface. Linked account flows do not yet use this system. The finish reviewer disposition is **ship** for the supplied overview and login desktop/mobile captures; Ask, Knowledge and People have source review only. This record does not extend that visual validation or claim production readiness.

**Key Characteristics:**

- Pine navigation framing light reading surfaces.
- Humanist text with restrained, sentence-case headings.
- Divided rows for lists and rounded insets for guidance.
- Source identity and evidence remain visible alongside the work.

## Colors

A green-tinted neutral family carries most of the interface; lime provides the brighter action accent. Normative values are in the frontmatter.

### Primary

- **Deep pine (`pine`)** anchors navigation and the login story, and fills the question send control.
- **Lime (`action`, `action-hover`)** marks primary calls to action, the brand dot, active project dot and text selection. `action-ink` supplies primary-button text.

### Neutral

- **Forest ink (`ink`)** carries primary reading and control text; **muted green (`muted`)** carries supporting descriptions and metadata.
- **Mineral ground (`ground`)**, **white sheet (`sheet`)**, **source paper (`source-paper`)** and **note wash (`note`)** distinguish workspace, main reading, evidence and contextual guidance.
- **Fine divider (`line`)** separates rows and panes. **Pale rail text (`rail-text`)** maintains contrast on pine.
- **Focus green (`focus`)** marks keyboard focus; **brick error (`error`)** marks failure messages.

**The Surface Roles Rule.** Keep navigation dark, main reading white and supporting evidence lightly tinted in FirstWeek workspace compositions.

## Typography

**Display and body font:** self-hosted Atkinson, registered as `FirstWeek`, with `Segoe UI, sans-serif` fallback. Regular and bold Latin WOFF2 files are served from `/fonts/firstweek/` with `font-display: swap`. There is no distinct display or label family.

The hierarchy is compact and purpose-based, not a mathematical scale. Body text uses the frontmatter body role; reading introductions use the reading role. Source prose uses a slightly looser line height (1.85) and a maximum measure of 72ch; lead descriptions stop at 66ch. Labels use 12px, metadata generally 10–11px, and row titles 12–16px.

Section headings use the recorded section-title role, reducing to 28px on narrow phones. Project headings use 32px, reducing to 29px. Larger introduction and login headings use fluid sizes with tight negative tracking; these are surface-specific compositions rather than a universal display token. The CSS requests intermediate weights (500, 550, 600 and 650), but only 400 and 700 font files are provided: these are browser-matched weights, not a variable-font range or separately supplied font faces.

**The One Family Rule.** Use the self-hosted humanist family across headings, controls and reading text; preserve tabular numerals for numbered reading steps, citation numbers and the composer count.

## Layout

Desktop workspace uses a sticky, viewport-height rail (240px), a flexible main area and a source pane (310px). The source reader expands to at least 310px or 43% of the available project body. The directory is centered with a maximum width of 1160px. Main sections and headers share a desktop gutter; spacing steps in frontmatter describe recurring values, not an enforced global grid.

At 1500px and wider, the principal gutter becomes 54px and the resting source pane 350px. At 1100px and below, the rail reduces to 200px and the source pane to 260px. At 800px and below, the rail becomes a horizontal header, the source pane follows the main content, and project tabs remain horizontally scrollable. The open mobile reader has no height cap; desktop reading is capped at 75vh with internal scrolling. A dedicated mobile sign-out control preserves the account action when the rail footer disappears.

At 520px and below, the project header stacks, the main gutter becomes 23px, and directory search fills its own row. Login changes from equal columns to a single column; its form remains constrained to 345px. These changes preserve reading order instead of shrinking a desktop board into the viewport.

## Elevation & Depth

The implemented system is flat: surface color, fine borders and adjacency provide depth. It has no drop-shadow vocabulary. Keyboard focus uses an outline rather than a shadow. Selecting a source reveals it with a clipped horizontal uncover animation (220ms, `cubic-bezier(.16, 1, .3, 1)`); project-row hover changes background over 150ms. Reduced-motion preference removes the reveal animation and workspace transitions.

**The Flat Reading Rule.** Use tonal surfaces and dividers to separate reading contexts; retain outline-based keyboard focus.

## Shapes

Small rounded controls use the control radius. Citation buttons and compact navigation links use the compact radius; identity initials use the initial radius; guidance notes and the composer use the inset radius. Numbered reading steps and project dots are circular. Main panes and document lists remain rectangular, with one-pixel dividers. Brand and utility icons are SVG strokes; no shipping raster imagery is used.

## Components

### Buttons

Primary actions use lime fill, dark text and the control radius, with the padding recorded above; hover darkens the lime. Text actions are unboxed and gain an underline on hover. Icon controls occupy 44px squares and gain a pale green background on hover. Disabled buttons reduce opacity to one-half and use a not-allowed cursor. Shared keyboard focus is a two-pixel focus-green outline offset four pixels.

### Chips

Citations are compact, pale-note buttons with a bold tabular number, source heading and SVG arrow. They open evidence. Technology labels are plain text separated by vertical rules, not filled chips. There is no generic selected-chip system.

### Cards / Containers

Guidance notes are inset, tinted and rounded, with a small heading, supporting text and optional text action. Directory projects, source documents, reading steps and people use divided rows. Main reading and source containers are flat panes without individual card shadows.

### Inputs / Fields

Login fields are white, lightly bordered and gently rounded, with labels above. The directory search uses only a lower border. The question composer groups a resizable textarea and pine send button inside a rounded white border; focus within strengthens that border with an additional outline. The textarea delegates its focus treatment to the group. Errors are explicit text in brick; request state disables dependent controls. The source contains no additional disabled-input visual variant to inherit.

### Navigation

Workspace navigation lives on pine with pale text, a softly filled All projects link and a darker green active project row with a lime dot. Project tabs use muted text, a pine underline and heavier text for the active destination. Breadcrumb and auxiliary text links underline on hover. Mobile retains the brand, project-directory entry and account action while omitting the expanded project list.

### Reading path and source reader

The reading path uses numbered circular steps with title, description and arrow. A source opens in the evidence pane, with document identity, snapshot metadata and expandable repository evidence. On mobile, selection brings that reader into view below the work. Document headings retain a separate compact reading hierarchy; code uses a pale inset background. Keep long source text wrappable and code blocks horizontally scrollable.

## Do's and Don'ts

### Do:

- **Do** use the self-hosted FirstWeek family and the recorded surface roles on new FirstWeek screens.
- **Do** distinguish list rows with fine dividers and reserve tinted rounded insets for guidance and composed controls.
- **Do** retain visible keyboard focus, reduced-motion behavior and source-reading order across breakpoints.
- **Do** show source identity, snapshot metadata and explicit empty or error states beside the relevant content.

### Don't:

- **Don't** assume other account routes use this system or were covered by the FirstWeek visual review.
- **Don't** turn intermediate CSS font-weight requests into claims of additional installed font faces.
- **Don't** replace readable source rows with decorative imagery or hide evidence behind an unlabeled icon.

Not canonized: the 9px mobile composer note and 10px metadata are existing compact text treatments, not a recommended new readability floor; surface-specific headline sizes and isolated colors are not global tokens. No invented kickers, hard offset shadows, glyph icons or system display faces are promoted into this system.

### Conversational Ask update

User turns appear in a pale mineral message panel aligned to the right, with a small “You” label. Assistant replies retain the reading column and adjacent source controls. A pending turn shows the submitted question immediately and a text status while sources are read. Enter submits, Shift+Enter inserts a line, and New conversation clears in-memory context. Context is scoped to this project and limited to the last three completed turns. The existing colors, typefaces, focus styling and mobile stacked source reader remain in use.

### Visual architecture

The Architecture tab uses native SVG to show source-backed components and directed connections. The same flow is available as readable text below the figure. Wide diagrams scroll within a keyboard-focusable region on mobile. Component responsibilities and a source-reader action provide supporting detail. Architecture data stays behind the project membership gateway.
