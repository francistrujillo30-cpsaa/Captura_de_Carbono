import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import folium
from streamlit_folium import folium_static
import io
import json

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Plataforma de Gestión NBS", layout="wide", page_icon="🌳")

# --- CONSTANTES GLOBALES Y BASES DE DATOS ---
FACTOR_CARBONO = 0.47
FACTOR_CO2E = 3.67
FACTOR_BGB_SECO = 0.28
AGB_FACTOR_A = 0.112
AGB_FACTOR_B = 0.916
FACTOR_KG_A_TON = 1000 # Constante para conversión

# BASE DE DATOS INICIAL DE DENSIDADES
DENSIDADES = {
    'Eucalipto (E. globulus)': 0.76, 'Cedro (C. odorata)': 0.48, 'Caoba (S. macrophylla)': 0.54,
    'Pino (P. patula)': 0.43, 'Ficus (F. benghalensis)': 0.50, 'Palmera (varias)': 0.35,
    'Roble Andino': 0.65, 'Meijo': 0.60, 'Algarrobo': 0.80, 'Torrellana': 0.55,
    'Palmera hawaii': 0.35, 'Hibiscus tiliaceus (Majao)': 0.65, 'Densidad Manual (g/cm³)': 0.0
}

# FACTORES DE CRECIMIENTO INICIAL
FACTORES_CRECIMIENTO = {
    'Eucalipto (E. globulus)': {'DAP': 0.15, 'Altura': 0.12, 'Agua': 0.0},
    'Pino (P. patula)': {'DAP': 0.10, 'Altura': 0.08, 'Agua': 0.0},
    'Caoba (S. macrophylla)': {'DAP': 0.05, 'Altura': 0.05, 'Agua': 0.0},
    'Factor Manual': {'DAP': 0.05, 'Altura': 0.05, 'Agua': 0.0}
}

# --- DATOS DE LA HUELLA CORPORATIVA (GAP CPSSA) - VALORES REALES 2024 ---
EMISIONES_SEDES = {
    'Planta Pacasmayo': 1265154.79,
    'Planta Piura': 595763.31,
    'Oficina Lima': 612.81,
    'Cantera Virrilá': 432.69,
    'Cantera Tembladera': 361.15,
    'Planta Rioja (Cementos Selva)': 264627.26,
    'DINO Piura': 3939.77,
    'DINO Moche': 3336.06,
    'DINO Trujillo': 1954.46,
    'DISAC Tarapoto': 708.38
}

# --- DEFINICIÓN DE TIPOS DE COLUMNAS ---
df_columns_types = {
    'Especie': str, 'Cantidad': int, 'DAP (cm)': float, 'Altura (m)': float, 
    'Densidad (ρ)': float, 'Biomasa Lote (Ton)': float, 'Carbono Lote (Ton)': float, 
    'CO2e Lote (Ton)': float, 'Detalle Cálculo': str
}
df_columns_numeric = ['Cantidad', 'DAP (cm)', 'Altura (m)', 'Densidad (ρ)', 'Biomasa Lote (Ton)', 'Carbono Lote (Ton)', 'CO2e Lote (Ton)']


# --- FUNCIONES DE CÁLCULO Y MANEJO DE INVENTARIO ---

def calcular_co2_arbol(rho, dap_cm, altura_m):
    """Calcula la biomasa, carbono y CO2e por árbol en KILOGRAMOS."""
    detalle = ""
    if rho <= 0 or dap_cm <= 0 or altura_m <= 0:
        detalle = "ERROR: Valores de entrada (DAP, Altura o Densidad) deben ser mayores a cero."
        return 0, 0, 0, 0, detalle
        
    agb_kg = AGB_FACTOR_A * ((rho * (dap_cm**2) * altura_m)**AGB_FACTOR_B)
    
    biomasa_total = agb_kg * (1 + FACTOR_BGB_SECO)
    carbono_total = biomasa_total * FACTOR_CARBONO
    co2e_total = carbono_total * FACTOR_CO2E
    
    detalle += f"## 1. Biomasa Aérea (AGB) por Árbol\n"
    detalle += f"**Fórmula (kg):** `{AGB_FACTOR_A} * (ρ * DAP² * H)^{AGB_FACTOR_B}` (Chave 2014)\n"
    detalle += f"**Resultado AGB (kg):** `{agb_kg:.4f}`\n\n"
    
    return agb_kg, agb_kg * FACTOR_BGB_SECO, biomasa_total, co2e_total, detalle

