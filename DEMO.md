# How to use CueBell

CueBell listens for a spoken announcement you care about and turns it into a personal visual alert, with optional vibration and sound.

For example: **“Tell me when pharmacy token 442 is called. Vibrate.”**

## 1. Open the app

- **Web:** open [cuebell.mathewjoseph.xyz](https://cuebell.mathewjoseph.xyz).
- **Android:** install the APK from the [Android preview release](https://github.com/mathew1046/CueBell/releases/tag/v1.4.0-preview). The preview is development-signed and supports ARM64 phones running Android 7 or later. Only install APKs you trust.

You need an internet connection and microphone access. No account, API key or server address needs to be entered in the current hosted app.

On the web, **keep the page visible and the screen unlocked while listening**. Switching tabs, minimizing the browser or locking the screen stops capture. Return and start listening again.

## 2. Describe what to listen for

You can type your request or say it aloud.

### Type a request

1. On Home, tap the **pencil** beside the listening task.
2. Read the processing disclosure and select **Allow audio & text processing**.
3. In **What should I listen for?**, enter a clear request:

   > Tell me when pharmacy token 442 is called. Vibrate.

4. Tap **Start Listening** and allow microphone access when prompted.

### Say a request

1. On Home, tap **Start Listening**. If prompted, read and accept the processing disclosure, then tap it again.
2. Allow microphone access and describe your task. For example:

   > Alert me when train 14922 arrives.

3. Finish speaking and wait while CueBell understands the request. Short pauses are allowed. You can also open the pencil screen and use **Speak**.

A clear, valid request starts monitoring automatically. There is no second task-confirmation tap. If CueBell asks for clarification, make the subject and event more specific, then try again.

**Check the active task before relying on it.** If a number, name or condition is wrong, stop listening and edit the request.

## 3. Wait for Listening

Keep the microphone within useful range of the announcement. Avoid covering it or placing the phone inside a bag.

- Wait for the **Listening** status. A saved task alone does not mean audio is being captured.
- Expand **Live captions** to see the completed speech transcripts.
- Open **History** to review recent session events.
- Check any connection or unclear-announcement warning. Audio missed during a connection gap is not recovered afterward.

On Android, start listening while the app is visible. The microphone foreground service can then continue in the background or with the screen locked. Keep its ongoing notification available; phone battery restrictions and permissions can still interrupt it.

## 4. Read the alert

With the pharmacy task above, these examples illustrate the intended behavior:

- **“Token 441, please go to counter one.”** No alert for your target token 442.
- **“Token four four two, please go to counter two.”** A visible alert for the matching call, including the counter when recognized.
- **“Correction: token 442 should go to counter three.”** A recognized correction updates the result rather than leaving the old directions unmarked.

Read the alert and its source text. Acknowledge it using the alert's acknowledgment control when available. Sound and vibration depend on your request, device support, permissions, volume and notification settings.

These are usage examples, not guarantees that every spoken announcement will be recognized correctly. Check the venue display or staff if the result is unclear.

## 5. Pause, change or clear a task

- **Pause capture:** tap **Stop Listening** on Home. The microphone stops, but the task and recent history remain.
- **Resume:** tap **Start Listening** again. On the web, return to the visible page first.
- **Change the task:** stop listening, tap the pencil, then enter a new request.
- **Remove the task and history:** open **Settings** and choose **Clear task**. Older Android preview builds may label this action **Stop**.
- **Android notification:** **Stop microphone** pauses capture. It does not replace clearing the task in Settings.

A spoken stop request can also pause listening when recognized. Use the on-screen control if it does not respond.

## Settings you may want

- **Language:** use the language control to change interface labels. Speech-language detection is automatic; changing the interface language does not guarantee recognition in that language.
- **Accessibility:** open accessibility settings for available display and spoken-alert options.
- **Noise reduction:** experimental and off by default. Stop setup or pause listening before changing it in Settings. It runs locally, but can make some words harder to recognize. Turn it off if results worsen. [Methods and results](docs/NOISE_REDUCTION.md).

## Common problems

- **No captions:** check Listening, microphone permission, internet access, speaker distance and, on the web, page visibility.
- **Captions appear but no alert:** check the active task and every digit or name. Wait for interpretation and inspect uncertainty warnings. Do not assume the transcript is correct.
- **No vibration or sound:** check the requested alert type, phone volume, notification permission, channel settings and Do Not Disturb. Some browsers do not support vibration.
- **Session expired:** submit your request again. Server restarts also clear active sessions.
- **Service busy or unavailable:** wait before retrying. The hosted prototype has session and provider limits.

## Privacy and safe use

The consent disclosure explains the processing: audio goes to **Gnani Prisma**, while requests and transcripts go to the configured **OpenAI text fallback**. The app and relay do not intentionally save audio recordings or transcript history to disk; provider terms still apply. See [Privacy](docs/PRIVACY.md).

Only capture speech where you have permission. For a first try, use your own voice or a consenting speaker in a quiet setting.

**CueBell is a supplemental aid, not an official queue display or emergency alarm.** Noise, recognition errors, network interruptions and device restrictions can cause missed or incorrect alerts. Always keep another way to check important announcements.
