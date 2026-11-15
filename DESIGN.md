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

One workflow: describe a task, inspect it, notice an alert.

## Keep controls simple

- Offer spoken setup and a typed alternative.
- Use short labels; keep captions, history and help expandable.
- Keep connection settings and provider keys out of the user interface.
- Activate valid requests automatically after consent and permissions.
- Keep Stop Listening available during setup/capture and Clear task in Settings.

## Make state visible

Distinguish a saved task from a connected microphone. Show consent, processing recipients, listening failures, uncertainty and coverage gaps. Mark corrections rather than silently leaving outdated directions. Pair sound and vibration with visual feedback; never rely on color alone.

## Accessibility

Support system font scaling, labelled controls, wrapping layouts, readable contrast, keyboards and screen readers. Target at least 48 dp for actions. Large text and small screens must not hide stopping, consent or warnings.

English and 20 Indian UI languages are bundled. This does not establish native-speaker review, recognition accuracy or representative-user usability.

## Platform limits

Android delivery depends on foreground-service permissions, device policy, notification channels and Do Not Disturb. Web listening requires a visible page; browser vibration, notifications, wake locks and audio vary. An installed web app does not gain Android background capture.

CueBell is supplemental. Source/browser checks do not establish physical-device alert reliability or accessibility outcomes.

## Implementation

[Theme](mobile/src/lib/theme.ts) · [Home](mobile/src/app/index.tsx) · [Navigation](mobile/src/app/_layout.tsx) · [Components](mobile/src/components) · [Capture runtimes](mobile/modules/queue-listener) · [Verification](docs/VERIFICATION.md)