def simular_crecimiento(df_inicial, anios_simulacion, factor_dap, factor_altura, max_dap=100, max_altura=30):
    """Simula el crecimiento y calcula el CO2e en TONELADAS."""
    resultados = []
    if df_inicial.empty: return pd.DataFrame()

    rho = df_inicial['Densidad (ρ)'].iloc[0]
    cantidad_arboles = df_inicial['Cantidad'].iloc[0]

    dap_actual = df_inicial['DAP (cm)'].iloc[0]
    altura_actual = df_inicial['Altura (m)'].iloc[0]

    for anio in range(1, anios_simulacion + 1):
        if dap_actual < max_dap: dap_actual *= (1 + factor_dap)
        else: dap_actual = max_dap
            
        if altura_actual < max_altura: altura_actual *= (1 + factor_altura)
        else: altura_actual = max_altura
            
        _, _, _, co2e_uni_kg, _ = calcular_co2_arbol(rho, dap_actual, altura_actual)
        
        co2e_lote_anual_ton = (co2e_uni_kg * cantidad_arboles) / FACTOR_KG_A_TON
        
        resultados.append({
            'Año': anio, 'DAP (cm)': dap_actual, 'Altura (m)': altura_actual, 
            'CO2e Lote (Ton)': co2e_lote_anual_ton,
        })
    
    df_simulacion = pd.DataFrame(resultados)
    df_simulacion['CO2e Acumulado (Ton)'] = df_simulacion['CO2e Lote (Ton)'].cumsum()
    
    return df_simulacion


# --- FUNCIÓN AGREGAR LOTE (ULTRA-DEFENSIVA) ---
def agregar_lote():
    especie = st.session_state.especie_sel
    cantidad = st.session_state.cantidad_input
    dap = st.session_state.dap_slider
    altura = st.session_state.altura_slider
    
    rho = 0.0
    if especie == 'Densidad Manual (g/cm³)' and 'densidad_manual_input' in st.session_state and st.session_state.densidad_manual_input > 0:
        rho = st.session_state.densidad_manual_input
    elif especie != 'Densidad Manual (g/cm³)':
        rho = DENSIDADES[especie]

    if cantidad <= 0 or dap <= 0 or altura <= 0 or rho <= 0:
        st.error("Por favor, asegúrate de que Cantidad, DAP, Altura y Densidad sean mayores a cero.")
        return

    _, _, biomasa_uni_kg, co2e_uni_kg, detalle_calculo = calcular_co2_arbol(rho, dap, altura)
    
    biomasa_lote_ton = (biomasa_uni_kg * cantidad) / FACTOR_KG_A_TON
    carbono_lote_ton = (biomasa_uni_kg * FACTOR_CARBONO * cantidad) / FACTOR_KG_A_TON
    co2e_lote_ton = (co2e_uni_kg * cantidad) / FACTOR_KG_A_TON
    
    # Generar la nueva fila con tipos explícitos
    nueva_fila = pd.DataFrame([{
        'Especie': especie, 
        'Cantidad': int(cantidad), 
        'DAP (cm)': float(dap), 
        'Altura (m)': float(altura), 
        'Densidad (ρ)': float(rho),
        'Biomasa Lote (Ton)': float(biomasa_lote_ton), 
        'Carbono Lote (Ton)': float(carbono_lote_ton), 
        'CO2e Lote (Ton)': float(co2e_lote_ton),
        'Detalle Cálculo': detalle_calculo
    }]).astype(df_columns_types)
    
    # Limpiar el DataFrame existente de cualquier degradación de tipo
    df_actual = st.session_state.inventario_df.copy()
    for col in df_columns_numeric:
        df_actual[col] = pd.to_numeric(df_actual[col], errors='coerce').fillna(0)
    
    # Concatena y actualiza el estado
    st.session_state.inventario_df = pd.concat([df_actual, nueva_fila], ignore_index=True).astype(df_columns_types)
    
    # Recalcular el total de forma segura
    st.session_state.total_co2e_ton = st.session_state.inventario_df['CO2e Lote (Ton)'].sum()
    
    st.session_state.cantidad_input = 0
    st.session_state.dap_slider = 0.0
    st.session_state.altura_slider = 0.0
    st.session_state.especie_sel = list(DENSIDADES.keys())[0]
    st.experimental_rerun()
    
