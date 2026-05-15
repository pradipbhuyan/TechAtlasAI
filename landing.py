import html
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import streamlit as st
from app_registry import APP_REGISTRY

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

APP_NAME = "TechAtlas AI"
APP_TAGLINE = "Executive Technology Knowledge Hub"
SESSION_TIMEOUT_MINUTES = 15

THEMES: Dict[str, Dict[str, str]] = {
    "Dark Neon Command Center": {"bg":"#070B16","surface":"#111827","surface2":"#0F172A","border":"#1E2D45","text":"#E2E8F0","muted":"#94A3B8","accent":"#00D4FF","accent2":"#7C3AED","success":"#10B981","warning":"#F59E0B","danger":"#EF4444"},
    "NTT Enterprise Blue": {"bg":"#F6F8FB","surface":"#FFFFFF","surface2":"#F1F5F9","border":"#DDE5F0","text":"#172033","muted":"#64748B","accent":"#005BAC","accent2":"#00A3E0","success":"#16A34A","warning":"#F59E0B","danger":"#DC2626"},
    "Midnight Blue Executive": {"bg":"#08111F","surface":"#0F1B2D","surface2":"#111E33","border":"#24344D","text":"#F8FAFC","muted":"#94A3B8","accent":"#38BDF8","accent2":"#818CF8","success":"#34D399","warning":"#FBBF24","danger":"#F87171"},
    "Purple AI Studio": {"bg":"#120A24","surface":"#1E1238","surface2":"#27164A","border":"#3B2366","text":"#F5F3FF","muted":"#C4B5FD","accent":"#A855F7","accent2":"#EC4899","success":"#22C55E","warning":"#F59E0B","danger":"#FB7185"},
    "White Glass Enterprise": {"bg":"#F8FAFC","surface":"#FFFFFF","surface2":"#F1F5F9","border":"#E2E8F0","text":"#0F172A","muted":"#64748B","accent":"#2563EB","accent2":"#7C3AED","success":"#059669","warning":"#D97706","danger":"#DC2626"},
    "Graphite Electric Green": {"bg":"#09090B","surface":"#18181B","surface2":"#111113","border":"#27272A","text":"#FAFAFA","muted":"#A1A1AA","accent":"#22C55E","accent2":"#84CC16","success":"#10B981","warning":"#EAB308","danger":"#EF4444"},
    "Ocean Data Theme": {"bg":"#061A1F","surface":"#0B2A33","surface2":"#092229","border":"#164E63","text":"#ECFEFF","muted":"#67E8F9","accent":"#06B6D4","accent2":"#14B8A6","success":"#2DD4BF","warning":"#FACC15","danger":"#FB7185"},
    "Amber Strategy Room": {"bg":"#17120A","surface":"#241A0E","surface2":"#1C140A","border":"#4A3410","text":"#FFF7ED","muted":"#FDBA74","accent":"#F59E0B","accent2":"#F97316","success":"#84CC16","warning":"#FBBF24","danger":"#F87171"},
    "Minimal Monochrome": {"bg":"#F5F5F4","surface":"#FFFFFF","surface2":"#FAFAF9","border":"#D6D3D1","text":"#1C1917","muted":"#78716C","accent":"#1F2937","accent2":"#525252","success":"#15803D","warning":"#B45309","danger":"#B91C1C"},
    "Aurora Gradient": {"bg":"#050816","surface":"#111827","surface2":"#0B1220","border":"#2E3658","text":"#F8FAFC","muted":"#94A3B8","accent":"#22D3EE","accent2":"#C084FC","success":"#34D399","warning":"#FBBF24","danger":"#F472B6"},
}

# Update these numbers if your OpenAI pricing changes. They are estimates used for the session sidebar only.
MODEL_PRICING_PER_1M = {
    "gpt-5.5": {"input": 5.00, "cached_input": 0.50, "output": 30.00},
    "gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    "gpt-4.1": {"input": 2.00, "cached_input": 0.50, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "cached_input": 0.10, "output": 1.60},
    "gpt-4o": {"input": 2.50, "cached_input": 1.25, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "cached_input": 0.075, "output": 0.60},
}
MODEL_OPTIONS = list(MODEL_PRICING_PER_1M.keys())


