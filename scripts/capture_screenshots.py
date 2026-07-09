"""Capture the six docs/images/*.png screenshots used in README.md, driven by
a real headless browser against the real running app - never hand-captured,
never a sleep-and-hope timer.

Prerequisites (see docs/DEMO.md for the full walkthrough):
    pip install -r requirements-dev.txt
    playwright install chromium
    python scripts/download_sample_video.py
    docker compose up -d --build postgres redis backend vision-worker frontend
    # then wait for the checkout-queue-demo alert to have fired at least
    # once already (~110s after vision-worker starts, see docs/DEMO.md) -
    # this script waits for a *fresh* one, up to --alert-timeout, but that
    # wait is much shorter if the pipeline has already been running a bit.

Usage:
    python -m scripts.capture_screenshots
    python -m scripts.capture_screenshots --headed          # watch it run
    python -m scripts.capture_screenshots --only dashboard,identities

Every wait below is a real condition on the live app - never a fixed sleep.
Each shot fails loudly (clear message, real timeout) rather than silently
capturing an empty/loading state; failures are collected and reported at
the end, and the script exits non-zero if any shot failed. This never
commits the resulting PNGs itself - review them, then `git add` yourself.
"""

import argparse
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

OUT_DIR = Path("docs/images")
ARCHITECTURE_DOC = Path("docs/ARCHITECTURE.md")
VIEWPORT = {"width": 1440, "height": 900}
DISABLE_ANIMATIONS_CSS = (
    "*, *::before, *::after { transition: none !important; animation: none !important; }"
)

PERSON_BOX_RGB = (57, 208, 216)  # LiveDetectionCanvas.tsx COLORS.person, #39d0d8


def log(msg: str) -> None:
    print(f"[capture] {msg}", flush=True)


def no_animations(page: Page) -> None:
    page.add_style_tag(content=DISABLE_ANIMATIONS_CSS)


def login(page: Page, base_url: str, email: str, password: str) -> None:
    page.goto(f"{base_url}/login")
    no_animations(page)
    page.fill('input[type="email"]', email)
    page.fill('input[type="password"]', password)
    page.click('button:has-text("Sign in")')
    page.wait_for_selector(".kpi", timeout=15_000)  # real nav target: the dashboard loaded
    log("logged in")


def wait_for_stable_attr(page: Page, selector: str, attr: str, timeout_ms: int) -> str:
    """Poll an attribute until two reads 300ms apart agree - dodges Recharts'
    mount animation without depending on how that animation is implemented
    (CSS vs. JS tweening) or guessing a duration."""
    deadline = time.monotonic() + timeout_ms / 1000
    last = None
    while time.monotonic() < deadline:
        el = page.query_selector(selector)
        cur = el.get_attribute(attr) if el else None
        if cur and cur == last:
            return cur
        last = cur
        page.wait_for_timeout(300)
    raise PlaywrightTimeoutError(f"{selector}[{attr}] never stabilized within {timeout_ms}ms")


