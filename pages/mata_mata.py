"""
pages/mata_mata.py — Aba: Mata-Mata.

Mostra:
  - Barra de filtro por fase (16-avos, Oitavas, Quartas, Semi, Final)
  - Grade de confrontos da fase selecionada
  - Mini-ranking exclusivo da fase
  - Grafico de barras: pontos por participante
"""
import json
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, callback_context
from dash.dependencies import Input, Output, State, ALL

from data_manager import get_full_df
from scoring import label_pontos, cor_pontos
from teams import flag_span


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Grupos que pertencem ao mata-mata (pode expandir para R16, QF, SF, F)
# Grupos que pertencem ao mata-mata (R32=16-avos, R16=oitavas, QF=quartas, SF=semi, F=final)
# Nota: o HTML da fase de grupos usa letras simples A-L para os grupos.
# "F" na fase de grupos significa Grupo F, nao Final — por isso usamos "FINAL" explicitamente
# ou filtramos pelo prefixo "R" e pelo comprimento.
KNOCKOUT_GRUPOS = {"R32", "R16", "QF", "SF", "FINAL"}

def _is_knockout(grupo: str) -> bool:
    """Retorna True se o jogo e do mata-mata (nao da fase de grupos A-L)."""
    g = str(grupo).upper().strip()
    # Fase de grupos: uma unica letra A-L
    if len(g) == 1 and g.isalpha():
        return False
    # Codigos de mata-mata conhecidos
    return g in KNOCKOUT_GRUPOS or g.startswith("R") or g in ("QF", "SF")

# Ordem das fases e labels
FASE_ORDEM = ["R32", "R16", "QF", "SF", "F", "FINAL"]
FASE_LABEL = {
    "R32":   "16-avos",
    "R16":   "Oitavas",
    "QF":    "Quartas",
    "SF":    "Semi",
    "F":     "Final",
    "FINAL": "Final",
}


def _fase_label(grupo: str) -> str:
    return FASE_LABEL.get(str(grupo).upper(), str(grupo))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score_badge(pontos):
    return html.Span(label_pontos(pontos), className=f"score-badge {cor_pontos(pontos)}")


