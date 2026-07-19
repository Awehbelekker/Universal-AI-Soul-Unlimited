# Offline LIGHT (honest path)

## Today (shipped)

- While online, PWA downloads `/api/offline-pack` (profile slice, family status, memory snippets, FAQ).
- When the phone has **no LAN / no PC brain**, the client uses that pack for **limited** replies and queues messages.
- On reconnect, the queue drains into shared PC memory (`/api/offline/drain`).

This is **not** a full on-device LLM. PWA cannot run GGUF.

## Ultimate (still open)

- Native Android (or similar) with **LIGHT ~27M / STANDARD GGUF** via llama.cpp.
- Encrypted sync of memory after reconnect.
- Clear UX: “Limited offline mode” vs “Full Soul (PC)”.

See [VISION.md](../VISION.md) and [DOC_TRUST.md](DOC_TRUST.md).
