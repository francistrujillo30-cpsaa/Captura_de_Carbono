import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go 
import io
import json
import re 

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Plataforma de Gestión NBS", layout="wide", page_icon="🌳")

# --- CONSTANTES GLOBALES Y BASES DE DATOS ---
FACTOR_CARBONO = 0.47
FACTOR_CO2E = 3.67
FACTOR_BGB_SECO = 0.28
AGB_FACTOR_A = 0.112
AGB_FACTOR_B = 0.916
FACTOR_KG_A_TON = 1000 # Constante para conversión

# CONSTANTES PARA COSTOS 
PRECIO_AGUA_POR_M3 = 3.0 # Precio fijo del m3 de agua en Perú (3 Soles)
FACTOR_L_A_M3 = 1000 # 1 m3 = 1000 Litros

# BASE DE DATOS INICIAL DE DENSIDADES, AGUA Y COSTO
# [FIX: ELIMINACIÓN SUPERVIVENCIA] Se ha removido el campo 'Supervivencia (%)'
DENSIDADES_BASE = {
    # DATOS ACTUALIZADOS DE LA IMAGEN DE REFERENCIA:
    
    # Especies existentes actualizadas con nuevos valores:
    'Eucalipto Torrellana (Corymbia torelliana)': {'Densidad': 0.68, 'Agua_L_Anio': 1500, 'Precio_Plantón': 5.00, 'DAP_Max': 43.0, 'Altura_Max': 30.0, 'Tiempo_Max_Anios': 15}, 
    'Majoe (Hibiscus tiliaceus)': {'Densidad': 0.55, 'Agua_L_Anio': 1200, 'Precio_Plantón': 5.00, 'DAP_Max': 30.0, 'Altura_Max': 12.0, 'Tiempo_Max_Anios': 20}, 
    'Molle (Schinus molle)': {'Densidad': 0.73, 'Agua_L_Anio': 900, 'Precio_Plantón': 6.00, 'DAP_Max': 65.0, 'Altura_Max': 13.0, 'Tiempo_Max_Anios': 40},
    'Algarrobo (Prosopis pallida)': {'Densidad': 0.8, 'Agua_L_Anio': 800, 'Precio_Plantón': 4.00, 'DAP_Max': 60.0, 'Altura_Max': 14.0, 'Tiempo_Max_Anios': 50},
    
    # Especies nuevas añadidas (Agua y Precio por defecto):
    'Shaina (Colubrina glandulosa Perkins)': {'Densidad': 0.63, 'Agua_L_Anio': 1000, 'Precio_Plantón': 5.00, 'DAP_Max': 40.0, 'Altura_Max': 20.0, 'Tiempo_Max_Anios': 28},
    'Limoncillo (Melicoccus bijugatus)': {'Densidad': 0.68, 'Agua_L_Anio': 1000, 'Precio_Plantón': 5.00, 'DAP_Max': 40.0, 'Altura_Max': 18.0, 'Tiempo_Max_Anios': 33},
    'Capirona (Calycophyllum decorticans)': {'Densidad': 0.78, 'Agua_L_Anio': 1000, 'Precio_Plantón': 5.00, 'DAP_Max': 38.0, 'Altura_Max': 25.0, 'Tiempo_Max_Anios': 23},
    'Bolaina (Guazuma crinita)': {'Densidad': 0.48, 'Agua_L_Anio': 1000, 'Precio_Plantón': 5.00, 'DAP_Max': 25.0, 'Altura_Max': 20.0, 'Tiempo_Max_Anios': 10},
    'Amasisa (Erythrina fusca)': {'Densidad': 0.38, 'Agua_L_Anio': 1000, 'Precio_Plantón': 5.00, 'DAP_Max': 33.0, 'Altura_Max': 15.0, 'Tiempo_Max_Anios': 15},
    'Moena (Ocotea aciphylla)': {'Densidad': 0.58, 'Agua_L_Anio': 1000, 'Precio_Plantón': 5.00, 'DAP_Max': 65.0, 'Altura_Max': 33.0, 'Tiempo_Max_Anios': 45},
    'Huayruro (Ormosia coccinea)': {'Densidad': 0.73, 'Agua_L_Anio': 1000, 'Precio_Plantón': 5.00, 'DAP_Max': 70.0, 'Altura_Max': 33.0, 'Tiempo_Max_Anios': 65},
    'Paliperro (Miconia barbeyana Cogniaux)': {'Densidad': 0.58, 'Agua_L_Anio': 1000, 'Precio_Plantón': 5.00, 'DAP_Max': 40.0, 'Altura_Max': 20.0, 'Tiempo_Max_Anios': 28},
    'Cedro (Cedrela odorata)': {'Densidad': 0.43, 'Agua_L_Anio': 1000, 'Precio_Plantón': 5.00, 'DAP_Max': 55.0, 'Altura_Max': 30.0, 'Tiempo_Max_Anios': 28},
    'Guayacán (Gualacum officinale)': {'Densidad': 0.54, 'Agua_L_Anio': 1000, 'Precio_Plantón': 5.00, 'DAP_Max': 45.0, 'Altura_Max': 12.0, 'Tiempo_Max_Anios': 60},
}

