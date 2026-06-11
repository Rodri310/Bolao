"""
teams.py — Mapeamento de siglas de seleções para códigos ISO de bandeira.
Usado com a biblioteca flag-icons (https://flagicons.lipis.dev/).

flag_span(sigla) → html.Span com a classe CSS da bandeira correta.
"""
from dash import html

# sigla bolão → código ISO alpha-2 (flag-icons)
TEAM_FLAGS: dict[str, str] = {
    "ALG": "dz",    # Argélia
    "ARG": "ar",    # Argentina
    "AUS": "au",    # Austrália
    "AUT": "at",    # Áustria
    "BEL": "be",    # Bélgica
    "BIH": "ba",    # Bósnia-Herzegovina
    "BRA": "br",    # Brasil
    "CAN": "ca",    # Canadá
    "CIV": "ci",    # Costa do Marfim
    "COD": "cd",    # RD do Congo
    "COL": "co",    # Colômbia
    "CPV": "cv",    # Cabo Verde
    "CRO": "hr",    # Croácia
    "CUW": "cw",    # Curaçao
    "CZE": "cz",    # República Tcheca
    "ECU": "ec",    # Equador
    "EGY": "eg",    # Egito
    "ENG": "gb-eng",# Inglaterra
    "ESP": "es",    # Espanha
    "FRA": "fr",    # França
    "GER": "de",    # Alemanha
    "GHA": "gh",    # Gana
    "HAI": "ht",    # Haiti
    "IRN": "ir",    # Irã
    "IRQ": "iq",    # Iraque
    "JOR": "jo",    # Jordânia
    "JPN": "jp",    # Japão
    "KOR": "kr",    # Coreia do Sul
    "KSA": "sa",    # Arábia Saudita
    "MAR": "ma",    # Marrocos
    "MEX": "mx",    # México
    "NED": "nl",    # Holanda
    "NOR": "no",    # Noruega
    "NZL": "nz",    # Nova Zelândia
    "PAN": "pa",    # Panamá
    "PAR": "py",    # Paraguai
    "POR": "pt",    # Portugal
    "QAT": "qa",    # Qatar
    "RSA": "za",    # África do Sul
    "SCO": "gb-sct",# Escócia
    "SEN": "sn",    # Senegal
    "SUI": "ch",    # Suíça
    "SWE": "se",    # Suécia
    "TUN": "tn",    # Tunísia
    "TUR": "tr",    # Turquia
    "URU": "uy",    # Uruguai
    "USA": "us",    # Estados Unidos
    "UZB": "uz",    # Uzbequistão
}


def flag_span(sigla: str, size: str = "1.25rem") -> html.Span:
    """Retorna um <span> com a bandeira do país, usando flag-icons CSS."""
    code = TEAM_FLAGS.get(str(sigla).upper(), "")
    if code:
        return html.Span(
            className=f"fi fi-{code}",
            title=sigla,
            style={
                "fontSize":    size,
                "borderRadius": "3px",
                "flexShrink":  "0",
                "display":     "inline-block",
                "verticalAlign": "middle",
                "boxShadow":   "0 1px 3px rgba(0,0,0,0.4)",
            },
        )
    # Fallback: sigla em texto pequeno
    return html.Span(sigla, style={"fontSize": "0.7rem", "color": "#64748b"})
