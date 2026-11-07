# Security policy

CueBell is a prototype with development-signed Android previews. It has not had
an independent security audit and must not be treated as a production medical
alarm or an authoritative queue system.

## Report a vulnerability privately

Use GitHub's private vulnerability reporting:
https://github.com/mathew1046/CueBell/security/advisories/new

Include the affected release/commit, reproduction steps, expected impact and a
minimal redacted proof of concept. Use synthetic data. Never include live provider
keys, bearer tokens, patient information or unconsented audio.

Do not publish exploit details in issues before the maintainer has assessed them.
If you exposed a credential, revoke/rotate it immediately; deleting the post or
commit does not invalidate the credential.

## Scope and support

Report issues involving microphone lifecycle, consent, session isolation,
credential exposure, provider routing, transcript handling or dependency risks.
Reports are assessed on a best-effort basis; no response-time guarantee or bug
bounty is offered. Start with the newest preview. Older previews may not receive
backported fixes.

Do not scan third-party speech/text services or stress a public deployment.
Use a local instance with dummy credentials and mocked providers where possible.

## Deployment boundaries

- Provider credentials belong on the backend, never in an APK or `EXPO_PUBLIC_` variable.
- Use HTTPS/WSS and explicitly configure trusted reverse proxies.
- Anonymous demo admission is opt-in, permits paid-provider use and is not
  production authentication. Add gateway/admission controls and spending limits.
- The relay uses bounded in-memory state: run one worker/instance as documented.
- Keep sensitive payloads out of application, proxy, hosting and monitoring logs.

Configuration and hosting guidance:
https://github.com/mathew1046/CueBell/blob/main/backend/README.md
