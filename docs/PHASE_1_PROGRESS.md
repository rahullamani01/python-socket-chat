# Python Socket Chat: Phase 1 progress and learning tracker

## Project goal

Grow a Python learning project into a well-engineered real-time collaboration
system suitable for demonstrating networking, testing, security and research
skills. Phase 1 prioritizes a reliable foundation over new product features.

## Starting point

- The root application is a threaded TCP server and Tkinter client.
- It supports public and private messages, file and voice transfers, and recent
  persistent public history. Communication is not encrypted or authenticated.
- There are several historical copies in the repository, plus a ZIP archive.
- The prior protocol tests lived inside an older copy and were not found by
  default test discovery.
- The server configured logging as an import side effect.

## Work completed in this phase

1. **Identified the active application.** The root scripts are the supported
   entry points; older snapshots are retained untouched to protect project history.
2. **Made client dependencies explicit.** `requirements.txt` provides the three
   existing third-party dependencies. They are not pinned; a lock or tested
   version ranges should be considered later.
3. **Removed an import side effect.** Server logging is initialized when
   `main()` starts rather than when another module imports the server.
4. **Created a discoverable test suite.** `tests/` checks JSON and binary frames,
   fragmented and combined TCP frames, invalid lengths and payloads, and EOF.
   Socket-pair integration tests exercise two-client public and private messages,
   file offer/accept/chunk forwarding, history loading and replay.
5. **Added continuous integration.** GitHub Actions is configured to run the
   standard-library suite on Python 3.10, 3.11, 3.12 and 3.13. Actual hosted
   results must be checked on GitHub after pushing.
6. **Documented the system and contributions.** The README, architecture
   document and contribution guide explain entry points, workflows, data,
   limitations and testing.

## How to verify

From the repository root:

```bash
python3 -m unittest discover -v
python3 -m pip install -r requirements.txt  # needed for the GUI, not tests
python3 server.py                            # separate terminal
python3 client.py                            # repeat in another terminal
```

The automated tests passed locally. They use socket pairs and temporary files,
not a running server or a graphical interface. The GUI, audio, notifications,
and real network connections still need manual end-to-end testing.

## Decisions and risks

- **No mass reorganization:** moving socket and GUI modules before tests cover
  behavior risks breaking imports or creating incompatible entry points.
  Package restructuring remains future work.
- **No deletion of historical snapshots or tracked data:** inspect and back up
  any useful information before deciding on cleanup. Git ignores do not remove
  already tracked files.
- **Security is not solved:** no authentication or TLS; private messages are
  written to logs. File metadata and resource limits need stronger validation.
  Use only on trusted networks.
- **Coverage is not complete:** malformed input, failures and concurrent load,
  client GUI behavior and actual restart at process level need further tests.
- The client and server each implement framing; future consolidation must retain
  protocol compatibility.

## Suggested next milestones

1. Manually verify the GUI and file/audio features on a real desktop; record
   OS, Python version, steps and observed results.
2. Add server tests for duplicate names, disconnects, declined/aborted file
   transfers, invalid input and client reconnection.
3. Plan a package layout and shared protocol module; migrate incrementally with
   compatibility checks.
4. Design database-backed users and rooms, followed by authentication and TLS
   using established libraries and a documented threat model.
5. Pick a research question, such as threaded versus asynchronous server
   scalability, and document a repeatable benchmark and its limitations.

## Learning journal prompts

For each milestone record: the problem, your hypothesis or design, alternatives
considered, code you personally wrote, tests and results, problems encountered,
what you learned, and what you would improve. This provides honest evidence
for a portfolio or master's application.
