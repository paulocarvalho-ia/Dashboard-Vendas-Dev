import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
import os
from io import BytesIO
from zoneinfo import ZoneInfo

# ============================================================
# CONFIGURAÇÃO DA PÁGINA (BARRA LATERAL ABERTA POR PADRÃO)
# ============================================================
st.set_page_config(
    page_title="Dashboard - Positivação & Cobertura",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Dashboard de Positivação e Cobertura")
st.caption("4 Elos Distribuidora Ltda. - Centro de Custo 622")

# ============================================================
# DATAS DE CONTROLE (MANUAL + FUSO BRASIL COM ZONEINFO)
# ============================================================
# ⚠️ ALTERE MANUALMENTE esta data quando fizer um deploy do código
COMPILATION_DATE = "21/07/2025 10:00"  # Formato: DD/MM/AAAA HH:MM (horário de Brasília)

# ============================================================
# CONEXÃO COM GOOGLE SHEETS
# ============================================================
SHEET_ID = "100LtVtmS76bT2CJd-EIb-bHTgX3F1BVm8Er5vUa-VYQ"

@st.cache_data(ttl=300)
def load_data():
    url_base = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet="

    df_base = pd.read_csv(url_base + "BASE")
    df_bi = pd.read_csv(url_base + "BI")

    # Data dos dados no fuso brasileiro
    data_dados = datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M')

    # Padronizar nomes da BASE
    df_base = df_base.rename(columns={
        'cd_clien': 'codigo_cliente',
        'nome_cliente': 'nome_cliente',
        'nome_vendedor': 'nome_vendedor_base',
        'Cliente_Coligacao': 'Cliente_Coligacao',
        'Coordenador': 'Nome_Coordenador'
    })

    # Padronizar nomes da BI
    df_bi = df_bi.rename(columns={
        'Código Cliente': 'codigo_cliente',
        'Nome_Vendedor_Ajustado': 'nome_vendedor_bi',
        'Ano e Mês': 'Ano_e_Mes',
        'Nome Fabricante': 'Nome_Fabricante'
    })

    # Converter data
    df_bi['Data'] = pd.to_datetime(df_bi['Ano_e_Mes'] + '-01', errors='coerce')
    df_bi['Mês'] = df_bi['Data'].dt.month
    df_bi['Ano'] = df_bi['Data'].dt.year
    df_bi['Mês_Ano'] = df_bi['Data'].dt.to_period('M').astype(str)

    # Merge: BASE + BI por código E vendedor
    df_merged = df_bi.merge(
        df_base[['codigo_cliente', 'nome_cliente', 'nome_vendedor_base', 'Cliente_Coligacao', 'Nome_Coordenador']],
        left_on=['codigo_cliente', 'nome_vendedor_bi'],
        right_on=['codigo_cliente', 'nome_vendedor_base'],
        how='left'
    )

    # Fallback: merge só por código
    df_fallback = df_bi.merge(
        df_base[['codigo_cliente', 'nome_cliente', 'nome_vendedor_base', 'Cliente_Coligacao', 'Nome_Coordenador']],
        on='codigo_cliente',
        how='left',
        suffixes=('', '_fb')
    )

    for col in ['nome_cliente', 'Cliente_Coligacao', 'Nome_Coordenador']:
        if col in df_merged.columns and f'{col}_fb' in df_fallback.columns:
            df_merged[col] = df_merged[col].fillna(df_fallback[f'{col}_fb'])

    df_merged['nome_vendedor'] = df_merged['nome_vendedor_bi']

    return df_base, df_bi, df_merged, data_dados

if st.sidebar.button("🔄 Atualizar Dados Agora"):
    st.cache_data.clear()
    st.rerun()

df_base, df_bi, df_merged, data_dados = load_data()

# ============================================================
# LISTA DE INDÚSTRIAS
# ============================================================
INDUSTRIAS = sorted(df_bi['Nome_Fabricante'].dropna().unique())
INDUSTRIAS = [i for i in INDUSTRIAS if i.strip() != '']
TOTAL_INDUSTRIAS = len(INDUSTRIAS)

# ============================================================
# FILTROS (VENDEDOR OBRIGATÓRIO, BARRA LATERAL ABERTA)
# ============================================================
st.sidebar.header("🎯 Filtros")

# Botão limpar filtros
st.sidebar.markdown(
    """
    <form action="" method="get" style="margin-bottom: 10px;">
        <button type="submit" style="
            width: 100%; 
            padding: 8px 12px; 
            border-radius: 8px; 
            border: 1px solid #555; 
            background-color: #333; 
            color: #f0f0f0; 
            cursor: pointer; 
            font-size: 14px;
            font-family: 'Source Sans Pro', sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        ">
        🧹 Limpar Filtros
        </button>
    </form>
    """,
    unsafe_allow_html=True
)

if not st.query_params:
    for key in ['vendedor', 'coligacao', 'ano', 'mes', 'industria_filtro', 'modo_gap']:
        st.session_state.pop(key, None)

# --- VENDEDOR (OBRIGATÓRIO) ---
lista_vendedores = sorted(df_base['nome_vendedor_base'].dropna().unique().tolist())
if 'vendedor' not in st.session_state or st.session_state['vendedor'] not in lista_vendedores:
    st.session_state['vendedor'] = None

vendedor_selecionado = st.sidebar.selectbox(
    "Selecione o Vendedor",
    [""] + lista_vendedores,
    index=0 if st.session_state['vendedor'] is None else lista_vendedores.index(st.session_state['vendedor']) + 1,
    key='vendedor_select'
)

if vendedor_selecionado == "":
    st.session_state['vendedor'] = None
    st.warning("Por favor, selecione um vendedor para visualizar os dados.")
    st.stop()
else:
    st.session_state['vendedor'] = vendedor_selecionado

# --- EXIBIR NOME DO VENDEDOR E COORDENADOR ---
vendedor_info = df_base[df_base['nome_vendedor_base'] == vendedor_selecionado].iloc[0]
coordenador_nome = vendedor_info['Nome_Coordenador'] if pd.notna(vendedor_info['Nome_Coordenador']) else "Não informado"
st.markdown(f"**Vendedor:** {vendedor_selecionado}")
st.markdown(f"**Coordenador:** {coordenador_nome}")

# --- COLIGAÇÃO ---
clientes_do_vendedor = df_base[df_base['nome_vendedor_base'] == vendedor_selecionado]['codigo_cliente'].unique()
coligacoes_filtradas = df_base[df_base['codigo_cliente'].isin(clientes_do_vendedor)]['Cliente_Coligacao'].dropna().unique()
lista_coligacoes = ["Todas"] + sorted(coligacoes_filtradas.tolist())
if 'coligacao' not in st.session_state:
    st.session_state['coligacao'] = 'Todas'
if st.session_state['coligacao'] not in lista_coligacoes:
    st.session_state['coligacao'] = 'Todas'

coligacao_selecionada = st.sidebar.selectbox(
    "Coligação", lista_coligacoes,
    index=lista_coligacoes.index(st.session_state['coligacao']),
    key='coligacao_select'
)
st.session_state['coligacao'] = coligacao_selecionada

# --- ANO ---
anos_disponiveis = sorted(df_merged['Ano'].dropna().unique())
lista_anos = ["Todos"] + [str(int(a)) for a in anos_disponiveis]
if 'ano' not in st.session_state:
    st.session_state['ano'] = 'Todos'
if st.session_state['ano'] not in lista_anos:
    st.session_state['ano'] = 'Todos'

ano_selecionado = st.sidebar.selectbox(
    "Ano", lista_anos,
    index=lista_anos.index(st.session_state['ano']),
    key='ano_select'
)
st.session_state['ano'] = ano_selecionado

# --- MÊS ---
if ano_selecionado != "Todos":
    meses_disponiveis = sorted(df_merged[df_merged['Ano'] == int(ano_selecionado)]['Mês'].dropna().unique())
else:
    meses_disponiveis = sorted(df_merged['Mês'].dropna().unique())

meses_nomes = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}
lista_meses = ["Todos"] + [f"{int(m):02d} - {meses_nomes.get(int(m), '')}" for m in meses_disponiveis]
if 'mes' not in st.session_state:
    st.session_state['mes'] = 'Todos'