# HUELLA DE CARBONO CORPORATIVA POR SEDE (EN MILES DE tCO2e)
# ... (Se mantiene igual) ...

# --- DEFINICIÓN DE TIPOS DE COLUMNAS ---
# ... (Se mantiene igual) ...

# --- FUNCIÓN CRÍTICA: DINÁMICA DE ESPECIES ---
def get_current_species_info():
    """
    Genera un diccionario de información de especies (Densidad, Agua, Precio, Maximos) 
    fusionando las especies base con las especies añadidas/modificadas por el usuario.
    """
    current_info = {
        name: {
            'Densidad': data['Densidad'], 
            'Agua_L_Anio': data['Agua_L_Anio'], 
            'Precio_Plantón': data['Precio_Plantón'],
            'DAP_Max': data['DAP_Max'],
            'Altura_Max': data['Altura_Max'],
            'Tiempo_Max_Anios': data['Tiempo_Max_Anios'],
        }
        for name, data in DENSIDADES_BASE.items()
    }
    
    df_bd = st.session_state.get('especies_bd', pd.DataFrame())
    if df_bd.empty:
        # [FIX: ELIMINACIÓN SUPERVIVENCIA] Defaults sin factor de supervivencia
        current_info['Densidad/Datos Manuales'] = {'Densidad': 0.0, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 0.0, 'DAP_Max': 20.0, 'Altura_Max': 10.0, 'Tiempo_Max_Anios': 10}
        return current_info
        
    df_unique_info = df_bd.drop_duplicates(subset=['Especie'], keep='last')
    
    for _, row in df_unique_info.iterrows():
        especie_name = row['Especie']
        
        # Asegurar la conversión segura de los campos base
        densidad_val = pd.to_numeric(row.get('Densidad (g/cm³)', 0.0), errors='coerce') 
        agua_val = pd.to_numeric(row.get('Consumo Agua (L/año)', 0.0), errors='coerce')
        precio_val = pd.to_numeric(row.get('Precio Plantón (S/)', 0.0), errors='coerce') 
        
        # Campos máximos
        dap_max_val = pd.to_numeric(row.get('DAP Máximo (cm)', 0.0), errors='coerce') 
        altura_max_val = pd.to_numeric(row.get('Altura Máxima (m)', 0.0), errors='coerce')
        tiempo_max_val = pd.to_numeric(row.get('Tiempo Máximo (años)', 0), errors='coerce')
        
        if pd.notna(densidad_val) and densidad_val > 0:
            current_info[especie_name] = {
                'Densidad': densidad_val,
                'Agua_L_Anio': agua_val if pd.notna(agua_val) and agua_val >= 0 else 0.0,
                'Precio_Plantón': precio_val if pd.notna(precio_val) and precio_val >= 0 else 0.0,
                # Campos Máximos
                'DAP_Max': dap_max_val if pd.notna(dap_max_val) and dap_max_val >= 0 else 0.0,
                'Altura_Max': altura_max_val if pd.notna(altura_max_val) and altura_max_val >= 0 else 0.0,
                'Tiempo_Max_Anios': int(tiempo_max_val) if pd.notna(tiempo_max_val) and tiempo_max_val >= 0 else 0,
            }
    
    # [FIX: ELIMINACIÓN SUPERVIVENCIA] Defaults sin factor de supervivencia
    current_info['Densidad/Datos Manuales'] = {'Densidad': 0.0, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 0.0, 'DAP_Max': 20.0, 'Altura_Max': 10.0, 'Tiempo_Max_Anios': 10}
    
    return current_info