def deshacer_ultimo_lote():
    if not st.session_state.inventario_df.empty:
        st.session_state.inventario_df = st.session_state.inventario_df.iloc[:-1]
        st.session_state.total_co2e_ton = st.session_state.inventario_df['CO2e Lote (Ton)'].sum()
        st.experimental_rerun()

def limpiar_inventario():
    st.session_state.inventario_df = pd.DataFrame(columns=df_columns_types.keys()).astype(df_columns_types)
    st.session_state.total_co2e_ton = 0.0
    st.experimental_rerun()
    
# --- FUNCIÓN ELIMINADA: guardar_memoria (Se elimina porque introduce errores de tipo al serializar)

def generar_excel_memoria(df_inventario, proyecto, hectareas, total_arboles, total_co2e_ton):
    # Función de descarga modificada para usar los datos actuales del inventario
    fecha = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # 1. Hoja de Inventario Detallado (ya en Toneladas)
    df_inventario.drop(columns=['Detalle Cálculo']).to_excel(writer, sheet_name='Inventario Detallado (Ton)', index=False)
    
    # 2. Hoja de Resumen
    df_resumen = pd.DataFrame({
        'Métrica': ['Proyecto', 'Fecha', 'Hectáreas', 'Total Árboles', 'CO2e Total (Ton)', 'CO2e Total (kg)'],
        'Valor': [
            proyecto if proyecto else "Sin Nombre",
            fecha,
            f"{hectareas:.1f}",
            f"{total_arboles:.0f}",
            f"{total_co2e_ton:.2f}", 
            f"{total_co2e_ton * FACTOR_KG_A_TON:.2f}" 
        ]
    })
    df_resumen.to_excel(writer, sheet_name='Resumen Proyecto', index=False)
    
    writer.close()
    processed_data = output.getvalue()
    return processed_data


# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN (SIMPLIFICADA) ---
if 'inventario_df' not in st.session_state:
    st.session_state.inventario_df = pd.DataFrame(columns=df_columns_types.keys()).astype(df_columns_types)
else:
    # Mantenemos la conversión ultra-defensiva de tipos para el DataFrame en memoria
    temp_df = pd.DataFrame(st.session_state.inventario_df).copy()
    for col in df_columns_numeric:
        temp_df[col] = pd.to_numeric(temp_df[col], errors='coerce').fillna(0)
    try:
        st.session_state.inventario_df = temp_df.astype(df_columns_types, errors='ignore')
    except:
        st.session_state.inventario_df = pd.DataFrame(columns=df_columns_types.keys()).astype(df_columns_types)

# Recalcular el total CO2e de forma segura desde el DataFrame limpio
st.session_state.total_co2e_ton = st.session_state.inventario_df['CO2e Lote (Ton)'].sum()


# Reiniciamos las demás variables (Se eliminan las 'memorias_proyectos')
if 'especies_bd' not in st.session_state: st.session_state.especies_bd = pd.DataFrame(columns=['Especie', 'Año', 'DAP (cm)', 'Altura (m)', 'Consumo Agua (L/año)'])
if 'proyecto' not in st.session_state: st.session_state.proyecto = ""
if 'hectareas' not in st.session_state: st.session_state.hectareas = 0.0
if 'dap_slider' not in st.session_state: st.session_state.dap_slider = 0.0
if 'altura_slider' not in st.session_state: st.session_state.altura_slider = 0.0
if 'especie_sel' not in st.session_state: st.session_state.especie_sel = list(DENSIDADES.keys())[0]
if 'cantidad_input' not in st.session_state: st.session_state.cantidad_input = 0


# -------------------------------------------------
# --- SECCIONES DE LA APLICACIÓN (EN FUNCIÓN) ---
# -------------------------------------------------

