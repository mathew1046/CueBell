---
name: QueueSaathi Android
description: A minimal native Material 3 shell for confirmed queue monitoring.
colors:
  light-primary: "#075E54"
  light-on-primary: "#FFFFFF"
  light-background: "#F1F8F6"
  light-surface: "#FFFFFF"
  light-surface-variant: "#DFECE6"
  light-on-surface-variant: "#3E4944"
  light-secondary-container: "#C4ECDD"
  light-on-secondary-container: "#002C23"
  light-on-surface: "#102F29"
  light-error: "#BA1A1A"
  light-outline: "#64776E"
  light-error-container: "rgba(249, 222, 220, 1)"
  light-on-error-container: "rgba(65, 14, 11, 1)"
  dark-primary: "#85D5BE"
  dark-on-primary: "#00382E"
  dark-background: "#101E1A"
  dark-surface: "#172B24"
  dark-surface-variant: "#293D34"
  dark-on-surface-variant: "#C1CEC6"
  dark-secondary-container: "#244C40"
  dark-on-secondary-container: "#C4ECDD"
  dark-on-surface: "#E0F2E9"
  dark-error: "#FFB4AB"
  dark-outline: "#94A79D"
  dark-error-container: "rgba(140, 29, 24, 1)"
  dark-on-error-container: "rgba(242, 184, 181, 1)"
typography:
  headline-medium:
    fontFamily: "sans-serif"
    fontSize: "28sp"
    fontWeight: 400
    lineHeight: "36sp"
    letterSpacing: "0sp"
  headline-small:
    fontFamily: "sans-serif"
    fontSize: "24sp"
    fontWeight: 400
    lineHeight: "32sp"
    letterSpacing: "0sp"
  title-large:
    fontFamily: "sans-serif"
    fontSize: "22sp"
    fontWeight: 400
    lineHeight: "28sp"
    letterSpacing: "0sp"
  title-medium:
    fontFamily: "sans-serif-medium"
    fontSize: "16sp"
    fontWeight: 500
    lineHeight: "24sp"
    letterSpacing: "0.15sp"
  body-large:
    fontFamily: "sans-serif"
    fontSize: "16sp"
    fontWeight: 400
    lineHeight: "24sp"
    letterSpacing: "0.15sp"
  body-medium:
    fontFamily: "sans-serif"
    fontSize: "14sp"
    fontWeight: 400
    lineHeight: "20sp"
    letterSpacing: "0.25sp"
  label-large:
    fontFamily: "sans-serif-medium"
    fontSize: "14sp"
    fontWeight: 500
    lineHeight: "20sp"
    letterSpacing: "0.1sp"
  token:
    fontFamily: "sans-serif"
    fontSize: "56sp"
    fontWeight: 700
    fontFeature: "tabular-nums"
  confirmation-token:
    fontFamily: "sans-serif"
    fontSize: "36sp"
    fontWeight: 700
    fontFeature: "tabular-nums"
rounded:
  field: "4dp"
  panel: "16dp"
  button: "20dp"
spacing:
  detail: "4dp"
  compact: "8dp"
  error-vertical: "12dp"
  group: "16dp"
  section: "24dp"
components:
  button-primary:
    backgroundColor: "{colors.light-primary}"
    textColor: "{colors.light-on-primary}"
    typography: "{typography.label-large}"
    rounded: "{rounded.button}"
  button-tonal:
    backgroundColor: "{colors.light-secondary-container}"
    textColor: "{colors.light-on-secondary-container}"
    typography: "{typography.label-large}"
    rounded: "{rounded.button}"
  button-outlined:
    textColor: "{colors.light-primary}"
    typography: "{typography.label-large}"
    rounded: "{rounded.button}"
  button-text:
    textColor: "{colors.light-primary}"
    typography: "{typography.label-large}"
    rounded: "{rounded.button}"
  request-field:
    backgroundColor: "{colors.light-background}"
    textColor: "{colors.light-on-surface}"
    rounded: "{rounded.field}"
  confirmation-panel:
    backgroundColor: "{colors.light-surface-variant}"
    rounded: "{rounded.panel}"
    padding: "{spacing.section}"
  alert-panel:
    backgroundColor: "{colors.light-secondary-container}"
    rounded: "{rounded.panel}"
    padding: "{spacing.section}"
  error-region:
    backgroundColor: "{colors.light-error-container}"
    textColor: "{colors.light-on-error-container}"
    typography: "{typography.body-large}"
    padding: "12dp 24dp"
  appbar:
    backgroundColor: "{colors.light-background}"
    textColor: "{colors.light-on-surface}"
    typography: "{typography.title-large}"