def _knockout_match_card(match_row, df_match: pd.DataFrame):
    """Card de um jogo do mata-mata com palpites colapsados."""
    m = match_row
    match_id        = str(m["match_id"])
    mandante_sigla  = str(m.get("mandante_sigla", ""))
    visitante_sigla = str(m.get("visitante_sigla", ""))
    mandante_nome   = str(m.get("mandante_nome",  mandante_sigla))
    visitante_nome  = str(m.get("visitante_nome", visitante_sigla))
    hora            = str(m.get("hora", ""))
    grupo           = str(m.get("grupo", ""))
    fase            = _fase_label(grupo)

    status     = m.get("status")
    is_live    = pd.notna(status) and status in ("IN_PLAY", "PAUSED")
    has_result = pd.notna(m.get("score_home")) and pd.notna(m.get("score_away"))

    # Verificar se houve prorrogacao (placar 90min diferente do placar final)
    has_et = False
    score_90_note = None
    if has_result:
        sh,  sa  = int(m["score_home"]),    int(m["score_away"])
        sh90 = m.get("score_home_90")
        sa90 = m.get("score_away_90")
        if pd.notna(sh90) and pd.notna(sa90):
            sh90, sa90 = int(sh90), int(sa90)
            if (sh, sa) != (sh90, sa90):
                has_et = True
                # Nota: "X-Y aos 90min | Z-W (apos prorrogacao)"
                score_90_note = html.Div([
                    html.Span(
                        f"{sh90}-{sa90} nos 90min",
                        style={"color": "var(--amber)", "fontWeight": "600",
                               "fontSize": "0.72rem"}
                    ),
                    html.Span(
                        f"  {sh}-{sa} final (prorrg.)",
                        style={"color": "var(--text-3)", "fontSize": "0.68rem",
                               "marginLeft": "0.35rem"}
                    ),
                ], style={"marginTop": "0.25rem"})

    # ---- Placar no cabecalho ----
    if has_result:
        sh, sa = int(m["score_home"]), int(m["score_away"])
        # Se houve prorrogacao, mostrar o placar dos 90min em destaque
        if has_et:
            score_display = f"{sh90}  –  {sa90}"
            score_style   = {"color": "var(--amber)"}
        else:
            score_display = f"{sh}  –  {sa}"
            score_style   = {"color": "var(--gold)"} if is_live else {}
        score_el = html.Div(score_display, className="ko-score", style=score_style)
    else:
        time_txt = "Em Andamento" if is_live else hora
        score_el = html.Div(time_txt, className="ko-score ko-score--pending")

    # ---- Cabecalho do card ----
    header_children = [
        html.Div([
            html.Span(f"#{match_id}", className="ko-match-num"),
            html.Span(fase, className="group-badge"),
        ], style={"display": "flex", "alignItems": "center", "gap": "0.5rem"}),
        html.Div([score_el] + ([score_90_note] if score_90_note else []),
                 style={"textAlign": "right"}),
    ]
    card_header = html.Div(header_children, className="ko-card-header")

    # ---- Times ----
    teams_row = html.Div([
        html.Div([
            flag_span(mandante_sigla, "1.4rem"),
            html.Div([
                html.Span(mandante_sigla, className="team-code",
                          style={"fontSize": "1.1rem"}),
                html.Div(mandante_nome, className="team-name"),
            ], style={"marginLeft": "0.5rem"}),
        ], className="ko-team", style={"flex": "1"}),

        html.Span("×", style={
            "color": "var(--text-3)", "fontSize": "1.1rem",
            "fontWeight": "700", "padding": "0 0.5rem"
        }),

        html.Div([
            html.Div([
                html.Span(visitante_sigla, className="team-code",
                          style={"fontSize": "1.1rem"}),
                html.Div(visitante_nome, className="team-name"),
            ], style={"marginRight": "0.5rem", "textAlign": "right"}),
            flag_span(visitante_sigla, "1.4rem"),
        ], className="ko-team", style={"flex": "1", "justifyContent": "flex-end"}),
    ], className="ko-teams-row")

    # ---- Mini-tabela de palpites ----
    # Nota de pontuacao quando houver prorrogacao
    palpites_header_note = None
    if has_et:
        palpites_header_note = html.Div(
            "Pontos calculados pelo placar aos 90min",
            style={
                "fontSize": "0.68rem", "color": "var(--amber)",
                "marginBottom": "0.4rem", "fontStyle": "italic",
            }
        )

    if df_match.empty:
        palpites_body = html.P("Sem palpites registrados.",
                               className="empty-text",
                               style={"fontSize": "0.78rem", "padding": "0.5rem 0"})
    else:
        df_sorted = df_match.sort_values(
            "pontos", key=lambda s: s.fillna(-1), ascending=False
        )
        rows = []
        for _, p in df_sorted.iterrows():
            palpite_str = f"{int(p['placar_mandante'])} × {int(p['placar_visitante'])}"
            rows.append(html.Tr([
                html.Td(str(p.get("name", p["member_id"])),
                        style={"fontSize": "0.78rem", "color": "var(--text-2)"}),
                html.Td(palpite_str,
                        className="palpite-score",
                        style={"fontSize": "0.82rem"}),
                html.Td(_score_badge(p["pontos"])),
            ]))

        palpites_body = html.Div(
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Participante",
                            style={"fontSize": "0.68rem", "color": "var(--text-3)"}),
                    html.Th("Palpite",
                            style={"fontSize": "0.68rem", "color": "var(--text-3)"}),
                    html.Th("Pts",
                            style={"fontSize": "0.68rem", "color": "var(--text-3)"}),
                ])),
                html.Tbody(rows),
            ], className="palpites-table"),
            className="palpites-table-wrapper",
            style={"maxHeight": "200px", "overflowY": "auto"},
        )

    palpites_el = html.Div(
        [palpites_header_note, palpites_body] if palpites_header_note else [palpites_body],
        style={"marginTop": "0.75rem"}
    )

    # ---- Card completo ----
    border_color = "rgba(210,161,109,0.5)" if has_et else ("rgba(156,176,128,0.4)" if has_result else "var(--border)")
    return html.Div([
        card_header,
        teams_row,
        html.Hr(style={"borderColor": "var(--border)", "margin": "0.75rem 0"}),
        palpites_el,
    ],
        id={"type": "nav-match", "id": match_id},
        n_clicks=0,
        className="ko-card match-card--nav",
        style={"borderColor": border_color},
    )