# --- FUNCIONES DE CÁLCULO Y MANEJO DE INVENTARIO ---
# ... (Funciones auxiliares se mantienen igual) ...

# --- FUNCIÓN DE RECÁLCULO SEGURO (CRÍTICA - PROGRESO) ---
def recalcular_inventario_completo(inventario_list):
    """
    [LÓGICA DE PROGRESO] Usa DAP y Altura MEDIDOS por el usuario. No aplica factor de supervivencia.
    """
    if not inventario_list:
        all_cols = list(df_columns_types.keys()) + columnas_salida
        dtype_map = {**df_columns_types, **dict.fromkeys(columnas_salida, float)}
        dtype_map = {k: v for k, v in dtype_map.items() if k in all_cols}
        return pd.DataFrame(columns=all_cols).astype(dtype_map)


    # 1. Crear DF base
    df_base = pd.DataFrame(inventario_list)
    df_calculado = df_base.copy()
    current_species_info = get_current_species_info() 
    
    if 'Detalle Cálculo' in df_calculado.columns:
        df_calculado = df_calculado.drop(columns=['Detalle Cálculo'])
    
    # 2. Asegurar columnas y tipos
    required_input_cols = [col for col in df_columns_types.keys() if col != 'Detalle Cálculo'] 
    for col in required_input_cols:
        if col not in df_calculado.columns:
            if df_columns_types[col] == str: default_val = ""
            elif df_columns_types[col] == int: default_val = 0
            else: default_val = 0.0
            df_calculado[col] = default_val
    
    for col in df_columns_numeric:
        df_calculado[col] = pd.to_numeric(df_calculado[col], errors='coerce').fillna(0)
    
    resultados_calculo = []
    riego_activado = st.session_state.get('riego_controlado_check', False)
    
    for _, row in df_calculado.iterrows():
        rho = row['Densidad (ρ)']
        dap = row['DAP (cm)']
        altura = row['Altura (m)']
        cantidad = row['Cantidad']
        consumo_agua_uni_base = row['Consumo Agua Unitario (L/año)'] 
        precio_planton_uni = row['Precio Plantón Unitario (S/)'] 
        años_plantados = row['Años Plantados'] 

        # 1. Cálculo de CO2e (Biomasa, Carbono, CO2e por árbol en kg)
        _, _, biomasa_uni_kg, co2e_uni_kg, detalle = calcular_co2_arbol(rho, dap, altura)
        
        # 2. Conversión a TONELADAS y Lote (Usando la cantidad COMPLETA, sin factor de supervivencia)
        biomasa_lote_ton = (biomasa_uni_kg * cantidad) / FACTOR_KG_A_TON
        carbono_lote_ton = (biomasa_uni_kg * FACTOR_CARBONO * cantidad) / FACTOR_KG_A_TON
        co2e_lote_ton = (co2e_uni_kg * cantidad) / FACTOR_KG_A_TON

        # 3. Costo y Agua (Se aplican a la cantidad INICIAL)
        costo_planton_lote = cantidad * precio_planton_uni
        
        if riego_activado:
            consumo_agua_uni = consumo_agua_uni_base
            años_para_costo = años_plantados
        else:
            consumo_agua_uni = 0.0
            años_para_costo = 0 
            
        consumo_agua_lote_l = cantidad * consumo_agua_uni
        
        volumen_agua_lote_m3_anual = consumo_agua_lote_l / FACTOR_L_A_M3
        costo_agua_anual_lote = volumen_agua_lote_m3_anual * PRECIO_AGUA_POR_M3
        costo_agua_acumulado_lote = costo_agua_anual_lote * años_para_costo
        
        costo_total_lote = costo_planton_lote + costo_agua_acumulado_lote
        
        # 4. Detalle de cálculo (se usa el detalle original, sin modificar por supervivencia)
        detalle_final = detalle
        
        resultados_calculo.append({
            'Biomasa Lote (Ton)': biomasa_lote_ton,
            'Carbono Lote (Ton)': carbono_lote_ton,
            'CO2e Lote (Ton)': co2e_lote_ton,
            'Consumo Agua Total Lote (L)': consumo_agua_lote_l,
            'Costo Total Lote (S/)': costo_total_lote, 
            'Detalle Cálculo': detalle_final
        })

    # 5. Unir los resultados
    df_resultados = pd.DataFrame(resultados_calculo)
    df_final = pd.concat([df_calculado.reset_index(drop=True), df_resultados], axis=1)
    
    # 6. Aplicar tipos de datos para las columnas de salida
    dtype_map = {col: float for col in columnas_salida if col in df_final.columns}
    df_final = df_final.astype(dtype_map)

    return df_final


