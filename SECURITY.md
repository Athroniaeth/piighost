# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest 1.x minor | ✅ Yes    |
| Older 1.x minors | ❌ No     |
| 0.x     | ❌ No     |

Security fixes land on the latest released 1.x minor. Older minors and the 0.x line are no longer supported, so upgrade to the current release to receive fixes.

## Reporting a Vulnerability

**Please do not report security vulnerabilities in public GitHub issues.**

If you discover a security vulnerability in PIIGhost, please report it **privately** via [GitHub's private vulnerability reporting](https://github.com/Athroniaeth/piighost/security/advisories/new).

Please include:
1. Description of the vulnerability
2. Steps to reproduce (if possible)
3. Potential impact assessment
4. Suggested fix (if you have one)

We aim to acknowledge reports within **48 hours** and provide an initial assessment within **1 week**.

## Security Considerations

PIIGhost handles potentially sensitive PII. Key design decisions:

- **De-identification is local**: PII is detected and replaced with placeholder tokens before any message reaches an LLM or external service.
- **Reversible pseudonymization, not hashing**: the default placeholders are opaque, collision-free tokens such as `<<PERSON:1>>`. The token-to-value map is held in the conversation memory (in-process, Redis, or SQLAlchemy), not embedded in the token. A hashed placeholder factory exists as an option, but it is not the default.
- **Optional encryption at rest**: the Redis backend can encrypt stored values with AES-GCM and hash the storage keys with Argon2id (the `crypto` and `argon2` extras, keyed by `PIIGHOST_CIPHER_KEY`). It is off by default; enable it for a shared backend.
- **No logging of raw PII**: the library does not log entity values, and the OpenTelemetry observation layer can tokenize span payloads so traces stay safe for a PII-untrusted backend.
- **Frozen dataclasses**: the data models are immutable.

> **Note**: de-identification protects PII from the model, not the store. Encryption at rest is available for the Redis backend but off by default, so secure your memory backend appropriately in production.
