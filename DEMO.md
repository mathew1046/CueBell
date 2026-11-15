# How to use CueBell

CueBell listens for a spoken announcement you describe and gives a visual alert, with optional vibration and sound.

## 1. Open the app

- **Web:** open [cuebell.mathewjoseph.xyz](https://cuebell.mathewjoseph.xyz). Keep the page visible and screen unlocked. Hiding it stops capture; return and restart listening.
- **Android:** install the [development-signed preview](https://github.com/mathew1046/CueBell/releases/tag/v1.4.1-preview) for ARM64 phones running Android 7+. Start listening while the app is visible. Its microphone service can continue in the background or with the screen locked, subject to device restrictions.

You need internet and microphone access, but no account, API key or server address.

## 2. Set a task

### Type

1. On Home, tap the **pencil** beside the task.
2. Read the disclosure and check **Allow audio & text processing**.
3. In **What should I listen for?**, enter:

   > Tell me when pharmacy token 442 is called. Vibrate.

4. Tap **Start Listening** and allow microphone access.

### Speak

1. With no task set, tap **Start Listening** on Home. Accept processing if prompted, then tap again.
2. Allow microphone access and say your request. For example: **“Alert me when train 14922 arrives.”**
3. Finish speaking and wait. Short pauses are allowed. You can also use **Speak** on the pencil screen.

A valid request starts monitoring automatically, without another confirmation. If asked for clarification, specify the subject and event. Check the active task, especially names and digits; stop and edit it if wrong.

## 3. Check listening

Wait for **Listening**, not just a saved task. Keep the microphone uncovered and near enough to hear the announcement.

- Expand **Live captions** to read completed transcripts.
- Open **History** for recent session events.
- Check connection and unclear-announcement warnings. Audio missed during a gap cannot be recovered.

## 4. Read an alert

For the pharmacy request above:

| Announcement | Intended result |
| --- | --- |
| “Token 441, counter one.” | No alert for token 442. |
| “Token four four two, counter two.” | Matching alert, including the counter when recognized. |
| “Correction: token 442, counter three.” | A recognized correction updates or marks the earlier alert. |

Open **Details** to see **What was heard**. Tap **I’ve seen this** to acknowledge. **Back** leaves the alert available in the app. Sound and vibration depend on the request, device support, permissions, volume and notification settings.

## 5. Stop or change a task

- **Stop Listening** on Home pauses capture but keeps the task and history. **Start Listening** resumes it.
- To edit, stop listening and tap the **pencil**.
- **Settings → Clear task** stops capture and removes the task and local history. Older previews may call this **Stop**.
- Android's notification action **Stop microphone** only pauses capture.

## Settings and troubleshooting

- The language control changes interface labels; speech-language detection is automatic.
- **Settings → Accessibility → Spoken alerts** controls spoken output. **Appearance** changes the theme.
- **Settings → Listening → Noise reduction** is experimental and off by default. Stop setup or pause listening before changing it. It runs locally but can worsen recognition.
- No captions? Check Listening, microphone permission, connection, microphone placement and web-page visibility.
- No alert? Check the task, transcript and uncertainty warning.
- Session expired? Submit the request again. Service busy? Wait before retrying.

## Privacy and safety

Audio goes to **Gnani Prisma**; requests and transcripts go to the configured **OpenAI text fallback**. The app/relay do not save recording files or transcript databases; provider terms still apply. [Privacy details](docs/PRIVACY.md).

Capture only permitted speech. Start with your own voice or a consenting speaker. CueBell is supplemental, not an official queue system or emergency alarm: errors, noise and interruptions can cause missed or false alerts. Keep the venue display or staff as your fallback.
