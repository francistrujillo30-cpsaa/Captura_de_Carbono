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
# [FIX: POTENCIAL MÁXIMO V2] Adición de DAP Máximo, Altura Máxima y Tiempo Máximo (bibliografía)
# Incluyendo las nuevas 10 especies y actualizando las 4 originales con datos máximos.
DENSIDADES_BASE = {
    'Eucalipto Torrellana (Corymbia torelliana)': {'Densidad': 0.68, 'Agua_L_Anio': 1500, 'Precio_Plantón': 5.00, 'DAP_Max': 43.0, 'Altura_Max': 30.0, 'Tiempo_Max_Anios': 15}, 
    'Majoe (Hibiscus tiliaceus)': {'Densidad': 0.55, 'Agua_L_Anio': 1200, 'Precio_Plantón': 5.00, 'DAP_Max': 30.0, 'Altura_Max': 12.0, 'Tiempo_Max_Anios': 20}, 
    'Molle (Schinus molle)': {'Densidad': 0.73, 'Agua_L_Anio': 900, 'Precio_Plantón': 6.00, 'DAP_Max': 65.0, 'Altura_Max': 13.0, 'Tiempo_Max_Anios': 40},
    'Algarrobo (Prosopis pallida)': {'Densidad': 0.8, 'Agua_L_Anio': 800, 'Precio_Plantón': 4.00, 'DAP_Max': 60.0, 'Altura_Max': 14.0, 'Tiempo_Max_Anios': 50},
    # --- NUEVAS ESPECIES INCORPORADAS ---
    'Shaina (Colubrina glandulosa Perkins)': {'Densidad': 0.63, 'Agua_L_Anio': 1000, 'Precio_Plantón': 5.50, 'DAP_Max': 40.0, 'Altura_Max': 20.0, 'Tiempo_Max_Anios': 28},
    'Limoncillo (Melicoccus bijugatus)': {'Densidad': 0.68, 'Agua_L_Anio': 1100, 'Precio_Plantón': 7.00, 'DAP_Max': 40.0, 'Altura_Max': 18.0, 'Tiempo_Max_Anios': 33},
    'Capirona (Calycophyllum decorticans)': {'Densidad': 0.78, 'Agua_L_Anio': 1300, 'Precio_Plantón': 8.00, 'DAP_Max': 38.0, 'Altura_Max': 25.0, 'Tiempo_Max_Anios': 23},
    'Bolaina (Guazuma crinita)': {'Densidad': 0.48, 'Agua_L_Anio': 950, 'Precio_Plantón': 4.50, 'DAP_Max': 25.0, 'Altura_Max': 20.0, 'Tiempo_Max_Anios': 10},
    'Amasisa (Erythrina fusca)': {'Densidad': 0.38, 'Agua_L_Anio': 1150, 'Precio_Plantón': 6.50, 'DAP_Max': 33.0, 'Altura_Max': 15.0, 'Tiempo_Max_Anios': 15},
    'Moena (Ocotea aciphylla)': {'Densidad': 0.58, 'Agua_L_Anio': 1400, 'Precio_Plantón': 7.50, 'DAP_Max': 65.0, 'Altura_Max': 33.0, 'Tiempo_Max_Anios': 45},
    'Huayruro (Ormosia coccinea)': {'Densidad': 0.73, 'Agua_L_Anio': 1050, 'Precio_Plantón': 9.00, 'DAP_Max': 70.0, 'Altura_Max': 33.0, 'Tiempo_Max_Anios': 65},
    'Paliperro (Miconia barbeyana Cogniaux)': {'Densidad': 0.58, 'Agua_L_Anio': 850, 'Precio_Plantón': 6.00, 'DAP_Max': 40.0, 'Altura_Max': 20.0, 'Tiempo_Max_Anios': 28},
    'Cedro (Cedrela odorata)': {'Densidad': 0.43, 'Agua_L_Anio': 1600, 'Precio_Plantón': 9.50, 'DAP_Max': 55.0, 'Altura_Max': 30.0, 'Tiempo_Max_Anios': 28},
    'Guayacán (Gualacum officinale)': {'Densidad': 0.54, 'Agua_L_Anio': 750, 'Precio_Plantón': 8.50, 'DAP_Max': 45.0, 'Altura_Max': 12.0, 'Tiempo_Max_Anios': 60},
}


# HUELLA DE CARBONO CORPORATIVA POR SEDE (EN MILES DE tCO2e)
HUELLA_CORPORATIVA = {
    # CEMENTOS PACASMAYO S.A.A.
    "Planta Pacasmayo": 1265.15,
    "Planta Piura": 595.76,
    "Oficina Lima": 0.613,
    "Cantera Tembladera": 0.361,
    "Cantera Cerro Pintura": 0.425,
    "Cantera Virrilá": 0.433,
    "Cantera Bayóvar 4": 0.029,
    "Cantera Bayóvar 9": 0.041,
    "Almacén Salaverry": 0.0038,
    "Almacén Piura": 0.0053,
    
    # CEMENTOS SELVA S.A.C.
    "Planta Rioja": 264.63,
    "Cantera Tioyacu": 0.198,
    
    # DINO S.R.L.
    "DINO Cajamarca": 2.193,
    "DINO Chiclayo": 3.293,
    "DINO Chimbote": 1.708,
    "DINO Moche": 3.336,
    "DINO Piura": 1.004,
    "DINO Pacasmayo": 1.188,
    "DINO Trujillo": 1.954,
    "DINO Almacén Paita": 0.0074,
    
    # DISAC
    "DISAC Tarapoto": 0.708
}

# --- DEFINICIÓN DE TIPOS DE COLUMNAS ---
df_columns_types = {
    'Especie': str, 'Cantidad': int, 'DAP (cm)': float, 'Altura (m)': float, 
    'Densidad (ρ)': float, 'Años Plantados': int, 'Consumo Agua Unitario (L/año)': float, 
    'Precio Plantón Unitario (S/)': float, 
    'Detalle Cálculo': str,
    # 'Latitud' y 'Longitud' ELIMINADOS
}
df_columns_numeric = ['Cantidad', 'DAP (cm)', 'Altura (m)', 'Densidad (ρ)', 'Años Plantados', 'Consumo Agua Unitario (L/año)', 'Precio Plantón Unitario (S/)'] 

columnas_salida = ['Biomasa Lote (Ton)', 'Carbono Lote (Ton)', 'CO2e Lote (Ton)', 'Consumo Agua Total Lote (L)', 'Costo Total Lote (S/)'] 

