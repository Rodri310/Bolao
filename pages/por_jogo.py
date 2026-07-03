"""
pages/por_jogo.py — Aba 3: Detalhes de uma partida específica.
"""
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
from dash.dependencies import Input, Output

from data_manager import get_full_df
from scoring import label_pontos, cor_pontos
from teams import flag_span

_FASE_LABEL = {
    "R32": "16-avos", "R16": "Oitavas",
    "QF":  "Quartas",  "SF":  "Semi",  "F": "Final",
}
def _grupo_label(grupo: str) -> str:
    return _FASE_LABEL.get(str(grupo).upper(), str(grupo))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _score_badge(pontos):
    return html.Span(label_pontos(pontos), className=f"score-badge {cor_pontos(pontos)}")


def _dist_chart(df_match: pd.DataFrame):
    """Gráfico de barras: distribuição dos palpites por resultado esperado."""
    if df_match.empty:
        return None

    df = df_match.copy()
    df["resultado_palpite"] = df.apply(
        lambda r: (
            f"{r['mandante_sigla']} vence" if r["placar_mandante"] > r["placar_visitante"]
            else ("Empate" if r["placar_mandante"] == r["placar_visitante"]
                  else f"{r['visitante_sigla']} vence")
        ), axis=1
    )

    dist = df["resultado_palpite"].value_counts().reset_index()
    dist.columns = ["resultado", "qtd"]

    color_map = {}
    for r in dist["resultado"]:
        if "Empate" in r:
            color_map[r] = "#d2a16d"
        elif dist.index[dist["resultado"] == r][0] == 0:
            color_map[r] = "#84a98c"
        else:
            color_map[r] = "#687d82"

    fig = go.Figure(go.Bar(
        x=dist["resultado"],
        y=dist["qtd"],
        marker_color=[color_map.get(r, "#687d82") for r in dist["resultado"]],
        text=dist["qtd"],
        textposition="outside",
        textfont=dict(color="#e2e8f0"),
        hovertemplate="<b>%{x}</b><br>%{y} palpites<extra></extra>",
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13,20,33,0.6)",
        margin=dict(l=20, r=20, t=10, b=10),
        font=dict(family="Poppins", color="#94a3b8"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)", title_text="Nº de apostas"),
        height=280,
        bargap=0.45,
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def _build_match_content(match_id: str):
    result = get_full_df()
    if result is None:
        return html.Div("Erro ao carregar dados.", className="error-msg")

    df, dim_jogos, _ = result

    match_row = dim_jogos[dim_jogos["match_id"] == match_id]
    if match_row.empty:
        return html.Div("Partida não encontrada.", className="error-msg")

    m = match_row.iloc[0]
    df_match = df[df["match_id"] == match_id].copy()

    # Card da partida
    status = m.get("status")
    is_live = pd.notna(status) and status in ("IN_PLAY", "PAUSED")
    has_result = pd.notna(m.get("score_home")) and pd.notna(m.get("score_away"))

    if has_result:
        if is_live:
            score_chip = html.Span(f"{int(m['score_home'])} – {int(m['score_away'])}", className="result-chip", style={"borderColor": "var(--gold)", "color": "var(--gold)"})
        else:
            score_chip = html.Span(f"{int(m['score_home'])} – {int(m['score_away'])}", className="result-chip")
    else:
        score_chip = html.Span("Aguardando resultado", className="result-chip result-chip--pending")

    data_fmt = (
        m["data_dt"].strftime("%d/%m/%Y")
        if pd.notna(m.get("data_dt")) else str(m.get("data_jogo", ""))
    )

    time_display = "Em Andamento" if is_live else m.get('hora', '')
    time_style = {"color": "var(--gold)", "fontSize": "0.8rem", "fontWeight": "700"} if is_live else {"color": "#64748b", "fontSize": "0.8rem"}

    match_card = html.Div([
        html.Div([
            html.Span(_grupo_label(str(m.get("grupo", ""))), className="group-badge"),
            html.Span(data_fmt, style={"color": "#64748b", "fontSize": "0.8rem"}),
            html.Span(time_display, style=time_style),
        ], style={"display": "flex", "alignItems": "center", "gap": "0.75rem", "marginBottom": "1.25rem"}),

        html.Div([
            # Mandante
            html.Div([
                html.Div([
                    flag_span(str(m.get("mandante_sigla", "")), "1.5rem"),
                    html.Span(str(m.get("mandante_sigla", "")), className="team-code",
                             style={"fontSize": "2rem", "marginLeft": "0.5rem"}),
                ], style={"display": "flex", "alignItems": "center", "justifyContent": "center"}),
                html.Div(str(m.get("mandante_nome", "")), className="team-name"),
            ], className="team-block"),

            # Placar / VS
            html.Div([
                html.Div("vs", className="match-vs"),
                html.Div(score_chip, style={"marginTop": "0.5rem"}),
            ], className="match-vs-block"),

            # Visitante
            html.Div([
                html.Div([
                    flag_span(str(m.get("visitante_sigla", "")), "1.5rem"),
                    html.Span(str(m.get("visitante_sigla", "")), className="team-code",
                             style={"fontSize": "2rem", "marginLeft": "0.5rem"}),
                ], style={"display": "flex", "alignItems": "center", "justifyContent": "center"}),
                html.Div(str(m.get("visitante_nome", "")), className="team-name"),
            ], className="team-block"),
        ], className="match-teams"),
    ], className="card", style={"marginBottom": "1.5rem"})

    # Tabela de palpites
    if df_match.empty:
        palpites_section = html.Div("Nenhum palpite registrado.", className="empty-state")
    else:
        df_sorted = df_match.sort_values("pontos", key=lambda s: s.fillna(-1), ascending=False)
        palpite_rows = []
        for _, p in df_sorted.iterrows():
            palpite_rows.append(html.Tr([
                html.Td(str(p.get("name", p["member_id"])), className="rank-name"),
                html.Td(
                    f"{int(p['placar_mandante'])} × {int(p['placar_visitante'])}",
                    className="palpite-score"
                ),
                html.Td(_score_badge(p["pontos"])),
            ]))

        palpites_section = html.Div([
            html.Div([
                html.Span("", className="section-icon"),
                html.H3("Palpites", className="section-title", style={"fontSize": "1rem"}),
            ], className="section-header"),
            html.Div(
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("Participante"),
                        html.Th("Palpite"),
                        html.Th("Pontuação"),
                    ])),
                    html.Tbody(palpite_rows),
                ], className="palpites-table"),
                className="palpites-table-wrapper card",
            ),
        ])

    # Gráfico de distribuição
    chart = _dist_chart(df_match)
    chart_section = html.Div([
        html.Div([
            html.Span("", className="section-icon"),
            html.H3("Distribuição dos Palpites", className="section-title",
                    style={"fontSize": "1rem"}),
        ], className="section-header", style={"marginTop": "1.5rem"}),
        html.Div(chart, className="chart-wrapper") if chart else html.Div(),
    ]) if chart else html.Div()

    return html.Div([match_card, palpites_section, chart_section])


