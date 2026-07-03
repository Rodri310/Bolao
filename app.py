"""
app.py — Ponto de entrada do Dashboard Bolão Copa do Mundo 2026.
"""
import os
import json
import logging

from dotenv import load_dotenv
load_dotenv()

import dash
from dash import html, dcc
from dash.dependencies import Input, Output, State, ALL
import dash_mantine_components as dmc

# ── Inicialização ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

from db import init_db
init_db()

# ── App ───────────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    title="Bolão dos Guerreiros",
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "viewport",     "content": "width=device-width, initial-scale=1"},
        {"name": "description",  "content": "Acompanhe os palpites e pontuações do bolão da Copa do Mundo 2026"},
        {"property": "og:title", "content": "Bolão dos Guerreiros"},
    ],
)

server = app.server  # exposto ao Gunicorn

# ── Layout ────────────────────────────────────────────────────────────────────

TAB_STYLE = {
    "background":    "transparent",
    "border":        "none",
    "borderBottom":  "2px solid transparent",
    "color":         "#64748b",
    "fontFamily":    "'Poppins', sans-serif",
    "fontWeight":    "500",
    "fontSize":      "0.88rem",
    "padding":       "0.75rem 1.5rem",
    "transition":    "all 0.2s",
}

TAB_SELECTED_STYLE = {
    **TAB_STYLE,
    "color":         "var(--gold)",
    "borderBottom":  "2px solid var(--gold)",
    "fontWeight":    "600",
}

app.layout = dmc.MantineProvider(
    html.Div([

        # ── Header ──────────────────────────────────────────────────────────────
        html.Header([
            html.Div([
                html.Div([
                    html.H1("Bolão dos Guerreiros", className="header-title"),
                    html.P("Acompanhe palpites e pontuações em tempo real",
                           className="header-subtitle"),
                ]),
            ], className="header-inner"),
        ], className="app-header"),

        # ── Tabs + Conteúdo ─────────────────────────────────────────────────────
        html.Main([
            dcc.Tabs(
                id="main-tabs",
                value="ranking",
                children=[
                    dcc.Tab(label="Ranking Geral", value="ranking",
                            style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                    dcc.Tab(label="Mata-Mata",     value="mata_mata",
                            style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                    dcc.Tab(label="Por Dia",        value="por_dia",
                            style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                    dcc.Tab(label="Por Jogo",       value="por_jogo",
                            style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                    dcc.Tab(label="Por Pessoa",     value="por_pessoa",
                            style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                ],
                style={
                    "background":   "transparent",
                    "borderBottom": "1px solid rgba(255,255,255,0.08)",
                },
            ),

            html.Div(id="tab-content", className="tab-content-wrapper"),

        ], className="main-container"),

        # ── Estado de navegação cruzada entre abas ──────────────────────────────
        # Formato: {"target_tab": "por_jogo", "match_id": "..."}
        #       ou {"target_tab": "por_pessoa", "member_id": "..."}
        dcc.Store(id="nav-store", data={}),

        # ── Auto-refresh (a cada 5 min) ─────────────────────────────────────────
        dcc.Interval(
            id="refresh-interval",
            interval=5 * 60 * 1000,   # ms
            n_intervals=0,
        ),

    ], className="app-wrapper"),
    forceColorScheme="dark"
)


# ── Callback de roteamento das abas ───────────────────────────────────────────
from pages import ranking, por_dia, por_jogo, por_pessoa, mata_mata


@app.callback(
    Output("tab-content", "children"),
    Input("main-tabs", "value"),
    State("nav-store", "data"),
)
def render_tab(tab, nav_data):
    nav = nav_data or {}
    if tab == "ranking":
        return ranking.layout()
    if tab == "mata_mata":
        return mata_mata.layout()
    if tab == "por_dia":
        return por_dia.layout()
    if tab == "por_jogo":
        return por_jogo.layout(initial_match=nav.get("match_id"))
    if tab == "por_pessoa":
        return por_pessoa.layout(initial_member=nav.get("member_id"))
    return html.Div("Aba não encontrada.")


# ── Callback: clique em card de jogo ou linha do ranking → atualiza Store ─────

@app.callback(
    Output("nav-store", "data"),
    Input({"type": "nav-match", "id": ALL}, "n_clicks"),
    Input({"type": "nav-member", "id": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_nav_click(match_clicks, member_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update

    triggered = ctx.triggered[0]
    # Ignora se o valor for 0 ou None (não é um clique real)
    if not triggered["value"]:
        return dash.no_update

    prop_id = triggered["prop_id"]          # ex: '{"id":"abc","type":"nav-match"}.n_clicks'
    id_str  = prop_id.rsplit(".", 1)[0]     # ex: '{"id":"abc","type":"nav-match"}'

    try:
        id_dict = json.loads(id_str)
    except (json.JSONDecodeError, ValueError):
        return dash.no_update

    nav_type = id_dict.get("type")
    nav_id   = id_dict.get("id")

    if nav_type == "nav-match":
        return {"target_tab": "por_jogo", "match_id": nav_id}
    if nav_type == "nav-member":
        return {"target_tab": "por_pessoa", "member_id": nav_id}

    return dash.no_update


# ── Callback: nav-store → mudar aba ─────────────────────────────────────────

@app.callback(
    Output("main-tabs", "value"),
    Input("nav-store", "data"),
    prevent_initial_call=True,
)
def switch_tab_on_nav(nav_data):
    if nav_data and "target_tab" in nav_data:
        return nav_data["target_tab"]
    return dash.no_update


# ── Registrar callbacks das páginas ───────────────────────────────────────────
ranking.register_callbacks(app)
mata_mata.register_callbacks(app)
por_dia.register_callbacks(app)
por_jogo.register_callbacks(app)
por_pessoa.register_callbacks(app)


# ── Scheduler (busca resultados a cada 5 min) ─────────────────────────────────

def _start_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    from api_fetcher import fetch_and_store_results
    from data_manager import get_bolao_data

    data = get_bolao_data()
    if data is None:
        logger.warning("Scheduler não iniciado: dados do bolão indisponíveis.")
        return

    dim_jogos = data["dim_jogos"]

    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo", daemon=True)
    scheduler.add_job(
        fetch_and_store_results,
        trigger="interval",
        minutes=5,
        args=[dim_jogos],
        id="fetch_results",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler iniciado — buscando resultados a cada 5 minutos.")

    # Buscar imediatamente ao iniciar
    try:
        fetch_and_store_results(dim_jogos)
    except Exception as exc:
        logger.warning("Fetch inicial falhou: %s", exc)


# Evita duplo-start no reloader do Werkzeug (debug=True cria 2 processos)
_is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
_is_production     = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "").lower()

if _is_production or _is_reloader_child or not app.server.debug:
    try:
        _start_scheduler()
    except Exception as exc:
        logger.error("Falha ao iniciar scheduler: %s", exc)


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=True, port=port, host="0.0.0.0")
