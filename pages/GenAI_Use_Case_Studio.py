"""
GenAI Use Case Studio - Practical GenAI Advisory App

Generates practical GenAI use cases by industry, function and maturity level.
Includes:
- Streamlit dark executive UI aligned with TelecomPulse style
- app-specific namespaced session state to avoid cross-page brief leakage
- OpenAI JSON generation
- internal review / refinement stage
- professional PDF proposal generation
- email-ready HTML/TXT assets
- optional SMTP delivery with attachment-size guard
- safe TXT export with textify()

Required env vars or .streamlit/secrets.toml keys:
OPENAI_API_KEY
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_sender@gmail.com
SENDER_APP_PASSWORD=your_gmail_app_password
RECIPIENT_EMAIL=recipient@example.com

Optional:
DEFAULT_MODEL=gpt-4o-mini
MAX_EMAIL_ATTACHMENT_MB=22
AUTO_EMAIL_AFTER_GENERATION=false
"""

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

# -----------------------------------------------------------------------------
# App identity and session namespace
# -----------------------------------------------------------------------------
APP_NAME = "GenAI Use Case Studio"
APP_ICON = "🧪"
APP_KEY = "genai_use_case_studio"
FILE_PREFIX = "genai_use_case_studio"
CREATOR_FOOTNOTE = "Content created by Pradip Bhuyan, Head of Delivery, TMT."


def skey(name: str) -> str:
    return f"{APP_KEY}_{name}"


def sget(name: str, default: Any = None) -> Any:
    return st.session_state.get(skey(name), default)


def sset(name: str, value: Any) -> None:
    st.session_state[skey(name)] = value


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
MAX_EMAIL_ATTACHMENT_MB = float(get_config_value("MAX_EMAIL_ATTACHMENT_MB", "22"))
AUTO_EMAIL_AFTER_GENERATION = get_config_value("AUTO_EMAIL_AFTER_GENERATION", "false").lower() in {"1", "true", "yes", "y"}

