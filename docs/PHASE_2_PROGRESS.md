# Phase 2: security foundations progress

## Completed so far

- Added optional TLS 1.2+ transport using Python's `ssl`, including client
  certificate and hostname verification. TLS handshakes run outside the
  accept loop, and a handshake inherits the socket timeout.
- Added a SQLite account storage building block with per-account random salts,
  scrypt password hashing and case-insensitive unique account names.
- Added tests for credential storage and TLS verification, including hostname
  rejection. TLS tests require the `openssl` executable to generate a temporary
  certificate and are skipped if it is not installed.
- Added a server-side limit on *announced* file size, rejecting invalid types,
  and documented security risks and a local TLS setup.

## Important: phase 2 is not finished

Accounts are **not wired into the chat application**, and clients still choose
an unauthenticated nickname. TLS is opt-in and off by default. Do not enter or
transmit passwords through chat. The TLS tests exercise the transport contexts,
not the full GUI/server application. No manual GUI or multi-machine TLS test
or external security review has been performed.

File transfer still needs enforcement of actual transferred bytes and other
abuse controls. Login needs mandatory TLS, rate limiting, session design and
a migration policy for existing usernames. See `docs/SECURITY.md`.

## Learning notes

TLS authenticates the server and encrypts the connection when the client trusts
the right certificate and verifies its name. Hashing protects stored passwords
in a different way: scrypt makes guesses expensive, and a unique salt prevents
equal passwords from producing equal stored hashes. Neither feature alone
provides account sessions or end-to-end encrypted messages.