---

# Design System: QueueSaathi Android

## Overview

**Creative North Star: "Native Material task shell"**

This is the incumbent implementation, not a newly selected visual concept. The user declined visual screen selection and requested a minimal native Android Material 3 application using React Native Paper. No visual comp was approved. The interface is calm, task-led and explicit about whether the microphone is actually listening.

Current decision: keep the experience very simple, elegant and minimal for elderly people and people with limited literacy. Remove greeting/help paragraphs and connection administration from the task surface. Use short labelled actions, a prominent Speak button and progressive disclosure rather than asking users to read a manual before acting. Keep processing recipients, explicit consent, listening failures, uncertainty and brief safety guidance visible; do not mistake less copy for permission to hide risk.

Validated intent and event data drive a fixed accessible shell; model output must not generate or execute arbitrary UI or code. Prominent token information, typed setup and visible coverage gaps support people who are deaf or hard of hearing. This remains a supplemental aid, not an official queue display.

**Key Characteristics:**
- Native Android controls and system typography, not a web interface.
- Muted green surfaces with a stronger teal action accent.
- One scrollable task shell and one confirmed monitor.
- Short labelled actions, a 64dp Speak target and collapsed secondary detail.
- Explicit consent, confirmation, listening health and correction states.

Source authority: /home/mathew/Arrakis/QueueSaathi/mobile/src/lib/theme.ts, /home/mathew/Arrakis/QueueSaathi/mobile/src/app/index.tsx, /home/mathew/Arrakis/QueueSaathi/mobile/src/app/_layout.tsx, /home/mathew/Arrakis/QueueSaathi/mobile/src/lib/api.ts and the local Kotlin queue-listener module. Paper defaults were checked in the installed react-native-paper source. This records source behavior, not a device-reliability certification.

Current minimal-interface review: Android 36 emulator light and dark/1.3× text captures were opened and independently reviewed with a **pass**, with no blocking issues in the initial task surface. Evidence: /home/mathew/Arrakis/QueueSaathi/.impeccable/review/minimal/main-light.png and /home/mathew/Arrakis/QueueSaathi/.impeccable/review/minimal/main-dark-large.png. The build is UI-only QA: no hosted origin has been supplied, so it is not a connected release. Tests: 227 backend, 13 mobile workflow and 6 native unit tests pass; TypeScript and lint pass. Active alerts, representative-user usability, physical phones, TalkBack and live end-to-end behavior remain unverified by this review. Legacy captures are historical only.

Historical review record: earlier Android 36 emulator screenshots and the then-reported 165 backend / 6 native test passes belonged to an older shell. Those captures predated error-region, confirmation-scroll, health-announcement and corrected-acknowledgement fixes as well as this simplification; they do not establish the current render or provider/device reliability.

## Colors

The frontmatter records all app overrides plus the inherited error-container pair used for visible failures. Keys prefixed `light-` and `dark-` are corresponding semantic roles; the Android system color scheme selects the theme. Components above show the light mapping; dark mode uses the same roles, not the light literals.

### Primary
- **Deep teal / soft mint primary:** contained actions, active microphone icon and active-rule token use `primary`; contained labels use `onPrimary`.

### Secondary
- **Mint secondary container:** normal call alerts and the pause-listening tonal button. Tonal buttons use `onSecondaryContainer`.

### Neutral
- **Pale mist / deep green background:** app canvas, app bar and outlined field fill.
- **White / forest surface:** Paper surface role, with `surfaceVariant` reserved for the confirmation panel.
- **Dark ink / pale mint ink:** `onSurface` for main content; `onSurfaceVariant` for explanatory copy and inactive status icons. Outlined fields use `outline`.
- **Error roles:** clarification uses `error`. Persistent failures use `errorContainer` with explicit `onErrorContainer`; corrected alerts switch to `errorContainer` and carry correction wording.

**The Named State Rule.** Listening, interruption, unknown counters and corrections must have words, not color alone.

The theme spreads Paper's MD3 defaults before overriding the listed colors. Disabled, ripple, divider, error-container and other unoverridden roles remain library-owned; do not invent a complete green tonal system or imply every Paper role has been recolored. The sidecar's eight-step OKLCH ramps are synthesized documentation swatches, not implemented Android palette tokens; extreme steps may be gamut-mapped by the panel. Corrected alert text currently inherits its Text defaults rather than explicitly assigning `onErrorContainer`; that is a review constraint, not a reusable semantic-color prescription.

## Typography