# [FUNCIÓN DE CÁLCULO - POTENCIAL MÁXIMO] 
def calcular_potencial_maximo_lotes(inventario_list, current_species_info):
    """
    [LÓGICA DE POTENCIAL MÁXIMO] Usa DAP_Max y Altura_Max de la base de datos.
    No aplica factor de supervivencia.
    """
    if not inventario_list:
        return pd.DataFrame()

    df_base = pd.DataFrame(inventario_list)
    df_potencial = df_base.copy()
    
    # Asegurar la conversión segura de columnas requeridas
    for col in ['Cantidad', 'Densidad (ρ)']:
        df_potencial[col] = pd.to_numeric(df_potencial[col], errors='coerce').fillna(0)
    
    resultados_calculo = []
    
    for _, row in df_potencial.iterrows():
        especie = row['Especie']
        cantidad = row['Cantidad']
        
        # Obtener los valores máximos
        info = current_species_info.get(especie)
        
        rho = 0.0
        dap = 0.0
        altura = 0.0
        tiempo_max = 0
        co2e_lote_ton = 0.0
        detalle = ""

        # --- Lógica de Asignación de Valores Máximos ---
        if info and especie != 'Densidad/Datos Manuales':
            rho = info['Densidad']
            dap = info['DAP_Max']
            altura = info['Altura_Max']
            tiempo_max = info['Tiempo_Max_Anios']
        elif especie == 'Densidad/Datos Manuales':
            # Valores por defecto para manuales (sin factor de supervivencia)
            info_manual = current_species_info.get('Densidad/Datos Manuales', {'Densidad': 0.0, 'DAP_Max': 0.0, 'Altura_Max': 0.0, 'Tiempo_Max_Anios': 0})
            rho = row['Densidad (ρ)'] if row['Densidad (ρ)'] > 0 else info_manual['Densidad']
            dap = info_manual['DAP_Max']
            altura = info_manual['Altura_Max']
            tiempo_max = info_manual['Tiempo_Max_Anios']
        else:
            rho = row['Densidad (ρ)']
            dap = row['DAP (cm)']
            altura = row['Altura (m)']
            tiempo_max = 0
        
        
        if dap <= 0 or altura <= 0 or rho <= 0 or cantidad <= 0:
            co2e_lote_ton = 0.0
            detalle = "ERROR: Valores DAP/Altura/Densidad/Cantidad deben ser > 0 para el cálculo potencial."
        else:
             # 1. Cálculo de CO2e unitario (kg)
             _, _, _, co2e_uni_kg, detalle = calcular_co2_arbol(rho, dap, altura)
             
             # 2. Conversión a TONELADAS y Lote (Usando la cantidad COMPLETA, sin factor de supervivencia)
             co2e_lote_ton = (co2e_uni_kg * cantidad) / FACTOR_KG_A_TON

        
        resultados_calculo.append({
            'Especie': especie,
            'Cantidad': cantidad,
            'Densidad (ρ)': rho,
            'DAP Potencial (cm)': dap,
            'Altura Potencial (m)': altura,
            'Tiempo Máximo (años)': tiempo_max,
            'CO2e Lote Potencial (Ton)': co2e_lote_ton,
            'Detalle Cálculo': detalle # JSON string
        })

    df_resultados = pd.DataFrame(resultados_calculo)
    return df_resultados