# -----------------------------------------------------------------------------
# Streamlit page and CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title=APP_NAME, page_icon=APP_ICON, layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');
:root { --bg:#0a0e1a; --surface:#111827; --border:#1e2d45; --accent:#00d4ff; --accent2:#7c3aed; --text:#e2e8f0; --muted:#64748b; --success:#10b981; --warning:#f59e0b; --danger:#ef4444; }
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
.metric-box{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1rem;text-align:center;} .metric-val{font-family:'Space Mono',monospace;font-size:1.4rem;font-weight:700;color:var(--accent);} .metric-label{font-size:0.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:0.1em;}
.approved-banner{background:linear-gradient(135deg,#064e3b,#065f46);border:1px solid #10b981;border-radius:8px;padding:0.75rem 1.25rem;margin-bottom:1.5rem;font-family:'Space Mono',monospace;font-size:0.78rem;color:#6ee7b7;letter-spacing:0.04em;}
.pulse-header{font-family:'Syne',sans-serif;font-weight:800;font-size:2.6rem;background:linear-gradient(90deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:0;line-height:1.1;} .pulse-sub{font-family:'Space Mono',monospace;font-size:0.75rem;color:var(--muted);letter-spacing:0.15em;text-transform:uppercase;margin-top:4px;}
.status-line{font-family:'Space Mono',monospace;font-size:0.7rem;color:var(--muted);padding:4px 0;letter-spacing:0.04em;} .tag{display:inline-block;font-family:'Space Mono',monospace;font-size:0.65rem;padding:2px 8px;border-radius:3px;margin-right:6px;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.08em;background:#3a2f1e;color:#fbbf24;border:1px solid #92400e;}
.usecase-card{background:#0f172a;border:1px solid #1e2d45;border-left:4px solid #00d4ff;border-radius:10px;padding:1rem 1.2rem;margin-bottom:0.85rem;}
.usecase-title{font-weight:800;color:#f8fafc;font-size:1rem;margin-bottom:0.35rem;}
.small-muted{font-family:'Space Mono',monospace;font-size:0.68rem;color:#64748b;letter-spacing:0.05em;text-transform:uppercase;}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Paths and constants
# -----------------------------------------------------------------------------
REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(exist_ok=True)

INDUSTRIES = ["Telecom", "Banking", "Insurance", "Manufacturing", "Healthcare", "Retail", "Public Sector", "Energy & Utilities", "Travel & Hospitality"]
FUNCTIONS = ["Customer Care", "Sales", "Operations", "HR", "Finance", "IT", "Marketing", "Risk & Compliance", "Supply Chain", "Field Service"]
MATURITY_LEVELS = ["Pilot", "Production", "Transformation"]


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
    return rpath("pdf", "_proposal")


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


def safe_html(text: Any) -> str:
    return escape(textify(text)).replace("\n", "<br>")


def textify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        lines = []
        for key, val in value.items():
            label = str(key).replace("_", " ").title()
            lines.append(f"{label}: {textify(val)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            item_text = textify(item).strip()
            if item_text:
                lines.append(f"- {item_text}")
        return "\n".join(lines)
    return str(value)

# -----------------------------------------------------------------------------
# Prompts
# -----------------------------------------------------------------------------
GENERATION_PROMPT = """You are GenAI Use Case Studio, a senior AI transformation advisor, enterprise architect and delivery leader.
Today is __DATE__.

Create a practical GenAI use case proposal for:
Industry: __INDUSTRY__
Business function: __FUNCTION__
Maturity level: __MATURITY__
Business context / pain points: __CONTEXT__
Target geography or market, if relevant: __GEOGRAPHY__
Technology constraints / preferences: __CONSTRAINTS__

Generate exactly 10 practical GenAI use cases. They must be grounded, implementable, business-value oriented and suitable for client workshop discussion.

Quality standards:
- Avoid generic hype. Be specific to the selected industry, function and maturity.
- For pilot maturity, emphasize narrow MVPs, limited data scope, human-in-the-loop and fast validation.
- For production maturity, emphasize integration, controls, monitoring, LLMOps, change management and measurable ROI.
- For transformation maturity, emphasize operating-model change, platform patterns, reuse, data foundations and enterprise governance.
- Do not invent regulatory facts, vendor pricing or unsupported benchmark numbers.
- Include delivery practicality, data needs, architecture, risk controls and KPIs.

Return a JSON object with exactly these keys:
"proposal_title", "industry", "function", "maturity", "executive_summary", "top_10_use_cases", "business_value_summary", "required_data", "architecture_pattern", "risks_and_controls", "mvp_roadmap", "kpis", "implementation_notes", "recommended_next_steps".

Schema details:
- top_10_use_cases: list of exactly 10 objects with keys: rank, title, problem_solved, genai_solution, business_value, required_data, architecture_pattern, risks, controls, mvp_scope, kpis, complexity, time_to_value.
- required_data: list of objects with data_domain, example_sources, sensitivity, readiness_notes.
- architecture_pattern: object with pattern_name, overview, components, integration_points, security_controls, llmops_controls.
- risks_and_controls: list of objects with risk, impact, mitigation.
- mvp_roadmap: list of phases with phase, duration, activities, outputs, owner_roles.
- kpis: list of objects with metric, target_direction, measurement_method.
- recommended_next_steps: list of 5 concise actions.
Return ONLY valid JSON. No markdown fences.
"""

REVIEW_PROMPT = """You are the Chief Advisory Partner reviewing a GenAI use case proposal.
Review the draft for specificity, feasibility, business value, delivery practicality, risk controls and executive quality.
For each major section, score 0-100 and provide issues and suggestions. Produce a revised version of every section scoring below 92. For sections scoring 92+, omit from revised.
Draft: __DRAFT__
Return JSON with exactly: overall_score, overall_verdict, reviews, revised, advisory_summary.
Return ONLY valid JSON.
"""

# -----------------------------------------------------------------------------
# OpenAI
# -----------------------------------------------------------------------------
def call_openai(client: openai.OpenAI, prompt: str, model: str, max_tokens: int = 10000) -> dict:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.45,
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


def generate_proposal(client: openai.OpenAI, model: str, industry: str, function: str, maturity: str, context: str, geography: str, constraints: str) -> dict:
    prompt = (GENERATION_PROMPT
        .replace("__DATE__", datetime.now().strftime("%A, %B %d, %Y"))
        .replace("__INDUSTRY__", industry)
        .replace("__FUNCTION__", function)
        .replace("__MATURITY__", maturity)
        .replace("__CONTEXT__", context or "Not specified")
        .replace("__GEOGRAPHY__", geography or "Not specified")
        .replace("__CONSTRAINTS__", constraints or "Not specified"))
    return call_openai(client, prompt, model, max_tokens=12000)


def review_proposal(client: openai.OpenAI, model: str, draft: dict) -> dict:
    return call_openai(client, REVIEW_PROMPT.replace("__DRAFT__", json.dumps(draft, indent=2, ensure_ascii=False)), model, max_tokens=10000)


def build_final(draft: dict, review: dict | None) -> dict:
    final = dict(draft)
    if review:
        for k, v in review.get("revised", {}).items():
            if v:
                final[k] = v
    return final

# -----------------------------------------------------------------------------
# Email
# -----------------------------------------------------------------------------
def email_subject(report: dict) -> str:
    industry = textify(report.get("industry", "Industry"))
    function = textify(report.get("function", "Function"))
    return f"GenAI Use Case Studio | {industry} - {function} | {today_str()}"


def build_email_summary(report: dict) -> dict:
    use_cases = report.get("top_10_use_cases", []) or []
    highlights = []
    for item in use_cases[:5]:
        if isinstance(item, dict):
            highlights.append({
                "title": item.get("title", ""),
                "detail": item.get("business_value", ""),
                "meta": f"Complexity: {item.get('complexity', 'TBD')} | Time to value: {item.get('time_to_value', 'TBD')}",
            })
    return {
        "intro": "Please find attached the GenAI Use Case Studio proposal, prepared for practical workshop and delivery planning.",
        "highlights": highlights,
        "why_it_matters": textify(report.get("business_value_summary", report.get("executive_summary", "")))[:700],
    }


def build_professional_email_html(report: dict, pdf_attached: bool = True) -> str:
    summary = build_email_summary(report)
    highlights_html = "".join(f"""
    <tr><td style='padding:12px 0;border-bottom:1px solid #e5e7eb;vertical-align:top;width:28px;'><div style='width:22px;height:22px;border-radius:50%;background:#e0f2fe;color:#0369a1;text-align:center;line-height:22px;font-family:Arial;font-size:12px;font-weight:700;'>{i}</div></td>
    <td style='padding:12px 0 12px 10px;border-bottom:1px solid #e5e7eb;'><div style='font-family:Arial;font-size:15px;font-weight:700;color:#0f172a;'>{escape(textify(h.get('title','')))}</div><div style='font-family:Arial;font-size:12px;color:#64748b;margin-top:2px;'>{escape(textify(h.get('meta','')))}</div><div style='font-family:Arial;font-size:13px;color:#334155;line-height:19px;margin-top:6px;'>{escape(textify(h.get('detail','')))}</div></td></tr>
    """ for i, h in enumerate(summary["highlights"], 1))
    attachment_text = "Professional PDF proposal" if pdf_attached else "Proposal content"
    return f"""<!doctype html><html><head><meta charset='utf-8'></head><body style='margin:0;padding:0;background:#f1f5f9;'>
<table width='100%' style='background:#f1f5f9;padding:28px 0;'><tr><td align='center'><table width='720' style='width:720px;max-width:94%;background:#ffffff;border-radius:18px;overflow:hidden;border:1px solid #dbe3ef;'>
<tr><td style='padding:30px 34px;background:#0f172a;color:white;'><div style='font-family:Arial;font-size:28px;font-weight:800;'>🧪 GenAI Use Case Studio</div><div style='font-family:Arial;font-size:11px;letter-spacing:2px;color:#c4b5fd;text-transform:uppercase;'>Practical GenAI Advisory Proposal</div><div style='font-family:Arial;color:#cbd5e1;font-size:13px;margin-top:16px;'>{escape(textify(report.get('industry','')))} · {escape(textify(report.get('function','')))} · {escape(textify(report.get('maturity','')))}</div></td></tr>
<tr><td style='padding:30px 34px;'><p style='font-family:Arial;font-size:15px;color:#334155;'>Hi,</p><p style='font-family:Arial;font-size:15px;line-height:24px;color:#334155;'>{escape(summary['intro'])}</p>
<div style='background:#f8fafc;border:1px solid #e2e8f0;border-left:5px solid #7c3aed;border-radius:12px;padding:18px 20px;margin:22px 0;'><div style='font-family:Arial;font-size:12px;font-weight:800;letter-spacing:1.4px;text-transform:uppercase;color:#6d28d9;margin-bottom:8px;'>Executive Summary</div><div style='font-family:Arial;font-size:15px;line-height:24px;color:#1e293b;'>{safe_html(report.get('executive_summary',''))}</div></div>
<div style='font-family:Arial;font-size:18px;font-weight:800;color:#0f172a;margin:26px 0 8px;'>Top use case highlights</div><table width='100%'>{highlights_html}</table>
<div style='font-family:Arial;font-size:18px;font-weight:800;color:#0f172a;margin:28px 0 10px;'>Business value</div><p style='font-family:Arial;font-size:14px;line-height:23px;color:#334155;'>{escape(summary['why_it_matters'])}</p>
<div style='background:#eef2ff;border:1px solid #c7d2fe;border-radius:12px;padding:16px 18px;margin:24px 0;'><div style='font-family:Arial;font-size:14px;line-height:22px;color:#312e81;'><strong>Attached:</strong> {escape(attachment_text)}.</div></div>
<p style='font-family:Arial;font-size:15px;line-height:23px;color:#334155;'>Regards,<br><strong>Pradip Bhuyan</strong><br>Head of Delivery, TMT</p></td></tr>
<tr><td style='padding:18px 34px;background:#0f172a;'><div style='font-family:Arial;font-size:11px;line-height:17px;color:#94a3b8;'>{escape(CREATOR_FOOTNOTE)}</div></td></tr></table></td></tr></table></body></html>"""


def build_professional_email_text(report: dict) -> str:
    summary = build_email_summary(report)
    lines = [f"Subject: {email_subject(report)}", "", "Hi,", "", summary["intro"], "", "EXECUTIVE SUMMARY", textify(report.get("executive_summary", "")), "", "TOP USE CASE HIGHLIGHTS"]
    for i, h in enumerate(summary["highlights"], 1):
        lines += [f"{i}. {textify(h.get('title',''))}", f"   {textify(h.get('detail',''))}"]
    lines += ["", "BUSINESS VALUE", summary["why_it_matters"], "", "Attached: Professional PDF proposal.", "", "Regards,", "Pradip Bhuyan", "Head of Delivery, TMT", "", CREATOR_FOOTNOTE]
    return "\n".join(lines)


def save_email_assets(report: dict, html_path: str, text_path: str, pdf_attached: bool = True):
    html = build_professional_email_html(report, pdf_attached=pdf_attached)
    text = build_professional_email_text(report)
    Path(html_path).write_text(html, encoding="utf-8")
    Path(text_path).write_text(text, encoding="utf-8")
    return html, text


def attachment_size_mb(paths: list[str]) -> float:
    total = 0
    for p in paths:
        if p and os.path.exists(p):
            total += os.path.getsize(p)
    return total / (1024 * 1024)


def attach_file(msg: MIMEMultipart, file_path: str, maintype: str, subtype: str, filename: str) -> None:
    with open(file_path, "rb") as f:
        part = MIMEBase(maintype, subtype)
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename={filename}")
    msg.attach(part)


def send_email(cfg: dict, report: dict, pdf_report_path: str | None = None) -> dict:
    if not all([cfg.get("smtp_host"), cfg.get("smtp_port"), cfg.get("sender"), cfg.get("password"), cfg.get("recipient")]):
        raise RuntimeError("SMTP/email settings are incomplete.")
    pdf_exists = bool(pdf_report_path and os.path.exists(pdf_report_path))
    files_to_attach = [str(pdf_report_path)] if pdf_exists else []
    if attachment_size_mb(files_to_attach) > MAX_EMAIL_ATTACHMENT_MB:
        files_to_attach = []
        pdf_exists = False

    msg = MIMEMultipart("mixed")
    msg["From"] = cfg["sender"]
    msg["To"] = cfg["recipient"]
    msg["Subject"] = email_subject(report)
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(build_professional_email_text(report), "plain", "utf-8"))
    alternative.attach(MIMEText(build_professional_email_html(report, pdf_attached=pdf_exists), "html", "utf-8"))
    msg.attach(alternative)

    if pdf_exists:
        attach_file(msg, str(pdf_report_path), "application", "pdf", f"{FILE_PREFIX}_{active_report_id()}_proposal.pdf")

    with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=60) as srv:
        srv.ehlo()
        srv.starttls(context=ssl.create_default_context())
        srv.ehlo()
        srv.login(cfg["sender"], cfg["password"])
        refused = srv.sendmail(cfg["sender"], [cfg["recipient"]], msg.as_string())
        if refused:
            raise RuntimeError(f"SMTP refused recipients: {refused}")

    result = {
        "sent": True,
        "sent_at": datetime.now().isoformat(timespec="seconds"),
        "recipient": cfg["recipient"],
        "pdf_attached": pdf_exists,
        "attachment_mb_before_base64": round(attachment_size_mb(files_to_attach), 2),
    }
    save_json(result, delivery_status_path())
    return result


def mark_email_failure(err: Exception) -> None:
    save_json({"sent": False, "failed_at": datetime.now().isoformat(timespec="seconds"), "error": str(err)}, delivery_status_path())

# -----------------------------------------------------------------------------
# PDF
# -----------------------------------------------------------------------------
def _clean_for_pdf(text: Any) -> str:
    return escape(textify(text)).replace("\n", "<br/>")


def generate_pdf_proposal(report: dict, output_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=44, leftMargin=44, topMargin=52, bottomMargin=44, title=f"{APP_NAME} Proposal - {today_str()}", author="Pradip Bhuyan")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24, leading=29, alignment=TA_CENTER, textColor=colors.HexColor("#0F172A"), spaceAfter=4)
    logo_style = ParagraphStyle("Logo", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=16, alignment=TA_CENTER, textColor=colors.HexColor("#6D28D9"), spaceAfter=12)
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#64748B"), spaceAfter=16)
    h_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13.5, leading=17, textColor=colors.HexColor("#6D28D9"), spaceBefore=13, spaceAfter=7)
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.3, leading=13.7, textColor=colors.HexColor("#1E293B"), alignment=TA_LEFT, spaceAfter=8)
    small_style = ParagraphStyle("Small", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.3, leading=10, textColor=colors.HexColor("#475569"))
    footer_style = ParagraphStyle("Footer", parent=styles["BodyText"], fontName="Helvetica-Oblique", fontSize=8.5, leading=12, textColor=colors.HexColor("#475569"), alignment=TA_CENTER)

    story = []
    logo_table = Table([[Paragraph(APP_ICON, ParagraphStyle("Icon", parent=styles["Normal"], fontSize=28, alignment=TA_CENTER))]], colWidths=[0.65 * inch], rowHeights=[0.65 * inch], hAlign="CENTER")
    logo_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3E8FF")), ("BOX", (0, 0), (-1, -1), 1.2, colors.HexColor("#7C3AED")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [logo_table, Spacer(1, 8), Paragraph(APP_NAME, title_style), Paragraph("Practical GenAI Advisory Proposal", logo_style), Paragraph(f"{escape(textify(report.get('industry','')))} · {escape(textify(report.get('function','')))} · {escape(textify(report.get('maturity','')))} · {today_str()}", subtitle_style)]

    story += [Paragraph("Executive Summary", h_style), Paragraph(_clean_for_pdf(report.get("executive_summary", "")), body_style)]
    story += [Paragraph("Business Value Summary", h_style), Paragraph(_clean_for_pdf(report.get("business_value_summary", "")), body_style)]

    use_cases = report.get("top_10_use_cases", []) or []
    if use_cases:
        story.append(Paragraph("Top 10 GenAI Use Cases", h_style))
        data = [[Paragraph("<b>#</b>", small_style), Paragraph("<b>Use Case</b>", small_style), Paragraph("<b>Business Value</b>", small_style), Paragraph("<b>Complexity</b>", small_style), Paragraph("<b>Time to Value</b>", small_style)]]
        for idx, item in enumerate(use_cases[:10], 1):
            if isinstance(item, dict):
                data.append([
                    Paragraph(escape(textify(item.get("rank", idx))), small_style),
                    Paragraph(escape(textify(item.get("title", ""))), small_style),
                    Paragraph(escape(textify(item.get("business_value", ""))), small_style),
                    Paragraph(escape(textify(item.get("complexity", ""))), small_style),
                    Paragraph(escape(textify(item.get("time_to_value", ""))), small_style),
                ])
        t = Table(data, colWidths=[0.35 * inch, 1.55 * inch, 2.8 * inch, 0.8 * inch, 1.1 * inch], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 5)]))
        story += [t, Spacer(1, 10)]

        story += [PageBreak(), Paragraph("Use Case Details", h_style)]
        for idx, item in enumerate(use_cases[:10], 1):
            if isinstance(item, dict):
                story.append(Paragraph(f"<b>{idx}. {escape(textify(item.get('title','')))}</b>", body_style))
                detail = (
                    f"Problem solved: {textify(item.get('problem_solved',''))}\n"
                    f"GenAI solution: {textify(item.get('genai_solution',''))}\n"
                    f"Required data: {textify(item.get('required_data',''))}\n"
                    f"Architecture pattern: {textify(item.get('architecture_pattern',''))}\n"
                    f"Risks: {textify(item.get('risks',''))}\n"
                    f"Controls: {textify(item.get('controls',''))}\n"
                    f"MVP scope: {textify(item.get('mvp_scope',''))}\n"
                    f"KPIs: {textify(item.get('kpis',''))}"
                )
                story.append(Paragraph(_clean_for_pdf(detail), body_style))

    for heading, key in [
        ("Required Data", "required_data"),
        ("Architecture Pattern", "architecture_pattern"),
        ("Risks and Controls", "risks_and_controls"),
        ("MVP Roadmap", "mvp_roadmap"),
        ("KPIs", "kpis"),
        ("Implementation Notes", "implementation_notes"),
        ("Recommended Next Steps", "recommended_next_steps"),
    ]:
        if report.get(key):
            story += [Paragraph(heading, h_style), Paragraph(_clean_for_pdf(report.get(key)), body_style)]

    story += [Spacer(1, 18), Paragraph(CREATOR_FOOTNOTE, footer_style)]

    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawRightString(A4[0] - 44, 26, f"{APP_NAME} · {today_str()} · Page {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return output_path

# -----------------------------------------------------------------------------
# Session state and sidebar
# -----------------------------------------------------------------------------
for k, default in [
    ("stage", None),
    ("draft", None),
    ("review", None),
    ("final", None),
    ("email_sent", False),
    ("email_last_error", ""),
    ("report_id", None),
]:
    if skey(k) not in st.session_state:
        sset(k, default)

with st.sidebar:
    st.markdown(f"### {APP_ICON} {APP_NAME}")
    st.caption("Practical GenAI advisory proposal generator")
    st.markdown("---")
    st.markdown("### 🎯 Scope")
    industry = st.selectbox("Industry", INDUSTRIES, index=0)
    function = st.selectbox("Function", FUNCTIONS, index=0)
    maturity = st.selectbox("Maturity", MATURITY_LEVELS, index=0)
    geography = st.text_input("Geography / market", placeholder="Optional, e.g., North America, India, Europe")
    context = st.text_area("Business context / pain points", placeholder="Optional. Example: reduce contact center AHT, improve sales productivity, automate knowledge retrieval.", height=90)
    constraints = st.text_area("Technology constraints / preferences", placeholder="Optional. Example: Azure preferred, ServiceNow integration, PII constraints, no public SaaS.", height=80)

    st.markdown("---")
    st.markdown("### ⚙️ Configuration")
    st.markdown("**🔑 OpenAI**")
    st.success("OpenAI key loaded" if OPENAI_API_KEY else "Set OPENAI_API_KEY in secrets/env")
    model_options = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-5", "gpt-5-mini"]
    default_model_index = model_options.index(DEFAULT_MODEL) if DEFAULT_MODEL in model_options else 1
    model_choice = st.selectbox("Model", model_options, index=default_model_index)
    st.markdown("---")
    st.markdown("**📧 Email Delivery**")
    email_configured_now = all([SMTP_HOST, SMTP_PORT, SENDER_EMAIL, SENDER_APP_PASSWORD, RECIPIENT_EMAIL])
    st.success(f"Configured to {RECIPIENT_EMAIL}" if email_configured_now else "Set SMTP/email secrets/env")
    auto_email_enabled = st.checkbox("Automatically email after generation", value=AUTO_EMAIL_AFTER_GENERATION)
    st.caption(f"PDF skipped if attachment exceeds {MAX_EMAIL_ATTACHMENT_MB:.0f} MB before base64 encoding.")
    st.markdown("---")
    skip_review = st.checkbox("Skip advisory review (faster)", value=False)
    use_cache = st.checkbox("Use current proposal cache", value=True)
    new_proposal = st.checkbox("Create a new proposal run", value=False)

if sget("stage") is None and use_cache:
    cf = load_json(rpath("json", "_final"))
    if cf:
        sset("final", cf)
        sset("review", load_json(rpath("json", "_review")))
        sset("draft", load_json(rpath("json", "_draft")))
        sset("stage", "final")
        ds = load_json(delivery_status_path())
        sset("email_sent", bool(ds and ds.get("sent")))
        sset("email_last_error", "" if sget("email_sent") else (ds or {}).get("error", ""))

# -----------------------------------------------------------------------------
# Header and pipeline
# -----------------------------------------------------------------------------
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown(f'<div class="pulse-header">{APP_ICON} {APP_NAME}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pulse-sub">{industry} · {function} · {maturity} · {datetime.now().strftime("%A, %B %d, %Y")}</div>', unsafe_allow_html=True)
with c2:
    st.markdown("<br>", unsafe_allow_html=True)
    run_btn = st.button("▶ Generate Proposal", use_container_width=True)
st.markdown("---")

STAGE_MAP = {None: ["pending", "pending", "pending", "pending"], "draft": ["active", "pending", "pending", "pending"], "review": ["done", "active", "pending", "pending"], "approved": ["done", "done", "active", "pending"], "final": ["done", "done", "done", "active"]}
states = STAGE_MAP.get(sget("stage"), STAGE_MAP[None])
st.markdown('<div class="pipeline">' + ''.join(f'<div class="stage {s}">{l}</div>' for s, l in zip(states, ["1 · Use Cases", "2 · Advisory Review", "3 · PDF Proposal", "4 · Delivery"])) + '</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Pipeline runner
# -----------------------------------------------------------------------------
def email_cfg() -> dict:
    return {"smtp_host": SMTP_HOST, "smtp_port": int(SMTP_PORT), "sender": SENDER_EMAIL, "password": SENDER_APP_PASSWORD, "recipient": RECIPIENT_EMAIL}


if run_btn:
    if new_proposal:
        sset("report_id", run_id())
        sset("draft", None)
        sset("review", None)
        sset("final", None)
        sset("email_sent", False)
        sset("email_last_error", "")
        sset("stage", None)
        use_cache = False
    if not OPENAI_API_KEY:
        st.error("Please set OPENAI_API_KEY in Streamlit secrets or environment variables.")
        st.stop()
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    with st.status("🧪 Stage 1 · Generating GenAI use case proposal...", expanded=True) as s1:
        try:
            draft_cache = rpath("json", "_draft")
            if use_cache and draft_cache.exists():
                draft = load_json(draft_cache)
                st.write("📂 Draft loaded from cache.")
            else:
                st.write(f"🧠 Generating top 10 GenAI use cases for {industry} / {function} / {maturity}...")
                draft = generate_proposal(client, model_choice, industry, function, maturity, context, geography, constraints)
                draft["industry"] = industry
                draft["function"] = function
                draft["maturity"] = maturity
                save_json(draft, draft_cache)
                st.write("✅ Draft proposal generated and saved.")
            sset("draft", draft)
            sset("stage", "draft")
        except Exception as e:
            st.error(f"Proposal generation failed: {e}")
            st.stop()
        s1.update(label="✅ Stage 1 · Proposal draft complete", state="complete")

    if skip_review:
        st.info("⏭️ Advisory review skipped. Draft will be used as-is.")
        sset("review", None)
        final_obj = dict(sget("draft"))
        save_json(final_obj, rpath("json", "_final"))
        sset("final", final_obj)
        sset("stage", "approved")
    else:
        with st.status("🔍 Stage 2 · Running advisory review...", expanded=True) as s2:
            try:
                review_cache = rpath("json", "_review")
                if use_cache and review_cache.exists():
                    review = load_json(review_cache)
                    st.write("📂 Review loaded from cache.")
                else:
                    st.write("🧐 Reviewing feasibility, value, risk controls and delivery practicality...")
                    review = review_proposal(client, model_choice, sget("draft"))
                    save_json(review, review_cache)
                    st.write("✅ Review complete.")
                sset("review", review)
                sset("stage", "review")
                final_obj = build_final(sget("draft"), review)
                save_json(final_obj, rpath("json", "_final"))
                sset("final", final_obj)
                sset("stage", "approved")
                st.write(f"✅ Final proposal assembled - Score: {review.get('overall_score','?')}/100 · {review.get('overall_verdict','')}")
            except Exception as e:
                st.error(f"Advisory review failed: {e}")
                st.stop()
            s2.update(label=f"✅ Stage 2 · Review complete - {review.get('overall_score','?')}/100", state="complete")

    pdf_out = str(pdf_path())
    with st.status("📄 Stage 3 · Generating professional PDF proposal...", expanded=True) as spdf:
        try:
            generate_pdf_proposal(sget("final"), pdf_out)
            st.write(f"✅ PDF proposal created - {Path(pdf_out).name}")
        except Exception as e:
            st.warning(f"PDF generation error: {e}")
        spdf.update(label="✅ Stage 3 · PDF proposal ready", state="complete")

    save_email_assets(sget("final"), str(email_html_path()), str(email_text_path()), pdf_attached=os.path.exists(pdf_out))

    if email_configured_now and auto_email_enabled:
        with st.status("📧 Stage 4 · Sending email delivery...", expanded=True) as s4:
            try:
                result = send_email(email_cfg(), sget("final"), pdf_out if os.path.exists(pdf_out) else None)
                sset("email_sent", True)
                sset("email_last_error", "")
                st.write(f"✅ Mailed to {RECIPIENT_EMAIL}. PDF attached: {result['pdf_attached']}.")
                s4.update(label="✅ Stage 4 · Delivered", state="complete")
            except Exception as e:
                sset("email_sent", False)
                sset("email_last_error", str(e))
                mark_email_failure(e)
                st.warning(f"Email error: {e}")
                s4.update(label="⚠️ Stage 4 · Email failed", state="error")
    elif not email_configured_now:
        st.info("📧 Email skipped - set SMTP/email secrets or environment variables.")
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
        score = review.get("overall_score", 0)
        verdict = review.get("overall_verdict", "")
        note = review.get("advisory_summary", "")
        st.markdown(f'<div class="approved-banner">✅ ADVISORY REVIEWED · <span class="score-badge {score_cls(score)}">{score}/100</span> · {safe_html(verdict)}<br><span style="color:#a7f3d0;font-size:0.83rem;">{safe_html(note)}</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="approved-banner" style="background:linear-gradient(135deg,#1a1208,#2d1f00);border-color:#f59e0b;color:#fcd34d;">📋 Proposal ready · Advisory review was skipped.</div>', unsafe_allow_html=True)

    use_cases = final.get("top_10_use_cases", []) or []
    cols = st.columns(5)
    metrics = [
        ("Industry", final.get("industry", industry)),
        ("Function", final.get("function", function)),
        ("Maturity", final.get("maturity", maturity)),
        ("Use Cases", len(use_cases)),
        ("Run ID", active_report_id()),
    ]
    for col, (label, value) in zip(cols, metrics):
        with col:
            st.markdown(f'<div class="metric-box"><div class="metric-val" style="font-size:1.0rem;">{safe_html(value)}</div><div class="metric-label">{safe_html(label)}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    t_proposal, t_details, t_review, t_delivery, t_email_copy = st.tabs(["📋 Proposal", "🧩 Use Case Details", "🔍 Advisory Review", "📄 PDF & Delivery", "✉️ Email Copy"])

    with t_proposal:
        st.markdown(f'<div class="section-card"><div class="section-title">🔭 Executive Summary</div><div class="report-body">{safe_html(final.get("executive_summary", ""))}</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-card" style="border-left-color:#7c3aed;"><div class="section-title" style="color:#a78bfa;">💼 Business Value Summary</div><div class="report-body">{safe_html(final.get("business_value_summary", ""))}</div></div>', unsafe_allow_html=True)
        if use_cases:
            st.markdown("### 🧭 Top 10 GenAI Use Cases")
            for item in use_cases:
                if isinstance(item, dict):
                    rank = textify(item.get("rank", ""))
                    st.markdown(f'<div class="usecase-card"><div class="small-muted">Rank {safe_html(rank)} · Complexity: {safe_html(item.get("complexity", "TBD"))} · Time to value: {safe_html(item.get("time_to_value", "TBD"))}</div><div class="usecase-title">{safe_html(item.get("title", ""))}</div><div class="report-body" style="font-size:0.86rem;line-height:1.6;">{safe_html(item.get("business_value", ""))}</div></div>', unsafe_allow_html=True)
        for heading, key in [
            ("Required Data", "required_data"),
            ("Architecture Pattern", "architecture_pattern"),
            ("Risks and Controls", "risks_and_controls"),
            ("MVP Roadmap", "mvp_roadmap"),
            ("KPIs", "kpis"),
            ("Recommended Next Steps", "recommended_next_steps"),
        ]:
            if final.get(key):
                st.markdown(f'<div class="section-card"><div class="section-title">{safe_html(heading)}</div><div class="report-body">{safe_html(final.get(key))}</div></div>', unsafe_allow_html=True)

        txt_parts = [
            f"{APP_NAME.upper()} - {today_str()}",
            "=" * 72,
            CREATOR_FOOTNOTE,
            "PROPOSAL TITLE",
            textify(final.get("proposal_title", "")),
            "EXECUTIVE SUMMARY",
            textify(final.get("executive_summary", "")),
            "TOP 10 USE CASES",
            textify(use_cases),
            "BUSINESS VALUE",
            textify(final.get("business_value_summary", "")),
            "REQUIRED DATA",
            textify(final.get("required_data", "")),
            "ARCHITECTURE PATTERN",
            textify(final.get("architecture_pattern", "")),
            "RISKS AND CONTROLS",
            textify(final.get("risks_and_controls", "")),
            "MVP ROADMAP",
            textify(final.get("mvp_roadmap", "")),
            "KPIs",
            textify(final.get("kpis", "")),
            "RECOMMENDED NEXT STEPS",
            textify(final.get("recommended_next_steps", "")),
        ]
        txt = "\n\n".join(textify(part) for part in txt_parts)
        st.download_button("⬇️ Download Proposal (TXT)", data=txt, file_name=f"{FILE_PREFIX}_{active_report_id()}_proposal.txt", mime="text/plain")

    with t_details:
        if not use_cases:
            st.info("No use cases available yet.")
        for item in use_cases:
            if isinstance(item, dict):
                with st.expander(f"{item.get('rank', '')}. {item.get('title', '')}", expanded=False):
                    st.markdown("**Problem solved**")
                    st.write(item.get("problem_solved", ""))
                    st.markdown("**GenAI solution**")
                    st.write(item.get("genai_solution", ""))
                    st.markdown("**Business value**")
                    st.write(item.get("business_value", ""))
                    st.markdown("**Required data**")
                    st.write(item.get("required_data", ""))
                    st.markdown("**Architecture pattern**")
                    st.write(item.get("architecture_pattern", ""))
                    st.markdown("**Risks and controls**")
                    st.write("Risks:", item.get("risks", ""))
                    st.write("Controls:", item.get("controls", ""))
                    st.markdown("**MVP scope and KPIs**")
                    st.write("MVP scope:", item.get("mvp_scope", ""))
                    st.write("KPIs:", item.get("kpis", ""))

    with t_review:
        if not review:
            st.info("Advisory review was skipped for this run.")
        else:
            st.markdown(f'<div class="metric-box" style="padding:1.5rem;max-width:260px;"><div class="metric-val" style="font-size:2.6rem;">{review.get("overall_score", 0)}</div><div class="metric-label">Overall / 100</div><br><span class="score-badge {score_cls(review.get("overall_score", 0))}">{safe_html(review.get("overall_verdict", ""))}</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="section-card"><div class="report-body" style="font-size:0.9rem;">{safe_html(review.get("advisory_summary", ""))}</div></div>', unsafe_allow_html=True)
            for sec_key, sec_rev in (review.get("reviews", {}) or {}).items():
                if isinstance(sec_rev, dict):
                    with st.expander(f"{sec_key} - {sec_rev.get('score', 0)}/100", expanded=False):
                        st.write("Issues:", sec_rev.get("issues", []))
                        st.write("Suggestions:", sec_rev.get("suggestions", []))

    with t_delivery:
        st.markdown("### 📄 PDF Proposal")
        pdf_file = pdf_path()
        if pdf_file.exists():
            pdf_bytes = pdf_file.read_bytes()
            st.success(f"✅ PDF proposal ready: {pdf_file.name}")
            st.download_button("⬇️ Download PDF Proposal", data=pdf_bytes, file_name=f"{FILE_PREFIX}_{active_report_id()}_proposal.pdf", mime="application/pdf")
        else:
            st.info("📄 PDF proposal not yet generated. Click Generate Proposal to create it.")
        st.markdown("---")
        st.markdown("### 📧 Email Delivery")
        ds = load_json(delivery_status_path()) or {}
        if sget("email_sent") or ds.get("sent"):
            st.success(f"✅ Last delivery mailed to **{ds.get('recipient', RECIPIENT_EMAIL)}** at {ds.get('sent_at', 'unknown time')}")
            st.caption(f"PDF attached: {ds.get('pdf_attached')} · Attachment MB: {ds.get('attachment_mb_before_base64')}")
        elif sget("email_last_error") or ds.get("error"):
            st.warning(f"Last email attempt failed: {sget('email_last_error') or ds.get('error')}")
        elif not email_configured_now:
            st.markdown('<div class="section-card" style="border-left-color:#f59e0b;"><strong>Email not configured.</strong><br>Set SMTP_HOST, SMTP_PORT, SENDER_EMAIL, SENDER_APP_PASSWORD and RECIPIENT_EMAIL in Streamlit secrets or environment variables.</div>', unsafe_allow_html=True)
        else:
            st.info("No delivery has been recorded for this run yet.")

        manual_disabled = not (email_configured_now and final and pdf_file.exists())
        if st.button("📧 Send Email Now", use_container_width=True, disabled=manual_disabled):
            try:
                result = send_email(email_cfg(), final, str(pdf_file) if pdf_file.exists() else None)
                sset("email_sent", True)
                sset("email_last_error", "")
                st.success(f"Email sent to {RECIPIENT_EMAIL}. PDF attached: {result['pdf_attached']}.")
            except Exception as e:
                sset("email_sent", False)
                sset("email_last_error", str(e))
                mark_email_failure(e)
                st.error(f"Manual email failed: {e}")

    with t_email_copy:
        st.markdown("### ✉️ Professional Email Copy")
        html_file = email_html_path()
        text_file = email_text_path()
        if not html_file.exists() or not text_file.exists():
            try:
                save_email_assets(final, str(html_file), str(text_file), pdf_attached=pdf_path().exists())
            except Exception as e:
                st.warning(f"Could not prepare email copy: {e}")
        st.markdown("**Subject line**")
        st.code(email_subject(final), language="text")
        if text_file.exists():
            st.text_area("Plain-text email", text_file.read_text(encoding="utf-8"), height=360, label_visibility="collapsed")
        c_html, c_txt = st.columns(2)
        if html_file.exists():
            with c_html:
                st.download_button("⬇️ Download Branded Email HTML", data=html_file.read_bytes(), file_name=f"{FILE_PREFIX}_{active_report_id()}_email_brief.html", mime="text/html", use_container_width=True)
        if text_file.exists():
            with c_txt:
                st.download_button("⬇️ Download Plain-Text Email", data=text_file.read_bytes(), file_name=f"{FILE_PREFIX}_{active_report_id()}_email_brief.txt", mime="text/plain", use_container_width=True)
        if html_file.exists():
            st.components.v1.html(html_file.read_text(encoding="utf-8"), height=780, scrolling=True)
else:
    st.markdown(f"""
    <div style="text-align:center;padding:4rem 2rem;"><div style="font-size:4.5rem;">{APP_ICON}</div><div style="font-family:'Syne',sans-serif;font-size:1.5rem;color:#64748b;margin-top:1rem;">Select industry, function and maturity, then click <strong style="color:#00d4ff;">▶ Generate Proposal</strong></div><div style="font-family:'Space Mono',monospace;font-size:0.7rem;color:#1e3a5f;margin-top:1.2rem;letter-spacing:0.15em;">USE CASES → ADVISORY REVIEW → PDF PROPOSAL → EMAIL</div></div>
    """, unsafe_allow_html=True)
