# Security policy

CueBell is a prototype with development-signed Android previews. It has not had
an independent security audit. It is not a production medical alarm or an
authoritative queue system.

## Report privately

Use [GitHub private vulnerability reporting](https://github.com/mathew1046/CueBell/security/advisories/new).
Include the affected release or commit, reproduction steps, likely impact and a
minimal redacted example. Use synthetic data, never live keys, bearer tokens,
patient information or unconsented audio.

Do not publish exploit details in public issues before assessment. If a credential
was exposed, revoke or rotate it immediately. Deleting a post or commit does not
invalidate it.

## Scope and support

Reports about microphone lifecycle, consent, session isolation, browser-origin
checks, credentials, provider routing, transcript handling and dependencies are
welcome. Assessment is best effort, with no response-time guarantee or bug bounty.
Start with the newest preview; older versions may not receive backported fixes.

Test a local instance with dummy credentials and mocked providers where possible.
Do not stress the public deployment or scan third-party speech/text services.

## Deployment requirements

- Keep provider credentials and pairing codes on the backend, never in APKs, web exports or `EXPO_PUBLIC_` variables.
- Use HTTPS/WSS, exact trusted proxy addresses and exact allowed browser origins. Keep the relay's upstream port private.
- Native streams use headers; browser streams authenticate in the first message after Origin validation. Never put bearer tokens in URLs. Origin checking is not user authentication.
- Anonymous admission is opt-in and permits paid-provider use. Add production admission controls, edge limits and provider spending limits.
- Run one relay worker/instance. Sessions and rate limits are bounded, in-memory safeguards, not durable accounts or distributed abuse controls.
- Exclude sensitive payloads, credentials and audio from application, proxy, host and monitoring logs.
- Recheck dependencies before release. Historical audit results do not establish the current dependency risk.

See [backend setup](backend/README.md), [browser deployment](docs/WEB.md),
[privacy](docs/PRIVACY.md) and the [documentation index](docs/README.md).
