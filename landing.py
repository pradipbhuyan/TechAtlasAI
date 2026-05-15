import os
from datetime import datetime
from typing import Dict, List

import streamlit as st
from app_registry import APP_REGISTRY

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

APP_NAME = "TechAtlas AI"
APP_TAGLINE = "Executive Technology Knowledge Hub"
DEFAULT_USER_ID = "pradip"

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

MODEL_PRICING_PER_1M = {
    # Update as needed from https://openai.com/api/pricing/
    "gpt-5.5": {"input": 5.00, "cached_input": 0.50, "output": 30.00},
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.75, "cached_input": 0.075, "output": 4.50},
    # Legacy/placeholder options: update these values if your account uses different GPT-4 SKUs.
    "gpt-4.1": {"input": 2.00, "cached_input": 0.50, "output": 8.00},
    "gpt-4o": {"input": 2.50, "cached_input": 1.25, "output": 10.00},
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
        "theme_name": "Dark Neon Command Center",
        "model_name": "gpt-5.4-mini",
        "session_input_tokens": 0,
        "session_cached_input_tokens": 0,
        "session_output_tokens": 0,
        "session_cost_usd": 0.0,
        "favorite_apps": [],
        "last_ai_result": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def cost_for_usage(model: str, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0) -> float:
    pricing = MODEL_PRICING_PER_1M.get(model, MODEL_PRICING_PER_1M["gpt-5.4-mini"])
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


