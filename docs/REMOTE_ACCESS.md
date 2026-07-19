# Remote access (off home Wi‑Fi)

Soul’s phone UI talks to the **PC brain**. Off your home Wi‑Fi you need a private path to that PC.

## Do I need Tailscale on both devices?

**Yes — for access away from home Wi‑Fi.** Tailscale creates a private mesh; the [download page](https://tailscale.com/download) covers Windows, Android, iOS, etc. Install on:

| Device | Needed? |
|--------|---------|
| PC (brain) | Yes |
| Phone | Yes |
| Extra family phones | Yes, each device that should reach the PC remotely |

**Coming back onto home Wi‑Fi:** you do **not** need Tailscale. Use the normal LAN URL (`http://192.168.x.x:8765/`). The PWA tries to reconnect automatically when the network returns.

## Recommended setup

1. Install [Tailscale](https://tailscale.com/download) on the **PC** and **phone** (same account).
2. On the PC keep the PWA server running:
   ```bash
   python scripts/serve_pwa.py --host 0.0.0.0 --port 8765
   ```
3. In the PWA **Settings → Remote access**, copy a **Tailscale** URL.
4. On the phone (mobile data), open that `http://100.x.y.z:8765/` URL.

## Reconnect behavior

- Leave home Wi‑Fi → chat falls back to limited offline LIGHT (if pack was cached).
- Return to Wi‑Fi → PWA detects `online`, probes the PC, syncs the offline queue, clears the offline banner when the brain answers.

## Not included (by design for now)

- Public ngrok/Cloudflare tunnels (possible later; less local-first)
- Full on-device offline LLM (see [OFFLINE_LIGHT.md](OFFLINE_LIGHT.md))
