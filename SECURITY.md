# Security policy

CueBell is an unaudited prototype with development-signed Android previews, not a production alarm or authoritative queue system.

## Report privately

Use [GitHub private vulnerability reporting](https://github.com/mathew1046/CueBell/security/advisories/new). Include the release/commit, reproduction steps, impact and a minimal redacted example. Never include live keys, bearer tokens, patient data or unconsented audio.

Do not publish exploit details before assessment. Revoke exposed credentials immediately; deleting a commit does not invalidate them.

Reports about consent, microphone lifecycle, session isolation, origins, credentials, provider routing, transcripts and dependencies are welcome. Support is best effort, without a response-time guarantee or bounty. Older previews may not receive backports.

Test locally with mocked providers and dummy credentials. Do not stress the public service or scan third-party providers.

## Deployment requirements

- Keep provider keys and pairing codes server-side, never in APKs, web exports or `EXPO_PUBLIC_` variables.
- Use HTTPS/WSS, exact proxy/origin allowlists and a private upstream port.
- Native streams authenticate with headers; browser streams use the first message after Origin validation. Never put bearer tokens in URLs. Origin checks are not user authentication.
- Anonymous admission permits paid-provider use. Production needs admission controls, edge limits and spending limits.
- Use one relay worker/instance. In-memory sessions and rate limits are not durable accounts or distributed abuse protection.
- Exclude sensitive payloads, credentials and audio from all logs. Recheck dependencies before release.

See [backend setup](backend/README.md), [web deployment](docs/WEB.md) and [privacy](docs/PRIVACY.md).
