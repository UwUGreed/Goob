# Goob

Modular contractor operations demonstration, with two independent applications.

- **Dispatch:** existing React/TypeScript app in `goob-dispatch/`; see its README. Preserved without modifications by the operations implementation.
- **Operations:** run `python3 -m operations.server` from this folder and open http://127.0.0.1:8081. See `operations/README.md` for the demo journey and limitations.

The operations vertical slice includes customer equipment, coverage, simulated work proposals, material disposition, billing review, transactional employee approval and history. AI and identity are simulated; readiness and migration are previews. No real messages or integrations run.

Verification: `python3 -m unittest discover -s tests -v`.

Architecture, assumptions and roadmap: `docs/OPERATIONS-ARCHITECTURE.md`.