# --- MANEJO DE ESTADO DE SESIÓN Y UTILIDADES ---

def inicializar_estado_de_sesion():
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "1. Cálculo de Progreso" 
    if 'inventario_list' not in st.session_state:
        st.session_state.inventario_list = []
    if 'especies_bd' not in st.session_state:
        # [FIX: ELIMINACIÓN SUPERVIVENCIA] Remoción de Supervivencia (%)
        df_cols = ['Especie', 'DAP (cm)', 'Altura (m)', 'Consumo Agua (L/año)', 'Densidad (g/cm³)', 'Precio Plantón (S/)', 'DAP Máximo (cm)', 'Altura Máxima (m)', 'Tiempo Máximo (años)'] 
        data_rows = [
            (name, 5.0, 5.0, data['Agua_L_Anio'], data['Densidad'], data['Precio_Plantón'], data['DAP_Max'], data['Altura_Max'], data['Tiempo_Max_Anios']) 
            for name, data in DENSIDADES_BASE.items()
        ]
        df_bd_inicial = pd.DataFrame(data_rows, columns=df_cols)
        st.session_state.especies_bd = df_bd_inicial
    if 'riego_controlado_check' not in st.session_state:
        st.session_state.riego_controlado_check = True 
    if 'proyecto' not in st.session_state:
        st.session_state.proyecto = ""
    if 'hectareas' not in st.session_state:
        st.session_state.hectareas = 0.0
    if 'dap_slider' not in st.session_state:
        st.session_state.dap_slider = 5
    if 'altura_slider' not in st.session_state:
        st.session_state.altura_slider = 5
    if 'anios_plantados_input' not in st.session_state:
        st.session_state.anios_plantados_input = 1
    if 'densidad_manual_input' not in st.session_state:
        st.session_state.densidad_manual_input = 0.500
    if 'consumo_agua_manual_input' not in st.session_state:
        st.session_state.consumo_agua_manual_input = 1000.0


# ... (resto de funciones auxiliares se mantienen igual) ...

# --- FUNCIONES DE VISUALIZACIÓN ---