if st.session_state['mes'] not in lista_meses:
    st.session_state['mes'] = 'Todos'

mes_selecionado = st.sidebar.selectbox(
    "Mês", lista_meses,
    index=lista_meses.index(st.session_state['mes']),
    key='mes_select'
)
st.session_state['mes'] = mes_selecionado

# --- INDÚSTRIA ---
st.sidebar.divider()
st.sidebar.header("🏭 Filtro por Indústria")
lista_industrias_filtro = ["Todas"] + INDUSTRIAS
if 'industria_filtro' not in st.session_state:
    st.session_state['industria_filtro'] = 'Todas'
if st.session_state['industria_filtro'] not in lista_industrias_filtro:
    st.session_state['industria_filtro'] = 'Todas'

industria_filtro = st.sidebar.selectbox(
    "Indústria", lista_industrias_filtro,
    index=lista_industrias_filtro.index(st.session_state['industria_filtro']),
    key='industria_select'
)
st.session_state['industria_filtro'] = industria_filtro

# --- MODO GAP ---
if 'modo_gap' not in st.session_state:
    st.session_state['modo_gap'] = False

modo_gap = st.sidebar.checkbox(
    "🔍 Mostrar apenas NÃO positivadas (GAP)",
    value=st.session_state['modo_gap'],
    key='modo_gap_check'
)
st.session_state['modo_gap'] = modo_gap

