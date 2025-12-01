import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
from io import StringIO
import folium
from streamlit_folium import folium_static


# --- CONFIGURACIÓN INICIAL DE LA APP ---
st.set_page_config(
    page_title="Herramienta de Huella de Carbono",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONSTANTES Y CONFIGURACIONES ---

# 1. Base de datos histórica (Inicial) de las especies y sus coeficientes
# NOTA IMPORTANTE: Se elimina 'Costo Anual (Soles/árbol)' para que sea ingresado manualmente por lote.
DENSIDADES_BASE = {
    'Especie': ['Eucalipto Torrellana', 'Majoe', 'Molle', 'Algarrobo'],
    'Captura CO2e (Kg/año)': [125.0, 78.0, 50.0, 65.0],
    'Densidad (Kg/m3)': [500, 700, 750, 800],
    'Crecimiento Anual DBH (cm/año)': [5.0, 3.0, 2.5, 2.0],
    'Factor BIOM (Kg Biom/Kg C)': [2.0, 2.0, 2.0, 2.0],
    'Factor CO2e (Kg CO2e/Kg C)': [3.67, 3.67, 3.67, 3.67],
    'Consumo Agua (L/año)': [1500, 1200, 900, 800] 
}

# Crear DataFrame base
DF_BASE = pd.DataFrame(DENSIDADES_BASE).set_index('Especie')


# --- CONSTANTES GLOBALES PARA EQUIVALENCIAS AMBIENTALES ---
# Basado en referencias estandarizadas (ej. EPA Equivalencies Calculator, ajustado a toneladas métricas)
CO2_POR_VEHICULO_ANUAL = 4.6      # Toneladas métricas de CO2e por vehículo particular al año
CO2_POR_HOGAR_ANUAL = 4.8         # Toneladas métricas de CO2e por consumo eléctrico promedio de un hogar al año
CO2_POR_CIGARRILLO = 0.000014     # Toneladas métricas de CO2e por cigarrillo (14 gramos, ciclo de vida)
CO2_POR_PLANTULA_10_ANOS = 0.019  # Toneladas métricas de CO2e capturado por una plántula de árbol en 10 años


# --- INICIALIZACIÓN DE SESSION STATE ---

def init_session_state():
    """Inicializa todas las variables de estado de sesión necesarias."""
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "1. Cálculo de Captura"
        
    # Variables de la calculadora
    if 'inventario_list' not in st.session_state:
        st.session_state.inventario_list = []
    if 'proyecto' not in st.session_state:
        st.session_state.proyecto = {'nombre': 'Proyecto Reforestación CP SAA', 'anio_plantacion': datetime.now().year}
    if 'lotes_mapa' not in st.session_state:
        st.session_state.lotes_mapa = []

    # Variables de gestión de datos
    if 'df_densidades' not in st.session_state:
        df_temp = DF_BASE.copy()
        # Inicializar la columna de costo de referencia en la BD base
        df_temp['Costo Anual (Soles/árbol)'] = [15.0, 10.0, 12.0, 8.0]
        st.session_state.df_densidades = df_temp
             
    if 'edicion_activa' not in st.session_state:
        st.session_state.edicion_activa = False

    # Variables para el mapa
    if 'ubicacion_mapa' not in st.session_state:
        # Coordenada central de ejemplo (Perú)
        st.session_state.ubicacion_mapa = [-8.70, -75.0] 
    if 'zoom_mapa' not in st.session_state:
        st.session_state.zoom_mapa = 5
        
    # Variables de simulación
    if 'df_simulacion_global' not in st.session_state:
        st.session_state.df_simulacion_global = pd.DataFrame()
        
def reiniciar_app_completo():
    """Borra completamente todos los elementos del estado de sesión."""
    keys_to_delete = list(st.session_state.keys())
    for key in keys_to_delete:
        del st.session_state[key]
    # Usamos st.rerun() para forzar el reinicio después de borrar el estado
    st.rerun()
    
# --- FUNCIONES DE CÁLCULO ---

def calcular_captura_y_costo(df_inventario, df_densidades_hist):
    """Calcula la captura total de CO2e y el costo anual de mantenimiento."""
    if df_inventario.empty:
        return 0, 0, 0, pd.DataFrame()

    # Combinar inventario con las propiedades de la especie (solo Captura CO2e y Agua)
    # El costo de mantenimiento YA ESTÁ en df_inventario (Costo Plantón (Soles/árbol))
    df_merged = pd.merge(
        df_inventario, 
        df_densidades_hist[['Captura CO2e (Kg/año)', 'Consumo Agua (L/año)']],
        on='Especie',
        how='left'
    )
    
    # Cálculos
    df_merged['Captura Total CO2e (Kg)'] = df_merged['Cantidad'] * df_merged['Captura CO2e (Kg/año)']
    
    # *** CÁLCULO DE COSTO CON VALOR MANUAL DEL LOTE ***
    df_merged['Costo Total (Soles)'] = df_merged['Cantidad'] * df_merged['Costo Plantón (Soles/árbol)'] 
    
    df_merged['Consumo Total Agua (L/año)'] = df_merged['Cantidad'] * df_merged['Consumo Agua (L/año)']

    # Totales
    co2e_total_kg = df_merged['Captura Total CO2e (Kg)'].sum()
    costo_total = df_merged['Costo Total (Soles)'].sum()
    agua_total = df_merged['Consumo Total Agua (L/año)'].sum()

    return co2e_total_kg, costo_total, agua_total, df_merged

def simular_crecimiento(df_inventario_completo, df_densidades_hist, anio_inicio, anios_simulacion=15):
    """Simula la captura de CO2e de la biomasa a lo largo de los años."""
    df_sim = pd.DataFrame()
    # Asegurar que los años sean enteros
    anios_simulacion = int(anios_simulacion)
    anos = np.arange(1, anios_simulacion + 1)
    
    # Iterar sobre cada lote en el inventario
    for index, lote in df_inventario_completo.iterrows():
        especie = lote['Especie']
        cantidad = lote['Cantidad']
        
        # Obtener los coeficientes de la especie
        try:
            coef = df_densidades_hist.loc[especie]
            dbh_anual = coef['Crecimiento Anual DBH (cm/año)']
            densidad = coef['Densidad (Kg/m3)']
            factor_biom = coef['Factor BIOM (Kg Biom/Kg C)']
            factor_co2e = coef = coef['Factor CO2e (Kg CO2e/Kg C)'] # Error corregido en la lógica de asignación
        except KeyError:
            # En caso de que la especie no esté en la BD histórica, saltar el lote
            st.error(f"Error: Especie '{especie}' no encontrada en la base de datos de coeficientes.")
            continue
            
        # Asumiendo un DAP (DBH) inicial de 5 cm (50 mm)
        DAP_INICIAL_MM = 50 
        
        # Calcular los datos por año de simulación
        data = {
            'Año de Simulación': anos,
            'Año Calendario': anio_inicio + anos,
            'Especie': especie,
            'Lote': f"Lote {index + 1}",
        }
        
        # 1. Diámetro a Altura del Pecho (DAP en mm)
        data['DAP (mm)'] = DAP_INICIAL_MM + (dbh_anual * 10 * anos)
        
        # 2. Volumen de Madera (V en m3)
        # Usando la fórmula de biomasa de Pagano: V = 0.000109 * DAP^2.3168 (Para obtener volumen m3/árbol)
        data['Volumen (m3/árbol)'] = 0.000109 * (data['DAP (mm)'] / 10)**2.3168
        
        # 3. Biomasa (BIOM en Kg)
        # Biomasa (Kg/árbol) = Volumen (m3/árbol) * Densidad (Kg/m3) * Factor de Biomasa (Factor BIOM)
        data['Biomasa (Kg/árbol)'] = data['Volumen (m3/árbol)'] * densidad * factor_biom
        
        # 4. Carbono Almacenado (C en Kg)
        # Asumiendo que el 50% de la Biomasa es Carbono (Factor de 2.0 en Factor BIOM ya lo implica)
        data['Carbono (Kg/árbol)'] = data['Biomasa (Kg/árbol)'] / factor_biom 
        
        # 5. CO2e Capturado (CO2e en Kg)
        # CO2e = Carbono (Kg) * Factor CO2e (3.67)
        data['CO2e (Kg/árbol)'] = data['Carbono (Kg/árbol)'] * factor_co2e
        
        # 6. Captura Total del Lote (CO2e en Kg)
        data['Captura Lote CO2e (Kg)'] = data['CO2e (Kg/árbol)'] * cantidad
        
        df_lote = pd.DataFrame(data)
        df_sim = pd.concat([df_sim, df_lote], ignore_index=True)
        
    return df_sim

# --- FUNCIONES DE VISUALIZACIÓN ---

def render_kpis(co2e_total_kg, costo_total_soles, agua_total_litros):
    """Muestra los indicadores clave del proyecto."""
    
    co2e_ton = co2e_total_kg / 1000
    agua_m3 = agua_total_litros / 1000
    
    col_cap, col_cost, col_agua = st.columns(3)

    with col_cap:
        st.metric(
            label="🌳 Captura Total de CO₂e Anual", 
            value=f"{co2e_ton:,.2f} Toneladas",
            help="Toneladas métricas de CO₂e capturadas por el total de árboles en un año."
        )
    with col_cost:
        st.metric(
            label="💰 Costo Total de Mantenimiento Anual", 
            value=f"S/. {costo_total_soles:,.2f}",
            help="Costo anual total para el mantenimiento, basado en el costo por árbol ingresado manualmente para cada lote."
        )
    with col_agua:
        st.metric(
            label="💧 Consumo Total de Agua Anual", 
            value=f"{agua_m3:,.2f} m³",
            help="Consumo total de agua en metros cúbicos (m³) por el total de árboles en un año."
        )
    
    return co2e_ton # Devuelve las toneladas para las equivalencias

def render_calculadora_y_graficos():
    """Función principal para la sección de cálculo, inventario y gráficos."""
    st.title("1. Cálculo de Captura, Simulación y Resultados")

    # Obtener el DataFrame de densidades actual
    df_densidades_hist = st.session_state.df_densidades

    # --- PESTAÑAS ---
    tab1_calc, tab2_sim, tab3_graf, tab4_costo, tab5_eq = st.tabs(["Calculadora y Datos", "Simulación de Crecimiento", "Gráficos (Total Lotes)", "Costo del Mantenimiento y Riego", "🌎 Equivalencias Ambientales"])

    # Inicializar el DF del inventario completo
    df_inventario_completo = pd.DataFrame(st.session_state.inventario_list)
    if not df_inventario_completo.empty:
        # Asegurar que las columnas numéricas sean float para evitar errores
        df_inventario_completo['Cantidad'] = df_inventario_completo['Cantidad'].astype(float)
        # Asegurar que el costo sea float
        df_inventario_completo['Costo Plantón (Soles/árbol)'] = df_inventario_completo['Costo Plantón (Soles/árbol)'].astype(float)


    # Calcular resultados
    co2e_total_kg, costo_total_soles, agua_total_litros, df_inventario_calculado = calcular_captura_y_costo(df_inventario_completo, df_densidades_hist)

    # -----------------------------------------------------------
    # Pestaña 1: Calculadora y Datos
    # -----------------------------------------------------------
    with tab1_calc:
        st.header("Inventario Actual de Lotes de Reforestación")

        # Renderizar KPIs (Métricas)
        co2e_proyecto_ton = render_kpis(co2e_total_kg, costo_total_soles, agua_total_litros)

        # Formulario para añadir lotes
        with st.expander("➕ **Añadir Nuevo Lote / Área de Reforestación**", expanded=False):
            with st.form("form_lote_nuevo", clear_on_submit=True):
                col1, col2 = st.columns(2)
                
                # Input de Especie
                especies_disponibles = df_densidades_hist.index.tolist()
                especie_seleccionada = col1.selectbox(
                    "Especie Forestal:",
                    options=especies_disponibles,
                    key="input_especie"
                )
                
                # Input de Cantidad
                cantidad_arboles = col2.number_input(
                    "Cantidad de Árboles:",
                    min_value=1,
                    step=1,
                    value=100,
                    key="input_cantidad"
                )
                
                # Input de Ubicación (para el mapa)
                ubicacion = st.text_input(
                    "Ubicación / Área (Ej: Zona P-1, Sector Norte):",
                    key="input_ubicacion",
                    value=f"Lote {len(st.session_state.inventario_list) + 1}"
                )
                
                # --- CAMPO: Costo Anual por Plantón ---
                col_costo, col_lat, col_lon = st.columns(3)

                # Obtener costo de referencia de la BD base para sugerir valor
                costo_ref = df_densidades_hist.loc[especie_seleccionada, 'Costo Anual (Soles/árbol)']
                
                costo_planton = col_costo.number_input(
                    "💰 Costo Anual de Mantenimiento por Árbol (Soles):",
                    min_value=0.0,
                    step=0.5,
                    value=float(costo_ref) if especie_seleccionada else 10.0, 
                    key="input_costo",
                    format="%.2f"
                )

                # Coordenadas
                latitud = col_lat.number_input("Latitud (Ej: -7.12345):", format="%.5f", key="input_lat", value=st.session_state.ubicacion_mapa[0])
                longitud = col_lon.number_input("Longitud (Ej: -79.12345):", format="%.5f", key="input_lon", value=st.session_state.ubicacion_mapa[1])


                submit_button = st.form_submit_button("Guardar Lote")
                
                if submit_button:
                    # Validar datos antes de guardar (por si acaso)
                    if not especie_seleccionada:
                        st.error("Debe seleccionar una especie.")
                    elif cantidad_arboles <= 0:
                        st.error("La cantidad de árboles debe ser mayor a cero.")
                    else:
                        nuevo_lote = {
                            'Especie': especie_seleccionada,
                            'Cantidad': int(cantidad_arboles),
                            'Ubicación': ubicacion,
                            'Costo Plantón (Soles/árbol)': float(costo_planton), # CAMPO CRÍTICO
                            'Latitud': latitud,
                            'Longitud': longitud
                        }
                        st.session_state.inventario_list.append(nuevo_lote)
                        st.session_state.lotes_mapa.append({'lat': latitud, 'lon': longitud, 'tooltip': f"{ubicacion} - {especie_seleccionada}"})
                        st.success(f"Lote '{ubicacion}' de {cantidad_arboles} árboles añadido correctamente.")
                        st.rerun() # Rerun para actualizar la tabla inmediatamente

        # Tabla del Inventario
        st.markdown("### Inventario Detallado por Lote")
        
        if df_inventario_completo.empty:
            st.warning("Aún no se han añadido lotes al inventario. Use el formulario superior para empezar.")
        else:
            # Columnas a mostrar, incluyendo el Costo por Plantón
            columnas_a_mostrar = ['Especie', 'Cantidad', 'Ubicación', 'Costo Plantón (Soles/árbol)']
            
            # Unir con la información calculada (incluye Captura y Costo Total)
            df_tabla = pd.concat([df_inventario_completo[columnas_a_mostrar], df_inventario_calculado[['Captura Total CO2e (Kg)', 'Costo Total (Soles)', 'Consumo Total Agua (L/año)']]], axis=1)
            
            # Formatear la tabla
            st.dataframe(
                df_tabla.style.format({
                    'Cantidad': '{:,.0f}',
                    'Costo Plantón (Soles/árbol)': 'S/. {:,.2f}', # NUEVO FORMATO
                    'Captura Total CO2e (Kg)': '{:,.2f}',
                    'Costo Total (Soles)': 'S/. {:,.2f}',
                    'Consumo Total Agua (L/año)': '{:,.0f} L'
                }),
                use_container_width=True,
                height=min(300, 35 * (len(df_tabla) + 1) + 20) # Altura dinámica
            )

            # Botón para borrar el inventario
            if st.button("🗑️ Limpiar Todo el Inventario", type="secondary"):
                st.session_state.inventario_list = []
                st.session_state.lotes_mapa = []
                st.session_state.df_simulacion_global = pd.DataFrame() # También borrar simulación
                st.success("Inventario completamente borrado. Recargando la página para reiniciar los cálculos...")
                st.rerun()
    
    # -----------------------------------------------------------
    # Pestaña 5: Equivalencias Ambientales 
    # -----------------------------------------------------------
    with tab5_eq:
        render_equivalencias_ambientales(co2e_proyecto_ton)


    # -----------------------------------------------------------
    # Pestaña 2: Simulación de Crecimiento
    # -----------------------------------------------------------
    with tab2_sim:
        st.header("Simulación de Crecimiento y Captura a Largo Plazo")
        
        if df_inventario_completo.empty:
            st.info("Necesita añadir lotes de reforestación en la sección 'Calculadora y Datos' para ejecutar la simulación.")
        else:
            col_sel_lote, col_sel_sim = st.columns([1, 1])

            # 1. Parámetros de Simulación
            with col_sel_sim:
                st.markdown("##### ⚙️ Parámetros de Simulación")
                
                # Input de años
                anios_simulacion = st.number_input(
                    "Años a simular (Máx 30):",
                    min_value=5,
                    max_value=30,
                    value=15,
                    step=5,
                    key="input_anios_sim"
                )
                
                # Botón de simulación
                if st.button("▶️ Ejecutar Simulación", type="primary", use_container_width=True):
                    with st.spinner(f"Calculando simulación para {anios_simulacion} años..."):
                        df_simulacion = simular_crecimiento(
                            df_inventario_completo, 
                            df_densidades_hist, 
                            st.session_state.proyecto['anio_plantacion'],
                            anios_simulacion
                        )
                        st.session_state.df_simulacion_global = df_simulacion
                        st.success(f"Simulación de {anios_simulacion} años completada.")
                        st.rerun()
            
            st.markdown("---")

            df_simulacion = st.session_state.df_simulacion_global
            
            if not df_simulacion.empty:
                # 2. Resumen de la Simulación
                total_captura_simulada = df_simulacion.groupby('Año Calendario')['Captura Lote CO2e (Kg)'].sum().reset_index()
                max_captura = total_captura_simulada['Captura Lote CO2e (Kg)'].max() / 1000 # a Toneladas
                
                st.subheader(f"Resultados Consolidados de la Simulación ({anios_simulacion} Años)")
                st.metric(
                    label=f"Captura Total de CO₂e al año {st.session_state.proyecto['anio_plantacion'] + anios_simulacion} (Máx)",
                    value=f"{max_captura:,.2f} Toneladas",
                    delta=f"{max_captura - co2e_proyecto_ton:,.2f} Toneladas más que el año actual",
                    delta_color="normal"
                )
                
                # 3. Gráfico de Simulación Total
                st.markdown("##### 📈 Evolución de la Captura Total de CO₂e del Proyecto (Biomasa)")
                fig_sim_total = px.bar(
                    total_captura_simulada, 
                    x='Año Calendario', 
                    y='Captura Lote CO2e (Kg)', 
                    title="Captura Acumulada de CO₂e por Año",
                    labels={'Captura Lote CO2e (Kg)': 'Captura CO₂e (Kg)', 'Año Calendario': 'Año'}
                )
                fig_sim_total.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_sim_total, use_container_width=True)
                
                # 4. Detalle por Lote (Selector)
                lotes_simulados = df_simulacion['Lote'].unique().tolist()
                
                with col_sel_lote:
                    st.markdown("##### 🔍 Detalle por Lote")
                    # Manejar el caso de que lotes_simulados esté vacío, aunque no debería ocurrir si df_simulacion no está vacío.
                    if lotes_simulados:
                        lote_sim_seleccionado = st.selectbox("Seleccione el Lote para el Detalle:", options=lotes_simulados, key="sel_lote_sim")
                        
                        df_detalle_lote = df_simulacion[df_simulacion['Lote'] == lote_sim_seleccionado]
                        
                        st.markdown(f"**Detalle de Crecimiento para {lote_sim_seleccionado} ({df_detalle_lote['Especie'].iloc[0]})**")
                        
                        fig_detalle = go.Figure()
                        
                        # Línea de DAP
                        fig_detalle.add_trace(go.Scatter(
                            x=df_detalle_lote['Año Calendario'], 
                            y=df_detalle_lote['DAP (mm)'], 
                            mode='lines+markers', 
                            name='DAP (mm)',
                            yaxis='y1'
                        ))
                        
                        # Línea de Captura CO2e
                        fig_detalle.add_trace(go.Scatter(
                            x=df_detalle_lote['Año Calendario'], 
                            y=(df_detalle_lote['Captura Lote CO2e (Kg)'] / 1000), 
                            mode='lines+markers', 
                            name='CO₂e Capturado (Ton)',
                            yaxis='y2'
                        ))
                        
                        # Configuración de ejes
                        fig_detalle.update_layout(
                            title=f"Crecimiento de DAP y Captura CO₂e del Lote",
                            xaxis=dict(title="Año"),
                            yaxis=dict(title="DAP (mm)", showgrid=False),
                            yaxis2=dict(title="CO₂e Capturado (Ton)", overlaying='y', side='right'),
                            legend=dict(x=0.01, y=0.99)
                        )
                        
                        st.plotly_chart(fig_detalle, use_container_width=True)
                    else:
                        st.info("No hay datos de lotes disponibles en la simulación para mostrar el detalle.")


    # -----------------------------------------------------------
    # Pestaña 3: Gráficos (Total de Lotes)
    # -----------------------------------------------------------
    with tab3_graf:
        st.header("Análisis Gráfico del Inventario Actual")

        if df_inventario_completo.empty:
            st.info("Añada lotes en la sección 'Calculadora y Datos' para generar los gráficos.")
        else:
            col_pie, col_bar = st.columns(2)
            
            # Gráfico de Torta (Distribución por Especie)
            with col_pie:
                st.markdown("##### 🥧 Distribución de Árboles por Especie")
                df_especie_count = df_inventario_completo.groupby('Especie')['Cantidad'].sum().reset_index()
                fig_pie = px.pie(
                    df_especie_count, 
                    values='Cantidad', 
                    names='Especie', 
                    title='Porcentaje de Árboles por Especie'
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            # Gráfico de Barras (Captura CO2e por Especie)
            with col_bar:
                st.markdown("##### 📊 Captura CO₂e Anual por Especie")
                df_especie_co2e = df_inventario_calculado.groupby('Especie')['Captura Total CO2e (Kg)'].sum().reset_index()
                fig_bar = px.bar(
                    df_especie_co2e, 
                    x='Especie', 
                    y='Captura Total CO2e (Kg)', 
                    title='Total de CO₂e Capturado por Especie',
                    labels={'Captura Total CO2e (Kg)': 'Captura CO₂e (Kg)'},
                    color='Especie'
                )
                st.plotly_chart(fig_bar, use_container_width=True)

    # -----------------------------------------------------------
    # Pestaña 4: Costo y Riego
    # -----------------------------------------------------------
    with tab4_costo:
        st.header("Análisis de Costos y Consumo Hídrico Anual")

        if df_inventario_completo.empty:
            st.info("Añada lotes en la sección 'Calculadora y Datos' para analizar costos y consumo de agua.")
        else:
            
            # Gráfico de Barras (Costo por Lote)
            st.markdown("##### 💰 Distribución del Costo de Mantenimiento Anual por Lote")
            fig_costo = px.bar(
                df_inventario_calculado, 
                x='Ubicación', 
                y='Costo Total (Soles)', 
                color='Especie',
                title='Costo Anual de Mantenimiento por Lote',
                labels={'Costo Total (Soles)': 'Costo (S/.)', 'Ubicación': 'Lote'}
            )
            st.plotly_chart(fig_costo, use_container_width=True)
            
            # Gráfico de Barras (Consumo de Agua por Lote)
            st.markdown("##### 💧 Distribución del Consumo de Agua Anual por Lote")
            fig_agua = px.bar(
                df_inventario_calculado, 
                x='Ubicación', 
                y='Consumo Total Agua (L/año)', 
                color='Especie',
                title='Consumo Total de Agua Anual por Lote',
                labels={'Consumo Total Agua (L/año)': 'Consumo de Agua (Litros)', 'Ubicación': 'Lote'}
            )
            st.plotly_chart(fig_agua, use_container_width=True)

# --- FUNCIÓN DE EQUIVALENCIAS ---

def render_equivalencias_ambientales(co2e_proyecto_ton):
    """Calcula y muestra las equivalencias ambientales en base a la captura total."""
    st.markdown("### 🌎 El Impacto de su Captura de Carbono en Cifras Reales")

    if co2e_proyecto_ton <= 0:
        st.info("Para calcular las equivalencias, primero debe tener una captura total de CO2e positiva en el proyecto (Sección 'Calculadora y Datos').")
        return
        
    st.subheader(f"Su proyecto de reforestación captura: **{co2e_proyecto_ton:,.0f} toneladas métricas de CO₂e** al año.")

    st.markdown("---")
    
    # Cálculos de Equivalencias
    eq_vehiculos = co2e_proyecto_ton / CO2_POR_VEHICULO_ANUAL
    eq_hogares = co2e_proyecto_ton / CO2_POR_HOGAR_ANUAL
    eq_plantulas = co2e_proyecto_ton / CO2_POR_PLANTULA_10_ANOS
    eq_cigarrillos = co2e_proyecto_ton / CO2_POR_CIGARRILLO
    
    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            label="🚗 Vehículos Particulares Retirados de Circulación (Anual)",
            value=f"{eq_vehiculos:,.0f} vehículos",
            help=f"Equivalencia de {CO2_POR_VEHICULO_ANUAL} toneladas de CO₂e por vehículo particular promedio al año."
        )
        st.metric(
            label="🏡 Consumo Eléctrico de Hogares (Anual)",
            value=f"{eq_hogares:,.0f} hogares",
            help=f"Equivalencia de {CO2_POR_HOGAR_ANUAL} toneladas de CO₂e por el consumo de electricidad de un hogar promedio al año."
        )

    with col2:
        st.metric(
            label="🌳 Plántulas de Árboles Crecidas por 10 Años",
            value=f"{eq_plantulas:,.0f} plántulas",
            help=f"Equivalencia de {CO2_POR_PLANTULA_10_ANOS:,.3f} toneladas de CO₂e capturadas por una plántula de árbol joven en crecimiento durante 10 años."
        )
        st.metric(
            label="🚬 Cantidad de Cigarrillos No Producidos (Ciclo de Vida)",
            value=f"{eq_cigarrillos:,.0f} cigarrillos",
            help=f"Equivalencia de {CO2_POR_CIGARRILLO:,.6f} toneladas de CO₂e (14 gramos) por el ciclo de vida completo de un cigarrillo."
        )
        
    st.markdown("---")
    st.caption("*Nota: Los factores de equivalencia son valores promedio globales/estándar. Las cifras son aproximadas y están destinadas a comunicar el impacto ambiental de forma sencilla.*")