def _knockout_ranking(df_ko: pd.DataFrame):
    """Ranking exclusivo da fase mata-mata."""
    if df_ko.empty:
        return None

    ranking = (
        df_ko.groupby(["member_id", "name"], as_index=False)
        .agg(
            pts        =("pontos", lambda x: x.dropna().sum()),
            exatos     =("pontos", lambda x: (x == 3).sum()),
            resultados =("pontos", lambda x: (x == 1).sum()),
            erros      =("pontos", lambda x: (x == 0).sum()),
            pendentes  =("pontos", lambda x: x.isna().sum()),
        )
        .sort_values(["pts", "exatos", "resultados"], ascending=False)
        .reset_index(drop=True)
    )

    if ranking["pts"].sum() == 0 and ranking["pendentes"].sum() > 0:
        # Nenhum jogo finalizado ainda
        return html.Div(
            html.P("Os resultados aparecerão aqui conforme os jogos forem finalizados.",
                   className="empty-text"),
            className="empty-state",
        )

    medals = ["1°", "2°", "3°"]
    rows = []
    for i, (_, r) in enumerate(ranking.iterrows()):
        pos = medals[i] if i < 3 else f"{i+1}°"
        cls = f"rank-row-{i+1} rank-row--nav" if i < 3 else "rank-row--nav"
        member_id = str(r["member_id"])
        rows.append(html.Tr([
            html.Td(pos, className="rank-pos"),
            html.Td([
                str(r["name"]),
                html.Span("→", className="nav-row-hint"),
            ], className="rank-name"),
            html.Td(str(int(r["pts"])),        className="rank-pts"),
            html.Td(str(int(r["exatos"])),     className="rank-cell rank-cell--green"),
            html.Td(str(int(r["resultados"])), className="rank-cell rank-cell--amber"),
            html.Td(str(int(r["erros"])),      className="rank-cell rank-cell--red"),
            html.Td(str(int(r["pendentes"])),  className="rank-cell rank-cell--gray"),
        ],
            id={"type": "nav-member", "id": member_id},
            n_clicks=0,
            className=cls,
        ))

    return html.Div(
        html.Table([
            html.Thead(html.Tr([
                html.Th("#"),
                html.Th("Nome"),
                html.Th("Pts"),
                html.Th("Exatos"),
                html.Th("Result."),
                html.Th("Erros"),
                html.Th("Pend."),
            ])),
            html.Tbody(rows),
        ], className="ranking-table"),
        className="ranking-table-wrapper",
    )