# ============================================================
# APLICAR FILTROS (sem coordenador)
# ============================================================
df_filtrado = df_merged.copy()
df_filtrado = df_filtrado[df_filtrado['nome_vendedor'] == vendedor_selecionado]

if coligacao_selecionada != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Cliente_Coligacao'] == coligacao_selecionada]
if ano_selecionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado['Ano'] == int(ano_selecionado)]
if mes_selecionado != "Todos":
    mes_num = int(mes_selecionado.split(' - ')[0])
    df_filtrado = df_filtrado[df_filtrado['Mês'] == mes_num]
if industria_filtro != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Nome_Fabricante'] == industria_filtro]

# ============================================================
# CARTEIRA ATIVA TOTAL (TODO O HISTÓRICO DO VENDEDOR)
# ============================================================
carteira_ativa_total = df_merged[
    (df_merged['nome_vendedor'] == vendedor_selecionado) &
    (df_merged['Nome_Fabricante'].notna())
]['codigo_cliente'].nunique()

total_positivados_ativos = df_filtrado[df_filtrado['Nome_Fabricante'].notna()]['codigo_cliente'].nunique()
pct_positivacao_ativa = (total_positivados_ativos / carteira_ativa_total * 100) if carteira_ativa_total > 0 else 0

clientes_ativos_ids = df_merged[
    (df_merged['nome_vendedor'] == vendedor_selecionado) &
    (df_merged['Nome_Fabricante'].notna())
]['codigo_cliente'].unique()

clientes_positivados_ids = df_filtrado[df_filtrado['Nome_Fabricante'].notna()]['codigo_cliente'].unique()
clientes_sem_venda_ativos = [c for c in clientes_ativos_ids if c not in clientes_positivados_ids]

# ============================================================
# MÉTRICAS DA CARTEIRA ATIVA
# ============================================================
st.subheader("📅 Carteira Ativa")
col_a1, col_a2, col_a3 = st.columns(3)
col_a1.metric("📅 Carteira Ativa Total (histórico)", carteira_ativa_total)
col_a2.metric("✅ Positivados no Período", total_positivados_ativos)
col_a3.metric("📈 % Positivação (Carteira Ativa)", f"{pct_positivacao_ativa:.1f}%")

