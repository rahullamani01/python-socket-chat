# Security: current status and local TLS setup

This is a trusted-network prototype, not a secure messaging service.
TLS is optional and **off by default**. There are no chat accounts or login yet:
`accounts.py` is a tested storage building block, not integrated authentication.
Never send real passwords over the existing nickname protocol.

TLS protects traffic in transit when correctly enabled on both sides. It does
not provide end-to-end encryption, verify user identity, secure server logs or
protect a compromised server. The server logs private message content.

## Local TLS experiment

The following creates a self-signed certificate for localhost. Protect
`server.key` and never commit or share it. Use an established certificate
authority and a suitable deployment process for anything beyond local testing.

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
  -keyout server.key -out server.crt -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
CHAT_TLS_CERT=server.crt CHAT_TLS_KEY=server.key python server.py
```

In a separate terminal, in the project directory:

```bash
CHAT_TLS=1 CHAT_TLS_CA=server.crt python client.py
```

The client verifies the server's certificate and the configured `HOST`; the
certificate must contain that hostname or IP as a subject alternative name.
`CHAT_TLS_SERVER_NAME` can explicitly specify the expected name, and
`CHAT_TLS_CA` specifies a trusted CA or self-signed certificate. If omitted,
the client uses the system trust store. Both server certificate and key must
be set together. The client does not automatically detect TLS; both sides
must be configured consistently. Keep certificates and keys out of Git.

## Account storage design

`AccountStore` stores users in SQLite with case-insensitive unique names,
random per-user salts, and scrypt hashes. Its current password policy is 12–128
characters and usernames are 3–32 ASCII letters, digits or underscores. It
does not handle account recovery, rate limiting, session management, password
changes or administrative controls. It has not been connected to the network
or audited. Protect the database and backups even though passwords are hashed.

## Before using accounts in the application

- Require TLS for all credential exchanges; no plaintext fallback.
- Design a versioned registration/login flow and safely manage sessions.
- Add rate limiting, connection/resource limits and abuse tests.
- Decide how existing nicknames and history migrate to accounts.
- Review privacy of logs, file-transfer validation and data retention.
- Conduct integration and adversarial testing and seek a security review.

Please report security concerns privately to the repository owner rather than
publishing sensitive details before they can be addressed.