# ── Layout ────────────────────────────────────────────────────────────────────

def layout(initial_match=None):
    result = get_full_df()
    options = []
    default = initial_match  # pode vir da navegação cruzada

    if result is not None:
        _, dim_jogos, _ = result
        for _, row in dim_jogos.sort_values("data_dt").iterrows():
            data_fmt = (
                row["data_dt"].strftime("%d/%m")
                if pd.notna(row.get("data_dt")) else ""
            )
            label = (
                f"{row.get('mandante_sigla','?')} × {row.get('visitante_sigla','?')}"
                f"  |  {_grupo_label(str(row.get('grupo','')))}"
                f"  |  {data_fmt}"
            )
            options.append({"label": label, "value": str(row["match_id"])})

        if options and default is None:
            default = options[0]["value"]

    return html.Div([
        html.Div([
            html.Span("", className="section-icon"),
            html.H2("Por Jogo", className="section-title"),
        ], className="section-header"),

        dcc.Dropdown(
            id="por-jogo-dropdown",
            options=options,
            value=default,
            clearable=False,
            placeholder="Selecione uma partida…",
            style={
                "background": "#0d1421",
                "color": "#e2e8f0",
                "border": "1px solid rgba(255,255,255,0.08)",
                "borderRadius": "10px",
                "marginBottom": "1.5rem",
            },
        ),

        html.Div(id="por-jogo-content"),
    ])


# ── Callbacks ─────────────────────────────────────────────────────────────────

def register_callbacks(app):
    @app.callback(
        Output("por-jogo-content", "children"),
        Input("por-jogo-dropdown", "value"),
    )
    def update_match(match_id):
        if not match_id:
            return html.Div([
                html.Div(className="empty-icon"),
                html.Div("Selecione uma partida acima.", className="empty-text"),
            ], className="empty-state")
        return _build_match_content(str(match_id))
