"""
Data_get_knockout.py — Parser para o HTML estatico dos palpites do mata-mata.

O HTML das oitavas (palpites-16avos.html) e uma tabela visual, diferente do
HTML principal que contem um bloco `const DATA = {...}`.

Estrutura real do HTML (sem thead/tbody explicitos):
  <table>
    <tr>  <!-- primeira linha: cabecalhos dos jogos -->
      <th class="pl sticky-l">Participante</th>
      <th class="mh fin">  <!-- jogo finalizado -->
        <div class="mn">#73</div>
        <div class="tc">RSA x CAN</div>
        <div class="dt">28/06 16:00</div>
        <div class="res">0-1</div>
      </th>
      ...
    </tr>
    <tr>  <!-- linhas seguintes: palpites por participante -->
      <td class="pl sticky-l">Nome do Participante</td>
      <td class="c ok">2-1</td>   <!-- palpite -->
      <td class="c empty">.</td>  <!-- sem palpite -->
      ...
    </tr>
  </table>

Extrai:
  - dim_jogos_r32    : jogos das oitavas (match_id, siglas, data, etc.)
  - fato_palpites_r32: palpites de cada participante (por nome)
"""

import re
import pandas as pd
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# Parser auxiliar de baixo nivel
# ---------------------------------------------------------------------------

class _KnockoutHTMLParser(HTMLParser):
    """Le o HTML e extrai cabecalhos de jogos e palpites dos participantes."""

    def __init__(self):
        super().__init__()
        self._in_table = False
        self._row_index = 0        # 0 = cabecalho, 1+ = participantes
        self._in_tr = False
        self._in_th_mh = False     # cabecalho de jogo
        self._in_td_player = False # nome do participante
        self._in_td_guess = False  # celula de palpite
        self._in_div = False
        self._div_class = ""
        self._text_buf = ""

        # Acumula o cabecalho do jogo atual
        self._cur_header: dict = {}

        # Estado da linha de participante atual
        self._cur_name: str = ""
        self._cur_guesses: list = []   # list of str|None
        self._col_idx: int = 0         # qual coluna de jogo estamos

        # Resultados finais
        self.match_headers: list[dict] = []   # [{mn, tc, dt, res}, ...]
        self.rows: list[dict] = []            # [{name, guesses}, ...]

    # ---- helpers --------------------------------------------------------

    @staticmethod
    def _cls(attrs):
        for k, v in attrs:
            if k == "class":
                return v or ""
        return ""

    # ---- handlers -------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        cls = self._cls(attrs)

        if tag == "table":
            self._in_table = True

        if not self._in_table:
            return

        if tag == "tr":
            self._in_tr = True
            if self._row_index > 0:
                # nova linha de participante
                self._cur_name = ""
                self._cur_guesses = []
                self._col_idx = 0

        if tag == "th" and "mh" in cls:
            self._in_th_mh = True
            self._cur_header = {}

        if tag == "td" and self._row_index > 0:
            if "sticky-l" in cls:
                self._in_td_player = True
            elif "c" in cls.split():
                self._in_td_guess = True
                self._text_buf = ""

        if tag == "div" and (self._in_th_mh or self._in_td_guess):
            self._in_div = True
            self._div_class = cls
            self._text_buf = ""

    def handle_endtag(self, tag):
        if tag == "table":
            self._in_table = False

        if not self._in_table:
            return

        if tag == "div" and self._in_div:
            self._in_div = False
            text = self._text_buf.strip()
            if self._in_th_mh:
                c = self._div_class
                if "mn" in c:
                    self._cur_header["mn"] = text
                elif "tc" in c:
                    self._cur_header["tc"] = text
                elif "dt" in c:
                    self._cur_header["dt"] = text
                elif "res" in c:
                    self._cur_header["res"] = text
            self._text_buf = ""

        if tag == "th" and self._in_th_mh:
            self._in_th_mh = False
            if self._cur_header.get("mn", "").startswith("#"):
                self.match_headers.append(dict(self._cur_header))
            self._cur_header = {}

        if tag == "td":
            self._in_td_player = False
            self._in_td_guess = False

        if tag == "tr" and self._in_tr:
            self._in_tr = False
            if self._row_index == 0:
                # primeira linha = cabecalho; incrementa para proximas serem participantes
                self._row_index = 1
            else:
                # linha de participante
                if self._cur_name:
                    self.rows.append({
                        "name": self._cur_name.strip(),
                        "guesses": list(self._cur_guesses),
                    })
                self._row_index += 1

    def handle_data(self, data):
        if self._in_div:
            self._text_buf += data

        if self._in_td_player:
            self._cur_name += data

        if self._in_td_guess and not self._in_div:
            text = data.strip()
            # "." ou "-" = sem palpite; "—" = sem resultado
            if text and text not in (".", "·", "—", ""):
                self._cur_guesses.append(text)
            else:
                self._cur_guesses.append(None)
            self._in_td_guess = False  # consome uma vez por td