# --- 1. CÁLCULO Y GRÁFICOS
def render_calculadora_y_graficos():
    st.title("🌳 1. Cálculo de Captura de Carbono")
    
    # --- INFORMACIÓN DEL PROYECTO ---
    st.subheader("📋 Información del Proyecto")
    col_proj, col_hectareas = st.columns([2, 1])

    with col_proj:
        nombre_proyecto = st.text_input("Nombre del Proyecto (Opcional)", value=st.session_state.proyecto, placeholder="Ej: Reforestación Bosque Seco 2024", key='proyecto_input')
        st.session_state.proyecto = nombre_proyecto

    with col_hectareas:
        hectareas = st.number_input("Hectáreas (ha)", min_value=0.0, value=st.session_state.hectareas, step=0.1, key='hectareas_input', help="Dejar en 0 si no se aplica o no se conoce el dato.")
        st.session_state.hectareas = hectareas
            
    st.divider()

    # --- NAVEGACIÓN POR PESTAÑAS (Ahora solo dentro de esta sección) ---
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Datos y Registro", "📈 Visor de Gráficos", "🔬 Detalle Técnico", "🚀 Potencial de Crecimiento"])

    with tab1:
        st.markdown("## 1.1 Registro y Acumulación de Inventario")
        col_input, col_totales = st.columns([1, 2])
        
        with col_input:
            st.subheader("Entrada de Lote por Especie")
            
            with st.form("lote_form", clear_on_submit=False):
                especie_sel = st.selectbox("Especie / Tipo de Árbol", list(DENSIDADES.keys()), key='especie_sel')
                
                if especie_sel == 'Densidad Manual (g/cm³)':
                    st.number_input("Densidad de madera (ρ, g/cm³)", min_value=0.1, max_value=1.5, value=0.5, step=0.01, key='densidad_manual_input')
                else:
                    rho_value = DENSIDADES[especie_sel]
                    st.info(f"Densidad de la madera seleccionada: **{rho_value} g/cm³**")
                
                st.markdown("---")
                
                st.number_input("Cantidad de Árboles (n)", min_value=0, step=1, key='cantidad_input', value=st.session_state.cantidad_input)
                st.slider("DAP promedio (cm)", min_value=0.0, max_value=150.0, step=1.0, key='dap_slider', help="Diámetro a la Altura del Pecho. 🌳", value=st.session_state.dap_slider)
                st.slider("Altura promedio (m)", min_value=0.0, max_value=50.0, step=0.1, key='altura_slider', help="Altura total del árbol. 🌲", value=st.session_state.altura_slider)
                
                st.form_submit_button("➕ Añadir Lote al Inventario", on_click=agregar_lote)

        with col_totales:
            st.subheader("Inventario Acumulado")
            
            # Cálculo de total de árboles (siempre seguro, ya que el DF está limpio)
            total_arboles_registrados = st.session_state.inventario_df['Cantidad'].sum()
            
            if total_arboles_registrados > 0:
                col_deshacer, col_limpiar = st.columns(2)
                col_deshacer.button("↩️ Deshacer Último Lote", on_click=deshacer_ultimo_lote, help="Elimina la última fila añadida a la tabla.")
                col_limpiar.button("🗑️ Limpiar Inventario Total", on_click=limpiar_inventario, help="Elimina todas las entradas y reinicia el cálculo.")
                
                # Botón de Descarga
                col_excel, _ = st.columns([1, 4])
                
                df_inventario_descarga = st.session_state.inventario_df.copy()
                total_co2e_ton_descarga = st.session_state.total_co2e_ton
                
                excel_data = generar_excel_memoria(
                    df_inventario_descarga, 
                    st.session_state.proyecto, 
                    st.session_state.hectareas, 
                    total_arboles_registrados, 
                    total_co2e_ton_descarga
                )
                
                with col_excel:
                    st.download_button(
                        label="Descargar Reporte Excel 💾",
                        data=excel_data,
                        file_name=f"Reporte_NBS_{st.session_state.proyecto if st.session_state.proyecto else 'Inventario'}_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="Descarga el inventario y el resumen del proyecto actual."
                    )
                    
                st.markdown("---")
                st.caption("Detalle de los Lotes Añadidos (Unidades en Toneladas):")
                st.dataframe(st.session_state.inventario_df.drop(columns=['Carbono Lote (Ton)', 'Detalle Cálculo']), use_container_width=True, hide_index=True)
                
            else:
                st.info("Añade el primer lote de árboles para iniciar el inventario.")
                
    with tab2: # Visor de Gráficos
        st.markdown("## 1.2 Resultados Clave y Visualización")
        if st.session_state.inventario_df.empty:
            st.warning("⚠️ No hay datos registrados.")
        else:
            df_inventario = st.session_state.inventario_df.copy()
            total_co2e_ton = st.session_state.total_co2e_ton
            
            # Cálculo seguro de KPIs
            total_arboles_registrados = df_inventario['Cantidad'].sum()
            biomasa_total_ton = df_inventario['Biomasa Lote (Ton)'].sum()

            st.subheader("✅ Indicadores Clave del Proyecto")
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Número de Árboles", f"{total_arboles_registrados:.0f}")
            kpi2.metric("Biomasa Total", f"{biomasa_total_ton:,.2f} Ton")
            kpi3.metric("CO2e Capturado", f"**{total_co2e_ton:,.2f} Toneladas**", delta="Total del Proyecto", delta_color="normal")
            
            # Data para gráficos 
            df_graficos = df_inventario.groupby('Especie').agg(
                Total_CO2e_Ton=('CO2e Lote (Ton)', 'sum'),
                Conteo_Arboles=('Cantidad', 'sum')
            ).reset_index()
            
            fig_co2e = px.bar(df_graficos, x='Especie', y='Total_CO2e_Ton', title='CO2e Capturado por Especie (Ton)', color='Total_CO2e_Ton', color_continuous_scale=px.colors.sequential.Viridis)
            fig_arboles = px.pie(df_graficos, values='Conteo_Arboles', names='Especie', title='Conteo de Árboles por Especie', hole=0.3, color_discrete_sequence=px.colors.sequential.Plasma) 
            
            col_graf1, col_graf2 = st.columns(2)
            with col_graf1: st.plotly_chart(fig_co2e, use_container_width=True)
            with col_graf2: st.plotly_chart(fig_arboles, use_container_width=True)

    with tab3: # Detalle Técnico 
        st.markdown("## 1.3 Detalle Técnico del Lote (Cálculo en kg)")
        if st.session_state.inventario_df.empty: st.info("Aún no hay lotes de árboles registrados.")
        else:
            lotes_info = [
                f"Lote {i+1}: {row['Especie']} ({row['Cantidad']} árboles) - DAP: {row['DAP (cm)']:.1f} cm" 
                for i, row in st.session_state.inventario_df.iterrows()
            ]
            lote_seleccionado_index = st.selectbox("Seleccione el Lote para Inspeccionar el Cálculo:", options=range(len(lotes_info)), format_func=lambda x: lotes_info[x], key='detalle_lote_select')
            st.markdown("---")
            detalle_lote = st.session_state.inventario_df.iloc[lote_seleccionado_index]['Detalle Cálculo']
            st.markdown(f"### Detalles del Lote {lote_seleccionado_index + 1}: {lotes_info[lote_seleccionado_index]}")
            st.code(detalle_lote, language='markdown')

    with tab4: # Potencial de Crecimiento
        st.markdown("## 1.4 Simulación de Potencial de Captura a Largo Plazo")
        if st.session_state.inventario_df.empty: st.info("Por favor, registre al menos un lote de árboles para iniciar la simulación.")
        else:
            df_inventario = st.session_state.inventario_df
            lotes_info = [
                f"Lote {i+1}: {row['Especie']} ({row['Cantidad']} árboles) - DAP Inicial: {row['DAP (cm)']:.1f} cm" 
                for i, row in df_inventario.iterrows()
            ]
            lote_sim_index = st.selectbox("Seleccione el Lote para la Proyección de Crecimiento:", options=range(len(lotes_info)), format_func=lambda x: lotes_info[x], key='sim_lote_select')
            lote_seleccionado = df_inventario.iloc[[lote_sim_index]]
            especie_sim = lote_seleccionado['Especie'].iloc[0]

            col_anios, col_factores = st.columns([1, 2])
            with col_anios: anios_simulacion = st.slider("Años de Proyección", min_value=1, max_value=50, value=20, step=1)
                
            with col_factores:
                factor_inicial = FACTORES_CRECIMIENTO.get(especie_sim, FACTORES_CRECIMIENTO['Factor Manual'])
                st.markdown(f"### Factores de Crecimiento Anual (Especie: **{especie_sim}**)")
                factor_dap_input = st.number_input("Tasa de Crecimiento Anual DAP (%)", min_value=0.01, max_value=0.30, value=factor_inicial['DAP'], step=0.01, format="%.2f", key='factor_dap_sim')
                factor_altura_input = st.number_input("Tasa de Crecimiento Anual Altura (%)", min_value=0.01, max_value=0.30, value=factor_inicial['Altura'], step=0.01, format="%.2f", key='factor_alt_sim')
                max_dap_input = st.number_input("DAP Máximo de Madurez (cm)", min_value=10.0, max_value=300.0, value=100.0, step=10.0)
                max_altura_input = st.number_input("Altura Máxima de Madurez (m)", min_value=5.0, max_value=100.0, value=30.0, step=5.0)

            df_simulacion = simular_crecimiento(lote_seleccionado, anios_simulacion, factor_dap_input, factor_altura_input, max_dap_input, max_altura_input)

            st.markdown("---")
            st.subheader(f"Resultados de la Simulación a {anios_simulacion} Años")
            if not df_simulacion.empty:
                co2e_final = df_simulacion['CO2e Acumulado (Ton)'].iloc[-1]
                st.metric("Potencial de Captura Total (Toneladas CO2e)", f"**{co2e_final:,.2f} Ton**")
                fig_proj = px.line(df_simulacion, x='Año', y='CO2e Acumulado (Ton)', title='Captura Acumulada de CO2e vs. Tiempo', labels={'CO2e Acumulado (Ton)': 'CO2e Acumulado (Ton)', 'Año': 'Año'}, markers=True)
                st.plotly_chart(fig_proj, use_container_width=True)
                st.caption("Detalle Anual de la Simulación:")
                st.dataframe(df_simulacion, use_container_width=True, hide_index=True)


