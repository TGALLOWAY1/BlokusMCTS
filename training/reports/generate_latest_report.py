"""Local preview of the nightly training report — no email sent.

Renders the exact email the nightly workflow would send (subject, markdown body,
Elo plot, and the extra graphics) to a local directory so you can eyeball the
report before it goes out, iterate on wording/visuals, or debug the reporting-era
filter — all without SMTP credentials or touching the send path.

Usage::

    python -m training.reports.generate_latest_report --preview
    python -m training.reports.generate_latest_report --preview --all-time
    python -m training.reports.generate_latest_report --preview --era multi-agent
    python -m training.reports.generate_latest_report --preview --out /tmp/report

Writes ``preview.md`` (the plain-text body), ``preview.html`` (a standalone page
that references the PNGs by relative path so it renders in a browser), and copies
the generated charts alongside them. Prints the subject and every artifact path.
"""

from __future__ import annotations

import argparse
import html as _html
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from training import TrainingPaths, reporting_era
from training import email_summary


# Order + captions for the images in the preview page (headline plot first).
_PREVIEW_IMAGES: List[tuple] = [
    ("plot", "Champion Elo trajectory"),
    ("matchup_matrix", "Champion matchup matrix"),
    ("approach_comparison", "Approach comparison chart"),
    ("recent_deltas", "Recent Elo change by generation"),
]


def _collect_image_paths(composed: Dict[str, Any]) -> Dict[str, Optional[Path]]:
    """Merge the headline plot + extra graphics into ``{key: path}``."""
    images: Dict[str, Optional[Path]] = {"plot": composed.get("plot_path")}
    images.update(composed.get("graphics") or {})
    return images


def _preview_html(body: str, image_files: List[tuple]) -> str:
    """Standalone HTML that references copied PNGs by filename (browser-renderable).

    Unlike the email HTML (which embeds images via ``cid:``), the preview points at
    on-disk files so it opens directly in a browser.
    """
    blocks: List[str] = []
    for filename, alt in image_files:
        blocks.append(
            f'<figure style="margin:0 0 18px 0;">'
            f'<figcaption style="font:600 13px -apple-system,Segoe UI,Roboto,'
            f'Helvetica,Arial,sans-serif;color:#374151;margin:0 0 6px 0;">'
            f'{_html.escape(alt)}</figcaption>'
            f'<img src="{_html.escape(filename)}" alt="{_html.escape(alt)}" '
            'style="max-width:100%;height:auto;display:block;'
            'border:1px solid #e5e7eb;border-radius:6px;" /></figure>'
        )
    images_html = "".join(blocks)
    escaped = _html.escape(body)
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>MCTS nightly report preview</title></head><body "
        'style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
        'margin:0;padding:12px;max-width:900px;">'
        f"{images_html}"
        '<pre style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace;'
        'white-space:pre-wrap;word-wrap:break-word;font-size:13px;line-height:1.45;">'
        f"{escaped}</pre></body></html>"
    )


def generate_preview(
    out_dir: Path | str,
    *,
    era: Optional[reporting_era.ReportingEra] = None,
    failed: bool = False,
    paths: Optional[TrainingPaths] = None,
) -> Dict[str, Any]:
    """Render the report + charts into ``out_dir`` and return a manifest dict.

    Returns ``{subject, era, body_md, html, images: {name: path}}`` where ``html``
    and ``body_md`` are the written file paths. Never sends email.
    """
    era = era or reporting_era.resolve_era()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    composed = email_summary.compose(paths=paths, failed=failed, era=era)
    subject = composed["subject"]
    body = composed["body"]

    # Copy each generated PNG next to the HTML and reference it by filename.
    images = _collect_image_paths(composed)
    image_files: List[tuple] = []
    copied: Dict[str, Path] = {}
    for key, alt in _PREVIEW_IMAGES:
        src = images.get(key)
        if src is None:
            continue
        src = Path(src)
        if not src.exists():
            continue
        dest = out_dir / src.name
        if src.resolve() != dest.resolve():
            shutil.copyfile(src, dest)
        image_files.append((src.name, alt))
        copied[key] = dest

    md_path = out_dir / "preview.md"
    md_path.write_text(f"Subject: {subject}\n\n{body}\n", encoding="utf-8")
    html_path = out_dir / "preview.html"
    html_path.write_text(_preview_html(body, image_files), encoding="utf-8")

    return {
        "subject": subject,
        "era": era,
        "body_md": md_path,
        "html": html_path,
        "images": copied,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview the nightly training report + charts locally (no email)."
    )
    parser.add_argument("--preview", action="store_true",
                        help="Generate the report/charts locally (default action).")
    parser.add_argument("--failed", action="store_true",
                        help="Render the failure variant of the report.")
    parser.add_argument("--era", default=None,
                        help="Reporting era to scope the report to "
                             f"({', '.join(reporting_era.known_eras())}). "
                             "Defaults to the debugged-backprop era.")
    parser.add_argument("--all-time", action="store_true",
                        help="Shortcut for --era all-time (include pre-fix history).")
    parser.add_argument("--out", default=None,
                        help="Output directory (default: training/reports/preview).")
    args = parser.parse_args(argv)

    era = reporting_era.resolve_era("all-time" if args.all_time else args.era)
    paths = TrainingPaths.default()
    out_dir = Path(args.out) if args.out else (paths.reports_dir / "preview")

    manifest = generate_preview(out_dir, era=era, failed=args.failed, paths=paths)

    print("=" * 70)
    print(f"Subject: {manifest['subject']}")
    print(f"Reporting era: {era.label} (since_run_id={era.since_run_id})")
    print("-" * 70)
    print(f"Markdown : {manifest['body_md']}")
    print(f"HTML     : {manifest['html']}")
    if manifest["images"]:
        for name, path in manifest["images"].items():
            print(f"Image    : {name} -> {path}")
    else:
        print("Image    : none (matplotlib unavailable or empty timeline)")
    print("=" * 70)
    print("Open the HTML file in a browser to see the report as it will be emailed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
