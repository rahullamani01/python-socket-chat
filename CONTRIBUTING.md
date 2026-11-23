# Contributing

## Development setup

Use Python 3.10 or newer. From the repository root, create and activate a virtual
environment, then run `python -m pip install -r requirements.txt` if working on
the GUI. Tkinter and system audio support may require OS-specific installation.
The server and tests need only the Python standard library.

Run `python -m unittest discover -v` before submitting a change. Tests use local
socket pairs and temporary history files; they do not require a running server.
For GUI changes, also start the server and at least two clients and describe
the manual checks performed.

## Making changes

1. Create a focused branch and describe the problem before a large change.
2. Change the root application, not the historical snapshots.
3. Add or update tests for behavior and failure cases.
4. Update documentation when setup, protocol, or user-visible behavior changes.
5. Explain what was tested and any remaining limitations in the pull request.

Do not commit credentials, private chat data, downloads or generated logs.
Treat this application as a trusted-network prototype, not a secure messenger.