# ---------------------------------------------------------------------------
# Mapeamento de sigla do HTML das oitavas -> sigla do bolao
# ---------------------------------------------------------------------------

_LABEL_TO_SIGLA = {
    "RSA": "RSA",  "CAN": "CAN",  "BRA": "BRA",  "JPN": "JPN",
    "GER": "GER",  "ALE": "GER",  "PAR": "PAR",
    "NED": "NED",  "HOL": "NED",  "MAR": "MAR",
    "CIV": "CIV",  "NOR": "NOR",  "FRA": "FRA",  "SWE": "SWE",
    "MEX": "MEX",  "ECU": "ECU",
    "ENG": "ENG",  "ING": "ENG",  "COD": "COD",
    "BEL": "BEL",  "SEN": "SEN",
    "USA": "USA",  "EUA": "USA",  "BIH": "BIH",
    "ESP": "ESP",  "AUT": "AUT",  "POR": "POR",  "CRO": "CRO",
    "SUI": "SUI",  "ALG": "ALG",  "AUS": "AUS",
    "EGY": "EGY",  "EGI": "EGY",
    "ARG": "ARG",  "CPV": "CPV",  "COL": "COL",
    "GHA": "GHA",  "GAN": "GHA",
}


def _parse_tc(tc: str):
    """'RSA x CAN' -> ('RSA', 'CAN')"""
    parts = [p.strip().upper() for p in tc.split("x")]
    if len(parts) != 2:
        return None, None
    return _LABEL_TO_SIGLA.get(parts[0], parts[0]), _LABEL_TO_SIGLA.get(parts[1], parts[1])


def _parse_score(s: str):
    """'2-1' -> (2, 1); invalido -> (None, None)"""
    if not s:
        return None, None
    m = re.match(r"^(\d+)-(\d+)$", s.strip())
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


# ---------------------------------------------------------------------------
# Funcao publica
# ---------------------------------------------------------------------------

def extrair_dados_knockout(caminho_arquivo: str):
    """
    Parseia o HTML estatico das oitavas e retorna:
      (dim_jogos_r32, fato_palpites_r32)

    dim_jogos_r32 colunas:
      match_id, mandante_sigla, visitante_sigla, hora, data_jogo, grupo,
      mandante_nome, visitante_nome

    fato_palpites_r32 colunas:
      member_name, match_id, placar_mandante, placar_visitante
      (member_id sera resolvido externamente pelo nome)
    """
    print(f"Carregando palpites do mata-mata de: {caminho_arquivo}")

    with open(caminho_arquivo, "r", encoding="utf-8") as f:
        html_content = f.read()

    p = _KnockoutHTMLParser()
    p.feed(html_content)

    # ---- dim_jogos_r32 --------------------------------------------------
    jogos = []
    for h in p.match_headers:
        mn  = h.get("mn", "")   # "#73"
        tc  = h.get("tc", "")   # "RSA x CAN"
        dt  = h.get("dt", "")   # "28/06 16:00"

        match_id = mn.lstrip("#").strip() if mn.startswith("#") else None
        if not match_id:
            continue

        home_sigla, away_sigla = _parse_tc(tc)

        parts = dt.split()
        data_jogo = parts[0] if parts else ""
        hora      = parts[1] if len(parts) > 1 else ""

        jogos.append({
            "match_id":        match_id,
            "mandante_sigla":  home_sigla or "",
            "visitante_sigla": away_sigla or "",
            "hora":            hora,
            "data_jogo":       data_jogo,
            "grupo":           "R32",
            "mandante_nome":   home_sigla or "",
            "visitante_nome":  away_sigla or "",
        })

    dim_jogos_r32 = pd.DataFrame(jogos) if jogos else pd.DataFrame(
        columns=["match_id","mandante_sigla","visitante_sigla",
                 "hora","data_jogo","grupo","mandante_nome","visitante_nome"]
    )
    print(f"  -> {len(dim_jogos_r32)} jogos das oitavas")

    col_match_ids = [j["match_id"] for j in jogos]

    # ---- fato_palpites_r32 ----------------------------------------------
    palpites = []
    for row in p.rows:
        name   = (row["name"] or "").strip()
        guesses = row["guesses"]

        for col_idx, guess_str in enumerate(guesses):
            if col_idx >= len(col_match_ids):
                break
            match_id = col_match_ids[col_idx]
            ph, pa = _parse_score(guess_str) if guess_str else (None, None)
            if ph is None:
                continue
            palpites.append({
                "member_name":     name,
                "match_id":        match_id,
                "placar_mandante": ph,
                "placar_visitante": pa,
            })

    fato_palpites_r32 = pd.DataFrame(palpites) if palpites else pd.DataFrame(
        columns=["member_name","match_id","placar_mandante","placar_visitante"]
    )
    print(f"  -> {len(fato_palpites_r32)} palpites das oitavas")

    return dim_jogos_r32, fato_palpites_r32
