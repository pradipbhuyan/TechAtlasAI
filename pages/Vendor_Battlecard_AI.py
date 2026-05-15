"""
Vendor Battlecard AI
Executive vendor comparison battlecards

Same construct as TelecomPulse-style apps:
- Streamlit secrets/env loading
- dark executive UI
- OpenAI JSON generation
- editorial/advisory review
- PDF export
- MP3 audio briefing
- automatic/manual email delivery
- branded email HTML/TXT assets
- app-specific session-state namespace
"""

import asyncio
import json
import os
import re
import smtplib
import ssl
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path
from typing import Any

import edge_tts
import openai
import streamlit as st

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

APP_NAME = "Vendor Battlecard AI"
APP_ICON = "⚔️"
APP_TAGLINE = "Executive vendor comparison battlecards"
APP_KEY = "vendor_battlecard"
FILE_PREFIX = "vendor_battlecard"
CREATOR_FOOTNOTE = "Content created by Pradip Bhuyan, Head of Delivery, TMT."

SECTIONS = ['executive_summary', 'comparison_snapshot', 'vendor_profiles', 'strengths_weaknesses', 'ideal_use_cases', 'pricing_commercial_notes', 'implementation_risks', 'client_talking_points', 'recommendation', 'next_steps']
SECTION_LABELS = {'executive_summary': '🔭 Executive Summary', 'comparison_snapshot': 'Comparison Snapshot', 'vendor_profiles': 'Vendor Profiles', 'strengths_weaknesses': 'Strengths Weaknesses', 'ideal_use_cases': 'Ideal Use Cases', 'pricing_commercial_notes': 'Pricing Commercial Notes', 'implementation_risks': 'Implementation Risks', 'client_talking_points': 'Client Talking Points', 'recommendation': 'Recommendation', 'next_steps': '✅ Next Steps', 'top_developments': '🧭 Top Developments', 'analyst_take': '🧠 Analyst Take', 'what_to_watch_next': '👀 What To Watch Next'}
BRIEFING_OPTIONS = ['Vendor Battlecard', 'Competitive Landscape Brief', 'Client Conversation Prep']

# -----------------------------------------------------------------------------
# Configuration helpers
# -----------------------------------------------------------------------------
def get_config_value(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, None)
        if value is not None:
            return str(value)
    except Exception:
        pass
    return str(os.getenv(name, default))

