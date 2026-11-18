"""HTML Session Report Generator for SUSCRCPY Workstation.

Compiles complete testing audit trails, device diagnostics, target app metadata,
chronological event timelines, bug observations, screenshot evidence, recordings,
log excerpts, and SHA-256 manifests into an offline, self-contained HTML report.
"""
from __future__ import annotations

import base64
import html
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.event_manager import TimelineEvent
from core.evidence_manager import EvidenceItem
from core.notes_manager import TestObservation
from core.recording_manager import RecordingMetadata
from core.screenshot_manager import ScreenshotMetadata
from core.session_manager import SessionMetadata

logger = logging.getLogger("suscrcpy.report_generator")


class ReportGenerator:
    """Generates self-contained, responsive HTML testing workstation reports."""

    @staticmethod
    def generate_html_report(
        session: SessionMetadata,
        output_path: Path,
        observations: Optional[List[TestObservation]] = None,
        timeline: Optional[List[TimelineEvent]] = None,
        screenshots: Optional[List[ScreenshotMetadata]] = None,
        recordings: Optional[List[RecordingMetadata]] = None,
        manifest_items: Optional[List[EvidenceItem]] = None,
        proxy_info: Optional[Dict[str, Any]] = None,
        log_errors_sample: Optional[List[str]] = None,
        embed_images: bool = False,
    ) -> Path:
        """Render complete HTML test report to output_path."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        observations = observations or []
        timeline = timeline or []
        screenshots = screenshots or []
        recordings = recordings or []
        manifest_items = manifest_items or []
        log_errors_sample = log_errors_sample or []
        proxy_info = proxy_info or {}

        # Severities counts
        crit_count = sum(1 for o in observations if o.severity == "Critical")
        high_count = sum(1 for o in observations if o.severity == "High")
        med_count = sum(1 for o in observations if o.severity == "Medium")
        low_count = sum(1 for o in observations if o.severity == "Low")

        # HTML template construction
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SUSCRCPY Test Report — {html.escape(session.session_id)}</title>
<style>
:root {{
  --bg: #0f141c;
  --card-bg: #18202c;
  --card-border: #263345;
  --text: #e2e8f0;
  --text-muted: #8da2bc;
  --primary: #3b82f6;
  --accent: #06b6d4;
  --danger: #ef4444;
  --warning: #f59e0b;
  --success: #10b981;
  --code-bg: #0b0f15;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background-color: var(--bg);
  color: var(--text);
  line-height: 1.5;
  padding: 24px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
header {{
  border-bottom: 2px solid var(--card-border);
  padding-bottom: 20px;
  margin-bottom: 28px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}}
.header-title h1 {{ font-size: 26px; font-weight: 700; color: #fff; }}
.header-title p {{ color: var(--text-muted); font-size: 14px; margin-top: 4px; }}
.badge {{
  display: inline-block;
  padding: 4px 10px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}}
.badge-status {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid #3b82f6; }}
.badge-crit {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }}
.badge-high {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }}
.badge-med {{ background: rgba(59, 130, 246, 0.2); color: #93c5fd; border: 1px solid #3b82f6; }}
.badge-low {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }}

.grid-metrics {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 28px;
}}
.metric-card {{
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 8px;
  padding: 18px;
}}
.metric-card .num {{ font-size: 28px; font-weight: 700; color: #fff; }}
.metric-card .label {{ color: var(--text-muted); font-size: 13px; text-transform: uppercase; margin-top: 2px; }}

.section {{
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 28px;
}}
.section h2 {{
  font-size: 18px;
  color: #fff;
  border-bottom: 1px solid var(--card-border);
  padding-bottom: 12px;
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  gap: 8px;
}}

.info-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px 24px;
}}
.info-row {{ display: flex; flex-direction: column; font-size: 14px; }}
.info-label {{ color: var(--text-muted); font-size: 12px; text-transform: uppercase; }}
.info-val {{ font-weight: 500; color: #fff; margin-top: 2px; word-break: break-all; }}

table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  margin-top: 10px;
}}
th, td {{
  padding: 10px 14px;
  text-align: left;
  border-bottom: 1px solid var(--card-border);
}}
th {{
  background: #111722;
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 12px;
}}
tr:hover td {{ background: rgba(255, 255, 255, 0.02); }}

.gallery {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
}}
.gallery-card {{
  background: #111722;
  border: 1px solid var(--card-border);
  border-radius: 6px;
  overflow: hidden;
}}
.gallery-card img {{
  width: 100%;
  height: auto;
  max-height: 400px;
  object-fit: contain;
  background: #000;
  display: block;
}}
.gallery-card .cap {{
  padding: 12px;
  font-size: 12px;
  color: var(--text-muted);
}}
.code-block {{
  background: var(--code-bg);
  border: 1px solid var(--card-border);
  border-radius: 6px;
  padding: 14px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  color: #38bdf8;
  max-height: 320px;
  overflow-y: auto;
  white-space: pre-wrap;
}}
.timeline-list {{
  list-style: none;
  position: relative;
  padding-left: 20px;
}}
.timeline-list:before {{
  content: "";
  position: absolute;
  left: 6px;
  top: 6px;
  bottom: 6px;
  width: 2px;
  background: var(--card-border);
}}
.timeline-item {{
  position: relative;
  margin-bottom: 16px;
  font-size: 13px;
}}
.timeline-item:before {{
  content: "";
  position: absolute;
  left: -18px;
  top: 5px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
}}
.timeline-time {{ color: var(--text-muted); font-size: 11px; }}
.timeline-desc {{ font-weight: 500; color: #fff; margin-top: 2px; }}

footer {{
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
  padding: 24px 0;
}}
@media print {{
  body {{ background: #fff; color: #000; }}
  .section, .metric-card {{ border-color: #ccc; background: #fff; }}
  .header-title h1, .section h2, .metric-card .num, .info-val {{ color: #000; }}
  th {{ background: #eee; color: #333; }}
}}
</style>
</head>
<body>
<div class="container">

<header>
  <div class="header-title">
    <h1>SUSCRCPY Test Session Report</h1>
    <p>Session ID: <strong>{html.escape(session.session_id)}</strong> &bull; Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
  </div>
  <div>
    <span class="badge badge-status">{html.escape(session.status)}</span>
  </div>
</header>

<div class="grid-metrics">
  <div class="metric-card">
    <div class="num">{len(observations)}</div>
    <div class="label">Observations ({crit_count} Crit / {high_count} High)</div>
  </div>
  <div class="metric-card">
    <div class="num">{session.total_crashes}</div>
    <div class="label">Crashes Detected</div>
  </div>
  <div class="metric-card">
    <div class="num">{session.total_errors}</div>
    <div class="label">Errors Recorded</div>
  </div>
  <div class="metric-card">
    <div class="num">{len(screenshots)}</div>
    <div class="label">Screenshots Captured</div>
  </div>
  <div class="metric-card">
    <div class="num">{len(recordings)}</div>
    <div class="label">Screen Recordings</div>
  </div>
</div>

<div class="section">
  <h2>📋 Session & Target Diagnostics</h2>
  <div class="info-grid">
    <div class="info-row"><span class="info-label">Project</span><span class="info-val">{html.escape(session.project_name)}</span></div>
    <div class="info-row"><span class="info-label">Session Name</span><span class="info-val">{html.escape(session.session_name)}</span></div>
    <div class="info-row"><span class="info-label">Test Type</span><span class="info-val">{html.escape(session.test_type)}</span></div>
    <div class="info-row"><span class="info-label">Tester</span><span class="info-val">{html.escape(session.tester_name or 'Unspecified')}</span></div>
    <div class="info-row"><span class="info-label">Start Time</span><span class="info-val">{html.escape(session.start_time)}</span></div>
    <div class="info-row"><span class="info-label">End Time</span><span class="info-val">{html.escape(session.end_time or 'In Progress')}</span></div>
    <div class="info-row"><span class="info-label">Device</span><span class="info-val">{html.escape(session.device_manufacturer)} {html.escape(session.device_model)} ({html.escape(session.device_serial)})</span></div>
    <div class="info-row"><span class="info-label">Android OS</span><span class="info-val">Android {html.escape(session.android_version)} (SDK {html.escape(session.sdk_version)})</span></div>
    <div class="info-row"><span class="info-label">Screen Resolution</span><span class="info-val">{session.screen_dimensions[0]}x{session.screen_dimensions[1]} (DPI: {session.display_density or 'N/A'})</span></div>
    <div class="info-row"><span class="info-label">Target App</span><span class="info-val">{html.escape(session.target_app_name or 'Full Device')}</span></div>
    <div class="info-row"><span class="info-label">Package Name</span><span class="info-val">{html.escape(session.target_package or 'N/A')}</span></div>
    <div class="info-row"><span class="info-label">App Version</span><span class="info-val">{html.escape(session.app_version or 'N/A')} (code: {html.escape(session.app_version_code or 'N/A')})</span></div>
    <div class="info-row"><span class="info-label">HTTP Proxy</span><span class="info-val">{html.escape(proxy_info.get('status_message', 'Not configured'))}</span></div>
  </div>
  {f'<div style="margin-top: 14px;"><span class="info-label">Tester Notes:</span><p style="margin-top: 4px; font-size: 14px;">{html.escape(session.tester_notes)}</p></div>' if session.tester_notes else ''}
</div>

<div class="section">
  <h2>🔍 Test Observations & Defects ({len(observations)})</h2>
"""
        if observations:
            html_content += """
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>Severity</th>
        <th>Category</th>
        <th>Title</th>
        <th>Expected vs Actual</th>
        <th>Screenshot</th>
      </tr>
    </thead>
    <tbody>
"""
            for obs in observations:
                badge_class = {
                    "Critical": "badge-crit",
                    "High": "badge-high",
                    "Medium": "badge-med",
                    "Low": "badge-low",
                }.get(obs.severity, "badge-status")
                
                shot_link = ""
                if obs.screenshot_path:
                    shot_name = Path(obs.screenshot_path).name
                    shot_link = f'<a href="../screenshots/{shot_name}" style="color: #60a5fa;" target="_blank">{shot_name}</a>'
                
                exp_act = ""
                if obs.expected_result or obs.actual_result:
                    exp_act = f"<div><strong>Exp:</strong> {html.escape(obs.expected_result)}</div><div><strong>Act:</strong> {html.escape(obs.actual_result)}</div>"

                html_content += f"""
      <tr>
        <td><code>{html.escape(obs.obs_id)}</code></td>
        <td><span class="badge {badge_class}">{html.escape(obs.severity)}</span></td>
        <td>{html.escape(obs.category)}</td>
        <td><strong>{html.escape(obs.title)}</strong><br><small style="color: var(--text-muted);">{html.escape(obs.description)}</small></td>
        <td>{exp_act}</td>
        <td>{shot_link}</td>
      </tr>
"""
            html_content += """
    </tbody>
  </table>
"""
        else:
            html_content += "<p style='color: var(--text-muted);'>No defects or observations logged during this session.</p>"
        html_content += "</div>\n"

        # Screenshots Gallery
        html_content += f"""
<div class="section">
  <h2>📸 Screenshot Evidence ({len(screenshots)})</h2>
"""
        if screenshots:
            html_content += '<div class="gallery">\n'
            for s in screenshots:
                img_src = ""
                display_path = Path(s.annotated_path if s.annotated_path and Path(s.annotated_path).exists() else s.raw_path)
                if embed_images and display_path.exists():
                    try:
                        with open(display_path, "rb") as img_f:
                            b64 = base64.b64encode(img_f.read()).decode("utf-8")
                            img_src = f"data:image/png;base64,{b64}"
                    except Exception:
                        img_src = f"../screenshots/{display_path.name}"
                else:
                    img_src = f"../screenshots/{display_path.name}"

                html_content += f"""
    <div class="gallery-card">
      <a href="{img_src}" target="_blank"><img src="{img_src}" alt="{html.escape(display_path.name)}"></a>
      <div class="cap">
        <strong>{html.escape(display_path.name)}</strong><br>
        <span>{s.width}x{s.height} &bull; {s.file_size_bytes} bytes</span><br>
        <code>SHA-256: {s.sha256[:16]}...</code>
      </div>
    </div>
"""
            html_content += '</div>\n'
        else:
            html_content += "<p style='color: var(--text-muted);'>No screenshots captured during this session.</p>"
        html_content += "</div>\n"

        # Recordings
        if recordings:
            html_content += f"""
<div class="section">
  <h2>🎥 Screen Recordings ({len(recordings)})</h2>
  <table>
    <thead><tr><th>ID</th><th>Filename</th><th>Duration</th><th>Size</th><th>SHA-256</th></tr></thead>
    <tbody>
"""
            for rec in recordings:
                fname = Path(rec.filepath).name
                html_content += f"""
      <tr>
        <td><code>{html.escape(rec.id)}</code></td>
        <td><a href="../recordings/{fname}" style="color: #60a5fa;" target="_blank">{html.escape(fname)}</a></td>
        <td>{rec.duration_seconds}s</td>
        <td>{rec.file_size_bytes} bytes</td>
        <td><code>{rec.sha256[:20]}...</code></td>
      </tr>
"""
            html_content += "</tbody></table></div>\n"

        # Timeline
        if timeline:
            html_content += f"""
<div class="section">
  <h2>⏱ Chronological Event Timeline ({len(timeline)})</h2>
  <ul class="timeline-list">
"""
            for ev in timeline:
                html_content += f"""
    <li class="timeline-item">
      <div class="timeline-time">{html.escape(ev.timestamp)} &bull; [{html.escape(ev.category.upper())}]</div>
      <div class="timeline-desc">{html.escape(ev.description)}</div>
    </li>
"""
            html_content += "</ul></div>\n"

        # Critical Log Excerpts
        if log_errors_sample:
            html_content += f"""
<div class="section">
  <h2>⚠️ Critical Error & Crash Logcat Excerpts ({len(log_errors_sample)})</h2>
  <div class="code-block">
"""
            for line in log_errors_sample[:100]:
                html_content += f"{html.escape(line)}\n"
            html_content += "</div></div>\n"

        # Manifest
        if manifest_items:
            html_content += f"""
<div class="section">
  <h2>🔒 Cryptographic Evidence Manifest (SHA-256)</h2>
  <table>
    <thead><tr><th>File</th><th>Category</th><th>Size</th><th>SHA-256 Hash</th></tr></thead>
    <tbody>
"""
            for m in manifest_items:
                html_content += f"""
      <tr>
        <td><code>{html.escape(m.relative_path)}</code></td>
        <td>{html.escape(m.category)}</td>
        <td>{m.size_bytes} B</td>
        <td><code style="font-size: 11px;">{m.sha256}</code></td>
      </tr>
"""
            html_content += "</tbody></table></div>\n"

        html_content += f"""
<footer>
  Generated by SUSCRCPY v3.0 &bull; Android Testing & Diagnostics Workstation &bull; Local & Offline Report
</footer>
</div>
</body>
</html>
"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info("Generated HTML session report at %s (%d bytes)", output_path, len(html_content))
        return output_path