# --- 2. GESTIÓN DE MEMORIAS (SE ELIMINA ESTA SECCIÓN) ---
def render_gestion_memorias():
    st.title("🚫 2. Gestión de Memorias de Proyectos (Funcionalidad Retirada)")
    st.warning("La funcionalidad de 'Gestión de Memorias' ha sido retirada temporalmente ya que causaba errores de tipo en la suma de inventario. Use el botón 'Descargar Reporte Excel' en la Sección 1 para guardar los datos.")


# --- 3. MAPA ---
def render_mapa():
    st.title("🗺️ 3. Localización del Proyecto")

    lat = st.number_input("Latitud", min_value=-90.0, max_value=90.0, value=-8.000000, step=0.000001, format="%.6f", key='map_lat')
    lon = st.number_input("Longitud", min_value=-180.0, max_value=180.0, value=-78.000000, step=0.000001, format="%.6f", key='map_lon')
    zoom = st.slider("Nivel de Zoom", min_value=1, max_value=20, value=8, key='map_zoom')
    
    m = folium.Map(location=[lat, lon], zoom_start=zoom)
    folium.Marker([lat, lon], popup=st.session_state.proyecto if st.session_state.proyecto else 'Ubicación del Proyecto').add_to(m)
    
    folium_static(m) 