def render_calculadora_y_graficos():
    """Función principal para la sección de cálculo y gráficos del progreso actual."""
    st.title("1. Cálculo de Progreso del Proyecto🌳")

    # --- Lógica de Riego Controlado (Checkbox) ---
    st.markdown("## ⚙️ Configuración del Proyecto")
    riego_controlado = st.checkbox(
        "**Proyecto con Riego Controlado y Costo Operativo (Agua)**", 
        value=st.session_state.riego_controlado_check, 
        key='riego_controlado_check',
        help="Marque esta opción para incluir el consumo de agua (Litros/año) y su costo (S/) acumulado basado en 'Años Plantados'."
    )
    st.divider()
    
    current_species_info = get_current_species_info()
    df_inventario_completo = recalcular_inventario_completo(st.session_state.inventario_list)
    co2e_proyecto_ton = get_co2e_total_seguro(df_inventario_completo)
    costo_proyecto_total = get_costo_total_seguro(df_inventario_completo)
    agua_proyecto_total = get_agua_total_seguro(df_inventario_completo)

    # ... (Sección de Información del Proyecto se mantiene igual) ...

    # --- NAVEGACIÓN POR PESTAÑAS ---
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Datos y Registro", "📈 Visor de Gráficos", "🔬 Detalle Técnico", "🌍 Equivalencias Ambientales"])
    
    with tab1:
        st.markdown("## Registro de Lotes📝")
        col_form, col_totales = st.columns([2, 1])

        with col_form:
            st.markdown("### Datos del Nuevo Lote")
            with st.form("form_lote", clear_on_submit=True):
                
                # 1. Especie, Cantidad y Precio Plantón
                col_esp, col_cant, col_precio_pl = st.columns(3)
                especie_keys = list(current_species_info.keys())
                especie_sel = col_esp.selectbox(
                    "Especie Forestal:", 
                    options=especie_keys,
                    key='especie_seleccionada',
                    help="Seleccione una especie o 'Datos Manuales'."
                )
                
                col_cant.number_input("Cantidad de Árboles", min_value=1, value=100, step=1, key='cantidad_input')
                
                # Obtener el precio por defecto para precargar el input
                precio_default = current_species_info.get(especie_sel, {}).get('Precio_Plantón', 0.0)
                
                if especie_sel != st.session_state.get('last_especie_sel') or st.session_state.get('first_run_form_lote', True):
                    st.session_state.precio_planton_input = precio_default
                    st.session_state.last_especie_sel = especie_sel
                    st.session_state.first_run_form_lote = False

                col_precio_pl.number_input(
                    "Precio Plantón Unitario (S/)", 
                    min_value=0.0, 
                    value=st.session_state.precio_planton_input, 
                    step=0.1, 
                    format="%.2f",
                    key='precio_planton_input', 
                    help="Costo de inversión por plantón. Puede editarlo."
                )

                # 2. Datos Físicos (DAP y Altura)
                col_dap, col_altura = st.columns(2)
                
                col_dap.slider(
                    "DAP medido (cm)", 
                    min_value=0, max_value=50, 
                    step=1, 
                    key='dap_slider', 
                    help="Diámetro a la altura del pecho. 🌳", 
                    value=int(st.session_state.dap_slider) 
                )
                col_altura.slider(
                    "Altura medida (m)", 
                    min_value=0, max_value=50, 
                    step=1, 
                    key='altura_slider', 
                    help="Altura total del árbol. 🌲", 
                    value=int(st.session_state.altura_slider) 
                )
                
                # 3. Años Plantados
                st.number_input(
                    "Años Plantados (Edad del lote)", 
                    min_value=0, 
                    value=st.session_state.anios_plantados_input, 
                    step=1, 
                    key='anios_plantados_input',
                    help="Define la edad actual del lote, usada para calcular la acumulación de CO2e y el costo de agua acumulado (si el riego está activado)."
                )

                # 4. Datos de Densidad/Agua (Manual si aplica)
                
                if especie_sel == 'Densidad/Datos Manuales':
                    st.markdown("---")
                    st.markdown("##### ✍️ Ingrese Datos Manuales de Densidad y Consumo de Agua")
                    col_dens, col_agua = st.columns(2)
                    col_dens.number_input("Densidad (ρ) (g/cm³)", min_value=0.001, value=st.session_state.densidad_manual_input, step=0.05, format="%.3f", key='densidad_manual_input')
                    col_agua.number_input("Consumo Agua Unitario (L/año)", min_value=0.0, value=st.session_state.consumo_agua_manual_input, step=100.0, key='consumo_agua_manual_input')
                    
                    st.info(f"Usando datos manuales para Densidad y Consumo de Agua.")

                else:
                    agua_info = current_species_info[especie_sel]['Agua_L_Anio']
                    densidad_info = current_species_info[especie_sel]['Densidad']
                    
                    info_agua_str = f"| Agua: **{agua_info} L/año**." if riego_controlado else "."
                    st.info(f"Usando valores por defecto para {especie_sel}: Densidad: **{densidad_info} g/cm³** {info_agua_str}")
                
                if not riego_controlado:
                    st.info("⚠️ El costo del agua no se contabilizará, ya que la casilla 'Riego Controlado' no está marcada.")
                    
                st.form_submit_button("➕ Añadir Lote al Inventario", on_click=agregar_lote)

        # ... (Sección de Totales y Descarga se mantiene igual) ...

        st.markdown("---")
        st.subheader("Inventario Detallado (Lotes)")
        
        if df_inventario_completo.empty:
            st.info("No hay lotes registrados. Use el formulario superior para empezar.")
        else:
            cols_to_drop = [col for col in ['Detalle Cálculo'] if col in df_inventario_completo.columns]
            df_mostrar = df_inventario_completo.drop(columns=cols_to_drop)
            
            st.dataframe(
                df_mostrar.style.format({
                    'DAP (cm)': '{:,.2f}',
                    'Altura (m)': '{:,.2f}',
                    'Densidad (ρ)': '{:,.3f}',
                    'Consumo Agua Unitario (L/año)': '{:,.0f}',
                    'Precio Plantón Unitario (S/)': 'S/{:,.2f}',
                    'Biomasa Lote (Ton)': '{:,.2f}',
                    'Carbono Lote (Ton)': '{:,.2f}',
                    'CO2e Lote (Ton)': '{:,.2f}',
                    'Consumo Agua Total Lote (L)': '{:,.0f}',
                    'Costo Total Lote (S/)': 'S/{:,.2f}',
                }),
                use_container_width=True
            )
            
    # ... (tab2, tab3, tab4 se mantienen igual) ...


