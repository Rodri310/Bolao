"""
pages/por_dia.py — Aba 2: Palpites e ranking de um dia específico.
"""
import pandas as pd
from dash import html, dcc
from dash.dependencies import Input, Output
import dash_mantine_components as dmc

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


def _result_chip(row):
    status = row.get("status")
    is_live = pd.notna(status) and status in ("IN_PLAY", "PAUSED")
    if pd.notna(row.get("score_home")) and pd.notna(row.get("score_away")):
        sh, sa = int(row["score_home"]), int(row["score_away"])
        if is_live:
            return html.Span(f"{sh} – {sa}", className="result-chip", style={"borderColor": "var(--gold)", "color": "var(--gold)"})
        return html.Span(f"{sh} – {sa}", className="result-chip")
    return html.Span("Aguardando resultado", className="result-chip result-chip--pending")


def _match_section(match_row, df_palpites):
    """Seção de uma partida: cabeçalho + tabela de palpites."""
    mandante_sigla  = str(match_row.get("mandante_sigla",  ""))
    visitante_sigla = str(match_row.get("visitante_sigla", ""))
    mandante_nome   = match_row.get("mandante_nome",  mandante_sigla)
    visitante_nome  = match_row.get("visitante_nome", visitante_sigla)
    hora            = match_row.get("hora", "")
    grupo           = match_row.get("grupo", "")

    status = match_row.get("status")
    is_live = pd.notna(status) and status in ("IN_PLAY", "PAUSED")

    time_display = "Em Andamento" if is_live else hora
    time_style = {"color": "var(--gold)", "fontSize": "0.8rem", "fontWeight": "700"} if is_live else {"color": "#64748b", "fontSize": "0.8rem"}

    header = html.Div([
        html.Div([
            html.Span(_grupo_label(str(grupo)), className="group-badge"),
            html.Div([
                flag_span(mandante_sigla, "1.1rem"),
                html.Span(mandante_sigla,  style={"fontWeight": "700", "color": "#e2e8f0"}),
                html.Span("×", style={"color": "#475569", "margin": "0 0.35rem"}),
                html.Span(visitante_sigla, style={"fontWeight": "700", "color": "#e2e8f0"}),
                flag_span(visitante_sigla, "1.1rem"),
            ], style={"display": "flex", "alignItems": "center", "gap": "0.4rem"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "0.75rem"}),
        html.Div([
            _result_chip(match_row),
            html.Span(time_display, style=time_style),
        ], style={"display": "flex", "alignItems": "center", "gap": "0.75rem"}),
    ], className="day-match-header")

    # Tabela de palpites
    if df_palpites.empty:
        body_content = html.P("Nenhum palpite registrado.", className="empty-text",
                              style={"padding": "1rem 0"})
    else:
        palpite_rows = []
        for _, p in df_palpites.sort_values("pontos", key=lambda s: s.fillna(-1), ascending=False).iterrows():
            palpite_rows.append(html.Tr([
                html.Td(str(p.get("name", p["member_id"])), className="rank-name"),
                html.Td(
                    f"{int(p['placar_mandante'])} × {int(p['placar_visitante'])}",
                    className="palpite-score"
                ),
                html.Td(_score_badge(p["pontos"])),
            ]))

        body_content = html.Div(
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Participante"),
                    html.Th("Palpite"),
                    html.Th("Pontuação"),
                ])),
                html.Tbody(palpite_rows),
            ], className="palpites-table"),
            className="palpites-table-wrapper",
        )

    body = html.Div(body_content, className="day-match-body")
    return html.Div([header, body], className="day-match-section")


def _day_mini_ranking(df_day):
    """Mini-ranking do dia."""
    ranking = (
        df_day.groupby(["member_id", "name"], as_index=False)
              .agg(pts=("pontos", lambda x: x.dropna().sum()))
              .sort_values("pts", ascending=False)
              .reset_index(drop=True)
    )

    if ranking.empty or ranking["pts"].sum() == 0:
        return None

    rows = []
    for i, (_, r) in enumerate(ranking.iterrows()):
        pos = f"{i+1}°"
        rows.append(html.Div([
            html.Span(pos,             className="day-ranking-pos"),
            html.Span(str(r["name"]), className="day-ranking-name"),
            html.Span(f"{int(r['pts'])} pts", className="day-ranking-pts"),
        ], className="day-ranking-row"))

    return html.Div([
        html.Div([
            html.H3("Ranking do Dia", className="section-title",
                    style={"fontSize": "1rem"}),
        ], className="section-header", style={"marginBottom": "0.75rem"}),
        html.Div(rows, className="card"),
    ])


def _build_day_content(selected_date_str: str):
    result = get_full_df()
    if result is None:
        return html.Div("Erro ao carregar dados.", className="error-msg")

    df, dim_jogos, _ = result

    try:
        sel_date = pd.Timestamp(selected_date_str).normalize().date()
    except Exception:
        return html.Div("Data inválida.", className="error-msg")

    jogos_dia = dim_jogos[dim_jogos["data_dt"].dt.date == sel_date]

    if jogos_dia.empty:
        return html.Div(
            html.P("Nenhum jogo neste dia.", className="empty-text"),
            className="empty-state"
        )

    match_ids_dia = set(jogos_dia["match_id"].tolist())
    df_dia = df[df["match_id"].isin(match_ids_dia)].copy()

    sections = []
    for _, match in jogos_dia.iterrows():
        df_match = df_dia[df_dia["match_id"] == match["match_id"]]
        sections.append(_match_section(match, df_match))

    mini_rank = _day_mini_ranking(df_dia)
    children  = sections + ([html.Hr(className="section-divider"), mini_rank] if mini_rank else [])
    return html.Div(children)


# ── Layout ────────────────────────────────────────────────────────────────────

def layout():
    result   = get_full_df()
    min_date = None
    max_date = None
    default  = None

    if result is not None:
        _, dim_jogos, _ = result
        dates = sorted(dim_jogos["data_dt"].dropna().dt.date.unique())
        if dates:
            min_date = str(dates[0])
            max_date = str(dates[-1])
            hoje     = pd.Timestamp.now(tz="America/Sao_Paulo").normalize().date()
            default  = next((str(d) for d in dates if d >= hoje), str(dates[-1]))

    return html.Div([
        html.Div([
            html.H2("Por Dia", className="section-title"),
        ], className="section-header"),

        html.Div([
            dmc.DatePickerInput(
                id="por-dia-date-picker",
                minDate=min_date,
                maxDate=max_date,
                value=default,
                valueFormat="DD/MM/YYYY",
                firstDayOfWeek=1,
                placeholder="Selecione uma data…",
                styles={
                    "input": {
                        "backgroundColor": "var(--bg)",
                        "borderColor": "var(--gold)",
                        "color": "var(--text)",
                        "fontFamily": "Poppins, sans-serif",
                    }
                },
                w=200,
            ),
        ], style={"marginBottom": "1.5rem"}),

        html.Div(id="por-dia-content"),
    ])


# ── Callbacks ─────────────────────────────────────────────────────────────────

def register_callbacks(app):
    @app.callback(
        Output("por-dia-content", "children"),
        Input("por-dia-date-picker", "value"),
    )
    def update_day(selected_date):
        if not selected_date:
            return html.Div(
                html.P("Selecione um dia no calendário acima.", className="empty-text"),
                className="empty-state"
            )
        return _build_day_content(selected_date)
