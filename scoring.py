"""
scoring.py — Lógica pura de pontuação do bolão.
Regras:
  - Placar exato          → 3 pontos
  - Resultado correto     → 1 ponto (vencedor ou empate)
  - Errou                 → 0 pontos
  - Sem resultado ainda   → None
"""
import math


def calcular_pontos(palpite_h, palpite_a, real_h, real_a):
    """
    Retorna 3, 1, 0 ou None (sem resultado ainda).
    Aceita int/float/None; converte internamente.
    """
    try:
        if real_h is None or real_a is None:
            return None
        if isinstance(real_h, float) and math.isnan(real_h):
            return None
        if isinstance(real_a, float) and math.isnan(real_a):
            return None
        ph, pa = int(palpite_h), int(palpite_a)
        rh, ra = int(real_h), int(real_a)
    except (TypeError, ValueError):
        return None

    # Placar exato
    if ph == rh and pa == ra:
        return 3

    # Resultado correto (vencedor ou empate)
    def sinal(h, a):
        if h > a:
            return 1
        if h < a:
            return -1
        return 0

    if sinal(ph, pa) == sinal(rh, ra):
        return 1

    return 0


def label_pontos(pontos):
    """Retorna string legível para o placar."""
    if pontos is None:
        return "—"
    if pontos == 3:
        return "3 pts"
    if pontos == 1:
        return "1 pt"
    return "0 pts"


def cor_pontos(pontos):
    """Retorna classe CSS para o badge de pontos."""
    if pontos is None:
        return "badge-pendente"
    if pontos == 3:
        return "badge-exato"
    if pontos == 1:
        return "badge-resultado"
    return "badge-erro"