col_a4, col_a5 = st.columns(2)
col_a4.metric("🔴 Clientes sem venda no período", len(clientes_sem_venda_ativos))
if len(clientes_sem_venda_ativos) > 0:
    with st.expander("👁️ Ver lista de clientes sem venda (Carteira Ativa)"):
        df_sem_venda_ativos = df_base[(df_base['codigo_cliente'].isin(clientes_sem_venda_ativos)) & 
                                      (df_base['nome_vendedor_base'] == vendedor_selecionado)][['codigo_cliente', 'nome_cliente', 'Cliente_Coligacao']]
        df_sem_venda_ativos.columns = ['Código', 'Nome', 'Coligação']
        st.dataframe(df_sem_venda_ativos, use_container_width=True, hide_index=True)

st.divider()

# ============================================================
# MÉTRICAS - CARTEIRA TOTAL
# ============================================================
total_clientes_base = df_base[df_base['nome_vendedor_base'] == vendedor_selecionado]['codigo_cliente'].nunique()
total_clientes_positivados = len(clientes_positivados_ids)
pct_positivacao = (total_clientes_positivados / total_clientes_base * 100) if total_clientes_base > 0 else 0

cobertura_por_cliente = df_filtrado.groupby('codigo_cliente')['Nome_Fabricante'].nunique()
cobertura_media = cobertura_por_cliente.mean() if len(cobertura_por_cliente) > 0 else 0
cobertura_total = df_filtrado[['codigo_cliente', 'Nome_Fabricante']].dropna().drop_duplicates().shape[0]

# Clientes da carteira total SEM VENDA no período
todos_ids_carteira = df_base[df_base['nome_vendedor_base'] == vendedor_selecionado]['codigo_cliente'].unique()
clientes_sem_venda_carteira = [c for c in todos_ids_carteira if c not in clientes_positivados_ids]

st.subheader("📋 Carteira Total")
col1, col2, col3 = st.columns(3)
col1.metric("📋 Clientes na Carteira", total_clientes_base)
col2.metric("✅ Clientes Positivados", total_clientes_positivados)
col3.metric("📈 % Positivação (Carteira Total)", f"{pct_positivacao:.1f}%")

col4, col5 = st.columns(2)
col4.metric("📊 Cobertura Média", f"{cobertura_media:.1f} ind/cliente")
col5.metric("🏭 Cobertura Total", f"{cobertura_total} coberturas")

col6, col7 = st.columns(2)
col6.metric("🔴 Clientes sem venda no período (Carteira Total)", len(clientes_sem_venda_carteira))
if len(clientes_sem_venda_carteira) > 0:
    with st.expander("👁️ Ver lista de clientes sem venda (Carteira Total)"):
        df_sem_venda_total = df_base[(df_base['codigo_cliente'].isin(clientes_sem_venda_carteira)) & 
                                     (df_base['nome_vendedor_base'] == vendedor_selecionado)][['codigo_cliente', 'nome_cliente', 'Cliente_Coligacao']]
        df_sem_venda_total.columns = ['Código', 'Nome', 'Coligação']
        st.dataframe(df_sem_venda_total, use_container_width=True, hide_index=True)

st.divider()

# ============================================================
# VISÃO MENSAL
# ============================================================
st.subheader("📅 Evolução Mensal")

df_mensal = df_merged.copy()
df_mensal = df_mensal[df_mensal['nome_vendedor'] == vendedor_selecionado]
if coligacao_selecionada != "Todas":
    df_mensal = df_mensal[df_mensal['Cliente_Coligacao'] == coligacao_selecionada]
if ano_selecionado != "Todos":
    df_mensal = df_mensal[df_mensal['Ano'] == int(ano_selecionado)]
if industria_filtro != "Todas":
    df_mensal = df_mensal[df_mensal['Nome_Fabricante'] == industria_filtro]

base_fixa = df_base[df_base['nome_vendedor_base'] == vendedor_selecionado]['codigo_cliente'].nunique()

