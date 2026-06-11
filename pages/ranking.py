"""
pages/ranking.py — Aba 1: Ranking Geral + Jogos de Hoje.
"""
import pandas as pd
from dash import html, dcc
from dash.dependencies import Input, Output

from data_manager import get_full_df, get_bolao_data
from scoring import label_pontos, cor_pontos
from teams import flag_span


# ── Helpers ──────────────────────────────────────────────────────────────────

def _match_card(row):
    """Card clicável para uma partida → navega para Por Jogo."""
    match_id   = str(row["match_id"])
    score_real = None
    if pd.notna(row.get("score_home")) and pd.notna(row.get("score_away")):
        score_real = f"{int(row['score_home'])} – {int(row['score_away'])}"

    mandante_sigla  = str(row.get("mandante_sigla",  ""))
    visitante_sigla = str(row.get("visitante_sigla", ""))

    status = row.get("status")
    is_live = pd.notna(status) and status in ("IN_PLAY", "PAUSED")

    time_display = "Em Andamento" if is_live else row.get("hora", "")
    time_style = {"color": "var(--gold)", "fontWeight": "700"} if is_live else {}

    return html.Div([
        html.Div([
            html.Span(str(row.get("grupo", "")), className="group-badge"),
            html.Span(time_display, className="match-time", style=time_style),
        ], className="match-card-top"),

        html.Div([
            # Mandante
            html.Div([
                html.Div([
                    flag_span(mandante_sigla, "1.25rem"),
                    html.Span(mandante_sigla, className="team-code", style={"marginLeft": "0.5rem"}),
                ], style={"display": "flex", "alignItems": "center", "justifyContent": "center"}),
                html.Div(str(row.get("mandante_nome", "")), className="team-name"),
            ], className="team-block"),

            # Placar / VS
            html.Div([
                html.Div("vs", className="match-vs"),
                html.Div(
                    score_real or "–",
                    className="match-score-real" if score_real else "match-vs",
                    style={"fontSize": "0.75rem"} if not score_real else {}
                ),
            ], className="match-vs-block"),

            # Visitante
            html.Div([
                html.Div([
                    flag_span(visitante_sigla, "1.25rem"),
                    html.Span(visitante_sigla, className="team-code", style={"marginLeft": "0.5rem"}),
                ], style={"display": "flex", "alignItems": "center", "justifyContent": "center"}),
                html.Div(str(row.get("visitante_nome", "")), className="team-name"),
            ], className="team-block"),
        ], className="match-teams"),

        html.Span("Ver detalhes →", className="nav-hint"),
    ],
        id={"type": "nav-match", "id": match_id},
        n_clicks=0,
        className="match-card match-card--nav",
    )


def _ranking_table(df: pd.DataFrame):
    medals = ["1°", "2°", "3°"]

    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        pos       = i + 1
        pos_label = medals[i] if i < 3 else f"{pos}°"
        cls       = f"rank-row-{pos} rank-row--nav" if pos <= 3 else "rank-row--nav"
        member_id = str(row["member_id"])

        rows.append(html.Tr([
            html.Td(pos_label, className="rank-pos"),
            html.Td([
                str(row["name"]),
                html.Span("→", className="nav-row-hint"),
            ], className="rank-name"),
            html.Td(str(int(row["pontos_total"])),  className="rank-pts"),
            html.Td(str(int(row["exatos"])),        className="rank-cell rank-cell--green"),
            html.Td(str(int(row["resultados"])),    className="rank-cell rank-cell--amber"),
            html.Td(str(int(row["erros"])),         className="rank-cell rank-cell--red"),
            html.Td(str(int(row["pendentes"])),     className="rank-cell rank-cell--gray"),
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


def _build_content():
    result = get_full_df()
    if result is None:
        err = html.Div("Erro ao carregar os dados do bolão.", className="error-msg")
        return err, err

    df, dim_jogos, _ = result

    # Jogos de Hoje
    hoje       = pd.Timestamp.now().normalize().date()
    jogos_hoje = dim_jogos[dim_jogos["data_dt"].dt.date == hoje]

    if jogos_hoje.empty:
        proximo = dim_jogos[dim_jogos["data_dt"].dt.date > hoje].head(1)
        if not proximo.empty:
            prox_data = proximo.iloc[0]["data_dt"].strftime("%d/%m/%Y")
            jogos_card = html.Div([
                html.P(f"Sem jogos hoje. Próximo jogo: {prox_data}.", className="empty-text"),
            ], className="empty-state")
        else:
            jogos_card = html.Div(
                html.P("Nenhum jogo agendado.", className="empty-text"),
                className="empty-state"
            )
    else:
        jogos_card = html.Div(
            [_match_card(r) for _, r in jogos_hoje.iterrows()],
            className="matches-grid",
        )

    # Ranking
    ranking = (
        df.groupby(["member_id", "name"], as_index=False)
          .agg(
              pontos_total=("pontos", lambda x: x.dropna().sum()),
              exatos      =("pontos", lambda x: (x == 3).sum()),
              resultados  =("pontos", lambda x: (x == 1).sum()),
              erros       =("pontos", lambda x: (x == 0).sum()),
              pendentes   =("pontos", lambda x: x.isna().sum()),
          )
          .sort_values(["pontos_total", "exatos", "resultados"], ascending=False)
          .reset_index(drop=True)
    )

    return jogos_card, _ranking_table(ranking)


# ── Layout ────────────────────────────────────────────────────────────────────

def layout():
    return html.Div([
        # Jogos de Hoje
        html.Section([
            html.Div([
                html.H2("Jogos de Hoje", className="section-title"),
            ], className="section-header"),
            html.Div(id="ranking-jogos-hoje"),
        ], className="section"),

        html.Hr(className="section-divider"),

        # Classificação Geral
        html.Section([
            html.Div([
                html.H2("Classificação Geral", className="section-title"),
            ], className="section-header"),
            html.Div(id="ranking-table-div"),
        ], className="section"),
    ])


# ── Callbacks ─────────────────────────────────────────────────────────────────

def register_callbacks(app):
    @app.callback(
        [
            Output("ranking-jogos-hoje", "children"),
            Output("ranking-table-div",  "children"),
        ],
        Input("refresh-interval", "n_intervals"),
    )
    def update_ranking(n):
        return _build_content()