# --- FUNCIONES DE GESTIÓN DE DATOS Y MAPA (Adaptadas) ---

def render_gestion_datos():
    """Permite al usuario ver y editar los coeficientes de las especies."""
    st.title("5. Gestión de Datos de Crecimiento de Especies")
    st.warning("⚠️ **¡Advertencia!** Modificar estos valores alterará todos los cálculos de captura para sus lotes existentes. Use con precaución.")

    # 1. Preparar el DataFrame
    df_actual = st.session_state.df_densidades.copy()
    
    st.markdown("### Tabla de Coeficientes y Datos Históricos (Edición)")

    # 2. Renderizar el editor de datos
    edited_df = st.data_editor(
        df_actual,
        use_container_width=True,
        num_rows="dynamic",
        key="data_editor_densidades",
        column_config={
            # Configuración de columnas (opcional: definir tipos/ayudas)
            'Captura CO2e (Kg/año)': st.column_config.NumberColumn(
                label="Captura CO2e (Kg/año)", format="%.2f", help="CO₂e capturado por un árbol adulto anualmente."
            ),
            'Densidad (Kg/m3)': st.column_config.NumberColumn(
                label="Densidad (Kg/m³)", format="%.0f", help="Densidad de la madera."
            ),
            'Crecimiento Anual DBH (cm/año)': st.column_config.NumberColumn(
                label="Crecimiento Anual DBH (cm/año)", format="%.1f", help="Incremento anual del Diámetro a Altura del Pecho (cm)."
            ),
            'Consumo Agua (L/año)': st.column_config.NumberColumn(
                label="Consumo Agua (L/año)", format="%.0f", help="Litros de agua consumidos anualmente por un árbol."
            ),
            'Costo Anual (Soles/árbol)': st.column_config.NumberColumn(
                label="Costo Anual (Soles/árbol)", format="%.2f", help="Costo de referencia para el mantenimiento anual (¡Nota: El cálculo usa el valor manual del Lote!)"
            ),
            'Factor BIOM (Kg Biom/Kg C)': st.column_config.NumberColumn(
                label="Factor BIOM (Kg Biom/Kg C)", format="%.2f", help="Factor para convertir Biomasa a Carbono (generalmente 2.0)."
            ),
            'Factor CO2e (Kg CO2e/Kg C)': st.column_config.NumberColumn(
                label="Factor CO2e (Kg CO2e/Kg C)", format="%.2f", help="Factor para convertir Carbono a CO₂e (3.67)."
            )
        }
    )
    
    if st.button("💾 Guardar Cambios en la BD Histórica", type="primary"):
        # 3. Guardar los cambios
        
        # Validar que los campos de índice se mantengan (Nombres de Especie)
        if edited_df.index.has_duplicates:
            st.error("Error: Las especies no pueden tener nombres duplicados. Revise los índices.")
        # Se asegura de que todas las columnas originales sigan presentes (excepto la de costo que es nueva y se maneja en el DF_BASE)
        elif not all(col in edited_df.columns for col in DF_BASE.columns.drop('Captura CO2e (Kg/año)', errors='ignore')):
             st.error("Error: No se puede eliminar ninguna columna esencial del DataFrame. Reinicie si es necesario.")
        else:
            # Reemplazar el DataFrame en el estado de sesión
            st.session_state.df_densidades = edited_df
            st.success("✅ Datos de especies actualizados correctamente.")
            st.rerun() # Recargar para que los cambios se reflejen en la calculadora