evolucao_list = []
meses_ordenados = sorted(df_mensal['Mês_Ano'].dropna().unique())
for mes in meses_ordenados:
    df_mes = df_mensal[df_mensal['Mês_Ano'] == mes]
    clientes_pos = df_mes[df_mes['Nome_Fabricante'].notna()]['codigo_cliente'].nunique()
    cobertura_mes = df_mes.groupby('codigo_cliente')['Nome_Fabricante'].nunique()
    cobertura_media_mes = cobertura_mes.mean() if len(cobertura_mes) > 0 else 0
    cobertura_total_mes = df_mes[['codigo_cliente', 'Nome_Fabricante']].dropna().drop_duplicates().shape[0]
    
    evolucao_list.append({
        'Mês_Ano': mes,
        'Clientes_Positivados': clientes_pos,
        '%_Positivação': round((clientes_pos / base_fixa * 100), 1) if base_fixa > 0 else 0,
        'Cobertura_Media': round(cobertura_media_mes, 2),
        'Cobertura_Total': cobertura_total_mes
    })

evolucao = pd.DataFrame(evolucao_list)

if len(evolucao) > 0:
    col1, col2 = st.columns(2)

    with col1:
        fig_evo = go.Figure()
        fig_evo.add_trace(go.Bar(
            x=evolucao['Mês_Ano'],
            y=evolucao['%_Positivação'],
            text=[f'{v:.1f}%' for v in evolucao['%_Positivação']],
            textposition='outside',
            marker=dict(color=evolucao['%_Positivação'], colorscale='Greens', showscale=False)
        ))
        fig_evo.update_layout(
            title='% de Positivação por Mês',
            xaxis_title="",
            yaxis_title="% Positivação",
            yaxis_range=[0, 105],
            xaxis=dict(type='category', categoryorder='array', categoryarray=meses_ordenados)
        )
        st.plotly_chart(fig_evo, use_container_width=True)

    with col2:
        fig_evo2 = go.Figure()
        fig_evo2.add_trace(go.Scatter(
            x=evolucao['Mês_Ano'],
            y=evolucao['Cobertura_Media'],
            mode='lines+markers+text',
            text=[f'{v:.2f}' for v in evolucao['Cobertura_Media']],
            textposition='top center',
            line=dict(color='blue', width=3),
            marker=dict(size=10)
        ))
        fig_evo2.update_layout(
            title='Cobertura Média por Mês',
            xaxis_title="",
            yaxis_title="Cobertura Média",
            yaxis_range=[0, max(evolucao['Cobertura_Media']) * 1.2 if len(evolucao) > 0 and max(evolucao['Cobertura_Media']) > 0 else 1],
            xaxis=dict(type='category', categoryorder='array', categoryarray=meses_ordenados)
        )
        st.plotly_chart(fig_evo2, use_container_width=True)

    st.dataframe(evolucao, use_container_width=True, hide_index=True)
else:
    st.warning("Sem dados para a evolução mensal.")

st.divider()

# ============================================================
# GAPS DE INDÚSTRIA
# ============================================================
if industria_filtro != "Todas" or modo_gap:
    st.subheader("🔍 Análise de GAPS")
    
    df_base_filtrada_gap = df_base[df_base['nome_vendedor_base'] == vendedor_selecionado]
    if coligacao_selecionada != "Todas":
        df_base_filtrada_gap = df_base_filtrada_gap[df_base_filtrada_gap['Cliente_Coligacao'] == coligacao_selecionada]
    
    todos_clientes = df_base_filtrada_gap['codigo_cliente'].unique()
    
    if industria_filtro != "Todas":
        clientes_com_industria = df_filtrado[df_filtrado['Nome_Fabricante'] == industria_filtro]['codigo_cliente'].unique()
        clientes_gap = [c for c in todos_clientes if c not in clientes_com_industria]
        st.warning(f"🚨 Clientes que NÃO compraram {industria_filtro}: {len(clientes_gap)} de {len(todos_clientes)}")
    else:
        clientes_com_industria = df_filtrado[df_filtrado['Nome_Fabricante'].notna()]['codigo_cliente'].unique()
        clientes_gap = [c for c in todos_clientes if c not in clientes_com_industria]
        st.warning(f"🚨 Clientes que NÃO compraram nenhuma indústria: {len(clientes_gap)} de {len(todos_clientes)}")
    
    if len(clientes_gap) > 0:
        df_gap = df_base_filtrada_gap[df_base_filtrada_gap['codigo_cliente'].isin(clientes_gap)][['codigo_cliente', 'nome_cliente', 'Cliente_Coligacao', 'nome_vendedor_base']]
        df_gap.columns = ['Código', 'Nome', 'Coligação', 'Vendedor']
        st.dataframe(df_gap, use_container_width=True, hide_index=True)

