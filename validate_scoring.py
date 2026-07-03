import logging
logging.disable(logging.CRITICAL)
from data_manager import get_full_df

result = get_full_df()
df, dim_jogos, _ = result

# Jogo #82 BEL x SEN
jogo82 = df[df['match_id'] == '82'].copy()
score_info = dim_jogos[dim_jogos['match_id'] == '82'][['score_home','score_away','score_home_90','score_away_90']].iloc[0]
print("Jogo #82 BEL x SEN")
print(f"  Placar final:  {int(score_info.score_home)}-{int(score_info.score_away)}")
print(f"  Placar 90min:  {int(score_info.score_home_90)}-{int(score_info.score_away_90)}")
print()
print("Palpites e pontos:")
df82 = jogo82.sort_values("pontos", key=lambda s: s.fillna(-1), ascending=False)
for _, r in df82.iterrows():
    pal = f"{int(r.placar_mandante)}-{int(r.placar_visitante)}"
    pts = r["pontos"]
    pts_str = str(int(pts)) if pts is not None and str(pts) != "nan" else "None"
    nome = str(r.get("name", r["member_id"]))
    print(f"  {nome:<25}  palpite={pal}  pts={pts_str}")