def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.getenv(name, default)


def init_state() -> None:
    defaults = {
        "authenticated": False,
        "login_user": "",
        "login_time": None,
        "theme_name": "Midnight Blue Executive",
        "model_name": "gpt-5-mini",
        "session_input_tokens": 0,
        "session_cached_input_tokens": 0,
        "session_output_tokens": 0,
        "session_cost_usd": 0.0,
        "last_ai_result": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def css(theme: Dict[str, str], hide_sidebar: bool = False) -> str:
    hide = """
[data-testid="stSidebar"] { display:none!important; }
[data-testid="collapsedControl"] { display:none!important; }
section[data-testid="stSidebar"] { display:none!important; }
""" if hide_sidebar else ""
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');
:root {{
    --bg:{theme['bg']}; --surface:{theme['surface']}; --surface2:{theme['surface2']}; --border:{theme['border']};
    --text:{theme['text']}; --muted:{theme['muted']}; --accent:{theme['accent']}; --accent2:{theme['accent2']};
    --success:{theme['success']}; --warning:{theme['warning']}; --danger:{theme['danger']};
}}
html, body, [data-testid="stAppViewContainer"] {{ background:var(--bg)!important; color:var(--text)!important; font-family:'Syne',sans-serif; }}
[data-testid="stSidebar"] {{ background:var(--surface)!important; border-right:1px solid var(--border)!important; }}
[data-testid="stHeader"] {{ background:rgba(0,0,0,0)!important; }}
.stTextInput input, .stSelectbox div[data-baseweb="select"] {{ background:var(--surface2)!important; color:var(--text)!important; border-color:var(--border)!important; }}
.stButton>button {{ background:linear-gradient(135deg,var(--accent),var(--accent2))!important; color:white!important; border:none!important; border-radius:10px!important; font-weight:800!important; }}
.login-wrap {{ max-width:480px; margin:9vh auto 0 auto; background:linear-gradient(145deg,var(--surface),var(--surface2)); border:1px solid var(--border); border-radius:24px; padding:34px; box-shadow:0 24px 80px rgba(0,0,0,.24); }}
.brand {{ font-weight:800; font-size:2.8rem; line-height:1.05; background:linear-gradient(90deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
.sub {{ font-family:'Space Mono',monospace; font-size:.76rem; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); }}
.hero {{ padding:22px 26px; border:1px solid var(--border); background:linear-gradient(135deg,var(--surface),var(--surface2)); border-radius:22px; margin-bottom:18px; }}
.hero-title {{ font-weight:800; font-size:1.75rem; color:var(--text); }}
.hero-sub {{ color:var(--muted); font-size:.96rem; margin-top:6px; line-height:1.5; }}
.metrics {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin:16px 0; }}
.metric {{ background:var(--surface); border:1px solid var(--border); border-radius:16px; padding:18px; }}
.metric-value {{ font-family:'Space Mono',monospace; color:var(--accent); font-size:1.7rem; font-weight:800; }}
.metric-label {{ color:var(--muted); font-size:.68rem; text-transform:uppercase; letter-spacing:.13em; }}
.view-tabs {{ display:flex; gap:10px; border:1px solid var(--border); background:var(--surface); padding:10px; border-radius:16px; margin:18px 0 10px; }}
.tab-pill {{ padding:8px 12px; border-radius:10px; font-family:'Space Mono',monospace; font-size:.72rem; color:var(--muted); border:1px solid transparent; }}
.tab-pill.active {{ color:white; background:linear-gradient(135deg,var(--accent),var(--accent2)); }}
 .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:22px; margin-top:18px; }}