# --- 4. GAP CPSSA ---
def render_gap_cpassa():
    st.title("📈 4. Análisis GAP de Mitigación Corporativa (CPSSA)")
    
    co2e_proyecto_ton = st.session_state.total_co2e_ton 
    
    if co2e_proyecto_ton <= 0:
        st.warning("⚠️ El inventario del proyecto debe tener CO2e registrado (sección 1) para realizar este análisis.")
        return

    st.subheader("Selección de Sede y Análisis")
    
    sede_sel = st.selectbox("Seleccione la Sede (Huella Corporativa)", list(EMISIONES_SEDES.keys()))
    
    emisiones_sede_ton = EMISIONES_SEDES[sede_sel] / FACTOR_KG_A_TON
    
    st.markdown("---")
    
    col_sede, col_proyecto = st.columns(2)
    
    with col_sede:
        st.metric(f"Emisiones Anuales de '{sede_sel}' (Ton CO2e)", f"**{emisiones_sede_ton:,.2f} Ton**", help="Valor extraído del Informe de Huella de Carbono Corporativa 2024, convertido a Toneladas.")
    
    with col_proyecto:
        st.metric("Captura Total del Proyecto (Ton CO2e)", f"**{co2e_proyecto_ton:,.2f} Ton**", delta="Total del Inventario Actual")
        
    if emisiones_sede_ton > 0:
        porcentaje_mitigacion = (co2e_proyecto_ton / emisiones_sede_ton) * 100
        
        st.subheader("Resultado del GAP de Mitigación")
        
        st.progress(min(100, int(porcentaje_mitigacion)))
        
        if porcentaje_mitigacion >= 100:
            st.success(f"¡Mitigación Completa! El proyecto compensa el **{porcentaje_mitigacion:,.2f}%** de las emisiones de '{sede_sel}'.")
        else:
            st.info(f"El proyecto compensa el **{porcentaje_mitigacion:,.2f}%** de las emisiones anuales de '{sede_sel}'.")

        co2e_restante = max(0, emisiones_sede_ton - co2e_proyecto_ton)
        st.metric("CO2e Restante por Mitigar", f"**{co2e_restante:,.2f} Ton**")

