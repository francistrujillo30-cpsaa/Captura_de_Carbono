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

# [FIX: ELIMINACIÓN SUPERVIVENCIA] Se ha removido el campo 'Supervivencia (%)'
DENSIDADES_BASE = {
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
HUELLA_CARBONO_SEDE = {
    'Sede A': 120.5,
    'Sede B': 85.2,
    'Sede C': 45.1,
    'Sede D': 15.7,
}

# --- DEFINICIÓN DE TIPOS DE COLUMNAS ---
df_columns_types = {
    'Lote': str,
    'Especie': str,
    'Cantidad': int,
    'Años Plantados': int,
    'DAP (cm)': float,
    'Altura (m)': float,
    'Consumo Agua Unitario (L/año)': float,
    'Densidad (ρ)': float,
    'Precio Plantón Unitario (S/)': float,
}
df_columns_numeric = [
    'Cantidad', 'Años Plantados', 'DAP (cm)', 'Altura (m)', 
    'Consumo Agua Unitario (L/año)', 'Densidad (ρ)', 'Precio Plantón Unitario (S/)'
]
columnas_salida = [
    'Biomasa Lote (Ton)', 'Carbono Lote (Ton)', 'CO2e Lote (Ton)', 
    'Consumo Agua Total Lote (L)', 'Costo Total Lote (S/)', 'Detalle Cálculo'
]

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
    
    current_info['Densidad/Datos Manuales'] = {'Densidad': 0.0, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 0.0, 'DAP_Max': 20.0, 'Altura_Max': 10.0, 'Tiempo_Max_Anios': 10}
    
    return current_info

# --- FUNCIONES DE CÁLCULO Y MANEJO DE INVENTARIO ---

def get_co2e_total_seguro(df):
    return df['CO2e Lote (Ton)'].sum() if not df.empty and 'CO2e Lote (Ton)' in df.columns else 0.0

def get_costo_total_seguro(df):
    return df['Costo Total Lote (S/)'].sum() if not df.empty and 'Costo Total Lote (S/)' in df.columns else 0.0

def get_agua_total_seguro(df):
    return df['Consumo Agua Total Lote (L)'].sum() if not df.empty and 'Consumo Agua Total Lote (L)' in df.columns else 0.0

def calcular_co2_arbol(rho, dap, altura):
    """Calcula la biomasa, carbono y CO2e para un árbol con un DAP y Altura dados."""
    # DAP se convierte de cm a m
    dap_m = dap / 100.0
    
    # 1. Biomasa Aérea Seca (AGB_SECO) en kg
    # Usando la fórmula general alométrica: AGB = exp(AGB_FACTOR_A + AGB_FACTOR_B * ln(rho * DAP^2 * H))
    # ln(rho * DAP^2 * H) = ln(rho) + 2*ln(DAP) + ln(H)
    if dap_m <= 0 or altura <= 0 or rho <= 0:
        agb_seco_kg = 0.0
    else:
        try:
            log_arg = rho * (dap_m**2) * altura
            ln_agb = AGB_FACTOR_A + AGB_FACTOR_B * np.log(log_arg)
            agb_seco_kg = np.exp(ln_agb)
        except FloatingPointError: # Manejo de log(0)
            agb_seco_kg = 0.0
    
    # 2. Biomasa Subterránea Seca (BGB_SECO) en kg
    bgb_seco_kg = agb_seco_kg * FACTOR_BGB_SECO
    
    # 3. Biomasa Total (BT_SECO) en kg
    biomasa_total_kg = agb_seco_kg + bgb_seco_kg
    
    # 4. Carbono Total (C_TOTAL) en kg
    carbono_total_kg = biomasa_total_kg * FACTOR_CARBONO
    
    # 5. CO2 Equivalente (CO2e) en kg
    co2e_total_kg = carbono_total_kg * FACTOR_CO2E
    
    detalle_calculo = {
        'AGB_SECO (kg)': agb_seco_kg,
        'BGB_SECO (kg)': bgb_seco_kg,
        'Biomasa Total (kg)': biomasa_total_kg,
        'Carbono Total (kg)': carbono_total_kg,
        'CO2e Total (kg)': co2e_total_kg,
        'rho': rho,
        'dap_m': dap_m,
        'altura': altura
    }
    
    return biomasa_total_kg, carbono_total_kg, biomasa_total_kg, co2e_total_kg, json.dumps(detalle_calculo)

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
        
        # 2. Conversión a TONELADAS y Lote (Usando la cantidad COMPLETA)
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
        
        # 4. Detalle de cálculo
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
            # Valores por defecto para manuales
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
             
             # 2. Conversión a TONELADAS y Lote (Usando la cantidad COMPLETA)
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

def reiniciar_app_completo():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def get_base_data_for_especie(especie_sel):
    info = get_current_species_info().get(especie_sel, {})
    return info

def agregar_lote():
    current_species_info = get_current_species_info()
    especie_sel = st.session_state.especie_seleccionada
    
    # Asignación de valores
    if especie_sel == 'Densidad/Datos Manuales':
        densidad = st.session_state.densidad_manual_input
        consumo_agua = st.session_state.consumo_agua_manual_input
        # Usar valores predeterminados para el manual
        info_max = current_species_info['Densidad/Datos Manuales'] 
        dap_max = info_max.get('DAP_Max', 20.0)
        altura_max = info_max.get('Altura_Max', 10.0)
        tiempo_max = info_max.get('Tiempo_Max_Anios', 10)
    else:
        info = get_base_data_for_especie(especie_sel)
        densidad = info.get('Densidad', 0.0)
        consumo_agua = info.get('Agua_L_Anio', 0.0)
        dap_max = info.get('DAP_Max', 0.0)
        altura_max = info.get('Altura_Max', 0.0)
        tiempo_max = info.get('Tiempo_Max_Anios', 0)
    
    nuevo_lote = {
        'Lote': f"Lote {len(st.session_state.inventario_list) + 1:03d}",
        'Especie': especie_sel,
        'Cantidad': st.session_state.cantidad_input,
        'Años Plantados': st.session_state.anios_plantados_input,
        'DAP (cm)': st.session_state.dap_slider,
        'Altura (m)': st.session_state.altura_slider,
        'Consumo Agua Unitario (L/año)': consumo_agua,
        'Densidad (ρ)': densidad,
        'Precio Plantón Unitario (S/)': st.session_state.precio_planton_input,
        # Guardar valores max para referencia en la BD de gestión
        'DAP Máximo (cm)': dap_max,
        'Altura Máxima (m)': altura_max,
        'Tiempo Máximo (años)': tiempo_max,
    }
    
    # 1. Validación básica
    if nuevo_lote['Cantidad'] <= 0 or nuevo_lote['DAP (cm)'] < 0 or nuevo_lote['Altura (m)'] < 0 or nuevo_lote['Densidad (ρ)'] <= 0:
        st.error("Error: La Cantidad, DAP, Altura y Densidad deben ser valores positivos y válidos. No se agregó el lote.")
        return
        
    st.session_state.inventario_list.append(nuevo_lote)

# --- FUNCIONES DE VISUALIZACIÓN ---

# ... (render_calculadora_y_graficos se mantiene igual, es muy largo para mostrar aquí, pero está intacto) ...

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

    # --- Información del Proyecto ---
    st.markdown("## 📊 Resultados Globales del Progreso")
    col_p, col_h = st.columns(2)
    with col_p:
        st.text_input("Nombre del Proyecto/Ubicación", key='proyecto', value=st.session_state.proyecto, help="Ej: Fundo El Sol - Lotes 1-5")
    with col_h:
        st.number_input("Hectáreas Totales", min_value=0.0, value=st.session_state.hectareas, step=0.1, key='hectareas')

    col1, col2, col3, col4 = st.columns(4)

    arboles_totales = df_inventario_completo['Cantidad'].sum()
    
    col1.metric("🌳 Árboles Plantados", f"{arboles_totales:,}")
    col2.metric("CO₂e Inventario (Progreso)", f"{co2e_proyecto_ton:,.2f} Ton")
    
    if riego_controlado:
        col3.metric("💦 Agua Consumida (Total)", f"{agua_proyecto_total/FACTOR_L_A_M3:,.2f} m³", help="Volumen total de agua acumulada basado en los 'Años Plantados'.")
        col4.metric("💰 Costo Total (S/)", f"S/{costo_proyecto_total:,.2f}", help="Costo acumulado (Plantones + Agua) hasta el año actual.")
    else:
        col3.metric("💦 Agua Consumida (Total)", "No Contabilizado", help="Active 'Riego Controlado' para calcular el consumo.")
        costo_planton_solo = df_inventario_completo['Cantidad'].mul(df_inventario_completo['Precio Plantón Unitario (S/)']).sum()
        col4.metric("💰 Costo Total (S/)", f"S/{costo_planton_solo:,.2f}", help="Solo incluye el costo de los plantones.")
    
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
                    help="Seleccione una especie o 'Densidad/Datos Manuales'."
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

        with col_totales:
            st.markdown("### Resumen del Inventario")
            
            # Gráfico de Proporción de CO2e por Especie (Gráfico de torta)
            if not df_inventario_completo.empty:
                df_grupo_especie = df_inventario_completo.groupby('Especie')['CO2e Lote (Ton)'].sum().reset_index()
                df_grupo_especie.columns = ['Especie', 'CO2e Lote (Ton)']
                
                # Crear el gráfico de torta
                fig_pie = px.pie(
                    df_grupo_especie, 
                    values='CO2e Lote (Ton)', 
                    names='Especie', 
                    title='Distribución de CO₂e Capturado por Especie',
                    hole=.3, # Efecto dona
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_pie.update_traces(textinfo='percent+label')
                fig_pie.update_layout(showlegend=False, margin=dict(t=30, b=0, l=0, r=0))
                st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
            else:
                st.info("Gráfico disponible al añadir lotes.")
                
            st.markdown("---")
            
            # Lógica para eliminar el último lote
            if st.session_state.inventario_list:
                if st.button("🗑️ Eliminar Último Lote Añadido", type="secondary", use_container_width=True):
                    st.session_state.inventario_list.pop()
                    st.success("Último lote eliminado.")
                    st.rerun()

            # Descargar inventario completo
            if not df_inventario_completo.empty:
                # Convertir a bytes para la descarga
                csv = df_inventario_completo.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="⬇️ Descargar Inventario Completo (.csv)",
                    data=csv,
                    file_name=f'Inventario_{st.session_state.proyecto}_Progreso.csv',
                    mime='text/csv',
                    use_container_width=True
                )

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
            
    with tab2:
        st.markdown("## Visualizador de Progreso 📊")
        if df_inventario_completo.empty:
            st.warning("Añada lotes en la pestaña 'Datos y Registro' para visualizar los gráficos.")
        else:
            df_agrupado_especie = df_inventario_completo.groupby('Especie')[['CO2e Lote (Ton)', 'Cantidad']].sum().reset_index()
            
            # Gráfico de Barras CO2e por Especie
            fig_bar_co2e = px.bar(
                df_agrupado_especie,
                x='Especie',
                y='CO2e Lote (Ton)',
                title='CO₂e Capturado por Especie (Toneladas)',
                text_auto='.2f',
                color='Especie',
                color_discrete_sequence=px.colors.qualitative.Vivid
            )
            fig_bar_co2e.update_layout(xaxis_title="Especie", yaxis_title="CO₂e Total (Ton)")
            st.plotly_chart(fig_bar_co2e, use_container_width=True)

            # Gráfico de dispersión (DAP vs Altura)
            df_progreso_plot = df_inventario_completo[['Especie', 'DAP (cm)', 'Altura (m)', 'CO2e Lote (Ton)']].copy()
            df_progreso_plot['CO2e por Árbol (kg)'] = (df_progreso_plot['CO2e Lote (Ton)'] / df_inventario_completo['Cantidad']) * FACTOR_KG_A_TON

            fig_scatter = px.scatter(
                df_progreso_plot,
                x='DAP (cm)',
                y='Altura (m)',
                color='Especie',
                size='CO2e por Árbol (kg)', # Usar el CO2e por árbol para el tamaño del marcador
                hover_data=['Especie', 'DAP (cm)', 'Altura (m)', 'CO2e por Árbol (kg)'],
                title='Relación DAP vs. Altura y CO₂e (Progreso Actual)',
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
            
            st.markdown("---")
            st.markdown("### CO₂e vs. Años Plantados")
            df_agrupado_años = df_inventario_completo.groupby('Años Plantados')['CO2e Lote (Ton)'].sum().reset_index()
            
            fig_line = px.line(
                df_agrupado_años,
                x='Años Plantados',
                y='CO2e Lote (Ton)',
                title='Acumulación de CO₂e por Antigüedad del Lote',
                markers=True
            )
            fig_line.update_layout(xaxis_title="Años Plantados", yaxis_title="CO₂e Acumulado (Ton)")
            st.plotly_chart(fig_line, use_container_width=True)


    with tab3:
        st.markdown("## Detalle Técnico de Cálculos🔬")
        if df_inventario_completo.empty:
            st.warning("Añada lotes para ver el detalle de los cálculos.")
        else:
            # Mostrar el detalle del cálculo
            df_detalle = df_inventario_completo[['Lote', 'Especie', 'Detalle Cálculo']].copy()
            
            if 'Detalle Cálculo' in df_detalle.columns:
                # Expandir la columna JSON 'Detalle Cálculo' a nuevas columnas
                expanded_data = df_detalle['Detalle Cálculo'].apply(lambda x: json.loads(x) if x else {})
                df_expanded = pd.json_normalize(expanded_data)
                
                # Limpiar nombres de columnas (quitar paréntesis y espacios)
                df_expanded.columns = [re.sub(r'[^a-zA-Z0-9_]+', '', col).replace('kg', '(kg)') for col in df_expanded.columns]
                
                # Unir el detalle con Lote/Especie
                df_final_detalle = pd.concat([df_detalle[['Lote', 'Especie']], df_expanded], axis=1)
                
                # Aplicar formato
                st.dataframe(
                    df_final_detalle.style.format({
                        col: '{:,.4f}' for col in df_final_detalle.columns if col not in ['Lote', 'Especie']
                    }),
                    use_container_width=True
                )
            else:
                st.error("Columna 'Detalle Cálculo' no encontrada.")

    with tab4:
        st.markdown("## 🌍 Equivalencias Ambientales")
        
        if co2e_proyecto_ton == 0.0:
            st.warning("El proyecto no ha capturado CO₂e o no tiene lotes registrados.")
        else:
            # Cálculo de equivalencias
            co2e_kg = co2e_proyecto_ton * FACTOR_KG_A_TON
            
            # 1. Autos fuera de circulación (Asumiendo 4.6 toneladas CO2e/auto/año)
            autos_circulacion = co2e_proyecto_ton / 4.6
            
            # 2. Casas abastecidas (Asumiendo 1.48 toneladas CO2e/casa/año)
            casas_abastecidas = co2e_proyecto_ton / 1.48
            
            # 3. Viajes de avión (Asumiendo 0.19 toneladas CO2e/viaje promedio)
            viajes_avion = co2e_proyecto_ton / 0.19
            
            # 4. Huella Corporativa Mitigada
            huella_corporativa_total = sum(HUELLA_CARBONO_SEDE.values()) * FACTOR_KG_A_TON / FACTOR_KG_A_TON # Mantener en Ton
            porcentaje_mitigado = (co2e_proyecto_ton / huella_corporativa_total) * 100 if huella_corporativa_total > 0 else 0
            
            st.markdown(f"El proyecto ha capturado un total de **{co2e_proyecto_ton:,.2f} toneladas de CO₂e**, lo que equivale a:")
            
            col_eq1, col_eq2 = st.columns(2)
            
            with col_eq1:
                st.metric("🚗 Autos Fuera de Circulación (1 Año)", f"{autos_circulacion:,.0f} autos", help="Basado en la emisión anual promedio de 4.6 toneladas de CO₂e por vehículo de pasajeros.")
                st.metric("🏡 Hogares Abastecidos (1 Año)", f"{casas_abastecidas:,.0f} hogares", help="Basado en el consumo promedio anual de energía de un hogar.")
            with col_eq2:
                st.metric("✈️ Viajes de Avión Promedio", f"{viajes_avion:,.0f} viajes", help="Basado en el CO₂e de un viaje de avión promedio (ida y vuelta).")
                st.metric("📈 Huella Corporativa (Mitigada)", f"{porcentaje_mitigado:,.2f} %", help=f"Porcentaje de la Huella de Carbono corporativa total ({huella_corporativa_total:,.2f} Ton) que el proyecto mitiga.")
                
            st.markdown("---")
            st.markdown("#### Desglose de la Huella Corporativa (Referencia)")
            
            # Crear tabla para el desglose de la huella
            df_huella = pd.DataFrame(HUELLA_CARBONO_SEDE.items(), columns=['Sede', 'CO2e (Miles de Ton)'])
            df_huella['CO2e (Ton)'] = df_huella['CO2e (Miles de Ton)'] * FACTOR_KG_A_TON / FACTOR_KG_A_TON
            st.dataframe(df_huella[['Sede', 'CO2e (Ton)']].style.format({'CO2e (Ton)': '{:,.2f}'}), use_container_width=True)


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
    
    # Gráfico de Potencial vs. Progreso (Barra agrupada)
    df_progreso_agrupado = df_inventario_progreso.groupby('Especie')['CO2e Lote (Ton)'].sum().reset_index()
    df_progreso_agrupado = df_progreso_agrupado.rename(columns={'CO2e Lote (Ton)': 'Progreso Actual (Ton)'})
    
    df_comparacion = df_agrupado.merge(df_progreso_agrupado, on='Especie', how='left').fillna(0)
    df_comparacion = df_comparacion.rename(columns={'Total_CO2e_Potencial': 'Potencial Máximo (Ton)'})
    
    # Derretir el DataFrame para Plotly Express
    df_melted = df_comparacion.melt(
        id_vars='Especie', 
        value_vars=['Progreso Actual (Ton)', 'Potencial Máximo (Ton)'], 
        var_name='Tipo de Cálculo', 
        value_name='CO2e (Ton)'
    )
    
    fig_comp = px.bar(
        df_melted,
        x='Especie',
        y='CO2e (Ton)',
        color='Tipo de Cálculo',
        barmode='group',
        title='Comparación: Progreso Actual vs. Potencial Máximo de Captura',
        text_auto='.2f',
        color_discrete_map={
            'Progreso Actual (Ton)': '#90EE90', # Verde claro
            'Potencial Máximo (Ton)': '#228B22' # Verde oscuro
        }
    )
    fig_comp.update_layout(yaxis_title="CO₂e Total (Ton)")
    st.plotly_chart(fig_comp, use_container_width=True)


# [NUEVO MENU: CRITERIOS EFICIENTES]
def render_criterios_eficientes():
    """Muestra el flujo de trabajo y criterios para la eficiencia en proyectos NBS."""
    st.title("3. Criterios para un Proyecto NBS Eficiente 📈")
    st.subheader("Flujo de Trabajo para Maximizar la Captura de CO₂e")

    st.markdown("""
        Un proyecto de Reforestación o Naturaleza como Solución (NBS) es eficiente no solo por la cantidad de carbono que captura, sino por la **sostenibilidad**, **permanencia** y la **certificación** de sus resultados.
    """)
    
    st.markdown("---")
    
    st.markdown("### 1️⃣ Selección de Especies: El Punto Crítico 🌳")
    st.markdown("""
        La elección de la especie es el factor más determinante para la captura de carbono:
        - **Alta Densidad de Madera (ρ):** Priorice especies con mayor densidad para maximizar la Biomasa por volumen.
        - **Crecimiento Rápido y Longevidad:** Especies que alcancen su DAP y Altura máxima en periodos óptimos y que permanezcan en el tiempo.
        - **Adaptación Ecológica:** Especies nativas o adecuadas a las condiciones climáticas y de suelo del sitio para garantizar la implantación.
    """)
    
    st.markdown("---")

    st.markdown("### 2️⃣ Diseño y Manejo del Proyecto 📐")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("**Permanencia (Riesgo)**", "Meta > 50 Años", help="Proyectos con planes de manejo a largo plazo (permanencia) obtienen mayor valor en los créditos de carbono, mitigando el riesgo de reversión (incendios, tala).")
        st.markdown("---")
    
    with col2:
        st.metric("**Costos (Agua/Plantón)**", "Optimización", help="Evaluar el costo del agua y la tasa de crecimiento. Especies que requieren menos riego o crecen más rápido pueden reducir los costos operativos a largo plazo.")
        st.markdown("---")

        
    st.markdown("""
    **Flujo de Eficiencia (Gráfico Conceptual):**
    1.  **Evaluación de Sitio:** Determinar condiciones (suelo, clima).
    2.  **Selección (Densidad y Crecimiento):** Elegir las mejores especies candidatas (usando la información de **Potencial Máximo**).
    3.  **Inversión Inicial:** Plantación y riego (medir **Precio Plantón** y **Consumo Agua**).
    4.  **Mantenimiento (Años 1-5):** Enfoque en la consolidación del lote.
    5.  **Monitoreo (Medición DAP/Altura):** Determinar **Progreso** actual.
    6.  **Cálculo:** Proyectar el **Potencial Máximo** para la toma de decisiones.
    """)
    
    st.markdown("---")

    st.markdown("### 3️⃣ Certificación y Trazabilidad (Monitoreo) 📊")
    st.markdown("""
        La eficiencia se valida con la trazabilidad:
        - **Monitoreo Continuo:** Medición periódica de DAP y Altura para actualizar el **Cálculo de Progreso** y verificar el modelo de crecimiento.
        - **Uso de Factores (Densidad):** Utilizar coeficientes y factores de riesgo basados en la realidad local y la bibliografía para asegurar la credibilidad del CO₂e reportado.
        - **Evidencia Digital:** Georreferenciación de lotes y árboles para demostrar la permanencia y evitar el doble conteo.
    """)

# [FUNCIÓN DE VISUALIZACIÓN - GAP CPSSA]
def render_gap_cpassa():
    """Muestra el cálculo de la brecha de captura (GAP) contra la huella corporativa."""
    st.title("4. GAP (Brecha de Captura vs. Huella Corporativa) 🎯")
    
    # Obtener datos de inventario y potencial
    df_inventario_progreso = recalcular_inventario_completo(st.session_state.inventario_list)
    co2e_progreso_total = get_co2e_total_seguro(df_inventario_progreso)
    
    current_species_info = get_current_species_info()
    df_potencial = calcular_potencial_maximo_lotes(st.session_state.inventario_list, current_species_info)
    co2e_potencial_total = df_potencial['CO2e Lote Potencial (Ton)'].sum()
    
    # Huella total corporativa (en Toneladas)
    huella_corporativa_total = sum(HUELLA_CARBONO_SEDE.values()) * FACTOR_KG_A_TON / FACTOR_KG_A_TON

    st.markdown("---")
    st.subheader("Cálculo de la Brecha de Captura (GAP)")

    col_gap1, col_gap2, col_gap3 = st.columns(3)

    with col_gap1:
        st.metric("Huella Corporativa Total (TCO₂e)", f"{huella_corporativa_total:,.2f} Ton", help="Suma de la huella de todas las sedes.")
    with col_gap2:
        st.metric("Captura de CO₂e (Progreso Actual)", f"{co2e_progreso_total:,.2f} Ton", help="CO₂e capturado hasta la fecha.")
    with col_gap3:
        st.metric("Captura de CO₂e (Potencial Máximo)", f"{co2e_potencial_total:,.2f} Ton", help="CO₂e que se capturaría al alcanzar la madurez.")

    # Cálculo del GAP (Brecha)
    gap_progreso = huella_corporativa_total - co2e_progreso_total
    gap_potencial = huella_corporativa_total - co2e_potencial_total

    st.markdown("---")
    st.subheader("Resumen de la Brecha (GAP)")

    col_res1, col_res2 = st.columns(2)

    with col_res1:
        st.metric(
            "GAP vs. Progreso Actual", 
            f"{gap_progreso:,.2f} Ton", 
            delta=f"Falta para mitigar la huella actual" if gap_progreso > 0 else f"Superávit de {-gap_progreso:,.2f} Ton",
            delta_color=("inverse" if gap_progreso > 0 else "normal")
        )
        st.markdown(f"**Progreso Mitigado:** {co2e_progreso_total / huella_corporativa_total * 100:,.2f}% de la huella.")
    
    with col_res2:
        st.metric(
            "GAP vs. Potencial Máximo", 
            f"{gap_potencial:,.2f} Ton", 
            delta=f"Falta para mitigar la huella si el proyecto madura" if gap_potencial > 0 else f"Superávit de {-gap_potencial:,.2f} Ton",
            delta_color=("inverse" if gap_potencial > 0 else "normal")
        )
        st.markdown(f"**Potencial Mitigado:** {co2e_potencial_total / huella_corporativa_total * 100:,.2f}% de la huella.")
        
    st.markdown("---")
    st.subheader("Visualización del GAP por Sede")

    # Preparar datos para el gráfico de barras apiladas
    df_huella_sedes = pd.DataFrame(HUELLA_CARBONO_SEDE.items(), columns=['Sede', 'CO2e (Miles de Ton)'])
    df_huella_sedes['CO2e (Ton)'] = df_huella_sedes['CO2e (Miles de Ton)'] * FACTOR_KG_A_TON / FACTOR_KG_A_TON
    
    # Crear una nueva fila para la captura de carbono (Progreso)
    captura_progreso = {'Sede': 'Captura Actual (Progreso)', 'CO2e (Ton)': -co2e_progreso_total}
    
    # Crear una nueva fila para la captura de carbono (Potencial)
    captura_potencial = {'Sede': 'Captura Potencial (Máx)', 'CO2e (Ton)': -co2e_potencial_total}
    
    # Combinar
    df_gap_plot = pd.concat([df_huella_sedes[['Sede', 'CO2e (Ton)']], pd.DataFrame([captura_progreso])])
    
    # Gráfico de Gantt/Barra apilada para visualizar la huella vs. mitigación
    fig_gap = go.Figure()

    # Huella (Positivo)
    fig_gap.add_trace(go.Bar(
        x=df_huella_sedes['CO2e (Ton)'], 
        y=df_huella_sedes['Sede'], 
        name='Huella Corporativa',
        orientation='h',
        marker_color='rgba(255, 99, 71, 0.8)' # Rojo
    ))

    # Captura (Negativo)
    fig_gap.add_trace(go.Bar(
        x=[captura_progreso['CO2e (Ton)']], 
        y=[captura_progreso['Sede']], 
        name='Progreso Actual (Mitigación)',
        orientation='h',
        marker_color='rgba(60, 179, 113, 0.8)' # Verde medio
    ))
    
    fig_gap.add_trace(go.Bar(
        x=[captura_potencial['CO2e (Ton)']], 
        y=[captura_potencial['Sede']], 
        name='Potencial Máximo (Mitigación)',
        orientation='h',
        marker_color='rgba(34, 139, 34, 0.8)' # Verde oscuro
    ))

    fig_gap.update_layout(
        barmode='relative',
        title='Mitigación de la Huella Corporativa (Huella Positivo, Captura Negativo)',
        xaxis_title='CO₂e (Toneladas)',
        yaxis_title='Fuente',
        height=400,
        showlegend=True
    )
    
    # Ajustar el eje X para que el cero quede centrado conceptualmente
    max_val = max(huella_corporativa_total, co2e_potencial_total)
    range_max = max(abs(huella_corporativa_total), abs(co2e_potencial_total)) * 1.1
    fig_gap.update_xaxes(range=[-range_max, range_max])

    st.plotly_chart(fig_gap, use_container_width=True)


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

def main_app():
    inicializar_estado_de_sesion()
    
    # Obtener el CO2e total para la métrica del sidebar
    df_inventario_completo = recalcular_inventario_completo(st.session_state.inventario_list)
    co2e_total_sidebar = get_co2e_total_seguro(df_inventario_completo)

    # 1. Sidebar para navegación
    with st.sidebar:
        st.header("Menú de Navegación")
        
        # [FIX: NAVEGACIÓN] Lista de opciones con Criterios Eficientes
        nav_options = [
            "1. Cálculo de Progreso", 
            "2. Potencial Máximo", 
            "3. Criterios Eficientes", 
            "4. GAP CPSSA", 
            "5. Gestión de Especie"
        ]

        # Lógica de renderizado de botones de navegación
        for option in nav_options:
            is_selected = (st.session_state.current_page == option)
            
            if st.button(
                option, 
                key=f"nav_{option}", 
                use_container_width=True,
                type=("primary" if is_selected else "secondary") 
            ):
                st.session_state.current_page = option 
                st.rerun() 

        # Métricas en el sidebar
        st.markdown("---")
        st.caption(f"Proyecto: {st.session_state.proyecto if st.session_state.proyecto else 'Sin nombre'}")
        st.metric("CO2e Inventario (Progreso)", f"{co2e_total_sidebar:,.2f} Ton") 
        
        st.markdown("---")
        if st.button("🔄 Reiniciar Aplicación (Borrar Datos de Sesión)", type="secondary"):
            reiniciar_app_completo()
    
    # 2. Renderizar la página basada en el estado de sesión
    selection = st.session_state.current_page 
    
    if selection == "1. Cálculo de Progreso":
        render_calculadora_y_graficos()
    elif selection == "2. Potencial Máximo":
        render_potencial_maximo()
    elif selection == "3. Criterios Eficientes": 
        render_criterios_eficientes()
    elif selection == "4. GAP CPSSA": 
        render_gap_cpassa()
    elif selection == "5. Gestión de Especie": 
        render_gestion_especie()
    
    # Pie de página
    st.caption("---")
    st.caption(
        "**Solicitar cambios y/o actualizaciones al Área de Cambio Climático**"
    )

if __name__ == "__main__":
    main_app()