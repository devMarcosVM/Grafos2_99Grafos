import streamlit as st
import networkx as nx
import pandas as pd
import pydeck as pdk
from geopy.distance import geodesic
import osmnx as ox
import heapq  # Para implementar a fila de prioridade

# Configuração da página
st.set_page_config(page_title="Menor Caminho Manual", layout="wide")
st.title("📍 Menor Caminho em Brasília (via ruas reais)")

# 1. Definir localizações manuais
locations = {
    "Rodoviária do Plano Piloto": (-15.7938, -47.8825),
    "UnB - Campus Darcy Ribeiro": (-15.754100460854655, -47.87513611438155),
    "UnB - Campus Gama": (-15.989299, -48.044103),
    "Palácio do Planalto": (-15.7997, -47.8645),
    "Torre de TV": (-15.7896, -47.8916),
    "Congresso Nacional": (-15.7995, -47.8646),
    "Esplanada dos Ministérios": (-15.7991, -47.8616),
    "Hospital de Base": (-15.7912, -47.8996),
    "Shopping Conjunto Nacional": (-15.7882, -47.8926),
    "Museu Nacional": (-15.7980, -47.8666),
    "Catedral de Brasília": (-15.7989, -47.8750),
}

# 2. Baixar o grafo real de ruas de Brasília
with st.spinner("Carregando ruas de Brasília..."):
    centro = locations["Rodoviária do Plano Piloto"]
    G_real = ox.graph_from_point(centro, dist=15000, network_type='drive')
    G_real = G_real.to_undirected()

# Implementação manual do algoritmo de Dijkstra
def dijkstra(G, origem, destino):
    """
    Implementação manual do algoritmo de Dijkstra para encontrar o caminho mais curto
    entre origem e destino em um grafo G, usando o atributo 'length' como peso.
    
    Parâmetros:
    G - Grafo NetworkX com pesos nas arestas
    origem - Nó de origem
    destino - Nó de destino
    
    Retorna:
    caminho - Lista de nós que formam o caminho mais curto
    custo - Custo total do caminho
    """
    # Inicialização
    distancias = {node: float('infinity') for node in G.nodes()}
    distancias[origem] = 0
    
    # Fila de prioridade (nó, distância)
    pq = [(0, origem)]
    
    # Para reconstruir o caminho
    predecessores = {node: None for node in G.nodes()}
    
    # Nós visitados
    visitados = set()
    
    while pq:
        # Pega o nó com menor distância
        dist_atual, no_atual = heapq.heappop(pq)
        
        # Se chegamos ao destino, terminamos
        if no_atual == destino:
            break
            
        # Se já visitamos este nó, pulamos
        if no_atual in visitados:
            continue
            
        # Marca como visitado
        visitados.add(no_atual)
        
        # Explora os vizinhos
        for vizinho in G.neighbors(no_atual):
            # Pega o peso da aresta (comprimento)
            try:
                peso = G[no_atual][vizinho][0]['length']  # Para grafos com múltiplas arestas entre nós
            except (KeyError, IndexError):
                try:
                    peso = G[no_atual][vizinho]['length']  # Para grafos simples
                except KeyError:
                    continue  # Se não há peso 'length', pula
            
            # Calcula nova distância
            distancia = dist_atual + peso
            
            # Se encontramos um caminho mais curto para o vizinho
            if distancia < distancias[vizinho]:
                distancias[vizinho] = distancia
                predecessores[vizinho] = no_atual
                # Adiciona à fila de prioridade
                heapq.heappush(pq, (distancia, vizinho))
    
    # Reconstrói o caminho do destino até a origem
    caminho = []
    no_atual = destino
    
    # Se não há caminho para o destino
    if predecessores[destino] is None and destino != origem:
        return [], float('infinity')
        
    while no_atual is not None:
        caminho.append(no_atual)
        no_atual = predecessores[no_atual]
        
    # Inverte o caminho para ficar da origem ao destino
    caminho.reverse()
    
    return caminho, distancias[destino]