# --- FUNCIÓN CRÍTICA: DINÁMICA DE ESPECIES ---
# [MODIFICACIÓN NECESARIA] Se modificó para incluir la extracción de los nuevos campos de Potencial Máximo.
def get_current_species_info():
    """
    Genera un diccionario de información de especies (Densidad, Agua, Precio, Maximos) 
    fusionando las especies base con las especies añadidas/modificadas por el usuario.
    """
    current_info = {
        # [FIX: POTENCIAL MÁXIMO V2] Incluir los nuevos campos máximos
        name: {
            'Densidad': data['Densidad'], 
            'Agua_L_Anio': data['Agua_L_Anio'], 
            'Precio_Plantón': data['Precio_Plantón'],
            'DAP_Max': data['DAP_Max'],
            'Altura_Max': data['Altura_Max'],
            'Tiempo_Max_Anios': data['Tiempo_Max_Anios']
        }
        for name, data in DENSIDADES_BASE.items()
    }
    
    df_bd = st.session_state.get('especies_bd', pd.DataFrame())
    if df_bd.empty:
        # [FIX: POTENCIAL MÁXIMO V2] Defaults para datos manuales
        current_info['Densidad/Datos Manuales'] = {'Densidad': 0.0, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 0.0, 'DAP_Max': 20.0, 'Altura_Max': 10.0, 'Tiempo_Max_Anios': 10}
        return current_info
        
    df_unique_info = df_bd.drop_duplicates(subset=['Especie'], keep='last')
    
    for _, row in df_unique_info.iterrows():
        especie_name = row['Especie']
        
        # Asegurar la conversión segura de los campos base
        densidad_val = pd.to_numeric(row.get('Densidad (g/cm³)', 0.0), errors='coerce') 
        agua_val = pd.to_numeric(row.get('Consumo Agua (L/año)', 0.0), errors='coerce')
        precio_val = pd.to_numeric(row.get('Precio Plantón (S/)', 0.0), errors='coerce') 
        
        # [FIX: POTENCIAL MÁXIMO V2] Asegurar la conversión de los nuevos campos
        dap_max_val = pd.to_numeric(row.get('DAP Máximo (cm)', 0.0), errors='coerce') 
        altura_max_val = pd.to_numeric(row.get('Altura Máxima (m)', 0.0), errors='coerce')
        tiempo_max_val = pd.to_numeric(row.get('Tiempo Máximo (años)', 0), errors='coerce')
        
        if pd.notna(densidad_val) and densidad_val > 0:
            current_info[especie_name] = {
                'Densidad': densidad_val,
                'Agua_L_Anio': agua_val if pd.notna(agua_val) and agua_val >= 0 else 0.0,
                'Precio_Plantón': precio_val if pd.notna(precio_val) and precio_val >= 0 else 0.0,
                # New fields
                'DAP_Max': dap_max_val if pd.notna(dap_max_val) and dap_max_val >= 0 else 0.0,
                'Altura_Max': altura_max_val if pd.notna(altura_max_val) and altura_max_val >= 0 else 0.0,
                'Tiempo_Max_Anios': int(tiempo_max_val) if pd.notna(tiempo_max_val) and tiempo_max_val >= 0 else 0,
            }
    
    # [FIX: POTENCIAL MÁXIMO V2] Defaults para datos manuales
    current_info['Densidad/Datos Manuales'] = {'Densidad': 0.0, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 0.0, 'DAP_Max': 20.0, 'Altura_Max': 10.0, 'Tiempo_Max_Anios': 10}
    
    return current_info


# --- FUNCIONES DE CÁLCULO Y MANEJO DE INVENTARIO ---

def get_co2e_total_seguro(df):
    """Calcula la suma total de CO2e capturado."""
    if df.empty or 'CO2e Lote (Ton)' not in df.columns:
        return 0.0
    return df['CO2e Lote (Ton)'].sum()

def get_costo_total_seguro(df):
    """Calcula la suma total del costo del proyecto."""
    if df.empty or 'Costo Total Lote (S/)' not in df.columns:
        return 0.0
    return df['Costo Total Lote (S/)'].sum()

def get_agua_total_seguro(df):
    """Calcula la suma total de consumo de agua (Anual)."""
    if df.empty or 'Consumo Agua Total Lote (L)' not in df.columns:
        return 0.0
    return df['Consumo Agua Total Lote (L)'].sum()


# --- MODIFICACIÓN CLAVE: calcular_co2_arbol para retornar JSON de detalle ---
def calcular_co2_arbol(rho, dap_cm, altura_m):
    """
    Calcula la biomasa, carbono y CO2e por árbol en KILOGRAMOS 
    y genera un diccionario de detalle con fórmulas para su posterior uso en Excel.
    """
    
    # 1. Validación de entradas
    if rho <= 0 or dap_cm <= 0 or altura_m <= 0:
        detalle = {
            "ERROR": "Valores de entrada (DAP, Altura o Densidad) deben ser mayores a cero para el cálculo."
        }
        return 0.0, 0.0, 0.0, 0.0, json.dumps(detalle)
        
    # Calcular AGB (Above-Ground Biomass) en kg
    # Fórmula: AGB = AGB_FACTOR_A × (ρ × D² × H)^AGB_FACTOR_B (Chave et al. 2014)
    # rho: Densidad (g/cm³), dap_cm: Diámetro (cm), altura_m: Altura (m)
    agb_kg = AGB_FACTOR_A * ((rho * (dap_cm**2) * altura_m)**AGB_FACTOR_B)
    
    # Calcular BGB (Below-Ground Biomass) en kg
    bgb_kg = agb_kg * FACTOR_BGB_SECO
    
    # Biomasa total (AGB + BGB)
    biomasa_total = agb_kg + bgb_kg
    
    # Carbono total
    carbono_total = biomasa_total * FACTOR_CARBONO
    
    # CO2 equivalente
    co2e_total = carbono_total * FACTOR_CO2E
    
    # Generación del detalle técnico como diccionario para convertir a JSON
    detalle_calculo = {
        "Inputs": [
            {"Métrica": "Densidad (ρ)", "Valor": rho, "Unidad": "g/cm³"},
            {"Métrica": "DAP (D)", "Valor": dap_cm, "Unidad": "cm"},
            {"Métrica": "Altura (H)", "Valor": altura_m, "Unidad": "m"}
        ],
        "AGB_Aerea_kg": [
            {"Paso": "Fórmula (Chave et al. 2014)", "Ecuación": f"AGB = {AGB_FACTOR_A} × (ρ × D² × H)^{AGB_FACTOR_B}"},
            {"Paso": "Sustitución", "Ecuación": f"AGB = {AGB_FACTOR_A:.3f} × ({rho:.3f} × {dap_cm:.2f}² × {altura_m:.2f})^{AGB_FACTOR_B:.3f}"},
            {"Paso": "Resultado AGB", "Valor": agb_kg, "Unidad": "kg"}
        ],
        "BGB_Subterranea_kg": [
            {"Paso": "Fórmula", "Ecuación": f"BGB = AGB × {FACTOR_BGB_SECO}"},
            {"Paso": "Sustitución", "Ecuación": f"BGB = {agb_kg:.4f} × {FACTOR_BGB_SECO}"},
            {"Paso": "Resultado BGB", "Valor": bgb_kg, "Unidad": "kg"}
        ],
        "Biomasa_Total_kg": [
            {"Paso": "Fórmula", "Ecuación": "Biomasa Total = AGB + BGB"},
            {"Paso": "Resultado Biomasa Total", "Valor": biomasa_total, "Unidad": "kg"}
        ],
        "Carbono_kg": [
            {"Paso": "Fórmula", "Ecuación": f"Carbono = Biomasa Total × {FACTOR_CARBONO}"},
            {"Paso": "Sustitución", "Ecuación": f"Carbono = {biomasa_total:.4f} × {FACTOR_CARBONO}"},
            {"Paso": "Resultado Carbono", "Valor": carbono_total, "Unidad": "kg"}
        ],
        "CO2e_kg": [
            {"Paso": "Fórmula", "Ecuación": f"CO2e = Carbono × {FACTOR_CO2E}"},
            {"Paso": "Sustitución", "Ecuación": f"CO2e = {carbono_total:.4f} × {FACTOR_CO2E}"},
            {"Paso": "Resultado CO2e (Unitario)", "Valor": co2e_total, "Unidad": "kg"}
        ]
    }
    
    return agb_kg, bgb_kg, biomasa_total, co2e_total, json.dumps(detalle_calculo)