# --- 5. GESTIÓN DE ESPECIE ---
def render_gestion_especie():
    st.title("🌿 5. Gestión de Datos de Crecimiento de Especies")
    st.markdown("Edite o ingrese datos de crecimiento (DAP, Altura) y consumo de agua por año para las especies, construyendo una base de datos histórica para refinar las simulaciones de crecimiento futuras.")

    st.subheader("Base de Datos Histórica de Especies (Editable)")

    especie_list = list(DENSIDADES.keys())
    especie_list.remove('Densidad Manual (g/cm³)')
    especie_a_gestionar = st.selectbox("Seleccione la Especie a Gestionar", especie_list, key='gestion_especie_sel')

    df_filtrado = st.session_state.especies_bd[st.session_state.especies_bd['Especie'] == especie_a_gestionar]
    
    # Crear un DataFrame base para el editor si no hay datos
    if df_filtrado.empty:
        df_base = pd.DataFrame({'Especie': [especie_a_gestionar], 'Año': [1], 'DAP (cm)': [0.0], 'Altura (m)': [0.0], 'Consumo Agua (L/año)': [0.0]})
        df_edit = st.data_editor(df_base, num_rows="dynamic", use_container_width=True)
    else:
        df_edit = st.data_editor(df_filtrado, num_rows="dynamic", use_container_width=True)
        
    if st.button(f"Guardar Cambios en la BD de {especie_a_gestionar}"):
        
        st.session_state.especies_bd = st.session_state.especies_bd[st.session_state.especies_bd['Especie'] != especie_a_gestionar]
        
        df_validas = df_edit[(df_edit['DAP (cm)'] > 0) | (df_edit['Altura (m)'] > 0) | (df_edit['Consumo Agua (L/año)'] > 0)].copy()
        
        df_validas['Especie'] = especie_a_gestionar
        
        new_data = pd.concat([st.session_state.especies_bd, df_validas], ignore_index=True)
        st.session_state.especies_bd = new_data.sort_values(by=['Especie', 'Año'])

        st.success(f"Datos de crecimiento y agua para '{especie_a_gestionar}' actualizados y guardados.")
        st.experimental_rerun()

    st.markdown("---")
    st.caption("Estructura de la Base de Datos Completa:")
    st.dataframe(st.session_state.especies_bd, use_container_width=True)

# -------------------------------------------------
# --- FUNCIÓN PRINCIPAL DE LA APLICACIÓN ---
# -------------------------------------------------
def main_app():
    
    st.sidebar.title("Menú de Navegación")
    
    # Menú sin la sección 2
    menu_options = [
        "1. Cálculo de Captura", 
        "3. Mapa", 
        "4. GAP CPSSA", 
        "5. Gestión de Especie"
    ]
    
    selection = st.sidebar.selectbox("Seleccione la Sección", menu_options)
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Proyecto: " + (st.session_state.proyecto if st.session_state.proyecto else "Sin nombre"))
    st.sidebar.metric("CO2e Inventario Total", f"{st.session_state.total_co2e_ton:,.2f} Ton")
    
    if selection == "1. Cálculo de Captura":
        render_calculadora_y_graficos()
    # Se omite la opción 2 para que no aparezca el error
    elif selection == "3. Mapa":
        render_mapa()
    elif selection == "4. GAP CPSSA":
        render_gap_cpassa()
    elif selection == "5. Gestión de Especie":
        render_gestion_especie()
    
    st.caption("Fórmula: AGB = 0.112 × (ρ × D² × H)^0.916 | Chave et al. (2014). Factores C=0.47, BGB=0.28, CO2e=3.67. Unidades en Toneladas.")

# --- LÍNEA VITAL DE EJECUCIÓN ---
if __name__ == '__main__':
    main_app()