OPENAI_API_KEY = get_config_value("OPENAI_API_KEY")
SMTP_HOST = get_config_value("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(get_config_value("SMTP_PORT", "587") or "587")
SENDER_EMAIL = get_config_value("SENDER_EMAIL")
SENDER_APP_PASSWORD = get_config_value("SENDER_APP_PASSWORD")
RECIPIENT_EMAIL = get_config_value("RECIPIENT_EMAIL")
DEFAULT_MODEL = get_config_value("DEFAULT_MODEL", "gpt-4o-mini")
DEFAULT_TTS_VOICE_LABEL = get_config_value("DEFAULT_TTS_VOICE_LABEL", "en-US-GuyNeural (Male, US)")
MAX_EMAIL_ATTACHMENT_MB = float(get_config_value("MAX_EMAIL_ATTACHMENT_MB", "22"))
AUTO_EMAIL_AFTER_GENERATION = get_config_value("AUTO_EMAIL_AFTER_GENERATION", "true").lower() in {"1", "true", "yes", "y"}

# -----------------------------------------------------------------------------
# Namespaced session state
# -----------------------------------------------------------------------------
def skey(name: str) -> str:
    return f"{APP_KEY}_{name}"

def sget(name: str, default=None):
    return st.session_state.get(skey(name), default)

def sset(name: str, value: Any) -> None:
    st.session_state[skey(name)] = value

# -----------------------------------------------------------------------------
# Page and CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title=APP_NAME, page_icon=APP_ICON, layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');
:root { --bg:#0a0e1a; --surface:#111827; --border:#1e2d45; --accent:#00d4ff; --accent2:#7c3aed; --text:#e2e8f0; --muted:#64748b; --success:#10b981; --warning:#f59e0b; }
html, body, [data-testid="stAppViewContainer"] { background-color:var(--bg)!important; color:var(--text)!important; font-family:'Syne',sans-serif; }
[data-testid="stSidebar"] { background:var(--surface)!important; border-right:1px solid var(--border)!important; }
.stButton>button { background:linear-gradient(135deg,var(--accent),var(--accent2))!important; color:white!important; border:none!important; font-family:'Syne',sans-serif!important; font-weight:700!important; border-radius:6px!important; padding:0.5rem 1.5rem!important; }
.stButton>button:hover { opacity:0.85!important; }
.pipeline { display:flex; align-items:center; background:var(--surface); border:1px solid var(--border); border-radius:10px; overflow:hidden; margin-bottom:1.5rem; }
.stage { flex:1; text-align:center; padding:0.6rem 0.5rem; font-family:'Space Mono',monospace; font-size:0.63rem; letter-spacing:0.08em; text-transform:uppercase; color:var(--muted); border-right:1px solid var(--border); }
.stage:last-child { border-right:none; } .stage.active{background:linear-gradient(135deg,#0d1f35,#162032);color:var(--accent);} .stage.done{background:#0d1f1a;color:var(--success);} .stage.pending{color:#2a3a4a;}
.score-badge { display:inline-block; font-family:'Space Mono',monospace; font-size:0.75rem; padding:3px 10px; border-radius:4px; font-weight:700; margin-left:8px; }
.score-high{background:#0d2e1f;color:#10b981;border:1px solid #064e3b;} .score-mid{background:#2d1f00;color:#f59e0b;border:1px solid #78350f;} .score-low{background:#2d0f0f;color:#ef4444;border:1px solid #7f1d1d;}
.section-card{background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:8px;padding:1.25rem 1.5rem;margin-bottom:1.25rem;} .section-title{font-family:'Syne',sans-serif;font-weight:700;font-size:1rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--accent);margin-bottom:0.75rem;} .report-body{font-family:'Syne',sans-serif;font-size:0.95rem;line-height:1.85;color:var(--text);}
.metric-box{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1rem;text-align:center;} .metric-val{font-family:'Space Mono',monospace;font-size:1.6rem;font-weight:700;color:var(--accent);} .metric-label{font-size:0.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:0.1em;}
.approved-banner{background:linear-gradient(135deg,#064e3b,#065f46);border:1px solid #10b981;border-radius:8px;padding:0.75rem 1.25rem;margin-bottom:1.5rem;font-family:'Space Mono',monospace;font-size:0.78rem;color:#6ee7b7;letter-spacing:0.04em;}
.pulse-header{font-family:'Syne',sans-serif;font-weight:800;font-size:2.6rem;background:linear-gradient(90deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:0;line-height:1.1;} .pulse-sub{font-family:'Space Mono',monospace;font-size:0.75rem;color:var(--muted);letter-spacing:0.15em;text-transform:uppercase;margin-top:4px;}
.status-line{font-family:'Space Mono',monospace;font-size:0.7rem;color:var(--muted);padding:4px 0;letter-spacing:0.04em;} .tag{display:inline-block;font-family:'Space Mono',monospace;font-size:0.65rem;padding:2px 8px;border-radius:3px;margin-right:6px;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.08em;background:#3a2f1e;color:#fbbf24;border:1px solid #92400e;}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(exist_ok=True)

def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def run_id() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def active_report_id() -> str:
    if not sget("report_id"):
        sset("report_id", today_str())
    return sget("report_id")

def rpath(ext: str, suffix: str = "") -> Path:
    return REPORT_DIR / f"{FILE_PREFIX}_{active_report_id()}{suffix}.{ext}"

def pdf_path() -> Path:
    return rpath("pdf", "_final_report")

def email_html_path() -> Path:
    return rpath("html", "_email_brief")

def email_text_path() -> Path:
    return rpath("txt", "_email_brief")

def delivery_status_path() -> Path:
    return rpath("json", "_delivery_status")

def load_json(path: Any) -> Any:
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None

def save_json(data: Any, path: Any) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def score_cls(s: Any) -> str:
    try:
        s = int(s)
    except Exception:
        s = 0
    return "score-high" if s >= 80 else ("score-mid" if s >= 60 else "score-low")

def textify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(f"{str(k).replace('_', ' ').title()}: {textify(v)}" for k, v in value.items())
    if isinstance(value, list):
        return "\n".join(f"- {textify(item)}" for item in value if textify(item).strip())
    return str(value)

def safe_html(text: Any) -> str:
    return escape(textify(text)).replace("\n", "<br>")

# -----------------------------------------------------------------------------
# Prompts
# -----------------------------------------------------------------------------
DRAFT_PROMPT = """You are Vendor Battlecard AI, a senior technology analyst and executive advisor.
Today is __DATE__.
Briefing type: __BRIEFING_TYPE__.
User context / request: __USER_CONTEXT__

__PROMPT_EXTRA__

QUALITY STANDARDS:
- Write for senior technology, delivery, architecture, consulting and business leaders.
- Be practical, specific, balanced and advisory.
- Do not invent deal values, dates, benchmark scores or vendor claims. If exact data is unknown, say "Not disclosed" or "Requires validation".
- Separate strategic implications from implementation detail.
- Prefer clear recommendations, risks, next actions and delivery considerations.

Return a JSON object with exactly these keys:
__JSON_KEYS__

Length guidance: __LENGTH_GUIDANCE__
Return ONLY valid JSON. No markdown fences.
"""

REVIEW_PROMPT = """You are the Chief Advisory Editor for Vendor Battlecard AI.
Review the draft for clarity, credibility, enterprise relevance, completeness and executive usefulness.
For each section, score 0-100 and provide issues and suggestions. Produce a revised version of every section scoring below 92. For sections scoring 92+, omit from revised.
Draft: __DRAFT__
Return JSON with exactly: overall_score, overall_verdict, reviews, revised, editorial_summary.
Return ONLY valid JSON.
"""

TTS_PROMPT = """You are Vendor Battlecard AI, a professional broadcast scriptwriter for senior technology executives.
Today is __DATE__. Briefing type: __BRIEFING_TYPE__.
Using the approved report below, write a spoken audio briefing script.
APPROVED REPORT: __REPORT__
Requirements: __TTS_LENGTH_GUIDANCE__
Spoken broadcast style, no bullets, no markdown headings, smooth transitions.
Return JSON with exactly: tts_script. Return ONLY valid JSON.
"""

# -----------------------------------------------------------------------------
# OpenAI
# -----------------------------------------------------------------------------
def call_openai(client: openai.OpenAI, prompt: str, model: str, max_tokens: int = 8000) -> dict:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.55,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            timeout=180,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI returned an empty response.")
        return json.loads(content)
    except openai.AuthenticationError as e:
        raise RuntimeError("OpenAI authentication failed. Check OPENAI_API_KEY.") from e
    except openai.RateLimitError as e:
        raise RuntimeError("OpenAI rate limit or quota issue. Check billing/quota.") from e
    except openai.APIConnectionError as e:
        raise RuntimeError(f"Could not connect to OpenAI API: {e}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"OpenAI returned non-JSON content: {e}") from e

def length_guidance(briefing_type: str) -> str:
    if any(x in briefing_type.lower() for x in ["daily", "flash", "prep"]):
        return "Concise executive output: 900-1,500 words total."
    return "Detailed advisory output: 2,500-4,500 words total."

def tts_length_guidance(briefing_type: str) -> str:
    if any(x in briefing_type.lower() for x in ["daily", "flash", "prep"]):
        return "Target length: 700 to 1,000 words, suitable for 5-8 minutes."
    return "Target length: 2,500 to 4,000 words, suitable for 18-30 minutes."

def generate_draft(client: openai.OpenAI, model: str, briefing_type: str, user_context: str) -> dict:
    keys = ["briefing_type"] + SECTIONS + ["tts_script"]
    prompt = (DRAFT_PROMPT
        .replace("Vendor Battlecard AI", APP_NAME)
        .replace("__DATE__", datetime.now().strftime("%A, %B %d, %Y"))
        .replace("__BRIEFING_TYPE__", briefing_type)
        .replace("__USER_CONTEXT__", user_context.strip() or "General executive technology advisory context.")
        .replace("__PROMPT_EXTRA__", "Create a practical vendor comparison battlecard. Compare vendors, products or platforms named by the user. Include strengths, weaknesses, ideal use cases, pricing/commercial notes, implementation risks, client conversation points and recommendation.")
        .replace("__JSON_KEYS__", json.dumps(keys))
        .replace("__LENGTH_GUIDANCE__", length_guidance(briefing_type)))
    return call_openai(client, prompt, model, max_tokens=10000)

def review_draft(client: openai.OpenAI, model: str, draft: dict) -> dict:
    slim = {k: v for k, v in draft.items() if k != "tts_script"}
    prompt = REVIEW_PROMPT.replace("Vendor Battlecard AI", APP_NAME).replace("__DRAFT__", json.dumps(slim, indent=2, ensure_ascii=False))
    return call_openai(client, prompt, model, max_tokens=8000)

def build_final(draft: dict, review: dict | None) -> dict:
    final = dict(draft)
    if review:
        for k, v in review.get("revised", {}).items():
            if v:
                final[k] = v
    return final

def generate_tts_script(client: openai.OpenAI, model: str, final: dict, briefing_type: str) -> str:
    report_for_tts = {k: v for k, v in final.items() if k != "tts_script"}
    prompt = (TTS_PROMPT
        .replace("Vendor Battlecard AI", APP_NAME)
        .replace("__DATE__", datetime.now().strftime("%A, %B %d, %Y"))
        .replace("__BRIEFING_TYPE__", briefing_type)
        .replace("__REPORT__", json.dumps(report_for_tts, indent=2, ensure_ascii=False))
        .replace("__TTS_LENGTH_GUIDANCE__", tts_length_guidance(briefing_type)))
    result = call_openai(client, prompt, model, max_tokens=9000)
    return result.get("tts_script", "")

# -----------------------------------------------------------------------------
# TTS and Email
# -----------------------------------------------------------------------------
VOICES = {
    "en-US-GuyNeural (Male, US)": "en-US-GuyNeural",
    "en-US-JennyNeural (Female, US)": "en-US-JennyNeural",
    "en-GB-RyanNeural (Male, UK)": "en-GB-RyanNeural",
    "en-GB-SoniaNeural (Female, UK)": "en-GB-SoniaNeural",
    "en-AU-WilliamNeural (Male, AU)": "en-AU-WilliamNeural",
}

async def _tts(text: str, voice: str, path: str):
    await edge_tts.Communicate(text, voice).save(path)

def generate_mp3(text: str, voice: str, path: str):
    asyncio.run(_tts(text, voice, path))

def email_subject(report: dict) -> str:
    return f"{APP_NAME} {textify(report.get('briefing_type', 'Executive Brief'))} | {today_str()}"

def _plain_preview(text: Any, max_chars: int = 420) -> str:
    t = re.sub(r"\s+", " ", textify(text)).strip()
    return t[:max_chars] + ("..." if len(t) > max_chars else "")

def build_email_summary(report: dict) -> dict:
    highlights = []
    for key in SECTIONS[:5]:
        value = report.get(key, "")
        if value:
            highlights.append({"title": SECTION_LABELS.get(key, key.replace('_',' ').title()), "detail": _plain_preview(value, 260), "meta": APP_TAGLINE})
    return {"intro": f"Please find attached the latest {APP_NAME} output, prepared for senior technology and delivery leaders.", "highlights": highlights[:5], "why_it_matters": _plain_preview(report.get("executive_summary", ""), 520)}

def build_professional_email_html(report: dict, pdf_attached: bool = True, mp3_attached: bool = True, mp3_omitted_reason: str = "") -> str:
    summary = build_email_summary(report)
    highlights_html = "".join(f"""
    <tr><td style='padding:12px 0;border-bottom:1px solid #e5e7eb;vertical-align:top;width:28px;'><div style='width:22px;height:22px;border-radius:50%;background:#e0f2fe;color:#0369a1;text-align:center;line-height:22px;font-family:Arial;font-size:12px;font-weight:700;'>{i}</div></td>
    <td style='padding:12px 0 12px 10px;border-bottom:1px solid #e5e7eb;'><div style='font-family:Arial;font-size:15px;font-weight:700;color:#0f172a;'>{escape(str(h.get('title','')))}</div><div style='font-family:Arial;font-size:12px;color:#64748b;margin-top:2px;'>{escape(str(h.get('meta','')))}</div><div style='font-family:Arial;font-size:13px;color:#334155;line-height:19px;margin-top:6px;'>{escape(str(h.get('detail','')))}</div></td></tr>
    """ for i, h in enumerate(summary["highlights"], 1))
    attachments = []
    if pdf_attached: attachments.append("Professional PDF report")
    if mp3_attached: attachments.append("MP3 audio briefing")
    if mp3_omitted_reason: attachments.append(f"MP3 not attached ({mp3_omitted_reason})")
    attachment_text = ", ".join(attachments) if attachments else "The briefing materials"
    return f"""<!doctype html><html><head><meta charset='utf-8'></head><body style='margin:0;padding:0;background:#f1f5f9;'>
<table width='100%' style='background:#f1f5f9;padding:28px 0;'><tr><td align='center'><table width='720' style='width:720px;max-width:94%;background:#ffffff;border-radius:18px;overflow:hidden;border:1px solid #dbe3ef;'>
<tr><td style='padding:30px 34px;background:#0f172a;color:white;'><div style='font-family:Arial;font-size:28px;font-weight:800;'>{APP_ICON} {APP_NAME}</div><div style='font-family:Arial;font-size:11px;letter-spacing:2px;color:#9bdcf5;text-transform:uppercase;'>{escape(APP_TAGLINE)}</div><div style='font-family:Arial;color:#cbd5e1;font-size:13px;margin-top:16px;'>{escape(textify(report.get('briefing_type','Executive Brief')))} · {escape(datetime.now().strftime('%A, %B %d, %Y'))}</div></td></tr>
<tr><td style='padding:30px 34px;'><p style='font-family:Arial;font-size:15px;color:#334155;'>Hi,</p><p style='font-family:Arial;font-size:15px;line-height:24px;color:#334155;'>{escape(summary['intro'])}</p>
<div style='background:#f8fafc;border:1px solid #e2e8f0;border-left:5px solid #0ea5e9;border-radius:12px;padding:18px 20px;margin:22px 0;'><div style='font-family:Arial;font-size:12px;font-weight:800;letter-spacing:1.4px;text-transform:uppercase;color:#0369a1;margin-bottom:8px;'>Executive Summary</div><div style='font-family:Arial;font-size:15px;line-height:24px;color:#1e293b;'>{safe_html(report.get('executive_summary',''))}</div></div>
<div style='font-family:Arial;font-size:18px;font-weight:800;color:#0f172a;margin:26px 0 8px;'>Top highlights</div><table width='100%'>{highlights_html}</table>
<div style='font-family:Arial;font-size:18px;font-weight:800;color:#0f172a;margin:28px 0 10px;'>Why it matters</div><p style='font-family:Arial;font-size:14px;line-height:23px;color:#334155;'>{escape(summary['why_it_matters'])}</p>
<div style='background:#eef2ff;border:1px solid #c7d2fe;border-radius:12px;padding:16px 18px;margin:24px 0;'><div style='font-family:Arial;font-size:14px;line-height:22px;color:#312e81;'><strong>Attached:</strong> {escape(attachment_text)}.</div></div>
<p style='font-family:Arial;font-size:15px;line-height:23px;color:#334155;'>Regards,<br><strong>Pradip Bhuyan</strong><br>Head of Delivery, TMT</p></td></tr>
<tr><td style='padding:18px 34px;background:#0f172a;'><div style='font-family:Arial;font-size:11px;line-height:17px;color:#94a3b8;'>{escape(CREATOR_FOOTNOTE)}</div></td></tr></table></td></tr></table></body></html>"""

def build_professional_email_text(report: dict, mp3_omitted_reason: str = "") -> str:
    summary = build_email_summary(report)
    lines = [f"Subject: {email_subject(report)}", "", "Hi,", "", summary["intro"], "", "EXECUTIVE SUMMARY", textify(report.get("executive_summary", "")), "", "TOP HIGHLIGHTS"]
    for i, h in enumerate(summary["highlights"], 1):
        meta = f" ({h.get('meta')})" if h.get("meta") else ""
        lines += [f"{i}. {h.get('title','')}{meta}", f"   {h.get('detail','')}"]
    attachment_line = "Attached: Professional PDF report and MP3 audio briefing."
    if mp3_omitted_reason:
        attachment_line = f"Attached: Professional PDF report. MP3 not attached: {mp3_omitted_reason}."
    lines += ["", "WHY IT MATTERS", summary["why_it_matters"], "", attachment_line, "", "Regards,", "Pradip Bhuyan", "Head of Delivery, TMT", "", CREATOR_FOOTNOTE]
    return "\n".join(lines)

def save_email_assets(report: dict, html_path: str, text_path: str, pdf_attached: bool = True, mp3_attached: bool = True, mp3_omitted_reason: str = ""):
    html = build_professional_email_html(report, pdf_attached, mp3_attached, mp3_omitted_reason)
    text = build_professional_email_text(report, mp3_omitted_reason)
    Path(html_path).write_text(html, encoding="utf-8")
    Path(text_path).write_text(text, encoding="utf-8")
    return html, text

def attachment_size_mb(paths: list[str]) -> float:
    return sum(os.path.getsize(p) for p in paths if p and os.path.exists(p)) / (1024 * 1024)

def attach_file(msg: MIMEMultipart, file_path: str, maintype: str, subtype: str, filename: str) -> None:
    with open(file_path, "rb") as f:
        part = MIMEBase(maintype, subtype)
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename={filename}")
    msg.attach(part)

def send_email(cfg: dict, report: dict, mp3_path: str | None, pdf_report_path: str | None = None, include_mp3: bool = True) -> dict:
    if not all([cfg.get("smtp_host"), cfg.get("smtp_port"), cfg.get("sender"), cfg.get("password"), cfg.get("recipient")]):
        raise RuntimeError("SMTP/email settings are incomplete.")
    pdf_exists = bool(pdf_report_path and os.path.exists(pdf_report_path))
    mp3_exists = bool(mp3_path and os.path.exists(mp3_path))
    mp3_omitted_reason = ""
    files_to_attach = []
    if pdf_exists: files_to_attach.append(str(pdf_report_path))
    if include_mp3 and mp3_exists:
        prospective = files_to_attach + [str(mp3_path)]
        if attachment_size_mb(prospective) <= MAX_EMAIL_ATTACHMENT_MB:
            files_to_attach.append(str(mp3_path))
        else:
            mp3_omitted_reason = f"combined attachment size exceeds {MAX_EMAIL_ATTACHMENT_MB:.0f} MB safe email limit"
    msg = MIMEMultipart("mixed")
    msg["From"] = cfg["sender"]
    msg["To"] = cfg["recipient"]
    msg["Subject"] = email_subject(report)
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(build_professional_email_text(report, mp3_omitted_reason), "plain", "utf-8"))
    alternative.attach(MIMEText(build_professional_email_html(report, pdf_exists, mp3_exists and str(mp3_path) in files_to_attach, mp3_omitted_reason), "html", "utf-8"))
    msg.attach(alternative)
    if pdf_exists: attach_file(msg, str(pdf_report_path), "application", "pdf", f"{FILE_PREFIX}_{active_report_id()}_final_report.pdf")
    if mp3_exists and str(mp3_path) in files_to_attach: attach_file(msg, str(mp3_path), "audio", "mpeg", f"{FILE_PREFIX}_{active_report_id()}.mp3")
    with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=60) as srv:
        srv.ehlo(); srv.starttls(context=ssl.create_default_context()); srv.ehlo(); srv.login(cfg["sender"], cfg["password"])
        refused = srv.sendmail(cfg["sender"], [cfg["recipient"]], msg.as_string())
        if refused: raise RuntimeError(f"SMTP refused recipients: {refused}")
    result = {"sent": True, "sent_at": datetime.now().isoformat(timespec="seconds"), "recipient": cfg["recipient"], "pdf_attached": pdf_exists, "mp3_attached": mp3_exists and str(mp3_path) in files_to_attach, "mp3_omitted_reason": mp3_omitted_reason, "attachment_mb_before_base64": round(attachment_size_mb(files_to_attach), 2)}
    save_json(result, delivery_status_path())
    return result

def mark_email_failure(err: Exception) -> None:
    save_json({"sent": False, "failed_at": datetime.now().isoformat(timespec="seconds"), "error": str(err)}, delivery_status_path())

# -----------------------------------------------------------------------------
# PDF
# -----------------------------------------------------------------------------
def _clean_for_pdf(text: Any) -> str:
    return escape(textify(text)).replace("\n", "<br/>")

def generate_pdf_report(report: dict, output_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=44, leftMargin=44, topMargin=52, bottomMargin=44, title=f"{APP_NAME} - {today_str()}", author="Pradip Bhuyan")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24, leading=29, alignment=TA_CENTER, textColor=colors.HexColor("#0F172A"), spaceAfter=4)
    logo_style = ParagraphStyle("Logo", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=16, alignment=TA_CENTER, textColor=colors.HexColor("#0369A1"), spaceAfter=12)
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#64748B"), spaceAfter=16)
    h_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13.5, leading=17, textColor=colors.HexColor("#0369A1"), spaceBefore=13, spaceAfter=7)
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5, leading=14, textColor=colors.HexColor("#1E293B"), alignment=TA_LEFT, spaceAfter=8)
    footer_style = ParagraphStyle("Footer", parent=styles["BodyText"], fontName="Helvetica-Oblique", fontSize=8.5, leading=12, textColor=colors.HexColor("#475569"), alignment=TA_CENTER)
    story = []
    logo_table = Table([[Paragraph(APP_ICON, ParagraphStyle("Icon", parent=styles["Normal"], fontSize=28, alignment=TA_CENTER))]], colWidths=[0.65 * inch], rowHeights=[0.65 * inch], hAlign="CENTER")
    logo_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E0F2FE")), ("BOX", (0, 0), (-1, -1), 1.2, colors.HexColor("#0284C7")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [logo_table, Spacer(1, 8), Paragraph(APP_NAME, title_style), Paragraph(APP_TAGLINE, logo_style), Paragraph(f"{escape(textify(report.get('briefing_type', 'Executive Brief')))} · {datetime.now().strftime('%A, %B %d, %Y')}", subtitle_style)]
    for key in ["executive_summary"] + [k for k in SECTIONS if k != "executive_summary"]:
        if report.get(key):
            story += [Paragraph(escape(SECTION_LABELS.get(key, key.replace('_',' ').title())), h_style), Paragraph(_clean_for_pdf(report.get(key, "")), body_style)]
    story += [Spacer(1, 18), Paragraph(CREATOR_FOOTNOTE, footer_style)]
    def add_page_number(canvas, doc):
        canvas.saveState(); canvas.setFont("Helvetica", 7.5); canvas.setFillColor(colors.HexColor("#64748B")); canvas.drawRightString(A4[0] - 44, 26, f"{APP_NAME} · {today_str()} · Page {doc.page}"); canvas.restoreState()
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return output_path

# -----------------------------------------------------------------------------
# Session state and sidebar
# -----------------------------------------------------------------------------
for k, default in [("stage", None), ("draft", None), ("review", None), ("final", None), ("mp3_ready", False), ("email_sent", False), ("email_last_error", ""), ("report_id", None)]:
    if skey(k) not in st.session_state:
        sset(k, default)

with st.sidebar:
    st.markdown(f"### {APP_ICON} {APP_NAME}")
    st.caption(APP_TAGLINE)
    st.markdown("---")
    st.markdown("### ⚙️ Configuration")
    st.markdown("**🔑 OpenAI**")
    st.success("OpenAI key loaded" if OPENAI_API_KEY else "Set OPENAI_API_KEY in secrets/env")
    briefing_type = st.selectbox("Briefing Type", BRIEFING_OPTIONS, index=0, key=skey("briefing_type_select"))
    model_options = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
    default_model_index = model_options.index(DEFAULT_MODEL) if DEFAULT_MODEL in model_options else 1
    model_choice = st.selectbox("Model", model_options, index=default_model_index, key=skey("model_select"))
    st.markdown("---")
    st.markdown("### 🧭 Advisory Input")
    input_one = st.text_input("Primary topic / vendors / technologies", placeholder="Example: Databricks vs Snowflake, RAG architecture, platform engineering", key=skey("input_one"))
    input_two = st.text_input("Industry / client context", placeholder="Example: telecom, banking, healthcare, manufacturing", key=skey("input_two"))
    input_three = st.text_area("Additional context", placeholder="Add goals, constraints, geography, current stack, risks or decision criteria.", height=120, key=skey("input_three"))
    st.markdown("---")
    st.markdown("**🔊 Audio Voice**")
    voice_labels = list(VOICES.keys())
    default_voice_index = voice_labels.index(DEFAULT_TTS_VOICE_LABEL) if DEFAULT_TTS_VOICE_LABEL in voice_labels else 0
    voice_label = st.selectbox("TTS Voice", voice_labels, index=default_voice_index, key=skey("voice_select"))
    voice = VOICES[voice_label]
    st.markdown("---")
    st.markdown("**📧 Email Delivery**")
    email_configured_now = all([SMTP_HOST, SMTP_PORT, SENDER_EMAIL, SENDER_APP_PASSWORD, RECIPIENT_EMAIL])
    st.success(f"Configured to {RECIPIENT_EMAIL}" if email_configured_now else "Set SMTP/email secrets/env")
    auto_email_enabled = st.checkbox("Automatically email after generation", value=AUTO_EMAIL_AFTER_GENERATION, key=skey("auto_email"))
    include_mp3_email = st.checkbox("Attach MP3 when size allows", value=True, key=skey("include_mp3"))
    st.caption(f"MP3 skipped if PDF+MP3 exceeds {MAX_EMAIL_ATTACHMENT_MB:.0f} MB before base64 encoding.")
    st.markdown("---")
    skip_review = st.checkbox("Skip advisory review (faster)", value=False, key=skey("skip_review"))
    use_cache = st.checkbox("Use current output cache", value=True, key=skey("use_cache"))
    force_mp3 = st.checkbox("Regenerate MP3 even if exists", value=False, key=skey("force_mp3"))
    new_briefing = st.checkbox("Create a new output run", value=False, key=skey("new_briefing"))

if sget("stage") is None and use_cache:
    cf = load_json(rpath("json", "_final"))
    if cf:
        sset("final", cf); sset("review", load_json(rpath("json", "_review"))); sset("draft", load_json(rpath("json", "_draft"))); sset("stage", "final"); sset("mp3_ready", rpath("mp3").exists())
        ds = load_json(delivery_status_path()); sset("email_sent", bool(ds and ds.get("sent"))); sset("email_last_error", "" if sget("email_sent") else (ds or {}).get("error", ""))

# -----------------------------------------------------------------------------
# Header and pipeline
# -----------------------------------------------------------------------------
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown(f'<div class="pulse-header">{APP_ICON} {APP_NAME}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pulse-sub">{briefing_type} · {datetime.now().strftime("%A, %B %d, %Y")}</div>', unsafe_allow_html=True)
with c2:
    st.markdown("<br>", unsafe_allow_html=True)
    run_btn = st.button("▶ Generate", use_container_width=True, key=skey("run_button"))
st.markdown("---")

STAGE_MAP = {None: ["pending", "pending", "pending", "pending"], "draft": ["active", "pending", "pending", "pending"], "review": ["done", "active", "pending", "pending"], "approved": ["done", "done", "active", "pending"], "final": ["done", "done", "done", "active"]}
states = STAGE_MAP.get(sget("stage"), STAGE_MAP[None])
st.markdown('<div class="pipeline">' + ''.join(f'<div class="stage {s}">{l}</div>' for s, l in zip(states, ["1 · Draft", "2 · Advisory Review", "3 · PDF + Audio", "4 · Delivery"])) + '</div>', unsafe_allow_html=True)

def email_cfg() -> dict:
    return {"smtp_host": SMTP_HOST, "smtp_port": int(SMTP_PORT), "sender": SENDER_EMAIL, "password": SENDER_APP_PASSWORD, "recipient": RECIPIENT_EMAIL}

if run_btn:
    if new_briefing:
        sset("report_id", run_id()); sset("draft", None); sset("review", None); sset("final", None); sset("mp3_ready", False); sset("email_sent", False); sset("email_last_error", ""); sset("stage", None); use_cache = False; force_mp3 = True
    if not OPENAI_API_KEY:
        st.error("Please set OPENAI_API_KEY in Streamlit secrets or environment variables."); st.stop()
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    user_context = f"Primary topic/vendors/technologies: {input_one}\nIndustry/client context: {input_two}\nAdditional context: {input_three}"

    with st.status("📝 Stage 1 · Generating draft…", expanded=True) as s1:
        try:
            draft_cache = rpath("json", "_draft")
            if use_cache and draft_cache.exists():
                draft = load_json(draft_cache); st.write("📂 Draft loaded from cache.")
            else:
                st.write(f"🧠 Generating {briefing_type.lower()}…")
                draft = generate_draft(client, model_choice, briefing_type, user_context); draft["briefing_type"] = briefing_type; save_json(draft, draft_cache); st.write("✅ Draft generated and saved.")
            sset("draft", draft); sset("stage", "draft")
        except Exception as e:
            st.error(f"Draft generation failed: {e}"); st.stop()
        s1.update(label="✅ Stage 1 · Draft complete", state="complete")

    if skip_review:
        st.info("⏭️ Advisory review skipped. Draft will be used as-is.")
        sset("review", None); final_obj = dict(sget("draft")); final_obj["briefing_type"] = briefing_type; sset("final", final_obj); save_json(final_obj, rpath("json", "_final")); sset("stage", "approved")
    else:
        with st.status("🔍 Stage 2 · Running advisory review…", expanded=True) as s2:
            try:
                review_cache = rpath("json", "_review")
                if use_cache and review_cache.exists():
                    review = load_json(review_cache); st.write("📂 Review loaded from cache.")
                else:
                    st.write("🧐 Reviewing clarity, credibility and enterprise usefulness…")
                    review = review_draft(client, model_choice, sget("draft")); save_json(review, review_cache); st.write("✅ Review complete.")
                sset("review", review); sset("stage", "review")
                final_obj = build_final(sget("draft"), review); final_obj["briefing_type"] = briefing_type; save_json(final_obj, rpath("json", "_final")); sset("final", final_obj); sset("stage", "approved")
                st.write(f"✅ Final output assembled — Score: {review.get('overall_score','?')}/100 · {review.get('overall_verdict','')}")
            except Exception as e:
                st.error(f"Advisory review failed: {e}"); st.stop()
            s2.update(label=f"✅ Stage 2 · Review complete — {review.get('overall_score','?')}/100", state="complete")

    final_obj = sget("final")
    mp3_out = str(rpath("mp3")); tts_cache = rpath("json", "_tts")
    with st.status("🎙️ Stage 3A · Generating audio script and MP3…", expanded=True) as s3:
        try:
            if force_mp3 or not os.path.exists(mp3_out):
                if use_cache and tts_cache.exists():
                    script = load_json(tts_cache).get("tts_script", ""); st.write("📂 TTS script loaded from cache.")
                else:
                    st.write("🗣️ Generating spoken briefing script…")
                    script = generate_tts_script(client, model_choice, final_obj, briefing_type)
                    if not script: raise ValueError("OpenAI returned an empty TTS script.")
                    final_obj["tts_script"] = script; sset("final", final_obj); save_json({"tts_script": script}, tts_cache); save_json(final_obj, rpath("json", "_final")); st.write(f"✅ TTS script generated — {len(script.split()):,} words.")
                st.write(f"🔊 Synthesising speech with {voice_label}…")
                generate_mp3(script, voice, mp3_out); sset("mp3_ready", True); st.write(f"✅ MP3 created — {Path(mp3_out).stat().st_size / (1024 * 1024):.1f} MB")
            else:
                st.write("📂 MP3 already exists for this report run."); sset("mp3_ready", True)
        except Exception as e:
            st.warning(f"TTS generation error: {e}")
        s3.update(label="✅ Stage 3A · Audio ready", state="complete")

    pdf_out = str(pdf_path())
    with st.status("📄 Stage 3B · Generating professional PDF…", expanded=True) as spdf:
        try:
            generate_pdf_report(sget("final"), pdf_out); st.write(f"✅ PDF created — {Path(pdf_out).name}")
        except Exception as e:
            st.warning(f"PDF generation error: {e}")
        spdf.update(label="✅ Stage 3B · PDF ready", state="complete")

    save_email_assets(sget("final"), str(email_html_path()), str(email_text_path()), pdf_attached=os.path.exists(pdf_out), mp3_attached=os.path.exists(mp3_out))

    if email_configured_now and auto_email_enabled:
        with st.status("📧 Stage 4 · Sending email delivery…", expanded=True) as s4:
            try:
                result = send_email(email_cfg(), sget("final"), mp3_out if sget("mp3_ready") else None, pdf_out if os.path.exists(pdf_out) else None, include_mp3=include_mp3_email)
                sset("email_sent", True); sset("email_last_error", ""); st.write(f"✅ Mailed to {RECIPIENT_EMAIL}. PDF attached: {result['pdf_attached']}; MP3 attached: {result['mp3_attached']}.")
                if result.get("mp3_omitted_reason"): st.write(f"ℹ️ {result['mp3_omitted_reason']}")
                s4.update(label="✅ Stage 4 · Delivered", state="complete")
            except Exception as e:
                sset("email_sent", False); sset("email_last_error", str(e)); mark_email_failure(e); st.warning(f"Email error: {e}"); s4.update(label="⚠️ Stage 4 · Email failed", state="error")
    elif not email_configured_now:
        st.info("📧 Email skipped — set SMTP/email secrets or environment variables.")
    else:
        st.info("📧 Automatic email disabled. Use the manual email button after generation.")
    sset("stage", "final")
    st.rerun()

# -----------------------------------------------------------------------------
# Display
# -----------------------------------------------------------------------------
final = sget("final")
review = sget("review")

if final:
    if review:
        score = review.get("overall_score", 0); verdict = review.get("overall_verdict", ""); ed_note = review.get("editorial_summary", "")
        st.markdown(f'<div class="approved-banner">✅ INTERNALLY REVIEWED · <span class="score-badge {score_cls(score)}">{score}/100</span> · {safe_html(verdict)}<br><span style="color:#a7f3d0;font-size:0.83rem;">{safe_html(ed_note)}</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="approved-banner" style="background:linear-gradient(135deg,#1a1208,#2d1f00);border-color:#f59e0b;color:#fcd34d;">📋 Output ready · Advisory review was skipped.</div>', unsafe_allow_html=True)

    populated_sections = sum(1 for k in SECTIONS if final.get(k))
    cols = st.columns(5)
    metrics = [("Brief Type", textify(final.get("briefing_type", "Brief"))), ("Sections", populated_sections), ("Review", review.get("overall_score", "N/A") if review else "Skipped"), ("Run ID", active_report_id()), ("Audio", "Ready" if sget("mp3_ready") else "Pending")]
    for col, (label, value) in zip(cols, metrics):
        with col: st.markdown(f'<div class="metric-box"><div class="metric-val" style="font-size:1.1rem;">{safe_html(value)}</div><div class="metric-label">{safe_html(label)}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    t_report, t_review, t_audio, t_email_copy = st.tabs(["📋 Final Output", "🔍 Advisory Review", "🎧 Audio, PDF & Delivery", "✉️ Email Copy"])

    with t_report:
        for key in SECTIONS:
            if final.get(key):
                st.markdown(f'<div class="section-card"><div class="section-title">{safe_html(SECTION_LABELS.get(key, key.replace("_", " ").title()))}</div><div class="report-body">{safe_html(final.get(key, ""))}</div></div>', unsafe_allow_html=True)
        txt_parts = [f"{APP_NAME.upper()} - {textify(final.get('briefing_type', 'EXECUTIVE BRIEF')).upper()} - {today_str()}", "=" * 72, CREATOR_FOOTNOTE]
        for key in SECTIONS:
            txt_parts.extend([SECTION_LABELS.get(key, key.replace('_',' ').title()).upper(), textify(final.get(key, ""))])
        txt = "\n\n".join(textify(part) for part in txt_parts)
        st.download_button("⬇️ Download Final Output (TXT)", data=txt, file_name=f"{FILE_PREFIX}_{active_report_id()}_final.txt", mime="text/plain", key=skey("download_txt"))

    with t_review:
        if not review:
            st.info("Advisory review was skipped for this run.")
        else:
            st.markdown(f'<div class="metric-box" style="padding:1.5rem;max-width:260px;"><div class="metric-val" style="font-size:2.6rem;">{review.get("overall_score", 0)}</div><div class="metric-label">Overall / 100</div><br><span class="score-badge {score_cls(review.get("overall_score", 0))}">{safe_html(review.get("overall_verdict", ""))}</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="section-card"><div class="report-body" style="font-size:0.9rem;">{safe_html(review.get("editorial_summary", ""))}</div></div>', unsafe_allow_html=True)
            for sec_key, sec_rev in (review.get("reviews", {}) or {}).items():
                if isinstance(sec_rev, dict):
                    with st.expander(f"{sec_key} — {sec_rev.get('score', 0)}/100", expanded=False):
                        st.write("Issues:", sec_rev.get("issues", [])); st.write("Suggestions:", sec_rev.get("suggestions", []))

    with t_audio:
        mp3_file = rpath("mp3")
        if sget("mp3_ready") and mp3_file.exists():
            st.markdown('<div class="approved-banner">🎧 Audio briefing ready</div>', unsafe_allow_html=True)
            audio_bytes = mp3_file.read_bytes(); st.audio(audio_bytes, format="audio/mpeg")
            st.markdown(f'<div class="status-line">Voice: {voice_label} · File: {mp3_file.stat().st_size / (1024 * 1024):.1f} MB · {mp3_file.name}</div>', unsafe_allow_html=True)
            st.download_button("⬇️ Download MP3", data=audio_bytes, file_name=f"{FILE_PREFIX}_{active_report_id()}.mp3", mime="audio/mpeg", key=skey("download_mp3"))
        else:
            st.info("🎙️ MP3 not yet generated. Click Generate to create it.")
        st.markdown("---")
        st.markdown("### 📄 PDF Report")
        pdf_file = pdf_path()
        if pdf_file.exists():
            pdf_bytes = pdf_file.read_bytes(); st.success(f"✅ PDF ready: {pdf_file.name}"); st.download_button("⬇️ Download PDF", data=pdf_bytes, file_name=f"{FILE_PREFIX}_{active_report_id()}_final_report.pdf", mime="application/pdf", key=skey("download_pdf"))
        else:
            st.info("📄 PDF not yet generated. Click Generate to create it.")
        st.markdown("---")
        st.markdown("### 📧 Email Delivery")
        ds = load_json(delivery_status_path()) or {}
        if sget("email_sent") or ds.get("sent"):
            st.success(f"✅ Last delivery mailed to **{ds.get('recipient', RECIPIENT_EMAIL)}** at {ds.get('sent_at', 'unknown time')}")
            st.caption(f"PDF attached: {ds.get('pdf_attached')} · MP3 attached: {ds.get('mp3_attached')} · Attachment MB: {ds.get('attachment_mb_before_base64')}")
            if ds.get("mp3_omitted_reason"): st.info(ds.get("mp3_omitted_reason"))
        elif sget("email_last_error") or ds.get("error"):
            st.warning(f"Last email attempt failed: {sget('email_last_error') or ds.get('error')}")
        elif not email_configured_now:
            st.warning("Email not configured. Set SMTP_HOST, SMTP_PORT, SENDER_EMAIL, SENDER_APP_PASSWORD and RECIPIENT_EMAIL.")
        else:
            st.info("No delivery has been recorded for this run yet.")
        manual_disabled = not (email_configured_now and final and pdf_file.exists())
        if st.button("📧 Send Email Now", use_container_width=True, disabled=manual_disabled, key=skey("manual_email")):
            try:
                result = send_email(email_cfg(), final, str(mp3_file) if mp3_file.exists() else None, str(pdf_file) if pdf_file.exists() else None, include_mp3=include_mp3_email)
                sset("email_sent", True); sset("email_last_error", ""); st.success(f"Email sent to {RECIPIENT_EMAIL}. PDF attached: {result['pdf_attached']}; MP3 attached: {result['mp3_attached']}.")
                if result.get("mp3_omitted_reason"): st.info(result["mp3_omitted_reason"])
            except Exception as e:
                sset("email_sent", False); sset("email_last_error", str(e)); mark_email_failure(e); st.error(f"Manual email failed: {e}")

    with t_email_copy:
        st.markdown("### ✉️ Professional Email Copy")
        html_file = email_html_path(); text_file = email_text_path()
        if not html_file.exists() or not text_file.exists():
            try: save_email_assets(final, str(html_file), str(text_file), pdf_attached=pdf_path().exists(), mp3_attached=rpath("mp3").exists())
            except Exception as e: st.warning(f"Could not prepare email copy: {e}")
        st.markdown("**Subject line**"); st.code(email_subject(final), language="text")
        if text_file.exists(): st.text_area("Plain-text email", text_file.read_text(encoding="utf-8"), height=360, label_visibility="collapsed", key=skey("email_text_area"))
        c_html, c_txt = st.columns(2)
        if html_file.exists():
            with c_html: st.download_button("⬇️ Download Branded Email HTML", data=html_file.read_bytes(), file_name=f"{FILE_PREFIX}_{active_report_id()}_email_brief.html", mime="text/html", use_container_width=True, key=skey("download_html"))
        if text_file.exists():
            with c_txt: st.download_button("⬇️ Download Plain-Text Email", data=text_file.read_bytes(), file_name=f"{FILE_PREFIX}_{active_report_id()}_email_brief.txt", mime="text/plain", use_container_width=True, key=skey("download_email_txt"))
        if html_file.exists(): st.components.v1.html(html_file.read_text(encoding="utf-8"), height=780, scrolling=True)
else:
    st.markdown(f"""
    <div style="text-align:center;padding:4rem 2rem;"><div style="font-size:4.5rem;">{APP_ICON}</div><div style="font-family:'Syne',sans-serif;font-size:1.5rem;color:#64748b;margin-top:1rem;">Set inputs and click <strong style="color:#00d4ff;">▶ Generate</strong></div><div style="font-family:'Space Mono',monospace;font-size:0.7rem;color:#1e3a5f;margin-top:1.2rem;letter-spacing:0.15em;">DRAFT → REVIEW → PDF + AUDIO → EMAIL</div></div>
    """, unsafe_allow_html=True)