# --------------------------------------------------------------------- shots
def capture_dashboard_and_alerts(page: Page, base_url: str, alert_timeout_ms: int) -> None:
    page.goto(f"{base_url}/")
    no_animations(page)

    log("dashboard: waiting for non-zero KPIs...")
    page.wait_for_function(
        """() => {
            const kpis = Array.from(document.querySelectorAll('.kpi'));
            if (kpis.length < 6) return false;
            const visitors = parseInt(kpis[0].textContent, 10);
            const camerasOnline = parseInt(kpis[4].textContent, 10);
            return Number.isFinite(visitors) && visitors > 0
                && Number.isFinite(camerasOnline) && camerasOnline > 0;
        }""",
        timeout=30_000,
    )

    log("dashboard: waiting for the traffic chart to render data...")
    page.wait_for_function(
        """() => {
            const path = document.querySelector('.recharts-line-curve');
            return !!path && (path.getAttribute('d') || '').length > 20;
        }""",
        timeout=30_000,
    )
    wait_for_stable_attr(page, ".recharts-line-curve", "d", timeout_ms=10_000)

    page.screenshot(path=str(OUT_DIR / "dashboard.png"))
    log(f"wrote {OUT_DIR / 'dashboard.png'}")

    # The live alert feed is populated only by *new* WebSocket pushes, not
    # history - it will read "No alerts in this session" on a fresh page
    # load even though old alerts exist in the DB. So: stay on this same
    # page/WS connection and wait for a genuinely new one to arrive.
    existing = page.locator("text=No alerts in this session")
    if existing.count() > 0:
        log(
            f"alert feed: waiting up to {alert_timeout_ms // 1000}s for a fresh alert "
            "(checkout-queue-demo re-fires every 5 minutes - see docs/DEMO.md)..."
        )
        page.wait_for_function(
            """() => document.querySelectorAll('ul.divide-y li').length > 0""",
            timeout=alert_timeout_ms,
        )
    page.screenshot(path=str(OUT_DIR / "alert-feed.png"))
    log(f"wrote {OUT_DIR / 'alert-feed.png'}")


