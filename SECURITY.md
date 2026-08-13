# Security Policy

## Supported versions

| Version / branch | Supported |
|------------------|-----------|
| `main` / `master` (active development) | Yes |
| Older unreleased snapshots | No |

Security fixes are applied to the active development branch. Tagged releases will be supported once versioning and release tagging are established.

## Reporting a vulnerability

**Do not open public GitHub issues for security vulnerabilities.**

If you believe you have found a security issue:

1. Review the repository to confirm it affects the current codebase.
2. Report it privately to the repository maintainer through GitHub's **Private vulnerability reporting** feature (if enabled) or the maintainer's designated private contact channel.
3. Include steps to reproduce, affected components, and potential impact.
4. Allow reasonable time for investigation and remediation before public disclosure.

We will acknowledge receipt and communicate progress when possible.

## Secrets and credentials

- **Never commit** API keys, access tokens, webhook secrets, private keys, or production database credentials.
- Local secrets belong in `.env` (gitignored) or a team secrets manager.
- Use `.env.example` for non-secret configuration templates only.
- Rotate compromised credentials immediately through Meta Business Manager / your secrets provider.

## Development practices

- Enable webhook signature validation (`WHATSAPP_APP_SECRET`) before exposing endpoints to the public internet.
- Replace default `SECRET_KEY` and `WHATSAPP_VERIFY_TOKEN` values in any shared or deployed environment.
- Do not log bearer tokens, app secrets, or full webhook payloads containing PII in production.
- Keep dependencies updated; CI runs on every push to catch regressions early.
- Review pull requests for accidental secret exposure before merge.

## Scope notes

This project integrates with Meta's WhatsApp Cloud API. Follow [Meta's platform policies](https://developers.facebook.com/docs/whatsapp/overview/policy-enforcement) and secure your Meta app credentials according to their documentation.

## Out of scope

The following are planned but not yet implemented — report issues only if they affect code that exists today:

- Admin authentication and authorization
- AI/LLM data handling policies
- Production deployment hardening (WAF, rate limiting at edge)