def _knockout_chart(df_ko: pd.DataFrame):
    """Gráfico de barras: pontos por participante na fase de 16-avos."""
    if df_ko.empty:
        return None

    ranking = (
        df_ko.groupby("name", as_index=False)
        .agg(pts=("pontos", lambda x: x.dropna().sum()))
        .sort_values("pts", ascending=False)
    )

    if ranking["pts"].sum() == 0:
        return None

    # Cores degradê do 1° ao último
    n = len(ranking)
    colors = [
        f"rgba(156, 176, 128, {max(0.35, 1.0 - (i / n) * 0.6):.2f})"
        for i in range(n)
    ]

    fig = go.Figure(go.Bar(
        x=ranking["name"],
        y=ranking["pts"],
        marker_color=colors,
        text=ranking["pts"].astype(int),
        textposition="outside",
        textfont=dict(color="#e2e8f0", size=11),
        hovertemplate="<b>%{x}</b><br>%{y} pts<extra></extra>",
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13,20,33,0.6)",
        margin=dict(l=20, r=20, t=10, b=80),
        font=dict(family="Poppins", color="#94a3b8", size=11),
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.05)",
            tickangle=-35,
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.05)",
            title_text="Pontos",
            dtick=1,
        ),
        height=320,
        bargap=0.35,
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Filter bar
# ---------------------------------------------------------------------------

def _build_filter_bar(dim_ko: pd.DataFrame, selected_fase: str) -> html.Div:
    """Barra de filtro com botoes de fase."""
    # Detectar fases disponiveis (na ordem correta)
    fases_disponiveis = [
        g for g in FASE_ORDEM
        if g in dim_ko["grupo"].str.upper().values
    ]
    # Remover duplicatas mantendo ordem
    seen = set()
    fases_unicas = []
    for f in fases_disponiveis:
        lbl = FASE_LABEL.get(f, f)
        if lbl not in seen:
            seen.add(lbl)
            fases_unicas.append(f)

    if len(fases_unicas) <= 1:
        return html.Div()  # Nao exibir filtro se so tem 1 fase

    buttons = []
    for fase_code in fases_unicas:
        label    = FASE_LABEL.get(fase_code, fase_code)
        is_active = (fase_code == selected_fase or
                     FASE_LABEL.get(selected_fase, selected_fase) == label)
        buttons.append(
            html.Button(
                label,
                id={"type": "fase-btn", "id": fase_code},
                n_clicks=0,
                className="fase-btn" + (" fase-btn--active" if is_active else ""),
            )
        )

    return html.Div(buttons, className="fase-filter-bar")


# ---------------------------------------------------------------------------
# Build content
# ---------------------------------------------------------------------------

