import json
import re
import pandas as pd

def extrair_dados_bolao(caminho_arquivo):
    print("Iniciando a extração dos dados...")
    
    # 1. Ler o conteúdo do arquivo HTML
    with open(caminho_arquivo, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # 2. Isolar o objeto JSON dentro do script
    # Usamos regex para encontrar o bloco "const DATA = {...};"
    match = re.search(r'const DATA = (\{.*?\});', html_content, re.DOTALL)

    if not match:
        print("Erro: Não foi possível encontrar a variável DATA no HTML.")
        return

    # 3. Converter a string extraída para um dicionário Python
    json_str = match.group(1)
    data = json.loads(json_str)
    
    # ---------------------------------------------------------
    # 4. Modelagem: Construindo a Dimensão de Jogos (dim_jogos)
    # ---------------------------------------------------------
    dim_jogos = pd.DataFrame(data['matches'])
    # Renomeando as colunas para facilitar o uso no Power BI ou Streamlit
    dim_jogos = dim_jogos.rename(columns={
        'id': 'match_id', 
        't': 'hora', 
        'day': 'data_jogo', 
        'g': 'grupo',
        'hc': 'mandante_sigla', 
        'ac': 'visitante_sigla',
        'hn': 'mandante_nome', 
        'an': 'visitante_nome'
    })
    
    # ---------------------------------------------------------
    # 5. Modelagem: Construindo a Dimensão de Membros (dim_membros)
    # ---------------------------------------------------------
    dim_membros = pd.DataFrame(data['members'])
    dim_membros = dim_membros.rename(columns={'id': 'member_id'})
    dim_membros = dim_membros.drop(columns=['owner'], errors='ignore')
    
    # ---------------------------------------------------------
    # 6. Modelagem: Construindo a Tabela Fato (fato_palpites)
    # ---------------------------------------------------------
    # O JSON original estrutura os palpites como: { member_id: { match_id: [placar_mandante, placar_visitante] } }
    # Precisamos transformar isso em linhas (achatar os dados)
    palpites_list = []
    
    for member_id, matches in data['pred'].items():
        for match_id, score in matches.items():
            palpites_list.append({
                'member_id': member_id,
                'match_id': match_id,
                'placar_mandante': score[0],
                'placar_visitante': score[1]
            })
            
    fato_palpites = pd.DataFrame(palpites_list)
    
    return dim_jogos, dim_membros, fato_palpites

def obter_dados_consolidados(caminho_arquivo):
    dim_jogos, dim_membros, fato_palpites = extrair_dados_bolao(caminho_arquivo)
    
    # Garantir compatibilidade de tipos para o join
    dim_jogos['match_id'] = dim_jogos['match_id'].astype(str)
    dim_membros['member_id'] = dim_membros['member_id'].astype(str)
    fato_palpites['match_id'] = fato_palpites['match_id'].astype(str)
    fato_palpites['member_id'] = fato_palpites['member_id'].astype(str)
    
    # Mesclar as tabelas
    df_consolidado = pd.merge(fato_palpites, dim_membros, on='member_id', how='left')
    df_consolidado = pd.merge(df_consolidado, dim_jogos, on='match_id', how='left')
    
    return df_consolidado