.tile-wrap {{ display:flex; flex-direction:column; gap:10px; height:100%; }}
.tile {{ min-height:265px; height:265px; background:linear-gradient(145deg,var(--surface),var(--surface2)); border:1px solid var(--border); border-radius:18px; padding:22px 22px 18px 22px; overflow:hidden; display:flex; flex-direction:column; box-sizing:border-box; transition:.18s ease; }}
.tile:hover {{ transform:translateY(-4px); box-shadow:0 18px 40px rgba(0,0,0,.22); border-color:var(--accent); }}
.tile.disabled {{ opacity:.48; filter:grayscale(.75); }}
.symbol {{ font-family:'Space Mono',monospace; font-weight:800; font-size:3rem; line-height:1; margin-bottom:18px; letter-spacing:-.06em; }}
.app-name {{ color:var(--text); font-weight:800; font-size:1.05rem; line-height:1.25; margin-bottom:14px; min-height:28px; }}
.app-desc {{ color:var(--muted); font-size:.88rem; line-height:1.5; margin-bottom:12px; min-height:68px; }}
.category {{ font-family:'Space Mono',monospace; font-size:.74rem; line-height:1.2; margin-bottom:auto; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.meta-row {{ display:flex; align-items:center; justify-content:space-between; gap:10px; margin-top:16px; }}
.status {{ display:inline-flex; align-items:center; justify-content:center; font-family:'Space Mono',monospace; font-size:.62rem; line-height:1; text-transform:uppercase; letter-spacing:.06em; border-radius:999px; padding:7px 10px; white-space:nowrap; border:1px solid var(--border); }}
.status.active {{ color:#34d399; background:rgba(16,185,129,.16); border-color:rgba(16,185,129,.55); }}
.status.beta {{ color:#fbbf24; background:rgba(245,158,11,.16); border-color:rgba(245,158,11,.55); }}
.status.disabled {{ color:var(--muted); background:rgba(100,116,139,.16); border-color:rgba(100,116,139,.55); }}
.cadence-pill {{ display:inline-flex; align-items:center; justify-content:center; font-family:'Space Mono',monospace; font-size:.62rem; line-height:1; text-transform:uppercase; letter-spacing:.06em; border-radius:999px; padding:7px 10px; white-space:nowrap; color:#cbd5e1; background:rgba(100,116,139,.12); border:1px solid rgba(100,116,139,.35); }}
.launch {{ text-decoration:none!important; font-family:'Space Mono',monospace; font-size:.65rem; color:white!important; padding:7px 10px; border-radius:9px; background:linear-gradient(135deg,var(--accent),var(--accent2)); }}
.launch.off {{ background:var(--surface2); color:var(--muted)!important; border:1px solid var(--border); }}
div[data-testid="stPageLink"] {{ margin-top:0!important; }}
div[data-testid="stPageLink"] a {{
    min-height:48px;
    width:100%;
    background:linear-gradient(135deg,var(--accent),var(--accent2))!important;
    color:white!important;
    border-radius:12px!important;
    font-family:'Space Mono',monospace!important;
    font-size:.78rem!important;
    font-weight:800!important;
    text-transform:uppercase!important;
    letter-spacing:.06em!important;
    text-align:center!important;
    border:none!important;
    text-decoration:none!important;
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
}}
div[data-testid="stPageLink"] a:hover {{ opacity:.88; transform:translateY(-1px); }}
.config-note {{ border:1px solid var(--border); background:var(--surface2); border-radius:14px; padding:14px; color:var(--muted); font-size:.82rem; line-height:1.45; }}
.cost-box {{ border:1px solid var(--border); background:var(--surface2); border-radius:14px; padding:12px; margin-top:10px; }}
.cost-line {{ display:flex; justify-content:space-between; gap:10px; color:var(--muted); font-family:'Space Mono',monospace; font-size:.68rem; margin:5px 0; }}
{hide}
</style>
"""


def get_credentials() -> Dict[str, str]:
    creds = {}
    pradip_pwd = get_secret("PRADIP_PASSWORD")
    admin_pwd = get_secret("ADMIN_PASSWORD")
    if pradip_pwd:
        creds["pradip"] = pradip_pwd
    if admin_pwd:
        creds["admin"] = admin_pwd
    return creds


def logout() -> None:
    st.session_state.authenticated = False
    st.session_state.login_user = ""
    st.session_state.login_time = None


def is_session_valid() -> bool:
    """Return True only when the login is active and inside the timeout window."""
    if not st.session_state.get("authenticated", False):
        return False
    login_time = st.session_state.get("login_time")
    if not isinstance(login_time, datetime):
        logout()
        return False
    if datetime.now() > login_time + timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        logout()
        return False
    return True


def minutes_remaining() -> int:
    login_time = st.session_state.get("login_time")
    if not isinstance(login_time, datetime):
        return 0
    expires_at = login_time + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    remaining = expires_at - datetime.now()
    return max(0, int(remaining.total_seconds() // 60))


def require_login() -> None:
    if is_session_valid():
        return
    theme = THEMES.get(st.session_state.theme_name, THEMES["Midnight Blue Executive"])
    st.markdown(css(theme, hide_sidebar=True), unsafe_allow_html=True)
    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="brand">TechAtlas AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub">Secure Executive Technology Knowledge Hub</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Sign in")
    user_id = st.text_input("User ID", placeholder="Enter user ID", autocomplete="off")
    password = st.text_input("Password", type="password", placeholder="Enter password")
    login = st.button("Login", use_container_width=True)
    creds = get_credentials()
    if not creds:
        st.warning("Set PRADIP_PASSWORD or ADMIN_PASSWORD in Streamlit secrets or environment variables before login.")
    if login:
        normalized = user_id.strip().lower()
        if normalized in creds and password == creds[normalized]:
            st.session_state.authenticated = True
            st.session_state.login_user = normalized
            st.session_state.login_time = datetime.now()
            st.rerun()
        else:
            logout()
            st.error("Invalid user ID or password.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


def cost_for_usage(model: str, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0) -> float:
    pricing = MODEL_PRICING_PER_1M.get(model, MODEL_PRICING_PER_1M["gpt-5-mini"])
    non_cached = max(input_tokens - cached_input_tokens, 0)
    return ((non_cached * pricing["input"]) + (cached_input_tokens * pricing["cached_input"]) + (output_tokens * pricing["output"])) / 1_000_000


def add_usage(model: str, usage) -> None:
    input_tokens = int(getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0) or 0)
    cached_tokens = 0
    try:
        details = getattr(usage, "input_tokens_details", None)
        cached_tokens = int(getattr(details, "cached_tokens", 0) or 0)
    except Exception:
        cached_tokens = 0
    st.session_state.session_input_tokens += input_tokens
    st.session_state.session_cached_input_tokens += cached_tokens
    st.session_state.session_output_tokens += output_tokens
    st.session_state.session_cost_usd += cost_for_usage(model, input_tokens, output_tokens, cached_tokens)


def status_class(status: str) -> str:
    status = str(status).lower()
    return status if status in {"active", "beta", "disabled"} else "disabled"


def app_page_path(app: Dict[str, str]) -> str:
    """Return a Streamlit-native page path for st.page_link.

    app_registry.py may use either:
    - "page": "TelecomPulse_AI"
    - "page": "pages/TelecomPulse_AI.py"
    """
    page = str(app.get("page", "")).strip()
    if not page:
        return ""
    if page.startswith("pages/") and page.endswith(".py"):
        return page
    if page.endswith(".py"):
        return f"pages/{page}"
    return f"pages/{page}.py"


def e(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def render_tile_card(app: Dict[str, str]) -> None:
    """Render a fixed-height aligned tile and use st.page_link for Streamlit-native navigation.

    Do not use raw <a href=...> links for app navigation. Raw links can trigger a browser-level
    reload and make the landing page ask for login again. st.page_link keeps navigation aligned
    with Streamlit's multipage router, the same way the sidebar works.
    """
    status = str(app.get("status", "disabled")).lower().strip()
    disabled = status == "disabled"
    accent = e(app.get("accent", "#38BDF8"))
    cls = "tile disabled" if disabled else "tile"
    status_cls = status_class(status)

    st.markdown(
        f'<div class="tile-wrap">'
        f'<div class="{cls}" style="border-top:5px solid {accent};">'
        f'<div class="symbol" style="color:{accent};">{e(app.get("symbol", "??"))}</div>'
        f'<div class="app-name">{e(app.get("name", "Unnamed App"))}</div>'
        f'<div class="app-desc">{e(app.get("description", ""))}</div>'
        f'<div class="category" style="color:{accent};">{e(app.get("category", "Other"))}</div>'
        f'<div class="meta-row">'
        f'<span class="status {status_cls}">{e(status)}</span>'
        f'<span class="cadence-pill">{e(app.get("cadence", ""))}</span>'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if disabled:
        st.button("Unavailable", disabled=True, use_container_width=True, key=f"disabled_{app.get('symbol','app')}_{app.get('name','app')}")
    else:
        page = app_page_path(app)
        if page:
            st.page_link(page, label=f"Launch {app.get('name', 'App')}", icon="🚀", use_container_width=True)
        else:
            st.button("Page missing", disabled=True, use_container_width=True, key=f"missing_{app.get('symbol','app')}_{app.get('name','app')}")

def filtered_apps(query: str, category: str, status_filter: str, show_disabled: bool) -> List[Dict[str, str]]:
    out = []
    for app in APP_REGISTRY:
        status = str(app.get("status", "disabled")).lower()
        if not show_disabled and status == "disabled":
            continue
        if category != "All" and app.get("category") != category:
            continue
        if status_filter != "All" and status != status_filter.lower():
            continue
        haystack = " ".join(str(app.get(k, "")) for k in ["symbol", "name", "description", "category", "cadence", "status"]).lower()
        if query and query.lower() not in haystack:
            continue
        out.append(app)
    return out


def _safe_index(options: list[str], value: str, default: int = 0) -> int:
    """Return a safe selectbox index even when session_state has an old/invalid value."""
    try:
        return options.index(value)
    except ValueError:
        return default


def sidebar() -> Tuple[str, str, str, bool, bool]:
    st.sidebar.markdown("### TechAtlas Controls")
    st.sidebar.markdown("### Session")
    st.sidebar.caption(f"Logged in as: {e(st.session_state.get('login_user', ''))}")
    st.sidebar.caption(f"Session expires in about {minutes_remaining()} minute(s).")
    st.sidebar.markdown("---")
    theme_names = list(THEMES.keys())

    if st.session_state.theme_name not in theme_names:
        st.session_state.theme_name = theme_names[0]
    if st.session_state.model_name not in MODEL_OPTIONS:
        st.session_state.model_name = MODEL_OPTIONS[0]

    st.session_state.theme_name = st.sidebar.selectbox(
        "Colour theme",
        theme_names,
        index=_safe_index(theme_names, st.session_state.theme_name),
    )
    st.session_state.model_name = st.sidebar.selectbox(
        "Model",
        MODEL_OPTIONS,
        index=_safe_index(MODEL_OPTIONS, st.session_state.model_name),
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Session token cost")
    pricing = MODEL_PRICING_PER_1M.get(st.session_state.model_name, MODEL_PRICING_PER_1M[MODEL_OPTIONS[0]])
    st.sidebar.markdown(f"""
<div class="cost-box">
  <div class="cost-line"><span>User</span><strong>{e(st.session_state.login_user)}</strong></div>
  <div class="cost-line"><span>Model</span><strong>{e(st.session_state.model_name)}</strong></div>
  <div class="cost-line"><span>Input</span><strong>{st.session_state.session_input_tokens:,}</strong></div>
  <div class="cost-line"><span>Cached</span><strong>{st.session_state.session_cached_input_tokens:,}</strong></div>
  <div class="cost-line"><span>Output</span><strong>{st.session_state.session_output_tokens:,}</strong></div>
  <div class="cost-line"><span>Est. cost</span><strong>${st.session_state.session_cost_usd:.6f}</strong></div>
</div>
""", unsafe_allow_html=True)
    st.sidebar.caption(f"Rates / 1M tokens: input ${pricing['input']}, cached ${pricing['cached_input']}, output ${pricing['output']}.")
    if st.sidebar.button("Reset session cost", use_container_width=True):
        st.session_state.session_input_tokens = 0
        st.session_state.session_cached_input_tokens = 0
        st.session_state.session_output_tokens = 0
        st.session_state.session_cost_usd = 0.0
        st.rerun()
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Filter apps")
    query = st.sidebar.text_input("Search apps", placeholder="AI, cloud, cyber, data...")
    category = st.sidebar.selectbox("Category", ["All"] + sorted({a.get("category", "Other") for a in APP_REGISTRY}))
    status_filter = st.sidebar.selectbox("Status", ["All", "active", "beta", "disabled"])
    show_disabled = st.sidebar.toggle("Show disabled apps", value=True)
    group_by_category = st.sidebar.toggle("Group by category", value=False)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Configure apps")
    st.sidebar.markdown('<div class="config-note">Add, remove, rename or disable apps in <code>app_registry.py</code>. Keep app pages under the <code>pages/</code> folder.</div>', unsafe_allow_html=True)
    if st.sidebar.button("Logout", use_container_width=True):
        logout()
        st.rerun()
    return query, category, status_filter, show_disabled, group_by_category


def ask_selected_model(prompt: str) -> str:
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        return "Set OPENAI_API_KEY in Streamlit secrets or environment variables to enable the model test."
    if OpenAI is None:
        return "Install the openai package: pip install openai"
    client = OpenAI(api_key=api_key)
    response = client.responses.create(model=st.session_state.model_name, input=prompt)
    if getattr(response, "usage", None):
        add_usage(st.session_state.model_name, response.usage)
    return getattr(response, "output_text", "") or "No text returned."


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="🧭", layout="wide", initial_sidebar_state="collapsed")
    init_state()
    require_login()
    theme = THEMES.get(st.session_state.theme_name, THEMES["Midnight Blue Executive"])
    st.markdown(css(theme), unsafe_allow_html=True)
    query, category, status_filter, show_disabled, group_by_category = sidebar()

    apps = filtered_apps(query, category, status_filter, show_disabled)
    active = sum(1 for a in APP_REGISTRY if a.get("status") == "active")
    beta = sum(1 for a in APP_REGISTRY if a.get("status") == "beta")
    disabled = sum(1 for a in APP_REGISTRY if a.get("status") == "disabled")

    st.markdown(f"""
<div class="hero">
  <div class="hero-title">Welcome, {e(st.session_state.login_user).title()}!</div>
  <div class="hero-sub">One landing page for your technology intelligence apps. Curated, reviewed and delivered across daily, weekly and on-demand workflows.</div>
</div>
<div class="metrics">
  <div class="metric"><div class="metric-value">{len(APP_REGISTRY)}</div><div class="metric-label">Total Apps</div></div>
  <div class="metric"><div class="metric-value">{active}</div><div class="metric-label">Active</div></div>
  <div class="metric"><div class="metric-value">{beta}</div><div class="metric-label">Beta</div></div>
  <div class="metric"><div class="metric-value">{disabled}</div><div class="metric-label">Disabled</div></div>
</div>
<div class="view-tabs"><span class="tab-pill active">Periodic Table View</span><span class="tab-pill">Category View</span><span class="tab-pill">Radar View</span><span class="tab-pill">Mission Control</span></div>
""", unsafe_allow_html=True)

    st.caption(f"Showing {len(apps)} of {len(APP_REGISTRY)} configured apps · Theme: {st.session_state.theme_name} · Model: {st.session_state.model_name}")

    if group_by_category:
        for cat in sorted({a.get("category", "Other") for a in apps}):
            st.markdown(f"#### {e(cat)}")
            cat_apps = [a for a in apps if a.get("category") == cat]
            cols_per_row = 4
            for row_start in range(0, len(cat_apps), cols_per_row):
                cols = st.columns(cols_per_row, gap="large")
                for col, app in zip(cols, cat_apps[row_start:row_start + cols_per_row]):
                    with col:
                        render_tile_card(app)
    else:
        cols_per_row = 4
        for row_start in range(0, len(apps), cols_per_row):
            cols = st.columns(cols_per_row, gap="large")
            for col, app in zip(cols, apps[row_start:row_start + cols_per_row]):
                with col:
                    render_tile_card(app)

    st.markdown("---")
    with st.expander("Optional: test selected GPT model and token-cost tracking"):
        prompt = st.text_area("Prompt", value="Give me a 5-bullet executive summary of today's top technology priorities.", height=110)
        if st.button("Run model test"):
            with st.spinner("Calling selected model..."):
                st.session_state.last_ai_result = ask_selected_model(prompt)
            st.rerun()
        if st.session_state.last_ai_result:
            st.write(st.session_state.last_ai_result)


if __name__ == "__main__":
    main()
