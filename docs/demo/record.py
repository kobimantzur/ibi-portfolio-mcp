"""Record docs/demo/demo.html into docs/demo.gif (needs ffmpeg). Run: uv run python docs/demo/record.py"""
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
OUT = HERE.parent / "demo.gif"
W, H, HOLD_MS = 820, 520, 3500

with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1,
                              record_video_dir=tmp, record_video_size={"width": W, "height": H})
    page = ctx.new_page()
    page.goto((HERE / "demo.html").resolve().as_uri())
    page.wait_for_function("window.demoDone === true", timeout=30_000)
    page.wait_for_timeout(HOLD_MS)
    video = page.video.path()
    ctx.close()
    browser.close()
    webm = Path(tmp) / "demo.webm"
    shutil.move(video, webm)
    # trim the blank first frames, 15 fps, shared palette for clean text
    vf = f"fps=15,scale={W}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=none"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.4", "-i", str(webm), "-vf", vf, "-loop", "0", str(OUT)],
                   check=True)

print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