def css(theme: Dict[str, str]) -> str:
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
.stTextInput input, .stSelectbox div[data-baseweb="select"], .stMultiSelect div[data-baseweb="select"] {{ background:var(--surface2)!important; color:var(--text)!important; border-color:var(--border)!important; }}
.stButton>button {{ background:linear-gradient(135deg,var(--accent),var(--accent2))!important; color:white!important; border:none!important; border-radius:10px!important; font-weight:800!important; }}
.login-wrap {{ max-width:460px; margin:8vh auto 0 auto; background:linear-gradient(145deg,var(--surface),var(--surface2)); border:1px solid var(--border); border-radius:24px; padding:34px; box-shadow:0 24px 80px rgba(0,0,0,.24); }}
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
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(205px,1fr)); gap:16px; }}
.tile {{ position:relative; min-height:220px; background:linear-gradient(145deg,var(--surface),var(--surface2)); border:1px solid var(--border); border-radius:18px; padding:18px; overflow:hidden; transition:.18s ease; }}
.tile:hover {{ transform:translateY(-4px); box-shadow:0 18px 40px rgba(0,0,0,.22); border-color:var(--accent); }}
.tile.disabled {{ opacity:.43; filter:grayscale(.85); }}
.symbol {{ font-family:'Space Mono',monospace; font-weight:800; font-size:2.55rem; line-height:1; }}
.app-name {{ color:var(--text); font-weight:800; font-size:1.05rem; margin-top:12px; }}
.app-desc {{ color:var(--muted); font-size:.8rem; line-height:1.45; margin-top:8px; }}
.category {{ font-family:'Space Mono',monospace; font-size:.68rem; margin-top:10px; }}
.meta-row {{ position:absolute; left:18px; right:18px; bottom:16px; display:flex; align-items:center; justify-content:space-between; gap:8px; }}
.status {{ font-family:'Space Mono',monospace; font-size:.58rem; text-transform:uppercase; padding:5px 8px; border-radius:999px; border:1px solid var(--border); }}
.status.active {{ color:#6ee7b7; background:rgba(16,185,129,.12); border-color:rgba(16,185,129,.45); }}
.status.beta {{ color:#fcd34d; background:rgba(245,158,11,.12); border-color:rgba(245,158,11,.45); }}
.status.disabled {{ color:var(--muted); background:rgba(100,116,139,.12); }}
.launch {{ text-decoration:none!important; font-family:'Space Mono',monospace; font-size:.65rem; color:white!important; padding:7px 10px; border-radius:9px; background:linear-gradient(135deg,var(--accent),var(--accent2)); }}
.launch.off {{ background:var(--surface2); color:var(--muted)!important; border:1px solid var(--border); }}
.config-note {{ border:1px solid var(--border); background:var(--surface2); border-radius:14px; padding:14px; color:var(--muted); font-size:.82rem; line-height:1.45; }}
.cost-box {{ border:1px solid var(--border); background:var(--surface2); border-radius:14px; padding:12px; margin-top:10px; }}
.cost-line {{ display:flex; justify-content:space-between; gap:10px; color:var(--muted); font-family:'Space Mono',monospace; font-size:.68rem; margin:5px 0; }}
</style>
"""


def require_login() -> None:
    configured_password = get_secret("PRADIP_PASSWORD") or get_secret("ADMIN_PASSWORD")
    if st.session_state.authenticated:
        return
    theme = THEMES.get(st.session_state.theme_name, THEMES["Dark Neon Command Center"])
    st.markdown(css(theme), unsafe_allow_html=True)
    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="brand">🧭 TechAtlas AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub">Secure Executive Technology Knowledge Hub</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Sign in")
    # No username field and no username preview. User ID is fixed internally as pradip.
    password = st.text_input("Password", type="password", placeholder="Enter your password")
    login = st.button("Login", use_container_width=True)
    if not configured_password:
        st.warning("Set PRADIP_PASSWORD in Streamlit secrets or environment variables before login.")
    if login:
        if configured_password and password == configured_password:
            st.session_state.authenticated = True
            st.session_state.login_user = DEFAULT_USER_ID
            st.rerun()
        else:
            st.error("Invalid password.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


def status_class(status: str) -> str:
    status = status.lower()
    return status if status in {"active", "beta", "disabled"} else "disabled"


def app_url(app: Dict[str, str]) -> str:
    page = app.get("page", "")
    if app.get("url"):
        return app["url"]
    return f"/{page}" if page else "#"


def render_tile(app: Dict[str, str]) -> str:
    status = app.get("status", "disabled").lower()
    disabled = status == "disabled"
    accent = app.get("accent", "var(--accent)")
    launch = '<span class="launch off">Unavailable</span>' if disabled else f'<a class="launch" href="{app_url(app)}" target="_self">Launch App →</a>'
    cls = "tile disabled" if disabled else "tile"
    return f"""
    <div class="{cls}" style="border-top:4px solid {accent};">
        <div class="symbol" style="color:{accent};">{app.get('symbol','??')}</div>
        <div class="app-name">{app.get('name','Unnamed App')}</div>
        <div class="app-desc">{app.get('description','')}</div>
        <div class="category" style="color:{accent};">{app.get('category','Other')}</div>
        <div class="app-desc" style="margin-top:4px;">{app.get('cadence','')}</div>
        <div class="meta-row"><span class="status {status_class(status)}">{status}</span>{launch}</div>
    </div>
    """


def filtered_apps(query: str, category: str, status_filter: str, show_disabled: bool) -> List[Dict[str, str]]:
    out = []
    for app in APP_REGISTRY:
        status = app.get("status", "disabled").lower()
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


def sidebar() -> None:
    st.sidebar.markdown("### 🧭 TechAtlas Controls")
    st.session_state.theme_name = st.sidebar.selectbox("Colour theme", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state.theme_name))
    st.session_state.model_name = st.sidebar.selectbox("Model", MODEL_OPTIONS, index=MODEL_OPTIONS.index(st.session_state.model_name))
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💵 Session token cost")
    pricing = MODEL_PRICING_PER_1M[st.session_state.model_name]
    st.sidebar.markdown(f"""
    <div class="cost-box">
      <div class="cost-line"><span>Model</span><strong>{st.session_state.model_name}</strong></div>
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
    st.sidebar.markdown("### 🔎 Filter apps")
    query = st.sidebar.text_input("Search apps", placeholder="AI, cloud, cyber, data...")
    category = st.sidebar.selectbox("Category", ["All"] + sorted({a.get("category", "Other") for a in APP_REGISTRY}))
    status_filter = st.sidebar.selectbox("Status", ["All", "active", "beta", "disabled"])
    show_disabled = st.sidebar.toggle("Show disabled apps", value=True)
    group_by_category = st.sidebar.toggle("Group by category", value=False)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ Configure apps")
    st.sidebar.markdown('<div class="config-note">Add, remove, rename or disable apps in <code>app_registry.py</code>. Keep app pages under the <code>pages/</code> folder.</div>', unsafe_allow_html=True)
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.login_user = ""
        st.rerun()
    return query, category, status_filter, show_disabled, group_by_category


def ask_selected_model(prompt: str) -> str:
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        return "Set OPENAI_API_KEY in Streamlit secrets or environment variables to enable the model test."
    if OpenAI is None:
        return "Install the openai package: pip install openai"
    client = OpenAI(api_key=api_key)
    # Responses API. If your selected model name is not enabled in your account, choose another model in the sidebar.
    response = client.responses.create(model=st.session_state.model_name, input=prompt)
    if getattr(response, "usage", None):
        add_usage(st.session_state.model_name, response.usage)
    return getattr(response, "output_text", "") or "No text returned."


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
    init_state()
    require_login()
    theme = THEMES.get(st.session_state.theme_name, THEMES["Dark Neon Command Center"])
    st.markdown(css(theme), unsafe_allow_html=True)
    query, category, status_filter, show_disabled, group_by_category = sidebar()

    apps = filtered_apps(query, category, status_filter, show_disabled)
    active = sum(1 for a in APP_REGISTRY if a.get("status") == "active")
    beta = sum(1 for a in APP_REGISTRY if a.get("status") == "beta")
    disabled = sum(1 for a in APP_REGISTRY if a.get("status") == "disabled")

    st.markdown(f"""
    <div class="hero">
      <div class="hero-title">Welcome, Pradip! 👋</div>
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
            st.markdown(f"#### {cat}")
            st.markdown('<div class="grid">' + "".join(render_tile(a) for a in apps if a.get("category") == cat) + '</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="grid">' + "".join(render_tile(a) for a in apps) + '</div>', unsafe_allow_html=True)

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
