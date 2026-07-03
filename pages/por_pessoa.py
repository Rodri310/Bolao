"""
pages/por_pessoa.py — Aba 4: Todos os palpites e pontuação de um participante.
"""
import pandas as pd
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


def _summary_cards(df_pessoa: pd.DataFrame):
    total      = int(df_pessoa["pontos"].dropna().sum())
    exatos     = int((df_pessoa["pontos"] == 3).sum())
    resultados = int((df_pessoa["pontos"] == 1).sum())
    erros      = int((df_pessoa["pontos"] == 0).sum())
    pendentes  = int(df_pessoa["pontos"].isna().sum())

    def card(value, label, variant):
        return html.Div([
            html.Div(str(value), className="stat-value"),
            html.Div(label, className="stat-label"),
        ], className=f"stat-card stat-card--{variant}")

    return html.Div([
        card(total,      "Pontos Totais",    "gold"),
        card(exatos,     "Exatos",         "green"),
        card(resultados, "Resultados",     "amber"),
        card(erros,      "Erros",          "red"),
        card(pendentes,  "Pendentes",      "gray"),
    ], className="stats-row")


def _palpites_table(df_pessoa: pd.DataFrame):
    df_sorted = df_pessoa.sort_values("data_dt", na_position="last")

    rows = []
    for _, p in df_sorted.iterrows():
        data_fmt = (
            p["data_dt"].strftime("%d/%m")
            if pd.notna(p.get("data_dt")) else "—"
        )

        jogo = (
            f"{p.get('mandante_sigla','?')} × {p.get('visitante_sigla','?')}"
        )
        jogo_completo = (
            f"{p.get('mandante_nome', p.get('mandante_sigla','?'))} "
            f"× {p.get('visitante_nome', p.get('visitante_sigla','?'))}"
        )

        palpite = f"{int(p['placar_mandante'])} × {int(p['placar_visitante'])}"

        has_result = pd.notna(p.get("score_home")) and pd.notna(p.get("score_away"))
        result_cell = (
            html.Span(
                f"{int(p['score_home'])} – {int(p['score_away'])}",
                className="result-chip",
                style={"fontSize": "0.8rem", "padding": "2px 8px"}
            ) if has_result
            else html.Span("—", style={"color": "#475569"})
        )

        rows.append(html.Tr([
            html.Td(data_fmt, style={"color": "#64748b", "fontSize": "0.8rem"}),
            html.Td([
                html.Div([
                    flag_span(p.get("mandante_sigla", ""), "1.1rem"),
                    html.Span(jogo, style={"margin": "0 0.4rem"}),
                    flag_span(p.get("visitante_sigla", ""), "1.1rem"),
                ], style={"display": "flex", "alignItems": "center", "fontWeight": "700", "fontSize": "0.85rem"}),
                html.Div(jogo_completo, style={"color": "#64748b", "fontSize": "0.72rem", "marginTop": "0.25rem"}),
            ]),
            html.Td(_grupo_label(str(p.get("grupo", ""))),
                    style={"color": "#94a3b8", "fontSize": "0.8rem"}),
            html.Td(palpite, className="palpite-score"),
            html.Td(result_cell),
            html.Td(_score_badge(p["pontos"])),
        ]))

    return html.Div(
        html.Table([
            html.Thead(html.Tr([
                html.Th("Data"),
                html.Th("Jogo"),
                html.Th("Grupo"),
                html.Th("Palpite"),
                html.Th("Resultado"),
                html.Th("Pts"),
            ])),
            html.Tbody(rows),
        ], className="palpites-table"),
        className="palpites-table-wrapper card",
    )


def _build_person_content(member_id: str):
    result = get_full_df()
    if result is None:
        return html.Div("Erro ao carregar dados.", className="error-msg")

    df, _, _ = result
    df_pessoa = df[df["member_id"] == member_id].copy()

    if df_pessoa.empty:
        return html.Div([
            html.Div(className="empty-icon"),
            html.Div("Participante sem palpites.", className="empty-text"),
        ], className="empty-state")

    name = str(df_pessoa.iloc[0].get("name", member_id))

    return html.Div([
        html.Div([
            html.Span(name, style={"fontWeight": "700", "fontSize": "1.25rem",
                                   "color": "var(--gold)"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "0.6rem",
                  "marginBottom": "1.5rem"}),

        _summary_cards(df_pessoa),

        html.Div([
            html.Span("", className="section-icon"),
            html.H3("Todos os Palpites", className="section-title",
                    style={"fontSize": "1rem"}),
        ], className="section-header"),

        _palpites_table(df_pessoa),
    ])


# ── Layout ────────────────────────────────────────────────────────────────────

def layout(initial_member=None):
    result = get_full_df()
    options = []
    default = initial_member  # pode vir da navegação cruzada

    if result is not None:
        _, _, dim_membros = result
        for _, row in dim_membros.iterrows():
            options.append({
                "label": str(row.get("name", row["member_id"])),
                "value": str(row["member_id"]),
            })
        options.sort(key=lambda o: o["label"])
        if options and default is None:
            default = options[0]["value"]

    return html.Div([
        html.Div([
            html.Span("", className="section-icon"),
            html.H2("Por Pessoa", className="section-title"),
        ], className="section-header"),

        dcc.Dropdown(
            id="por-pessoa-dropdown",
            options=options,
            value=default,
            clearable=False,
            placeholder="Selecione um participante…",
            style={
                "background": "#0d1421",
                "color": "#e2e8f0",
                "border": "1px solid rgba(255,255,255,0.08)",
                "borderRadius": "10px",
                "marginBottom": "1.5rem",
            },
        ),

        html.Div(id="por-pessoa-content"),
    ])


# ── Callbacks ─────────────────────────────────────────────────────────────────

def register_callbacks(app):
    @app.callback(
        Output("por-pessoa-content", "children"),
        Input("por-pessoa-dropdown", "value"),
    )
    def update_person(member_id):
        if not member_id:
            return html.Div([
                html.Div(className="empty-icon"),
                html.Div("Selecione um participante acima.", className="empty-text"),
            ], className="empty-state")
        return _build_person_content(str(member_id))