st.divider()

# ============================================================
# RELATÓRIO BATALHA NAVAL
# ============================================================
st.subheader("📋 Relatório Batalha Naval")

matriz = df_filtrado.pivot_table(
    index='codigo_cliente',
    columns='Nome_Fabricante',
    aggfunc='size',
    fill_value=0
)

mapa_nomes = df_filtrado[['codigo_cliente', 'nome_cliente']].drop_duplicates('codigo_cliente')
mapa_nomes_dict = dict(zip(mapa_nomes['codigo_cliente'], mapa_nomes['nome_cliente']))

matriz_bin = (matriz > 0).astype(int)
matriz_bin['Nome_Cliente'] = matriz.index.map(lambda x: mapa_nomes_dict.get(x, 'N/A'))
matriz_bin['Total_Indústrias'] = matriz_bin.drop(columns=['Nome_Cliente']).sum(axis=1)
matriz_bin = matriz_bin.reset_index()
matriz_bin = matriz_bin.rename(columns={'codigo_cliente': 'Código'})

colunas_fabricantes = [c for c in matriz_bin.columns if c not in ['Código', 'Nome_Cliente', 'Total_Indústrias']]
colunas_ordem = ['Código', 'Nome_Cliente'] + colunas_fabricantes + ['Total_Indústrias']
matriz_bin = matriz_bin[colunas_ordem]

st.metric("📊 Total de Clientes no Relatório", len(matriz_bin))

col1, col2, col3 = st.columns(3)

with col1:
    csv = matriz_bin.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar CSV", data=csv, file_name=f'positivacao_{datetime.now().strftime("%Y%m%d")}.csv', mime='text/csv', use_container_width=True)