# --- FUNCIÓN DE RECÁLCULO SEGURO (CRÍTICA) ---
# NO MODIFICADA en su lógica de cálculo: Sigue usando DAP (cm) y Altura (m) MEDIDOS.
def recalcular_inventario_completo(inventario_list):
    """
    Toma la lista de entradas (List[Dict]) y genera un DataFrame completo y limpio, 
    incluyendo CO2e, Consumo de Agua y Costo Total (Plantones + Agua Acumulada).
    """
    if not inventario_list:
        # Crear un DF vacío con todas las columnas esperadas
        all_cols = list(df_columns_types.keys()) + columnas_salida
        dtype_map = {**df_columns_types, **dict.fromkeys(columnas_salida, float)}
        dtype_map = {k: v for k, v in dtype_map.items() if k in all_cols}
        return pd.DataFrame(columns=all_cols).astype(dtype_map)


    # 1. Crear DF base
    df_base = pd.DataFrame(inventario_list)
    df_calculado = df_base.copy()
    
    # [FIX: CORRECCIÓN DE ERROR JSON] Eliminamos la columna Detalle Cálculo del input (si existe) 
    # para asegurar que siempre se use la nueva cadena JSON calculada y evitar TypeErrors de valores NaN/None.
    if 'Detalle Cálculo' in df_calculado.columns:
        df_calculado = df_calculado.drop(columns=['Detalle Cálculo'])
    
    # 2. FIX CRÍTICO: Asegurar que todas las columnas de entrada requeridas existan
    required_input_cols = [col for col in df_columns_types.keys() if col != 'Detalle Cálculo'] # Excluimos Detalle Cálculo
    for col in required_input_cols:
        if col not in df_calculado.columns:
            if df_columns_types[col] == str:
                default_val = ""
            elif df_columns_types[col] == int:
                default_val = 0
            else: # float
                default_val = 0.0
            df_calculado[col] = default_val
    
    # 3. Asegurar que todas las columnas numéricas sean números
    for col in df_columns_numeric:
        df_calculado[col] = pd.to_numeric(df_calculado[col], errors='coerce').fillna(0)
    
    resultados_calculo = []
    
    # --- Lógica de Riego Controlado (Checkbox) ---
    riego_activado = st.session_state.get('riego_controlado_check', False)
    
    for _, row in df_calculado.iterrows():
        rho = row['Densidad (ρ)']
        dap = row['DAP (cm)'] # <<< Usamos el DAP MEDIDO
        altura = row['Altura (m)'] # <<< Usamos la Altura MEDIDA
        cantidad = row['Cantidad']
        consumo_agua_uni_base = row['Consumo Agua Unitario (L/año)'] 
        precio_planton_uni = row['Precio Plantón Unitario (S/)'] 
        años_plantados = row['Años Plantados'] 

        # 1. Cálculo de CO2e (Biomasa, Carbono, CO2e por árbol en kg)
        _, _, biomasa_uni_kg, co2e_uni_kg, detalle = calcular_co2_arbol(rho, dap, altura)
        
        # 2. Conversión a TONELADAS y Lote
        biomasa_lote_ton = (biomasa_uni_kg * cantidad) / FACTOR_KG_A_TON
        carbono_lote_ton = (biomasa_uni_kg * FACTOR_CARBONO * cantidad) / FACTOR_KG_A_TON
        co2e_lote_ton = (co2e_uni_kg * cantidad) / FACTOR_KG_A_TON

        # 3. Costo y Agua
        costo_planton_lote = cantidad * precio_planton_uni
        
        # --- LÓGICA DE RIEGO CONDICIONAL ---
        if riego_activado:
            consumo_agua_uni = consumo_agua_uni_base
            años_para_costo = años_plantados
        else:
            # Si el riego no está activado, el consumo de agua y su costo son CERO.
            consumo_agua_uni = 0.0
            años_para_costo = 0 
            
        consumo_agua_lote_l = cantidad * consumo_agua_uni
        
        # Calcular el costo de agua por UN AÑO (operación anual)
        volumen_agua_lote_m3_anual = consumo_agua_lote_l / FACTOR_L_A_M3
        costo_agua_anual_lote = volumen_agua_lote_m3_anual * PRECIO_AGUA_POR_M3
        
        # Costo de agua acumulado: Costo Anual * Años Plantados (solo si riego_activado)
        costo_agua_acumulado_lote = costo_agua_anual_lote * años_para_costo
        
        # Costo total = Costo Plantones (Inversión Inicial) + Costo Agua (Operación Acumulada)
        costo_total_lote = costo_planton_lote + costo_agua_acumulado_lote
        # --- FIN DE LÓGICA DE RIEGO CONDICIONAL ---
        
        resultados_calculo.append({
            'Biomasa Lote (Ton)': biomasa_lote_ton,
            'Carbono Lote (Ton)': carbono_lote_ton,
            'CO2e Lote (Ton)': co2e_lote_ton,
            'Consumo Agua Total Lote (L)': consumo_agua_lote_l,
            'Costo Total Lote (S/)': costo_total_lote, 
            'Detalle Cálculo': detalle # JSON string
        })

    # 4. Unir los resultados
    df_resultados = pd.DataFrame(resultados_calculo)
    df_final = pd.concat([df_calculado.reset_index(drop=True), df_resultados], axis=1)
    
    # 5. Aplicar tipos de datos para las columnas de salida
    dtype_map = {col: float for col in columnas_salida if col in df_final.columns}
    df_final = df_final.astype(dtype_map)

    return df_final