def _build_content(fase: str = "R32"):
    result = get_full_df()
    if result is None:
        return html.Div("Erro ao carregar dados.", className="error-msg")

    df, dim_jogos, _ = result

    # Filtrar apenas jogos do mata-mata
    dim_ko = dim_jogos[dim_jogos["grupo"].apply(_is_knockout)].copy()
    if dim_ko.empty:
        return html.Div([
            html.Div(className="empty-icon"),
            html.P("Os jogos do mata-mata aparecerao aqui quando forem cadastrados.",
                   className="empty-text"),
        ], className="empty-state")

    # Auto-detectar fase padrao: a mais recente com jogos cadastrados
    if fase is None or fase not in dim_ko["grupo"].str.upper().values:
        # Usar a ultima fase com jogos
        for f in reversed(FASE_ORDEM):
            if f in dim_ko["grupo"].str.upper().values:
                fase = f
                break
        else:
            fase = dim_ko["grupo"].iloc[0]

    # Barra de filtro
    filter_bar = _build_filter_bar(dim_ko, fase)

    # Filtrar pela fase selecionada
    dim_fase = dim_ko[
        dim_ko["grupo"].str.upper().isin(
            {fase, *[k for k, v in FASE_LABEL.items() if v == FASE_LABEL.get(fase, fase)]}
        )
    ].copy()
    fase_label = FASE_LABEL.get(fase.upper(), fase)

    match_ids_fase = set(dim_fase["match_id"].tolist())
    match_ids_ko   = set(dim_ko["match_id"].tolist())
    df_ko    = df[df["match_id"].isin(match_ids_ko)].copy()
    df_fase  = df[df["match_id"].isin(match_ids_fase)].copy()

    # ---- Estatisticas de resumo da fase selecionada ----
    n_total       = len(dim_fase)
    n_finalizados = int(dim_fase["score_home"].notna().sum()) if "score_home" in dim_fase.columns else 0
    n_pendentes   = n_total - n_finalizados

    summary = html.Div([
        html.Div([
            html.Div(str(n_total),        className="stat-value"),
            html.Div("Jogos",             className="stat-label"),
        ], className="stat-card stat-card--gold"),
        html.Div([
            html.Div(str(n_finalizados),  className="stat-value"),
            html.Div("Finalizados",       className="stat-label"),
        ], className="stat-card stat-card--green"),
        html.Div([
            html.Div(str(n_pendentes),    className="stat-value"),
            html.Div("Aguardando",        className="stat-label"),
        ], className="stat-card stat-card--gray"),
    ], className="stats-row", style={"gridTemplateColumns": "repeat(3,1fr)", "marginBottom": "2rem"})

    # ---- Grade de jogos da fase ----
    cards = []
    for _, match in dim_fase.sort_values("data_dt").iterrows():
        df_match = df_fase[df_fase["match_id"] == match["match_id"]].copy()
        cards.append(_knockout_match_card(match, df_match))

    matches_grid = html.Div(cards, className="ko-matches-grid")

    # ---- Ranking da fase selecionada ----
    ranking_section = html.Section([
        html.Div([
            html.H2(f"Ranking — {fase_label}", className="section-title"),
        ], className="section-header"),
        _knockout_ranking(df_fase) or html.Div(),
    ], className="section")

    # ---- Grafico da fase selecionada ----
    chart = _knockout_chart(df_fase)
    chart_section = html.Section([
        html.Div([
            html.H2("Pontos por Participante", className="section-title"),
        ], className="section-header"),
        html.Div(chart, className="chart-wrapper") if chart else html.Div(
            html.P("Gráfico disponível após os primeiros resultados.", className="empty-text"),
            className="empty-state",
        ),
    ], className="section") if chart else html.Div()

    return html.Div([
        filter_bar,
        html.Div([
            html.Div([html.Span(fase_label, className="group-badge")],
                     style={"marginBottom": "1.25rem"}),
            summary,
        ]),
        html.Section([
            html.Div([
                html.H2(f"Jogos — {fase_label}", className="section-title"),
            ], className="section-header"),
            matches_grid,
        ], className="section"),
        html.Hr(className="section-divider"),
        ranking_section,
        html.Hr(className="section-divider"),
        chart_section,
    ])


# ---------------------------------------------------------------------------
# Layout & Callbacks
# ---------------------------------------------------------------------------

def layout():
    return html.Div([
        html.Div([
            html.H2("Mata-Mata", className="section-title"),
        ], className="section-header"),
        # Store para fase selecionada
        dcc.Store(id="mata-mata-fase", data="R32"),
        # Container: filtro + conteudo juntos
        html.Div(id="mata-mata-content"),
    ])


def register_callbacks(app):
    @app.callback(
        Output("mata-mata-fase", "data"),
        Input({"type": "fase-btn", "id": ALL}, "n_clicks"),
        State({"type": "fase-btn", "id": ALL}, "id"),
        State("mata-mata-fase", "data"),
        prevent_initial_call=True,
    )
    def update_fase(n_clicks_list, ids, current_fase):
        """Atualiza a fase selecionada ao clicar num botao."""
        ctx = callback_context
        if not ctx.triggered or not any(n for n in (n_clicks_list or []) if n):
            return current_fase
        triggered_prop = ctx.triggered[0]["prop_id"]
        try:
            triggered_id = json.loads(triggered_prop.split(".")[0])
            return triggered_id["id"]
        except Exception:
            return current_fase

    @app.callback(
        Output("mata-mata-content", "children"),
        Input("refresh-interval", "n_intervals"),
        Input("mata-mata-fase", "data"),
    )
    def update_mata_mata(n, fase):
        return _build_content(fase or "R32")