def render_mapa():
    """Muestra la ubicación de los lotes en un mapa interactivo."""
    st.title("3. Mapa de Ubicación de Lotes")
    
    if not st.session_state.lotes_mapa:
        st.info("Aún no se han añadido lotes con coordenadas. Use la sección '1. Cálculo de Captura' para añadir lotes y verlos aquí.")
        return

    # Usar el centro promedio de los lotes para centrar el mapa
    df_lotes = pd.DataFrame(st.session_state.lotes_mapa)
    lat_centro = df_lotes['lat'].mean()
    lon_centro = df_lotes['lon'].mean()

    m = folium.Map(location=[lat_centro, lon_centro], zoom_start=6)

    # Agregar marcadores para cada lote
    for index, row in df_lotes.iterrows():
        folium.Marker(
            [row['lat'], row['lon']], 
            tooltip=row['tooltip'],
            icon=folium.Icon(color="green", icon="tree", prefix="fa")
        ).add_to(m)

    # Mostrar el mapa
    st.markdown("### Ubicaciones Geográficas de Lotes Plantados")
    folium_static(m)
    st.caption("Los marcadores verdes indican la ubicación y la información de cada lote de reforestación.")

# --- FUNCIÓN PRINCIPAL ---

def main_app():
    """Define la estructura de la barra lateral y el contenido principal."""
    init_session_state()
    
    # 1. Barra Lateral (Sidebar)
    with st.sidebar:
        # st.image("URL de la imagen del logo", width=80) # Reemplazar con el URL de su logo
        st.title("🌳 Calculadora CO₂e")
        st.markdown(f"**Proyecto:** {st.session_state.proyecto['nombre']}")
        st.markdown(f"**Año Base:** {st.session_state.proyecto['anio_plantacion']}")
        
        st.markdown("---")
        st.subheader("Menú de Navegación")
        
        options = [
            "1. Cálculo de Captura", 
            "2. Resumen Ejecutivo (PDF)", 
            "3. Mapa",
            "4. GAP CPSSA",
            "5. Gestión de Datos de Crecimiento de Especies"
        ]
        
        # Mapeo de la selección a la función de renderizado
        for option in options:
            is_selected = (st.session_state.current_page == option)
            
            # El tipo se ajusta para simular un botón seleccionado
            button_type = "primary" if is_selected else "secondary"
            
            if st.button(
                option,
                key=f"nav_{option}",
                use_container_width=True,
                type=button_type
            ):
                st.session_state.current_page = option
                st.rerun() # Forzar el cambio de página

        st.markdown("---")
        # Botón de reinicio con el tipo correcto para Streamlit
        if st.button("🔄 Reiniciar Aplicación (Borrar Datos)", type="secondary"):
            reiniciar_app_completo()

    # 2. Contenido Principal
    selection = st.session_state.current_page
    
    # 3. Renderizar la sección seleccionada
    if selection == "1. Cálculo de Captura":
        render_calculadora_y_graficos()
    elif selection == "3. Mapa":
        render_mapa()
    elif selection == "5. Gestión de Datos de Crecimiento de Especies":
        render_gestion_datos()
    elif selection == "2. Resumen Ejecutivo (PDF)":
        st.title("2. Generación de Resumen Ejecutivo (PDF)")
        st.info("Funcionalidad Pendiente de Implementar: Aquí se generaría un informe consolidado con todos los cálculos y gráficos.")
    elif selection == "4. GAP CPSSA":
        st.title("4. GAP CPSSA (Análisis de Brecha)")
        st.info("Funcionalidad Pendiente de Implementar: Esta sección podría contener un análisis comparativo entre la captura actual y los objetivos de la empresa.")


if __name__ == "__main__":
    main_app()