with col2:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        matriz_bin.to_excel(writer, index=False, sheet_name='Batalha Naval')
    st.download_button("📥 Baixar Excel", data=output.getvalue(), file_name=f'batalha_naval_{datetime.now().strftime("%Y%m%d")}.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)

with col3:
    html_pdf = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ text-align: center; color: #1a3a4a; font-size: 18px; }}
            h2 {{ text-align: center; color: #666; font-size: 12px; font-weight: normal; }}
            table {{ border-collapse: collapse; width: 100%; font-size: 8px; }}
            th {{ background-color: #1a3a4a; color: white; padding: 6px 4px; text-align: center; }}
            td {{ padding: 4px; text-align: center; border: 1px solid #ddd; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .positivo {{ background-color: #0F5220; color: white; }}
            .negativo {{ background-color: #8B0000; color: white; }}
            .footer {{ text-align: center; font-size: 10px; color: #999; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <h1>Relatório Batalha Naval</h1>
        <h2>4 Elos Distribuidora Ltda. - Centro de Custo 622 | Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}</h2>
        <table>
            <thead>
                <tr>
                    <th>Código</th>
                    <th>Cliente</th>"""
    
    for col in colunas_fabricantes:
        html_pdf += f"<th>{col}</th>"
    html_pdf += "<th>Total</th></tr></thead><tbody>"
    
    for _, row in matriz_bin.iterrows():
        html_pdf += "<tr>"
        html_pdf += f"<td>{row['Código']}</td>"
        html_pdf += f"<td style='text-align:left;'>{row['Nome_Cliente']}</td>"
        for col in colunas_fabricantes:
            valor = row[col]
            classe = "positivo" if valor == 1 else "negativo"
            html_pdf += f"<td class='{classe}'>{valor}</td>"
        html_pdf += f"<td><strong>{row['Total_Indústrias']}</strong></td>"
        html_pdf += "</tr>"
    
    html_pdf += f"""
            </tbody>
        </table>
        <div class="footer">
            4 Elos Distribuidora Ltda. - Centro de Custo 622 | Total: {len(matriz_bin)} clientes | 
            Cobertura Total: {matriz_bin['Total_Indústrias'].sum()} coberturas
        </div>
    </body>
    </html>
    """
    
    st.download_button("📥 Baixar PDF (HTML)", data=html_pdf.encode('utf-8'), file_name=f'batalha_naval_{datetime.now().strftime("%Y%m%d")}.html', mime='text/html', use_container_width=True)
    st.caption("💡 Abra o arquivo HTML e salve como PDF (Ctrl+P)")

with st.expander("👁️ Visualizar tabela"):
    st.dataframe(matriz_bin, use_container_width=True, hide_index=True)

st.divider()

# ============================================================
# FICHA DO CLIENTE
# ============================================================
st.subheader("🔍 Ficha do Cliente")

try:
    df_clientes_unicos = df_filtrado[['codigo_cliente', 'nome_cliente']].drop_duplicates()
    df_clientes_unicos = df_clientes_unicos.dropna(subset=['codigo_cliente', 'nome_cliente'])
    df_clientes_unicos['cliente_label'] = df_clientes_unicos['codigo_cliente'].astype(str) + ' - ' + df_clientes_unicos['nome_cliente'].astype(str)
    lista_clientes = sorted(df_clientes_unicos['cliente_label'].unique().tolist())
except:
    lista_clientes = []

if len(lista_clientes) > 0:
    cliente_selecionado_label = st.selectbox("Selecione um cliente:", lista_clientes, key='ficha_cliente')

    if cliente_selecionado_label:
        try:
            codigo_selecionado = cliente_selecionado_label.split(' - ')[0].strip()
            df_cliente = df_filtrado[df_filtrado['codigo_cliente'].astype(str).str.strip() == codigo_selecionado]

            if not df_cliente.empty:
                st.write(f"**Código:** {codigo_selecionado}")
                st.write(f"**Nome:** {df_cliente['nome_cliente'].iloc[0]}")
                st.write(f"**Coligação:** {df_cliente['Cliente_Coligacao'].iloc[0]}")
                st.write(f"**Vendedor:** {df_cliente['nome_vendedor'].iloc[0]}")
                st.write(f"**Coordenador:** {df_cliente['Nome_Coordenador'].iloc[0]}")

                st.write("**Positivação por Indústria e Mês:**")
                meses_disponiveis = sorted(df_cliente['Mês_Ano'].dropna().unique())
                
                if len(meses_disponiveis) > 0:
                    tabela_dados = []
                    for industria in INDUSTRIAS:
                        linha = {'Indústria': industria}
                        for mes in meses_disponiveis:
                            tem_venda = len(df_cliente[(df_cliente['Nome_Fabricante'] == industria) & (df_cliente['Mês_Ano'] == mes)]) > 0
                            linha[mes] = '✅' if tem_venda else '❌'
                        linha['Total'] = sum(1 for m in meses_disponiveis if linha[m] == '✅')
                        tabela_dados.append(linha)
                    
                    df_tabela = pd.DataFrame(tabela_dados)
                    st.dataframe(df_tabela, use_container_width=True, hide_index=True)
                    
                    total_industrias_positivadas = sum(1 for l in tabela_dados if l['Total'] > 0)
                    cobertura_total_cliente = df_cliente[['codigo_cliente', 'Nome_Fabricante']].dropna().drop_duplicates().shape[0]
                    st.metric("Indústrias Positivadas", f"{total_industrias_positivadas} de {TOTAL_INDUSTRIAS}")
                    st.metric("Cobertura Total do Cliente", f"{cobertura_total_cliente} coberturas")
                else:
                    st.warning("Nenhum dado mensal.")
            else:
                st.warning("Cliente não encontrado.")
        except:
            st.warning("Erro ao carregar dados do cliente.")
else:
    st.warning("Nenhum cliente encontrado.")

# ============================================================
# RODAPÉ COM DATAS
# ============================================================
st.divider()
col1, col2 = st.columns(2)
col1.caption(f"📅 Dashboard compilado em: {COMPILATION_DATE}")
col2.caption(f"📊 Dados carregados em: {data_dados}")