# [FUNCIÓN DE VISUALIZACIÓN - POTENCIAL MÁXIMO]
def render_potencial_maximo():
    """Calcula y muestra el potencial máximo de captura de CO2e utilizando los datos de la especie."""
    st.title("2. Potencial Máximo de Captura de Carbono (Escenario Máximo) 🚀")
    
    st.info("Este cálculo utiliza los valores máximos de DAP y Altura por **bibliografía** de cada especie en los lotes registrados en el inventario (Sección 1) para determinar el potencial máximo de captura de CO₂e del proyecto.")

    current_species_info = get_current_species_info()
    df_inventario_progreso = recalcular_inventario_completo(st.session_state.inventario_list)
    
    if df_inventario_progreso.empty:
        st.warning("No hay lotes registrados en el inventario (Sección 1) para calcular el potencial máximo.")
        return

    # Se ejecuta el cálculo usando los datos máximos de CADA especie en el inventario
    df_potencial = calcular_potencial_maximo_lotes(st.session_state.inventario_list, current_species_info)
    
    co2e_potencial_total = df_potencial['CO2e Lote Potencial (Ton)'].sum()
    co2e_progreso_total = get_co2e_total_seguro(df_inventario_progreso)
    brecha_potencial = co2e_potencial_total - co2e_progreso_total
    
    st.markdown("---")
    st.subheader("Resultados del Potencial Máximo del Inventario Actual")
    
    col_max, col_gap = st.columns(2)
    
    with col_max:
        st.metric("🌱 Captura CO₂e Total Potencial (Máx)", f"{co2e_potencial_total:,.2f} Toneladas")
    
    with col_gap:
        st.metric(
            "Diferencia: Potencial vs. Progreso Actual",
            f"{brecha_potencial:,.2f} Toneladas",
            delta=f"Falta capturar para alcanzar el potencial máximo."
        )
    
    st.markdown("---")
    st.subheader("Detalle del Potencial Máximo por Especie")

    # Agrupar por especie para el detalle y la gráfica
    df_agrupado = df_potencial.groupby('Especie').agg(
        Total_Cantidad=('Cantidad', 'sum'),
        Total_CO2e_Potencial=('CO2e Lote Potencial (Ton)', 'sum'),
        DAP_Max=('DAP Potencial (cm)', 'first'), 
        Altura_Max=('Altura Potencial (m)', 'first'), 
        Tiempo_Max=('Tiempo Máximo (años)', 'first'),
        # [FIX: ELIMINACIÓN SUPERVIVENCIA] Se ha eliminado la métrica de Supervivencia (%)
    ).reset_index()

    # Se excluye 'Detalle Cálculo' de la visualización principal
    cols_to_show = ['Especie', 'Total_Cantidad', 'DAP_Max', 'Altura_Max', 'Tiempo_Max', 'Total_CO2e_Potencial']
    df_mostrar = df_agrupado[cols_to_show].rename(columns={
        'Total_Cantidad': 'Cantidad Total de Árboles',
        'DAP_Max': 'DAP Máximo (cm)',
        'Altura_Max': 'Altura Máxima (m)',
        'Tiempo_Max': 'Tiempo Máximo (años)',
        'Total_CO2e_Potencial': 'CO2e Total Potencial (Ton)',
    })
    
    st.dataframe(
        df_mostrar.style.format({
            'DAP Máximo (cm)': '{:,.1f}',
            'Altura Máxima (m)': '{:,.1f}',
            'Tiempo Máximo (años)': '{:,.0f}',
            'CO2e Total Potencial (Ton)': '{:,.2f}',
        }),
        use_container_width=True
    )
    
    # ... (Gráfica de potencial se mantiene igual) ...