def capture_live_detection(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/")
    no_animations(page)
    page.wait_for_selector("canvas")

    # checkout-queue-demo has a real, steady ~4 people for its whole length
    # (see docs/DEMO.md) - selecting it makes "a box is actually drawn" a
    # near-immediate condition instead of waiting on demo-entrance's sparser
    # footage (max 3 concurrent people, often 0).
    select = page.locator("select").first
    options = select.locator("option").all_text_contents()
    if "checkout-queue-demo" in options:
        select.select_option(label="checkout-queue-demo")

    log("live-detection: waiting for a real bounding box to be drawn on the canvas...")
    page.wait_for_function(
        f"""() => {{
            const canvas = document.querySelector('canvas');
            if (!canvas) return false;
            const ctx = canvas.getContext('2d');
            const {{ data }} = ctx.getImageData(0, 0, canvas.width, canvas.height);
            for (let i = 0; i < data.length; i += 4) {{
                if (Math.abs(data[i] - {PERSON_BOX_RGB[0]}) < 25
                    && Math.abs(data[i + 1] - {PERSON_BOX_RGB[1]}) < 25
                    && Math.abs(data[i + 2] - {PERSON_BOX_RGB[2]}) < 25) return true;
            }}
            return false;
        }}""",
        timeout=30_000,
    )
    page.screenshot(path=str(OUT_DIR / "live-detection.png"))
    log(f"wrote {OUT_DIR / 'live-detection.png'}")


def capture_zone_editor(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/cameras")
    no_animations(page)
    page.click("tr:has-text('demo-entrance')")
    page.click('button:has-text("Edit zones")')

    log("zone-editor: waiting for the snapshot image to load...")
    page.wait_for_function(
        """() => {
            const img = document.querySelector('img[alt="Camera snapshot"]');
            return !!img && img.complete && img.naturalWidth > 0;
        }""",
        timeout=20_000,
    )
    log("zone-editor: waiting for the existing zone polygon(s) to render...")
    page.wait_for_function(
        """() => document.querySelectorAll('svg polygon').length > 0""",
        timeout=10_000,
    )
    page.screenshot(path=str(OUT_DIR / "zone-editor.png"))
    log(f"wrote {OUT_DIR / 'zone-editor.png'}")


def capture_identities(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/identities")
    no_animations(page)

    log("identities: waiting for a real re-match (sightings > 1)...")
    try:
        page.wait_for_function(
            """() => {
                const rows = document.querySelectorAll('table tbody tr');
                for (const row of rows) {
                    const cells = row.querySelectorAll('td');
                    if (!cells.length) continue;
                    const v = parseInt(cells[cells.length - 1].textContent, 10);
                    if (Number.isFinite(v) && v > 1) return true;
                }
                return false;
            }""",
            timeout=15_000,
        )
    except PlaywrightTimeoutError as exc:
        raise PlaywrightTimeoutError(
            "identities: no identity with track_count > 1 found yet - the demo hasn't "
            "produced a real re-match. Let the stack run longer (Re-ID needs multiple "
            "closed tracks matched to the same identity - see docs/REID.md), then retry. "
            "Refusing to capture an empty/unconvincing table."
        ) from exc
    page.screenshot(path=str(OUT_DIR / "identities.png"))
    log(f"wrote {OUT_DIR / 'identities.png'}")


def capture_architecture(page: Page) -> None:
    text = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    match = re.search(r"## System diagram\s*```mermaid\n(.*?)```", text, re.DOTALL)
    if not match:
        raise RuntimeError(
            f"couldn't find the '## System diagram' mermaid block in {ARCHITECTURE_DOC}"
        )
    diagram = match.group(1)

    html = f"""<!doctype html><html><body style="margin:0;background:white">
<div id="target"></div>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  const {{ svg }} = await mermaid.render("diagram", {json_escape(diagram)});
  document.getElementById("target").innerHTML = svg;
  window.__mermaidRendered = true;
</script>
</body></html>"""
    page.set_content(html)
    log("architecture: waiting for mermaid to render the diagram...")
    # Not a bare "svg" selector: mermaid.render() creates its own transient,
    # off-DOM element for text-measurement while computing the layout, which
    # a bare selector can match before the real one (inside #target) exists -
    # this flag is only set after the actual assignment below completes.
    page.wait_for_function("window.__mermaidRendered === true", timeout=20_000)
    page.locator("#target svg").screenshot(path=str(OUT_DIR / "architecture.png"))
    log(f"wrote {OUT_DIR / 'architecture.png'}")


def json_escape(s: str) -> str:
    import json

    return json.dumps(s)


# --------------------------------------------------------------------- main
SHOTS = ["architecture", "zone-editor", "identities", "live-detection", "dashboard"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:5173")
    parser.add_argument("--email", default="admin@retail.local")
    parser.add_argument("--password", default="admin12345")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--alert-timeout",
        type=int,
        default=360_000,
        help="ms to wait for a fresh alert - the dedup window is 5 minutes, so this "
        "should stay comfortably above 300_000 (default 360_000 = 6 min)",
    )
    parser.add_argument(
        "--only",
        default=",".join(SHOTS),
        help=f"comma-separated subset of: {','.join(SHOTS)}",
    )
    args = parser.parse_args()
    wanted = set(args.only.split(","))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)

        if "architecture" in wanted:
            try:
                capture_architecture(browser.new_page(viewport=VIEWPORT))
            except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                log(f"FAILED architecture.png: {exc}")
                failures.append("architecture")

        app_shots = wanted & {"zone-editor", "identities", "live-detection", "dashboard"}
        if app_shots:
            context = browser.new_context(viewport=VIEWPORT)
            page = context.new_page()
            try:
                login(page, args.base_url, args.email, args.password)
            except Exception as exc:  # noqa: BLE001
                log(f"FAILED to log in - skipping all app shots: {exc}")
                failures.extend(app_shots)
                app_shots = set()

            for name, fn in [
                ("zone-editor", lambda: capture_zone_editor(page, args.base_url)),
                ("identities", lambda: capture_identities(page, args.base_url)),
                ("live-detection", lambda: capture_live_detection(page, args.base_url)),
                (
                    "dashboard",
                    lambda: capture_dashboard_and_alerts(page, args.base_url, args.alert_timeout),
                ),
            ]:
                if name not in app_shots:
                    continue
                try:
                    fn()
                except Exception as exc:  # noqa: BLE001
                    log(f"FAILED {name}: {exc}")
                    failures.append(name)
            context.close()

        browser.close()

    log("---")
    if failures:
        log(f"{len(failures)} shot(s) failed: {', '.join(failures)}")
        sys.exit(1)
    log(f"all requested shots written to {OUT_DIR}/ - review them, then `git add` yourself")


if __name__ == "__main__":
    main()