# [MODIFICACIÓN NECESARIA] Función para calcular el potencial máximo usando los valores Max de la especie.
def calcular_potencial_maximo_lotes(inventario_list, current_species_info):
    """
    Calcula el CO2e potencial máximo utilizando los valores máximos de DAP y Altura 
    propios de cada especie en los lotes del inventario.
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
        
        # Obtener los valores máximos de la especie
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
            # Para datos manuales, usar DAP/Altura máxima por defecto si la densidad es válida
            info_manual = current_species_info.get('Densidad/Datos Manuales', {'Densidad': 0.0, 'DAP_Max': 0.0, 'Altura_Max': 0.0, 'Tiempo_Max_Anios': 0})
            rho = row['Densidad (ρ)'] if row['Densidad (ρ)'] > 0 else info_manual['Densidad']
            dap = info_manual['DAP_Max']
            altura = info_manual['Altura_Max']
            tiempo_max = info_manual['Tiempo_Max_Anios']
        else:
            # Caso de especie no encontrada/datos inconsistentes. Usar DAP/Altura Medidos, pero es menos potencial
            rho = row['Densidad (ρ)']
            dap = row['DAP (cm)']
            altura = row['Altura (m)']
            tiempo_max = 0
        
        
        if dap <= 0 or altura <= 0 or rho <= 0 or cantidad <= 0:
            co2e_lote_ton = 0.0
            detalle = "ERROR: Valores DAP/Altura/Densidad/Cantidad deben ser > 0 para el cálculo potencial."
        else:
             # 1. Cálculo de CO2e (Biomasa, Carbono, CO2e por árbol en kg)
             _, _, _, co2e_uni_kg, detalle = calcular_co2_arbol(rho, dap, altura)
             
             # 2. Conversión a TONELADAS y Lote
             co2e_lote_ton = (co2e_uni_kg * cantidad) / FACTOR_KG_A_TON

        
        resultados_calculo.append({
            'Especie': especie,
            'Cantidad': cantidad,
            'Densidad (ρ)': rho,
            'DAP Potencial (cm)': dap,
            'Altura Potencial (m)': altura,
            'Tiempo Máximo (años)': tiempo_max, # Nuevo campo
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
        # [MODIFICACIÓN NECESARIA] Incluir los nuevos campos máximos para la tabla de gestión
        df_cols = ['Especie', 'DAP (cm)', 'Altura (m)', 'Consumo Agua (L/año)', 'Densidad (g/cm³)', 'Precio Plantón (S/)', 'DAP Máximo (cm)', 'Altura Máxima (m)', 'Tiempo Máximo (años)'] 
        data_rows = [
            (name, 5.0, 5.0, data['Agua_L_Anio'], data['Densidad'], data['Precio_Plantón'], data['DAP_Max'], data['Altura_Max'], data['Tiempo_Max_Anios']) 
            for name, data in DENSIDADES_BASE.items()
        ]
        df_bd_inicial = pd.DataFrame(data_rows, columns=df_cols)
        st.session_state.especies_bd = df_bd_inicial
    if 'proyecto' not in st.session_state:
        st.session_state.proyecto = "Proyecto Reforestación CPSSA"
    if 'hectareas' not in st.session_state:
        st.session_state.hectareas = 0.0
    # --- NUEVA VARIABLE DE SESIÓN ---
    if 'riego_controlado_check' not in st.session_state:
        st.session_state.riego_controlado_check = False
        
    # Inicialización de inputs del formulario
    if 'especie_seleccionada' not in st.session_state: st.session_state.especie_seleccionada = list(DENSIDADES_BASE.keys())[0]
    if 'cantidad_input' not in st.session_state: st.session_state.cantidad_input = 100
    if 'dap_slider' not in st.session_state: st.session_state.dap_slider = 5
    if 'altura_slider' not in st.session_state: st.session_state.altura_slider = 5
    if 'anios_plantados_input' not in st.session_state: st.session_state.anios_plantados_input = 5
    if 'densidad_manual_input' not in st.session_state: st.session_state.densidad_manual_input = 0.5
    if 'consumo_agua_manual_input' not in st.session_state: st.session_state.consumo_agua_manual_input = 1000.0
    if 'precio_planton_input' not in st.session_state: st.session_state.precio_planton_input = 5.0 


def reiniciar_app_completo():
    """Borra completamente todos los elementos del estado de sesión (CRÍTICO PARA ARREGLAR CORRUPCIONES)."""
    keys_to_delete = list(st.session_state.keys())
    for key in keys_to_delete:
        del st.session_state[key]
    st.rerun() 

def agregar_lote():
    """Añade un lote al inventario basado en los valores de los inputs."""
    current_species_info = get_current_species_info()
    
    especie = st.session_state.especie_seleccionada
    cantidad = st.session_state.cantidad_input
    dap = float(st.session_state.dap_slider) 
    altura = float(st.session_state.altura_slider)
    años = st.session_state.anios_plantados_input
    precio_planton_unitario = st.session_state.precio_planton_input 
    
    rho = 0.0
    consumo_agua_unitario = 0.0
    
    if especie == 'Densidad/Datos Manuales':
        rho = st.session_state.densidad_manual_input
        consumo_agua_unitario = st.session_state.consumo_agua_manual_input
    elif especie in current_species_info:
        info = current_species_info[especie]
        rho = info['Densidad']
        consumo_agua_unitario = info['Agua_L_Anio']

    if cantidad <= 0 or dap <= 0 or altura <= 0 or rho <= 0 or años < 0 or consumo_agua_unitario < 0 or precio_planton_unitario < 0:
        st.error("Por favor, asegúrate de que Cantidad, DAP, Altura y Densidad sean mayores a cero, y los valores de Años, Agua y Precio sean mayores o iguales a cero.")
        return

    _, _, _, _, detalle_calculo = calcular_co2_arbol(rho, dap, altura)
    
    nuevo_lote = {
        'Especie': especie,
        'Cantidad': int(cantidad),
        'DAP (cm)': float(dap), 
        'Altura (m)': float(altura), 
        'Densidad (ρ)': float(rho),
        'Años Plantados': int(años),
        'Consumo Agua Unitario (L/año)': float(consumo_agua_unitario),
        'Precio Plantón Unitario (S/)': float(precio_planton_unitario), 
        'Detalle Cálculo': detalle_calculo, # JSON string
    }
    
    st.session_state.inventario_list.append(nuevo_lote)
    st.success(f"Lote de {cantidad} árboles de {especie} añadido.")


def deshacer_ultimo_lote():
    """Elimina el último lote añadido."""
    if st.session_state.inventario_list:
        st.session_state.inventario_list.pop()
        st.success("Último lote eliminado.")
    else:
        st.warning("El inventario está vacío.")

def limpiar_inventario():
    """Limpia todo el inventario."""
    st.session_state.inventario_list = []
    st.success("Inventario completamente limpiado.")


def generar_excel_memoria(df_inventario, proyecto, hectareas, total_arboles, total_co2e_ton, total_agua_l, total_costo):
    """Genera el archivo Excel en memoria con el resumen, el inventario detallado y el detalle de cálculo."""
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # 1. Preparar Inventario Detallado (sin Detalle Cálculo JSON)
    cols_to_drop = ['Detalle Cálculo']
    df_inventario_download = df_inventario.drop(columns=cols_to_drop, errors='ignore')
    df_inventario_download.to_excel(writer, sheet_name='1_Inventario Detallado', index=False)
    
    # 2. Resumen del Proyecto
    df_resumen = pd.DataFrame({
        'Métrica': ['Proyecto', 'Fecha', 'Hectáreas (ha)', 'Total Árboles', 'CO2e Total (Ton)', 'CO2e Total (Kg)', 'Agua Total Anual (L)', 'Costo Total Acumulado (S/)'], 
        'Valor': [ 
            proyecto if proyecto else "Sin Nombre", 
            str(pd.Timestamp.today().normalize().date()), 
            f"{hectareas:.1f}", 
            f"{total_arboles:.0f}", 
            f"{total_co2e_ton:.2f}", 
            f"{total_co2e_ton * FACTOR_KG_A_TON:.2f}", 
            f"{total_agua_l:,.0f}", 
            f"S/{total_costo:,.2f}" 
        ]
    })
    df_resumen.to_excel(writer, sheet_name='2_Resumen Proyecto', index=False)
    
    # 3. Detalle de Cálculo (Evidencia) - Una hoja por lote
    
    for i, row in df_inventario.iterrows():
        try:
            detalle_json = row['Detalle Cálculo']
            
            # Si el detalle es NaN o no es string (error de migración de sesión), lo saltamos
            if not isinstance(detalle_json, str):
                continue
                
            detalle_dict = json.loads(detalle_json)
            
            # Crear un DataFrame para el detalle de este lote
            data_lote = []
            
            # Estructurar los inputs
            for item in detalle_dict.get('Inputs', []):
                data_lote.append(['INPUT', item['Métrica'], item['Valor'], item['Unidad'], ''])
                
            # Estructurar los pasos de cálculo
            orden = ['AGB_Aerea_kg', 'BGB_Subterranea_kg', 'Biomasa_Total_kg', 'Carbono_kg', 'CO2e_kg']
            seccion_nombres = {
                'AGB_Aerea_kg': '1. Biomasa Aérea (AGB)', 
                'BGB_Subterranea_kg': '2. Biomasa Subterránea (BGB)',
                'Biomasa_Total_kg': '3. Biomasa Total', 
                'Carbono_kg': '4. Carbono Capturado',
                'CO2e_kg': '5. CO2 Equivalente Capturado'
            }
            
            for key in orden:
                data_lote.append([seccion_nombres[key], '---', '---', '---', '---']) # Separador
                for item in detalle_dict.get(key, []):
                    paso = item.get('Paso', '')
                    ecuacion = item.get('Ecuación', item.get('Fórmula', ''))
                    valor = item.get('Valor', '')
                    unidad = item.get('Unidad', '')
                    
                    if valor != '':
                        data_lote.append([seccion_nombres[key], paso, valor, unidad, ''])
                    elif ecuacion != '':
                        data_lote.append([seccion_nombres[key], paso, 'ECUACIÓN/SUSTITUCIÓN', '', ecuacion])
            
            df_detalle = pd.DataFrame(data_lote, columns=['Sección', 'Métrica/Paso', 'Valor', 'Unidad', 'Ecuación/Detalle'])
            
            sheet_name = f'3_Detalle_Lote_{i+1}'
            if len(sheet_name) > 31: # Límite de nombre de hoja de Excel
                sheet_name = f'3_Detalle_{i+1}'
            
            df_detalle.to_excel(writer, sheet_name=sheet_name, index=False)
            
        except json.JSONDecodeError:
            print(f"Error al decodificar JSON para el lote {i+1}. El lote tiene datos incorrectos.")
            continue
        except Exception as e:
            print(f"Error inesperado al generar hoja de detalle para el lote {i+1}: {e}")
            continue

    writer.close()
    processed_data = output.getvalue()
    return processed_data


# --- FUNCIÓN NUEVA: EQUIVALENCIAS AMBIENTALES ---
def render_equivalencias_ambientales(co2e_ton):
    """Muestra indicadores de equivalencia ambiental con un diseño mejorado."""
    st.subheader("📊 Equivalencias Ambientales de la Captura Total")
    
    if co2e_ton <= 0:
        st.info("Aún no hay suficiente CO₂e capturado para generar equivalencias.")
        return

    # Factores de Equivalencia (Ejemplos genéricos)
    AUTO_GASOLINA_ANUAL = 4.6 * 1000 # 4.6 Ton CO2e por auto/año (EE. UU.)
    CASA_ELECTRICIDAD_ANUAL = 10.0 # 10 Ton CO2e por casa/año (Estimado)
    VUELOS_NY_SF = 0.8 # Ton CO2e por vuelo redondo NY-SF (Aprox)

    equivalencias = {
        "🚗 Vehículos de Gasolina Retirados por 1 Año": co2e_ton / AUTO_GASOLINA_ANUAL,
        "🏠 Electricidad Anual de Hogares Evitada": co2e_ton / CASA_ELECTRICIDAD_ANUAL,
        "✈️ Vuelos Redondos (NY-SF) Compensados": co2e_ton / VUELOS_NY_SF
    }

    cols = st.columns(len(equivalencias))
    
    emojis = ["🚗", "🏠", "✈️"]
    
    st.markdown("---")
    
    for i, (descripcion, valor) in enumerate(equivalencias.items()):
        
        # El valor se calcula y luego se redondea para la presentación
        valor_presentacion = round(valor, 2) if valor >= 1 else round(valor, 4)
        
        with cols[i]:
            st.metric(
                label=f"{emojis[i]} {descripcion}",
                value=f"{valor_presentacion:,.0f}" if valor >= 1 else f"{valor_presentacion:,.2f}",
                delta=f"Equivalente a {descripcion.split('(')[0].strip()}"
            )
            
    st.markdown("---")


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
    # [FIX: COMPLETAR EL TRUNCADO] Llamada correcta a la función
    agua_proyecto_total = get_agua_total_seguro(df_inventario_completo) 
    total_arboles = df_inventario_completo['Cantidad'].sum()
    
    st.markdown("## 📥 Ingrese Lotes de Inventario")
    
    # Formulario de entrada de lotes
    col1, col2, col3, col4, col5 = st.columns([1.5, 1, 1, 1, 1])
    
    # 1. Selección de Especie
    especies_disponibles = list(current_species_info.keys())
    especie_seleccionada = col1.selectbox(
        "**Especie**", 
        options=especies_disponibles,
        key='especie_seleccionada',
        help="Seleccione una especie de la base de datos o 'Densidad/Datos Manuales' para ingresar la densidad manualmente."
    )
    
    # 2. Cantidad de Árboles
    col2.number_input(
        "**Cantidad (Árboles)**", 
        min_value=1, 
        value=st.session_state.cantidad_input, 
        key='cantidad_input',
        step=10,
        help="Número de árboles en este lote/área."
    )
    
    # 3. DAP (Diámetro a Altura del Pecho)
    col3.slider(
        "**DAP (cm)**", 
        min_value=0.1, 
        max_value=150.0, 
        value=st.session_state.dap_slider, 
        key='dap_slider',
        step=0.1,
        help="Diámetro medido a 1.3m del suelo. DAP se usa para el cálculo de progreso."
    )
    
    # 4. Altura
    col4.slider(
        "**Altura (m)**", 
        min_value=0.1, 
        max_value=100.0, 
        value=st.session_state.altura_slider, 
        key='altura_slider',
        step=0.1,
        help="Altura total del árbol, usada para el cálculo de progreso."
    )
    
    # 5. Años Plantados
    col5.number_input(
        "**Años Plantados**", 
        min_value=0, 
        value=st.session_state.anios_plantados_input, 
        key='anios_plantados_input',
        step=1,
        help="Años desde la plantación. Usado para el cálculo de costos acumulados de agua."
    )

    # --- Bloque de Datos Manuales (Condicional) ---
    if especie_seleccionada == 'Densidad/Datos Manuales':
        st.markdown("### 📝 Ingrese Datos de Densidad y Costos Manuales")
        col_man1, col_man2, col_man3 = st.columns(3)
        col_man1.number_input(
            "Densidad (g/cm³)", 
            min_value=0.01, 
            max_value=1.0, 
            value=st.session_state.densidad_manual_input, 
            key='densidad_manual_input',
            step=0.01
        )
        col_man2.number_input(
            "Consumo Agua (L/año)", 
            min_value=0.0, 
            value=st.session_state.consumo_agua_manual_input, 
            key='consumo_agua_manual_input',
            step=10.0
        )
        col_man3.number_input(
            "Precio Plantón (S/)", 
            min_value=0.0, 
            value=st.session_state.precio_planton_input, 
            key='precio_planton_input',
            step=0.10
        )
    else:
        # Mostrar info de la especie seleccionada
        info = current_species_info.get(especie_seleccionada, {})
        st.markdown(f"**Densidad:** {info.get('Densidad', 0.0):.2f} g/cm³ | **Agua (L/año):** {info.get('Agua_L_Anio', 0.0):,.0f} L | **Precio Plantón (S/):** S/{info.get('Precio_Plantón', 0.0):.2f}")


    st.button("➕ Añadir Lote al Inventario", on_click=agregar_lote, use_container_width=True, type="primary")

    st.markdown("---")

    # --- Métricas y Resumen ---
    st.markdown("## 📈 Resumen del Proyecto y Métricas Clave (Progreso Actual)")
    
    col_res1, col_res2, col_res3, col_res4 = st.columns(4)
    
    col_res1.metric("**Total Árboles Plantados**", f"{total_arboles:,.0f}")
    col_res2.metric("**CO2e Capturado (Progreso)**", f"{co2e_proyecto_ton:,.2f} Ton")
    
    if riego_controlado:
        col_res3.metric("**Costo Total Acumulado**", f"S/{costo_proyecto_total:,.2f}")
        col_res4.metric("**Consumo Agua Anual**", f"{agua_proyecto_total:,.0f} L")
    else:
        col_res3.metric("**Costo Total (Plantones)**", f"S/{costo_proyecto_total:,.2f}")
        col_res4.metric("**Consumo Agua Anual**", f"N/A (Riego Desactivado)")

    # Botones de gestión y descarga
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    col_btn1.button("⬅️ Deshacer Último Lote", on_click=deshacer_ultimo_lote, use_container_width=True)
    col_btn2.button("🗑️ Limpiar Todo el Inventario", on_click=limpiar_inventario, use_container_width=True)

    # Botón de descarga de Excel
    excel_data = generar_excel_memoria(
        df_inventario_completo, 
        st.session_state.proyecto, 
        st.session_state.hectareas, 
        total_arboles, 
        co2e_proyecto_ton, 
        agua_proyecto_total, 
        costo_proyecto_total
    )
    col_btn3.download_button(
        label="⬇️ Descargar Informe Excel Detallado",
        data=excel_data,
        file_name=f"Informe_NBS_{st.session_state.proyecto.replace(' ', '_')}_{pd.Timestamp.today().date()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    
    st.markdown("---")

    # --- Equivalencias Ambientales ---
    render_equivalencias_ambientales(co2e_proyecto_ton)
    
    st.markdown("---")

    # --- Tabla de Inventario ---
    st.markdown("## 📋 Inventario Completo")
    if not df_inventario_completo.empty:
        # Formatear el DF para visualización
        df_display = df_inventario_completo.copy()
        
        # Eliminar el JSON de la vista
        df_display = df_display.drop(columns=['Detalle Cálculo'], errors='ignore')
        
        # Redondear columnas de salida
        for col in columnas_salida:
            if col in df_display.columns:
                df_display[col] = df_display[col].round(2)
                
        # Mostrar tabla
        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("El inventario está vacío. Por favor, añada lotes para ver los resultados.")

    # --- Gráfico por Especie ---
    st.markdown("## 📊 CO2e Capturado por Especie")
    if total_arboles > 0:
        df_especie_agg = df_inventario_completo.groupby('Especie').agg(
            {'CO2e Lote (Ton)': 'sum', 'Cantidad': 'sum'}
        ).reset_index()

        fig = px.bar(
            df_especie_agg, 
            x='Especie', 
            y='CO2e Lote (Ton)',
            text='CO2e Lote (Ton)',
            title='CO₂e Capturado (Ton) por Especie (Progreso Actual)',
            labels={'CO2e Lote (Ton)': 'CO₂e Capturado (Ton)', 'Especie': 'Especie'},
            color='Especie'
        )
        fig.update_traces(texttemplate='%{text:.2f} Ton', textposition='outside')
        fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', xaxis_title='')
        st.plotly_chart(fig, use_container_width=True)


# --- SECCIÓN 2: POTENCIAL MÁXIMO (CUMPLIMIENTO DE REQUISITOS) ---

def render_potencial_maximo():
    st.title("2. Potencial Máximo y Análisis de Brecha (Gap) 🌱")
    
    current_species_info = get_current_species_info()
    df_inventario_completo = recalcular_inventario_completo(st.session_state.inventario_list)
    co2e_proyecto_actual = get_co2e_total_seguro(df_inventario_completo)
    
    if df_inventario_completo.empty:
        st.warning("El inventario está vacío. Por favor, añada lotes en la sección '1. Cálculo de Progreso' para analizar el potencial.")
        return

    # --- CÁLCULO DE POTENCIAL MÁXIMO ---
    df_potencial_completo = calcular_potencial_maximo_lotes(st.session_state.inventario_list, current_species_info)
    co2e_proyecto_potencial = get_co2e_total_seguro(df_potencial_completo.rename(columns={'CO2e Lote Potencial (Ton)': 'CO2e Lote (Ton)'}))
    
    st.markdown("## 📊 Resumen de Potencial")
    col_met1, col_met2, col_met3 = st.columns(3)
    
    brecha = co2e_proyecto_potencial - co2e_proyecto_actual
    porcentaje_progreso = (co2e_proyecto_actual / co2e_proyecto_potencial) * 100 if co2e_proyecto_potencial > 0 else 0
    
    col_met1.metric("**CO2e Progreso Actual**", f"{co2e_proyecto_actual:,.2f} Ton", delta=f"{porcentaje_progreso:,.1f}% de Potencial")
    col_met2.metric("**CO2e Potencial Máximo**", f"{co2e_proyecto_potencial:,.2f} Ton")
    col_met3.metric("**Brecha (GAP) CO2e**", f"{brecha:,.2f} Ton", delta_color="inverse")
    
    st.markdown("---")
    
    # --- PREPARACIÓN DE DATOS PARA GRÁFICOS (MERGE) ---
    df_progreso_agg = df_inventario_completo.groupby('Especie').agg(
        {'CO2e Lote (Ton)': 'sum'}
    ).reset_index().rename(columns={'CO2e Lote (Ton)': 'CO2e Progreso (Ton)'})
    
    df_potencial_agg = df_potencial_completo.groupby('Especie').agg(
        {'CO2e Lote Potencial (Ton)': 'sum', 'Tiempo Máximo (años)': 'mean'}
    ).reset_index().rename(columns={'CO2e Lote Potencial (Ton)': 'CO2e Potencial (Ton)'})
    
    df_comparativa = pd.merge(df_progreso_agg, df_potencial_agg, on='Especie', how='outer').fillna(0)
    df_comparativa['Brecha (CO2e Ton)'] = df_comparativa['CO2e Potencial (Ton)'] - df_comparativa['CO2e Progreso (Ton)']
    
    # --- GRÁFICO 1: Brecha (GAP) por Especie ---
    st.markdown("## 📈 Brecha (GAP) de CO₂e por Especie (Progreso vs. Potencial)")
    
    # Derretir el DataFrame para usar plotly express (facilita barras agrupadas)
    df_melt = df_comparativa.melt(
        id_vars='Especie', 
        value_vars=['CO2e Progreso (Ton)', 'CO2e Potencial (Ton)'], 
        var_name='Métrica', 
        value_name='CO2e (Ton)'
    )
    
    fig1 = px.bar(
        df_melt,
        x='Especie',
        y='CO2e (Ton)',
        color='Métrica',
        barmode='group',
        text_auto='.2f',
        title="CO₂e Capturado Actual vs. Potencial Máximo por Especie",
        labels={'CO2e (Ton)': 'CO₂e (Ton)', 'Métrica': 'Tipo de Valor'}
    )
    fig1.update_traces(textposition='outside')
    fig1.update_layout(legend_title_text='Métrica de Captura', xaxis_title='')
    st.plotly_chart(fig1, use_container_width=True)

    st.markdown("---")
    
    # --- GRÁFICO 2: Eficiencia del Potencial (Potencial vs. Tiempo Máximo) ---
    st.markdown("## 🌳 Análisis de Eficiencia del Potencial (Potencial CO₂e vs. Tiempo de Madurez)")
    
    fig2 = px.scatter(
        df_comparativa,
        x='Tiempo Máximo (años)',
        y='CO2e Potencial (Ton)',
        size='CO2e Potencial (Ton)',
        color='Especie',
        hover_name='Especie',
        text='Especie',
        title="Potencial de Captura Máxima vs. Años de Madurez (Eficiencia)",
        labels={
            'Tiempo Máximo (años)': 'Años de Madurez de la Especie (Menor es más rápido)',
            'CO2e Potencial (Ton)': 'CO₂e Potencial Máximo (Ton)'
        }
    )
    fig2.update_traces(textposition='top center', textfont=dict(size=10))
    st.plotly_chart(fig2, use_container_width=True)
    
    st.markdown("---")
    
    # --- TABLA DE DATOS DE POTENCIAL ---
    st.markdown("## 📋 Detalle de Potencial Máximo por Especie")
    df_tabla_potencial = df_comparativa[['Especie', 'CO2e Progreso (Ton)', 'CO2e Potencial (Ton)', 'Brecha (CO2e Ton)', 'Tiempo Máximo (años)']]
    df_tabla_potencial = df_tabla_potencial.round(2)
    st.dataframe(df_tabla_potencial, use_container_width=True)

# --- SECCIÓN 3: GAP CPSSA ---

def render_gap_cpassa():
    st.title("3. Análisis de Brecha (GAP) con Huella Corporativa 🏭")

    co2e_proyecto_actual = get_co2e_total_seguro(recalcular_inventario_completo(st.session_state.inventario_list))

    if co2e_proyecto_actual <= 0:
        st.warning("El proyecto de reforestación debe tener CO₂e capturado (sección 1) para compararlo con la huella corporativa.")
        return

    # 1. Preparar datos de la huella corporativa
    df_huella = pd.DataFrame(HUELLA_CORPORATIVA.items(), columns=['Sede', 'Huella Corporativa (Miles de tCO2e)'])
    df_huella['Huella Corporativa (Ton)'] = df_huella['Huella Corporativa (Miles de tCO2e)'] * FACTOR_KG_A_TON

    total_huella_ton = df_huella['Huella Corporativa (Ton)'].sum()
    
    st.markdown("## ⚖️ Comparación de Mitigación")

    col_h1, col_h2, col_h3 = st.columns(3)
    
    col_h1.metric("**Huella Corporativa Total (Anual)**", f"{total_huella_ton:,.0f} Ton CO₂e")
    col_h2.metric("**CO2e Capturado (NBS Progreso)**", f"{co2e_proyecto_actual:,.0f} Ton CO₂e")

    gap_mitigacion = total_huella_ton - co2e_proyecto_actual
    porcentaje_mitigado = (co2e_proyecto_actual / total_huella_ton) * 100 if total_huella_ton > 0 else 0
    
    col_h3.metric(
        "**GAP Pendiente de Mitigación**", 
        f"{gap_mitigacion:,.0f} Ton CO₂e",
        delta=f"{porcentaje_mitigado:,.2f}% Mitigado",
        delta_color="normal" if porcentaje_mitigado < 100 else "inverse" # Inverso para mostrar que cubrir la brecha es bueno
    )
    
    st.markdown("---")
    
    # 2. Gráfico de Comparación
    st.markdown("## 📊 Huella por Sede vs. Captura NBS")

    df_plot = df_huella.copy()
    df_plot['Tipo'] = 'Huella Corporativa'

    df_mitigacion = pd.DataFrame({
        'Sede': ['Proyecto Reforestación NBS'],
        'Huella Corporativa (Ton)': [co2e_proyecto_actual],
        'Tipo': ['Captura NBS (Progreso)']
    })

    # Unir la captura como una barra separada
    df_consolidado = pd.concat([
        df_plot[['Sede', 'Huella Corporativa (Ton)', 'Tipo']],
        df_mitigacion[['Sede', 'Huella Corporativa (Ton)', 'Tipo']]
    ], ignore_index=True)
    
    # Ordenar por huella de forma descendente, con la captura al final
    df_consolidado = df_consolidado.sort_values(by='Huella Corporativa (Ton)', ascending=False)
    
    fig = px.bar(
        df_consolidado,
        x='Sede',
        y='Huella Corporativa (Ton)',
        color='Tipo',
        text='Huella Corporativa (Ton)',
        title='Huella de CO₂e por Sede vs. Captura de CO₂e por Proyecto NBS',
        labels={'Huella Corporativa (Ton)': 'CO₂e (Ton)', 'Sede': 'Sede/Proyecto'},
        color_discrete_map={'Huella Corporativa': 'firebrick', 'Captura NBS (Progreso)': 'forestgreen'}
    )
    fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', xaxis_title='')
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    
    # 3. Distribución de Mitigación por Sede
    st.markdown("## 🎯 Distribución de la Mitigación por Sede")
    
    df_mitigacion_sede = df_huella.copy()
    df_mitigacion_sede['Mitigación Aplicada (Ton)'] = co2e_proyecto_actual / len(df_huella) # Distribución equitativa para el ejemplo
    df_mitigacion_sede['Huella Neta (Ton)'] = df_mitigacion_sede['Huella Corporativa (Ton)'] - df_mitigacion_sede['Mitigación Aplicada (Ton)']
    
    # Asegurar que el neto no sea negativo
    df_mitigacion_sede['Huella Neta (Ton)'] = df_mitigacion_sede['Huella Neta (Ton)'].apply(lambda x: max(0, x))
    
    st.dataframe(df_mitigacion_sede.round(2), use_container_width=True)
    st.caption("Nota: La mitigación de CO₂e se distribuye equitativamente entre las sedes para fines de demostración en esta tabla.")


# --- SECCIÓN 4: GESTIÓN DE ESPECIES (CUMPLIMIENTO DE REQUISITOS) ---

def render_gestion_especie():
    st.title("4. Gestión de Base de Datos de Especies 🛠️")
    st.info("Aquí puede añadir o modificar especies, sus densidades, consumo de agua, costos y valores máximos de potencial.")

    # Inicializar la base de datos de especies con los nuevos campos
    # Se utiliza la session_state.especies_bd que ya fue inicializada con todos los campos.
    df_bd_actual = st.session_state.get('especies_bd', pd.DataFrame())
    
    st.markdown("## 📝 Editar/Actualizar Base de Datos de Especies")
    
    # Columnas de DAP y Altura inicial son ahora opcionales en la tabla de gestión
    df_editado = st.data_editor(
        df_bd_actual,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Especie": st.column_config.TextColumn(
                "Especie (Nombre Científico/Común)",
                required=True,
                help="Nombre de la especie (debe ser único)."
            ),
            "Densidad (g/cm³)": st.column_config.NumberColumn(
                "Densidad (g/cm³)",
                min_value=0.01,
                max_value=1.0,
                format="%.2f",
                required=True,
                help="Densidad de la madera (ρ) usada en la fórmula alométrica."
            ),
            "Consumo Agua (L/año)": st.column_config.NumberColumn(
                "Consumo Agua (L/año)",
                min_value=0.0,
                format="%d",
                help="Consumo anual estimado de agua por plantón (Litros)."
            ),
            "Precio Plantón (S/)": st.column_config.NumberColumn(
                "Precio Plantón (S/)",
                min_value=0.0,
                format="S/ %.2f",
                help="Costo unitario del plantón para cálculo de inversión inicial."
            ),
            "DAP Máximo (cm)": st.column_config.NumberColumn(
                "DAP Máximo (cm)",
                min_value=0.01,
                max_value=150.0,
                format="%.1f",
                required=True,
                help="Diámetro máximo que el árbol alcanza en su madurez (para potencial)."
            ),
            "Altura Máxima (m)": st.column_config.NumberColumn(
                "Altura Máxima (m)",
                min_value=0.01,
                max_value=100.0,
                format="%.1f",
                required=True,
                help="Altura máxima que el árbol alcanza en su madurez (para potencial)."
            ),
            "Tiempo Máximo (años)": st.column_config.NumberColumn(
                "Tiempo Máximo (años)",
                min_value=1,
                format="%d",
                required=True,
                help="Años estimados para alcanzar el potencial máximo de crecimiento."
            ),
             "DAP (cm)": st.column_config.NumberColumn(
                "DAP Inicial (cm)",
                disabled=True,
                help="Valor de ejemplo. No usado para la base de datos."
            ),
            "Altura (m)": st.column_config.NumberColumn(
                "Altura Inicial (m)",
                disabled=True,
                help="Valor de ejemplo. No usado para la base de datos."
            ),
        }
    )
    
    # 2. Validar y guardar
    if st.button("💾 Guardar Cambios en Especies", type="primary"):
        # Validación de duplicados
        if df_editado['Especie'].duplicated().any():
            st.error("Error: Hay especies duplicadas. Los nombres de las especies deben ser únicos.")
        else:
            # Revalidar que todos los campos requeridos tengan valor
            required_cols = ['Especie', 'Densidad (g/cm³)', 'DAP Máximo (cm)', 'Altura Máxima (m)', 'Tiempo Máximo (años)']
            valid = True
            for col in required_cols:
                if df_editado[col].isnull().any() or (df_editado[col] == 0).any():
                    valid = False
                    st.error(f"Error: La columna '{col}' no puede estar vacía o ser cero (excepto para Consumo Agua y Precio Plantón).")
                    break
            
            if valid:
                st.session_state.especies_bd = df_editado
                st.success("Base de datos de especies actualizada correctamente. Ahora están disponibles en la Calculadora.")
                # st.rerun() # No es necesario el rerun si el get_current_species_info es llamado al inicio de las otras funciones.
            

# --- MAIN APP LOGIC ---

def main():
    inicializar_estado_de_sesion()
    
    # 1. Sidebar de Navegación y Resumen
    with st.sidebar:
        st.image("https://i.ibb.co/L50Hj13/logo.png", width=200) # Logo de CPSSA (asumiendo uno genérico)
        st.title("NBS Carbon Manager")
        
        # Inputs de Configuración Global
        st.markdown("### ⚙️ Configuración Global")
        st.text_input(
            "Nombre del Proyecto", 
            key='proyecto', 
            placeholder="Ej: Reforestación Zona Norte"
        )
        st.number_input(
            "Hectáreas (ha)", 
            min_value=0.0, 
            key='hectareas', 
            step=0.1,
            format="%.1f",
            help="Área total del proyecto en hectáreas."
        )
        
        # Recálculo de CO2e para la métrica del sidebar
        df_inventario_sidebar = recalcular_inventario_completo(st.session_state.inventario_list)
        co2e_total_sidebar = get_co2e_total_seguro(df_inventario_sidebar)

        st.markdown("---")
        st.markdown("### 🗺️ Navegación")
        
        # Menú de navegación
        options = ["1. Cálculo de Progreso", "2. Potencial Máximo", "3. GAP CPSSA", "4. Gestión de Especie"]
        
        for option in options:
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
    elif selection == "3. GAP CPSSA":
        render_gap_cpassa()
    elif selection == "4. Gestión de Especie":
        render_gestion_especie()
    
    # Pie de página
    st.caption("---")
    st.caption(
        "**Solicitar cambios y/o actualizaciones al Área de Cambio Climático** - Desarrollado con Streamlit."
    )


if __name__ == '__main__':
    main()