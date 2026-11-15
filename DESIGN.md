---
name: CueBell Android
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

# Interface principles

CueBell uses a calm Material 3 interface focused on one task: tell it what to listen for, inspect the active task, and notice the alert.

## Keep the main workflow simple

- One active monitor, with a prominent Speak action and typed alternative.
- Short labels instead of greeting paragraphs or repeated instructions.
- No server URL, pairing code or provider settings in the user workflow.
- Captions, history and detailed help can expand without obscuring the task.
- A valid request activates automatically after consent and permissions; Stop stays available during setup and capture.

## Do not hide essential information

Processing recipients, consent, listening failures, uncertainty and the missed-call warning stay visible. An active task and an actively connected microphone are different states. Corrections must visibly replace or supersede outdated directions.

Visual feedback accompanies sound and vibration. The app should never use color alone to indicate failure, listening health or an alert.

## Accessibility

Use system font scaling, labelled controls, wrapping layouts, readable contrast and keyboard/screen-reader support. The primary Speak target is 64 dp; other actions should remain at least 48 dp. Large text and small screens must not hide Stop, consent or the latest warning.

English and 20 Indian UI languages are bundled. Translation coverage is not evidence of native-speaker review or speech-recognition accuracy. Test comprehension with representative users before claiming low-literacy or accessibility outcomes.

## Platform differences

Android uses native foreground-service capture and notification channels. Delivery still depends on permission, device policy, channel settings and Do Not Disturb.

The web interface shares the workflow but must explain visible-page listening. Browser vibration, notification, wake-lock and audio support vary by device. Do not imply an installed web app has Android foreground-service capabilities.

## Implementation references

- [Theme and semantic colors](mobile/src/lib/theme.ts)
- [Home](mobile/src/app/index.tsx) and [navigation](mobile/src/app/_layout.tsx)
- [Shared components](mobile/src/components)
- [Android and browser runtime](mobile/modules/queue-listener)
- [Verification checklist](docs/VERIFICATION.md)

The frontmatter preserves the existing machine-readable design tokens. Source and browser checks do not establish real-device alert reliability, TalkBack quality or representative-user usability.