# 3. Interface de seleção
pontos = list(locations.keys())
origem = st.selectbox("📍 Origem", pontos, index=0)
destino = st.selectbox("📍 Destino", pontos, index=1)

# 4. Calcular menor caminho real (Dijkstra nas ruas)
caminho = []
custo_total = 0

if origem != destino:
    try:
        # Converter coordenadas para nós mais próximos no grafo
        no_origem = ox.distance.nearest_nodes(G_real, locations[origem][1], locations[origem][0])
        no_destino = ox.distance.nearest_nodes(G_real, locations[destino][1], locations[destino][0])
        
        caminho, custo_total = dijkstra(G_real, no_origem, no_destino)
        
        if caminho:
            st.success(f"🚗 Menor caminho (via ruas): {origem} ➡️ {destino} — {custo_total:.0f} metros")
        else:
            st.error("❌ Não há caminho viável entre os pontos.")
    except Exception as e:
        st.error(f"❌ Erro ao calcular o caminho: {e}")

# 5. Preparar dados para o mapa
nodes_df = pd.DataFrame([
    {"name": nome, "lat": lat, "lon": lon} 
    for nome, (lat, lon) in locations.items()
])

edges_df = pd.DataFrame([
    {
        "from_lat": G_real.nodes[u]['y'],
        "from_lon": G_real.nodes[u]['x'],
        "to_lat": G_real.nodes[v]['y'],
        "to_lon": G_real.nodes[v]['x']
    }
    for u, v in G_real.edges()
])

# Se temos um caminho válido, criar dataframe para o caminho
path_df = pd.DataFrame()
if caminho and len(caminho) > 1:
    path_df = pd.DataFrame([
        {
            "from_lat": G_real.nodes[a]['y'],
            "from_lon": G_real.nodes[a]['x'],
            "to_lat": G_real.nodes[b]['y'],
            "to_lon": G_real.nodes[b]['x']
        }
        for a, b in zip(caminho, caminho[1:])
    ])

# 6. Mapas com Pydeck
layer_ruas = pdk.Layer(
    "LineLayer",
    data=edges_df,
    get_source_position='[from_lon, from_lat]',
    get_target_position='[to_lon, to_lat]',
    get_color=[180, 180, 180],
    get_width=1
)

layers = [layer_ruas]

# Adicionar camada do caminho se existir
if not path_df.empty:
    layer_caminho = pdk.Layer(
        "LineLayer",
        data=path_df,
        get_source_position='[from_lon, from_lat]',
        get_target_position='[to_lon, to_lat]',
        get_color=[255, 0, 0],
        get_width=4
    )
    layers.append(layer_caminho)

layer_pontos = pdk.Layer(
    "ScatterplotLayer",
    data=nodes_df,
    get_position='[lon, lat]',
    get_color='[0, 100, 255]',
    get_radius=100,
    pickable=True
)
layers.append(layer_pontos)

# 7. Renderização
st.pydeck_chart(pdk.Deck(
    map_style="mapbox://styles/mapbox/light-v9",
    initial_view_state=pdk.ViewState(
        latitude=centro[0],
        longitude=centro[1],
        zoom=12
    ),
    layers=layers,
    tooltip={"text": "{name}"}
), height=800)

# Informações adicionais sobre o algoritmo de Dijkstra
st.markdown("""
## Sobre o Algoritmo de Dijkstra

Neste aplicativo, implementamos manualmente o **algoritmo de Dijkstra** para encontrar o caminho mais curto entre dois pontos em Brasília, utilizando o grafo real de ruas.

### Como o algoritmo funciona:

1. **Inicialização**: Todas as distâncias são definidas como infinito, exceto a origem (distância 0)
2. **Processo iterativo**: A cada passo, escolhemos o nó não visitado com menor distância
3. **Relaxamento**: Atualizamos as distâncias dos vizinhos se encontrarmos um caminho mais curto
4. **Término**: Paramos quando chegamos ao destino ou visitamos todos os nós alcançáveis

O algoritmo garante o caminho mais curto em grafos com pesos positivos, como é o caso das distâncias nas ruas.
""")