Android system sans-serif (normally Roboto), with `sans-serif-medium` for medium roles; no downloaded display font. This is an intentional native-platform choice. Font sizes and line heights above are Android scaled text units, not CSS lengths. Body text keeps system font scaling; do not add a scaling cap or force single-line content.

Hierarchy: task/alert headings use headline-small; app bar, confirmation heading and section titles use title-large; listening status uses title-medium. Request/alert/history text and expanded privacy details use body-large; recipient disclosure, brief safety guidance, health detail and timeline detail use body-medium; transcript labels and Paper button labels use label-large. The inherited headline-medium role remains recorded above but is not used for a greeting or introductory headline in the current shell. Custom token and confirmation-token styles are bold, tabular numerals; their source does not set a custom line height. Preserve prefixes and leading zeros as text. Checkbox label is explicitly 16sp and left aligned.

**The Digits First Rule.** Keep the token prominent and checkable; never shorten it, convert away leading zeros or rely on a colored status badge to convey its meaning.

## Layout

Single-column native app: title-only app bar, persistent error region when needed, then a keyboard-aware ScrollView. Outstanding alerts precede short listening health, consent/recipient disclosure when the microphone is off, the active rule, request/clarification/confirmation, the collapsed Announcements disclosure, brief safety guidance and About & privacy. Request setup is hidden during announcement monitoring. Errors stay outside the scroll body below the app bar, with Dismiss and an Android-permissions recovery action when appropriate.

Content is centered, full available width with maximum width (640dp), horizontal padding (24dp), top padding (16dp) and section gap (24dp). Bottom padding is `max(bottomSafeInset, 24) + 24` dp. App bar uses Paper's native safe-area behavior. Groups/panels use 16dp gaps; action rows wrap with 8dp gaps rather than shrinking controls. Small text/detail gaps are 4dp. The implemented reusable spacing is 4/8/12/16/24dp; the earlier 32dp suggestion is not an implemented spacing token.

Every app Button content has minimum height (48dp), with Speak enlarged to (64dp); consent Checkbox.Item also has minimum height (48dp). Outlined multiline request has minimum height (120dp). Text and controls must wrap and remain reachable by scrolling at larger Android font sizes; there is no implemented breakpoint grid or desktop layout.

There is no settings screen, cog, connection Modal, URL field or pairing-code field. The operator supplies the service origin through EXPO_PUBLIC_API_URL before building; the app obtains and securely stores an expiring bearer automatically on the first consented action. This is not a user connection task. The keyboard is avoided with padding; request taps remain handled while open. Confirmation dismisses the keyboard, scrolls the review panel into view without animation and announces its availability. New alerts scroll to the top without animation.

## Elevation & Depth

Flat task grouping: alert and confirmation Surfaces explicitly use elevation (0), with tonal fills and whitespace rather than decorative card shadows. The app bar is background-colored. Paper owns its own ripple, focus, loading and disabled behavior; no custom shadow vocabulary is implemented. Do not infer a global ban on native elevation from these two flat panels.

No decorative motion. Existing functional movement is Paper control feedback/loading and keyboard behavior; alert and confirmation scrolls are explicitly nonanimated. Disclosure toggles reveal inline content, not a modal. No custom motion durations or easing tokens are established.

## Shapes

Rounded alert/confirmation panels (16dp corners), padded (24dp). Installed Paper MD3 roundness is (4dp); outlined inputs inherit that radius and buttons use five times roundness (20dp). Preserve Paper outlines and native ripple clipping. Ordinary sections and timeline entries are not boxed cards. No chip, tab bar or decorative illustration system exists.

## Components

### Buttons
Short visible labels name actions: Speak, Continue, Start listening, Change, Pause, Stop and I’ve seen this. Speak is contained for an empty request and outlined once text is present; Continue does the inverse. Speak has a microphone icon and 64dp minimum content height; other buttons retain 48dp. Request capture offers outlined Cancel; pause is tonal; stop/change/disclosure actions are text buttons. Paper supplies pressed/ripple/focus/disabled states, not custom web hover effects. Busy state disables conflicting operations and uses loading indicators on relevant actions. Speaking and interpretation require explicit consent and prepare a session automatically; Continue additionally requires nonempty text and an idle microphone.

### Inputs / Fields
One Paper outlined multiline request field labelled “Token and alert”, with the short placeholder “Token 442. Vibrate.” and a 1500-character limit. It is not editable while busy or capturing. There are no user-facing service URL, pairing-code or masked-code fields. Typed setup remains available without microphone permission. Do not replace the field label with a placeholder or rely on an icon alone for speaking.