# ... (render_gap_cpassa y render_criterios_eficientes se mantienen igual) ...

# [FUNCIÓN DE GESTIÓN DE ESPECIE] 
def render_gestion_especie():
    """Permite al usuario ver y editar los coeficientes de las especies."""
    st.title("5. Gestión de Datos de Especies y Factores")
    st.warning("⚠️ **¡Advertencia!** Modificar estos valores alterará todos los cálculos de captura en los lotes existentes que usen la especie modificada.")

    df_actual = st.session_state.especies_bd.copy().set_index('Especie')
    
    st.markdown("### Tabla de Coeficientes y Datos Históricos (Edición)")

    df_edit = st.data_editor(
        df_actual,
        use_container_width=True,
        num_rows="dynamic",
        key="data_editor_especies",
        column_config={
            "Precio Plantón (S/)": st.column_config.NumberColumn("Precio Plantón (S/)", format="%.2f", help="Costo unitario de compra o producción del plantón.", min_value=0.0), 
            "DAP (cm)": st.column_config.NumberColumn("DAP (cm)", format="%.2f", help="Diámetro a la altura del pecho", min_value=0.0),
            "Altura (m)": st.column_config.NumberColumn("Altura (m)", format="%.2f", help="Altura total del árbol", min_value=0.0),
            "Consumo Agua (L/año)": st.column_config.NumberColumn("Consumo Agua (L/año)", format="%.0f", help="Consumo de agua anual por árbol", min_value=0.0),
            "Densidad (g/cm³)": st.column_config.NumberColumn("Densidad (g/cm³)", format="%.3f", help="Densidad de la madera (ρ)", min_value=0.001),
            "DAP Máximo (cm)": st.column_config.NumberColumn("DAP Máximo (cm)", format="%.1f", help="DAP máximo por literatura o madurez. Usado en la sección 2.", min_value=0.0),
            "Altura Máxima (m)": st.column_config.NumberColumn("Altura Máxima (m)", format="%.1f", help="Altura máxima por literatura o madurez. Usada en la sección 2.", min_value=0.0),
            "Tiempo Máximo (años)": st.column_config.NumberColumn("Tiempo Máximo (años)", format="%.0f", help="Tiempo de madurez o rotación de la especie. Usado en la sección 2.", min_value=0),
            # [FIX: ELIMINACIÓN SUPERVIVENCIA] Se ha removido la columna de Supervivencia (%)
        }
    )
    
    if st.button("💾 Guardar Cambios en la BD Histórica"):
        df_edit_clean = df_edit.reset_index()
        
        if df_edit_clean['Especie'].duplicated().any():
            st.error("Error: Las especies no pueden tener nombres duplicados. Por favor, corrija los nombres.")
        else:
            st.session_state.especies_bd = df_edit_clean
            st.success("✅ Datos de especies actualizados correctamente. Los cálculos se actualizarán al volver a la sección 1.")
            st.rerun() 


# --- FUNCIÓN PRINCIPAL DE LA APLICACIÓN (main_app) ---
# ... (Se mantiene igual) ...

if __name__ == "__main__":
    main_app()