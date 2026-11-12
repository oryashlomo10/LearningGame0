"""All CSS for Conquest in one place.

Colors are CSS variables defined in PALETTE, so the whole look can be changed
from here. The map itself is drawn inside the custom component
(components/world_map/index.html), which has its own small stylesheet.
"""

PALETTE = {
    "bg": "#090d1a",
    "panel": "#10172e",
    "panel2": "#172042",
    "border": "#27315f",
    "text": "#e9edff",
    "muted": "#8f9bc7",
    "gold": "#f5b942",
    "gold-dark": "#d9901a",
    "good": "#34d399",
    "bad": "#f0616d",
    "neutral": "#3a4570",
}
GOLD = PALETTE["gold"]


def _root_variables():
    lines = "\n".join(f"  --{name}: {value};" for name, value in PALETTE.items())
    return f":root {{\n{lines}\n}}"


_STATIC_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700;800;900&display=swap');

html, body, .stApp { direction: rtl; text-align: right; font-family: 'Heebo', sans-serif; color: var(--text); }
.stApp {
  background:
    radial-gradient(circle at 85% -5%, rgba(124,92,255,0.20), transparent 42%),
    radial-gradient(circle at 5% 15%, rgba(245,185,66,0.08), transparent 38%),
    var(--bg);
}
header[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }
.block-container { max-width: 1480px; padding: 1.2rem 1.5rem 3rem; }
code, [data-testid="stMarkdownContainer"] code { direction: ltr; unicode-bidi: isolate; font-family: Consolas, monospace; background: rgba(255,255,255,0.09) !important; color: #ffe08a !important; padding: 0.1rem 0.4rem; border-radius: 6px; font-size: 0.92em; }
h1, h2, h3, p, label, span, div { font-family: 'Heebo', sans-serif; }

/* ---------- Buttons ---------- */
[data-testid="stBaseButton-primary"], button[kind="primary"] {
  background: linear-gradient(180deg, var(--gold), var(--gold-dark)) !important;
  color: #1b1204 !important; font-weight: 800 !important; font-size: 1.1rem !important;
  border: none !important; border-radius: 12px !important; padding: 0.7rem 1.4rem !important;
  box-shadow: 0 4px 0 #8a5a0c, 0 10px 24px rgba(245,185,66,0.28) !important;
  transition: transform .12s, filter .12s;
}
[data-testid="stBaseButton-primary"] p { font-size: 1.1rem !important; font-weight: inherit; color: inherit; }
[data-testid="stBaseButton-primary"]:hover:not(:disabled) { filter: brightness(1.08); transform: translateY(-2px); }
[data-testid="stBaseButton-primary"]:active:not(:disabled) { transform: translateY(3px); box-shadow: 0 1px 0 #8a5a0c !important; }
[data-testid="stBaseButton-primary"]:disabled, button[kind="primary"]:disabled {
  background: var(--panel2) !important; color: var(--muted) !important;
  box-shadow: none !important; border: 1px solid var(--border) !important; opacity: 1 !important;
}
[data-testid="stBaseButton-secondary"], button[kind="secondary"] {
  background: var(--panel2); color: var(--text); border: 1px solid var(--border); border-radius: 12px; font-weight: 600;
}
[data-testid="stBaseButton-secondary"]:hover { border-color: var(--gold); color: var(--gold); }

/* ---------- Top bar ---------- */
.topbar { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
  background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--border);
  border-radius: 16px; padding: 0.7rem 1.1rem; margin-bottom: 1rem; }
.brand { display: flex; align-items: center; gap: 0.6rem; direction: ltr; }
.brand-mark { color: var(--gold); font-size: 1.4rem; filter: drop-shadow(0 0 8px rgba(245,185,66,.6)); }
.brand-name { font-weight: 900; letter-spacing: 0.3rem; font-size: 1.35rem;
  background: linear-gradient(180deg, #ffe08a, var(--gold)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.course { color: var(--muted); font-weight: 600; }
.course b { color: var(--text); }
.topbar-end { display: flex; align-items: center; gap: 0.9rem; }
.chip { display: inline-block; padding: 0.2rem 0.75rem; border-radius: 999px; font-size: 0.85rem; font-weight: 700;
  background: rgba(255,255,255,0.06); border: 1px solid var(--border); color: var(--muted); }
.chip.live { color: var(--good); border-color: rgba(52,211,153,.45); background: rgba(52,211,153,.08); }
.chip.gold { color: var(--gold); border-color: rgba(245,185,66,.5); background: rgba(245,185,66,.08); }
.chip.red { color: var(--bad); border-color: rgba(240,97,109,.5); background: rgba(240,97,109,.08); }
.profile { display: flex; align-items: center; gap: 0.55rem; }
.avatar { width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-weight: 800; color: #05201c; background: linear-gradient(160deg, #5eead4, #14b8a6); box-shadow: 0 0 14px rgba(45,212,191,.5); }
.pname { font-weight: 700; line-height: 1.1; }
.prole { color: var(--muted); font-size: 0.78rem; }

/* ---------- Stats ---------- */
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.8rem; margin-bottom: 0.8rem; }
.stats.six { grid-template-columns: repeat(3, 1fr); }
.stat { background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 0.75rem 1rem; }
.stat-label { color: var(--muted); font-size: 0.82rem; font-weight: 600; }
.stat-value { font-size: 1.8rem; font-weight: 900; line-height: 1.2; }
.stat-value small { font-size: 0.9rem; color: var(--muted); font-weight: 600; }
.stat.gold .stat-value { color: var(--gold); }
.stat.teal .stat-value { color: #5eead4; }

.progress-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; margin-bottom: 1.1rem; }
.progress-label { display: flex; justify-content: space-between; color: var(--muted); font-size: 0.82rem; font-weight: 600; margin-bottom: 0.3rem; }
.bar { height: 9px; background: var(--panel2); border-radius: 999px; overflow: hidden; border: 1px solid var(--border); }
.bar > span { display: block; height: 100%; border-radius: 999px; }
.bar.gold > span { background: linear-gradient(90deg, var(--gold-dark), var(--gold)); }
.bar.teal > span { background: linear-gradient(90deg, #14b8a6, #5eead4); }

/* ---------- Map board (the map is an iframe component) ---------- */
.st-key-map_board iframe { display: block; width: 100%; min-height: 320px; border: 1px solid var(--border); border-radius: 18px;
  background: #070b18; box-shadow: 0 10px 40px rgba(0,0,0,0.45), inset 0 0 0 1px rgba(245,185,66,0.08); }
.legend { display: flex; flex-wrap: wrap; gap: 1rem; margin-top: 0.7rem; color: var(--muted); font-size: 0.85rem; }
.legend span.dot { display: inline-block; width: 12px; height: 12px; border-radius: 4px; margin-left: 0.4rem; vertical-align: -1px; }
.legend .stone { background: #5d6a5f; }
.legend .dashed { background: transparent; border: 2px dashed var(--gold); box-sizing: border-box; }

/* ---------- Side panels ---------- */
.panel { background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--border); border-radius: 16px; padding: 1rem 1.1rem; margin-bottom: 0.9rem; }
.panel-title { color: var(--muted); font-size: 0.8rem; font-weight: 700; letter-spacing: 0.06rem; margin-bottom: 0.6rem; }
.sel-name { font-size: 1.4rem; font-weight: 900; margin-bottom: 0.4rem; }
.sel-row { display: flex; justify-content: space-between; padding: 0.3rem 0; border-top: 1px solid rgba(255,255,255,0.06); font-size: 0.92rem; }
.sel-row span:first-child { color: var(--muted); }
.nbrs { font-size: 0.8rem; text-align: left; max-width: 60%; line-height: 1.4; }
.empty-hint { color: var(--muted); line-height: 1.6; }
.reason { color: var(--muted); font-size: 0.82rem; text-align: center; margin-top: 0.4rem; }
.owner-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-left: 0.4rem; }

.lb-row { display: flex; align-items: center; gap: 0.6rem; padding: 0.5rem 0.6rem; border-radius: 10px; margin-bottom: 0.3rem; background: rgba(255,255,255,0.03); }
.lb-row.me { background: rgba(45,212,191,0.12); border: 1px solid rgba(45,212,191,0.4); }
.lb-rank { width: 1.4rem; font-weight: 900; color: var(--gold); }
.lb-name { flex: 1; font-weight: 700; }
.lb-demo { font-size: 0.7rem; color: var(--muted); font-weight: 500; margin-right: 0.3rem; }
.lb-count { color: var(--muted); font-size: 0.85rem; }
.lb-score { font-weight: 800; min-width: 2.2rem; text-align: left; }
.lb-note { color: var(--muted); font-size: 0.75rem; margin-top: 0.4rem; }

.log-item { font-size: 0.88rem; padding: 0.3rem 0; border-top: 1px solid rgba(255,255,255,0.06); color: var(--muted); }
.log-item.win { color: var(--good); }
.log-item.loss { color: var(--bad); }

/* ---------- Question / result ---------- */
.st-key-question_card, .qcard { background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--border); border-radius: 20px; padding: 1.4rem 1.6rem; }
.q-meta { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; }
.q-text { font-size: 1.55rem; font-weight: 800; line-height: 1.55; margin: 0.4rem 0 1rem; }
[data-testid="stRadio"], .st-key-question_card [data-testid="stElementContainer"] { width: 100% !important; }
[data-testid="stRadioGroup"] { display: flex; flex-direction: column; align-items: stretch; gap: 0.6rem; }
[data-testid="stRadioGroup"] > div { width: 100%; }
[data-testid="stRadioOption"] > div > div:first-child { background: transparent !important; border: 2px solid var(--muted) !important; }
[data-testid="stRadioOption"]:has(input:checked) > div > div:first-child { border-color: var(--gold) !important; }
[data-testid="stRadioOption"]:has(input:checked) > div > div:first-child > div { background: var(--gold) !important; }
[data-testid="stRadioOption"] { background: var(--panel); border: 1.5px solid var(--border); border-radius: 12px; padding: 0.85rem 1rem; width: 100%; cursor: pointer; transition: border-color .15s, background .15s; }
[data-testid="stRadioOption"]:hover { border-color: var(--gold); }
[data-testid="stRadioOption"]:has(input:checked) { border-color: var(--gold); background: rgba(245,185,66,0.12); }
[data-testid="stRadioOption"] p { font-size: 1.08rem; color: var(--text); }
.q-hint { color: var(--muted); font-size: 0.85rem; margin-top: 0.4rem; }

.banner { border-radius: 18px; padding: 1.2rem 1.5rem; margin-bottom: 1rem; border: 1px solid; }
.banner.win { background: linear-gradient(135deg, rgba(52,211,153,.18), rgba(45,212,191,.06)); border-color: rgba(52,211,153,.55); }
.banner.loss { background: linear-gradient(135deg, rgba(240,97,109,.18), rgba(240,97,109,.05)); border-color: rgba(240,97,109,.55); }
.banner-title { font-size: 1.9rem; font-weight: 900; }
.banner.win .banner-title { color: var(--good); }
.banner.loss .banner-title { color: var(--bad); }
.banner-sub { color: var(--text); opacity: .85; margin-top: 0.2rem; }
.opt { display: flex; align-items: center; gap: 0.6rem; padding: 0.65rem 0.9rem; margin-bottom: 0.45rem; border-radius: 10px; border: 1px solid var(--border); background: var(--panel); }
.opt.right { border-color: rgba(52,211,153,.7); background: rgba(52,211,153,.12); }
.opt.wrong { border-color: rgba(240,97,109,.7); background: rgba(240,97,109,.12); }
.opt-mark { font-weight: 900; width: 1.3rem; }
.opt-tag { margin-right: auto; font-size: 0.78rem; font-weight: 700; color: var(--muted); }
.explain { border-right: 4px solid var(--gold); background: rgba(245,185,66,0.08); border-radius: 10px; padding: 0.9rem 1.1rem; margin: 1rem 0; line-height: 1.7; }
.explain b { color: var(--gold); }
.rival { color: var(--muted); font-size: 0.92rem; margin-bottom: 1rem; }
.rival b { color: var(--text); }
.rival.alert { color: var(--text); background: rgba(240,97,109,0.10); border: 1px solid rgba(240,97,109,0.5); border-radius: 10px; padding: 0.7rem 1rem; }
/* knowledge regions panel */
.rg-row { display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0.5rem; border-radius: 8px; font-size: 0.86rem; }
.rg-row.me { background: rgba(45,212,191,0.12); }
.rg-dots { display: inline-flex; flex-shrink: 0; }
.rg-dots .owner-dot { margin-left: 0.2rem; }
.rg-name { flex: 1; }
.rg-bonus { font-weight: 800; font-size: 0.8rem; white-space: nowrap; }
.rg-open { color: var(--muted); font-size: 0.78rem; }

/* ---------- Main menu ---------- */
.hero { text-align: center; padding: 1.5rem 0 0.5rem; }
.logo-icon { font-size: 3rem; color: var(--gold); filter: drop-shadow(0 0 18px rgba(245,185,66,0.5)); }
.title { font-size: 4.6rem; font-weight: 900; letter-spacing: 0.35rem; margin: 0; line-height: 1.1; direction: ltr;
  background: linear-gradient(180deg, #ffe08a, var(--gold) 55%, var(--gold-dark)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.tagline { direction: ltr; font-size: 1.15rem; font-weight: 600; letter-spacing: 0.25rem; color: var(--muted); margin-top: 0.4rem; }
.tagline b { color: var(--bad); }
.desc { text-align: center; font-size: 1.15rem; line-height: 1.8; opacity: .92; margin: 1.5rem auto 1.6rem; max-width: 600px; }
.steps-title { text-align: center; color: var(--muted); font-weight: 600; letter-spacing: 0.1rem; margin: 2.6rem 0 1rem; }
.steps { display: flex; gap: 1rem; max-width: 820px; margin: 0 auto; }
.step { flex: 1; background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 1.3rem 1rem; text-align: center; position: relative; transition: transform .15s, border-color .15s; }
.step:hover { transform: translateY(-4px); border-color: var(--gold); }
.step-num { position: absolute; top: 0.6rem; right: 0.8rem; font-size: 0.9rem; font-weight: 800; color: var(--gold); opacity: .8; }
.step-icon { font-size: 2.2rem; margin-bottom: 0.4rem; }
.step-name { font-size: 1.2rem; font-weight: 800; margin-bottom: 0.3rem; }
.step-desc { font-size: 0.93rem; color: var(--muted); line-height: 1.5; }
.footer { text-align: center; color: var(--muted); opacity: .6; font-size: 0.85rem; margin-top: 2.5rem; }
.st-key-start_btn { align-items: center; }
.st-key-start_btn button { padding: 0.8rem 3.5rem !important; }
.st-key-start_btn button p { font-size: 1.6rem !important; }

/* ---------- End screen ---------- */
.end-hero { text-align: center; padding: 2rem 1rem; border-radius: 22px; border: 1px solid; margin-bottom: 1.2rem; }
.end-hero.victory { background: radial-gradient(circle at 50% 0%, rgba(245,185,66,.25), transparent 65%), var(--panel); border-color: rgba(245,185,66,.6); }
.end-hero.defeat { background: radial-gradient(circle at 50% 0%, rgba(240,97,109,.2), transparent 65%), var(--panel); border-color: rgba(240,97,109,.5); }
.end-title { font-size: 3rem; font-weight: 900; }
.end-hero.victory .end-title { color: var(--gold); text-shadow: 0 0 30px rgba(245,185,66,.5); }
.end-hero.defeat .end-title { color: var(--bad); }
.end-sub { font-size: 1.1rem; opacity: .9; margin-top: 0.4rem; }

@media (max-width: 760px) {
  .stats { grid-template-columns: repeat(4, 1fr); gap: 0.4rem; }
  .stat { padding: 0.45rem 0.55rem; }
  .stat-label { font-size: 0.68rem; }
  .stat-value { font-size: 1.3rem; }
  .stat-value small { font-size: 0.65rem; display: block; line-height: 1; }
  .topbar { padding: 0.5rem 0.7rem; }
  .block-container { padding: 0.8rem 0.8rem 2rem; }
  .progress-row { grid-template-columns: 1fr; }
  .steps { flex-direction: column; }
  .title { font-size: 3rem; }
  .q-text { font-size: 1.25rem; }
}
"""


def build_css():
    """Return the full <style> block to inject with st.markdown."""
    return f"<style>\n{_root_variables()}\n{_STATIC_CSS}\n</style>"