### Consent and progressive disclosure
While the microphone is off, the explicit “Allow audio & text processing” checkbox is accompanied by “Audio goes to Gnani. Text goes to OpenAI.” Processing requires the checkbox; it is not implicit in tapping Speak or Continue. About & privacy is collapsed by default and expands inline to show the hospital-pharmacy token grammar, Malayalam/English speech or typing, Gnani Prisma audio and OpenAI text processing, app/relay storage claims and provider-terms qualification, background interruption and microphone-notification guidance, and the supplemental-aid limitation. These are source disclosure statements, not independent verification of provider retention or device reliability. “Calls may be missed. Check the venue display.” stays visible outside the disclosure.

### Navigation
One route shell with a title-only app bar, not a navigation dashboard. About & privacy and Announcements are labelled inline disclosure buttons with expanded accessibility state, not settings navigation. Secure-session restore has a labelled ActivityIndicator. No settings action, modal, tab or drawer navigation is implemented.

### Listening health
An icon (24dp) and short status distinguish “Listening”, “Paused” and “Not listening”; request capture says “Speak, then pause”, with “Starting...” and “Listening interrupted” for nonready capture. Additional native detail appears for interruptions/gaps or other relevant health messages, not a permanent help paragraph. A confirmed rule is not listening coverage. Health transition announcements deduplicate on native mode/state/active-rule presence; repeated heartbeats and countdown messages do not repeatedly interrupt TalkBack. The initial state is not announced as a transition.

### Confirmation panel
Flat surface-variant panel with “Is this right?”, a large token, alert preferences, primary “Start listening” and secondary “Change”. No venue paragraph or repeated confirmation instructions are displayed here. The accessibility announcement still explains that nothing has started and requests review. Ambiguous interpretation instead shows polite live-region clarification; it cannot silently start listening. Source scroll-and-announcement behavior is documented above; native verification of the latest minimal copy remains pending.

### Alerts and timeline
Outstanding alerts use “Your turn”, a prominent token, “Go to counter …” or “Counter unclear”, “Check the venue display.” and “I’ve seen this”. Corrected/cancelled calls use “Call changed” and “Previous call corrected or cancelled.” Alerts/corrections are spoken through AccessibilityInfo. Acknowledgement dismisses the native notification; corrected alerts are hidden after acknowledgement using either state or the separate acknowledged boolean.

Announcements is collapsed by default, absent when there are no events and no active rule. An active monitor can expose the disclosure before events arrive; expanding it then shows “No announcements yet.” A latest uncertain observation keeps “Unclear announcement. Check the display.” visible even while history is collapsed. Expanded uncertain entries retain their own warning and ambiguity detail. Completed transcript text is selectable. UI renders at most 30 recent entries from a bounded 100-event list; no seeded live data. Headers are marked where implemented; status has a combined accessible label. Persistent errors use an assertive alert live region. Do not claim complete TalkBack coverage from these attributes alone.

### Native notification surface
Kotlin, not JavaScript timers, owns microphone capture, transport and notifications. Capture starts only with the app visible and the required permissions/visible listening channel. Ongoing private listening-status notification has a Stop microphone action and visible interruption/gap messages. Token-call notifications use separate preference-specific channels, optional sound/vibration and a generic public lock-screen version; visual in-app alerts remain necessary. Notification preferences are subject to Android channel settings and OS behavior. No full-screen takeover or guaranteed background/lock-screen delivery is promised.

## Do's and Don'ts

### Do:
- **Do** use native Paper controls, semantic theme roles and system font scaling.
- **Do** preserve the 64dp Speak target, 48dp minimum other actions, wrapping rows and scroll access to every action.
- **Do** keep consent, confirmation, listening failures and correction language visible.
- **Do** keep recipients, brief safety guidance and the latest uncertainty warning outside collapsed detail.
- **Do** preserve token prefixes and leading zeros and provide visual alternatives to sound/vibration.
- **Do** verify final light/dark, large-text, keyboard, Back, permission and TalkBack states on Android.

### Don't:
- **Don't** replace this Android shell with a web dashboard or restart visual-direction selection.
- **Don't** render arbitrary model-generated UI/code or fabricate live timeline entries.
- **Don't** equate a confirmed monitor with an actively connected microphone.
- **Don't** reintroduce greeting/help paragraphs, connection settings or URL/pairing entry into the minimal task shell.
- **Don't** use color alone for health, uncertainty, errors or correction states.
- **Don't** claim provider access, final active-alert testing or physical-device/background reliability from source or prior emulator screenshots.
