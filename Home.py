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
# [MODIFICACIÓN] Adición de DAP Máximo, Altura Máxima y Tiempo Máximo (bibliografía)
DENSIDADES_BASE = {
    # --- Especies Originales (Ajustadas a nuevos campos) ---
    'Eucalipto Torrellana (Corymbia torelliana)': {'Densidad': 0.46, 'Agua_L_Anio': 1500, 'Precio_Plantón': 5.00, 'DAP_Max': 45.0, 'Altura_Max': 35.0, 'Tiempo_Max_Anios': 20}, 
    'Majoe (Hibiscus tiliaceus)': {'Densidad': 0.57, 'Agua_L_Anio': 1200, 'Precio_Plantón': 5.00, 'DAP_Max': 25.0, 'Altura_Max': 15.0, 'Tiempo_Max_Anios': 15}, 
    'Molle (Schinus molle)': {'Densidad': 0.44, 'Agua_L_Anio': 900, 'Precio_Plantón': 6.00, 'DAP_Max': 30.0, 'Altura_Max': 20.0, 'Tiempo_Max_Anios': 25},
    'Algarrobo (Prosopis pallida)': {'Densidad': 0.53, 'Agua_L_Anio': 800, 'Precio_Plantón': 4.00, 'DAP_Max': 40.0, 'Altura_Max': 18.0, 'Tiempo_Max_Anios': 30},
    
    # --- [NUEVAS ESPECIES AGREGADAS DE LA TABLA] ---
    # Usaremos Densidad Básica como Densidad (ρ) para el potencial
    # Valores de Agua y Precio por defecto si no se indican.
    # Eucalipto Torrellana (Corymbia torelliana) - Actualizado con la tabla (DAP, Altura, Tiempo)
    'Eucalipto Torrellana (Corymbia torelliana) [Tabla]': {'Densidad': 0.68, 'Agua_L_Anio': 1500, 'Precio_Plantón': 5.00, 'DAP_Max': 43.0, 'Altura_Max': 30.0, 'Tiempo_Max_Anios': 15}, 
    # Majoe (Hibiscus tiliaceus) - Actualizado con la tabla (DAP, Altura, Tiempo)
    'Majoe (Hibiscus tiliaceus) [Tabla]': {'Densidad': 0.55, 'Agua_L_Anio': 1200, 'Precio_Plantón': 5.00, 'DAP_Max': 30.0, 'Altura_Max': 12.0, 'Tiempo_Max_Anios': 20},
    # Molle (Schinus molle) - Actualizado con la tabla (DAP, Altura, Tiempo)
    'Molle (Schinus molle) [Tabla]': {'Densidad': 0.73, 'Agua_L_Anio': 900, 'Precio_Plantón': 6.00, 'DAP_Max': 65.0, 'Altura_Max': 13.0, 'Tiempo_Max_Anios': 40},
    # Algarrobo (Prosopis pallida) - Actualizado con la tabla (DAP, Altura, Tiempo)
    'Algarrobo (Prosopis pallida) [Tabla]': {'Densidad': 0.80, 'Agua_L_Anio': 800, 'Precio_Plantón': 4.00, 'DAP_Max': 60.0, 'Altura_Max': 14.0, 'Tiempo_Max_Anios': 50},
    'Shaina (Colubrina glandulosa Perkins)': {'Densidad': 0.63, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 5.00, 'DAP_Max': 40.0, 'Altura_Max': 20.0, 'Tiempo_Max_Anios': 28},
    'Limoncillo (Melicoccus bijugatus)': {'Densidad': 0.68, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 5.00, 'DAP_Max': 40.0, 'Altura_Max': 18.0, 'Tiempo_Max_Anios': 33},
    'Capirona (Calycophyllum decorticáns)': {'Densidad': 0.78, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 5.00, 'DAP_Max': 38.0, 'Altura_Max': 25.0, 'Tiempo_Max_Anios': 23},
    'Bolaina (Guazuma crinita)': {'Densidad': 0.48, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 5.00, 'DAP_Max': 25.0, 'Altura_Max': 20.0, 'Tiempo_Max_Anios': 10},
    'Amasisa (Erythrina fusca)': {'Densidad': 0.38, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 5.00, 'DAP_Max': 33.0, 'Altura_Max': 15.0, 'Tiempo_Max_Anios': 15},
    'Moena (Ocotea aciphylla)': {'Densidad': 0.58, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 5.00, 'DAP_Max': 65.0, 'Altura_Max': 33.0, 'Tiempo_Max_Anios': 45},
    'Huayruro (Ormosia coccinea)': {'Densidad': 0.73, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 5.00, 'DAP_Max': 70.0, 'Altura_Max': 33.0, 'Tiempo_Max_Anios': 65},
    'Paliperro (Miconia barbeyana Cogniaux)': {'Densidad': 0.58, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 5.00, 'DAP_Max': 40.0, 'Altura_Max': 20.0, 'Tiempo_Max_Anios': 28},
    'Cedro (Cedrela odorata)': {'Densidad': 0.43, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 5.00, 'DAP_Max': 55.0, 'Altura_Max': 30.0, 'Tiempo_Max_Anios': 28},
    'Guayacán (Guaiacum officinale)': {'Densidad': 0.54, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 5.00, 'DAP_Max': 45.0, 'Altura_Max': 12.0, 'Tiempo_Max_Anios': 60},
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


# [FIX: POTENCIAL MÁXIMO V2] Función modificada para usar valores max de la especie
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
        # [MODIFICACIÓN] Ahora incluye todas las especies de DENSIDADES_BASE
        df_cols = ['Especie', 'DAP (cm)', 'Altura (m)', 'Consumo Agua (L/año)', 'Densidad (g/cm³)', 'Precio Plantón (S/)', 'DAP Máximo (cm)', 'Altura Máxima (m)', 'Tiempo Máximo (años)'] 
        data_rows = [
            # Se usa una DAP y Altura inicial baja (5.0) para el campo de 'progresos' 
            # de la tabla de gestión, pero se usan los valores de DENSIDADES_BASE para el potencial
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
    # Se usa la primera clave para evitar errores si la lista cambia
    first_species = next(iter(DENSIDADES_BASE.keys()), 'Densidad/Datos Manuales')
    if 'especie_seleccionada' not in st.session_state: st.session_state.especie_seleccionada = first_species
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

# ... (agregar_lote, deshacer_ultimo_lote, limpiar_inventario se mantienen sin cambios mayores)

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


# --- MODIFICACIÓN CLAVE: generar_excel_memoria para incluir hojas de detalle ---
# (Se mantiene la lógica para incluir detalle JSON en el Excel)
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
# (Se mantiene sin cambios)
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
    agua_proyecto_total = get_agua_total_seguro(df_inventario_completo)

    # --- INFORMACIÓN DEL PROYECTO ---
    st.subheader("📋 Información del Proyecto")
    col_proj, col_hectareas = st.columns([2, 1])
    with col_proj:
        st.text_input("Nombre del Proyecto (Opcional)", value=st.session_state.proyecto, placeholder="Ej: Reforestación Bosque Seco 2024", key='proyecto')
    with col_hectareas:
        st.number_input("Hectáreas (ha)", min_value=0.0, value=st.session_state.hectareas, step=0.1, key='hectareas', help="Dejar en 0 si no se aplica o no se conoce el dato.")
    
    st.divider()

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
                    "DAP medido (cm)", # Etiqueta cambiada para clarificar que es medido
                    min_value=0, max_value=50, 
                    step=1, 
                    key='dap_slider', 
                    help="Diámetro a la altura del pecho. 🌳", 
                    value=int(st.session_state.dap_slider) 
                )
                col_altura.slider(
                    "Altura medida (m)", # Etiqueta cambiada para clarificar que es medida
                    min_value=0, max_value=50, 
                    step=1, 
                    key='altura_slider', 
                    help="Altura total del árbol. 🌲", 
                    value=int(st.session_state.altura_slider) 
                )
                
                # 3. Años Plantados (Ahora siempre visible, pero solo cuenta para costo si el riego está marcado)
                st.number_input(
                    "Años Plantados (Edad del lote)", 
                    min_value=0, 
                    value=st.session_state.anios_plantados_input, 
                    step=1, 
                    key='anios_plantados_input',
                    help="Define la edad actual del lote, usada para calcular la acumulación de CO2e y el costo de agua acumulado (si el riego está activado)."
                )
                if not riego_controlado:
                    st.info("⚠️ El costo del agua no se contabilizará, ya que la casilla 'Riego Controlado' no está marcada.")

                # 4. Datos de Densidad/Agua (Manual si aplica)
                if especie_sel == 'Densidad/Datos Manuales':
                    st.markdown("---")
                    st.markdown("##### ✍️ Ingrese Datos Manuales de Densidad y Consumo de Agua")
                    col_dens, col_agua = st.columns(2)
                    col_dens.number_input("Densidad (ρ) (g/cm³)", min_value=0.001, value=st.session_state.densidad_manual_input, step=0.05, format="%.3f", key='densidad_manual_input')
                    col_agua.number_input("Consumo Agua Unitario (L/año)", min_value=0.0, value=st.session_state.consumo_agua_manual_input, step=100.0, key='consumo_agua_manual_input')
                else:
                    densidad_info = current_species_info[especie_sel]['Densidad']
                    agua_info = current_species_info[especie_sel]['Agua_L_Anio']
                    info_agua_str = f"| Agua: **{agua_info} L/año**." if riego_controlado else "."
                    st.info(f"Usando valores por defecto para {especie_sel}: Densidad: **{densidad_info} g/cm³** {info_agua_str}")
                    
                st.form_submit_button("➕ Añadir Lote al Inventario", on_click=agregar_lote)

        with col_totales:
            st.subheader("Inventario Acumulado")
            total_arboles_registrados = sum(item.get('Cantidad', 0) for item in st.session_state.inventario_list)
            
            st.metric("🌳 Total Árboles Registrados", f"{total_arboles_registrados:,.0f} Árboles")
            st.metric("🌱 Captura CO₂e (Actual)", f"{co2e_proyecto_ton:,.2f} Toneladas")
            
            # Etiqueta adaptada para reflejar el costo acumulado
            costo_label = "💰 Costo Total (Acumulado) S/"
            st.metric(costo_label, f"S/{costo_proyecto_total:,.2f}") 
            
            # Etiqueta adaptada para reflejar el consumo anual
            agua_label = "💧 Consumo Agua Total (Anual) L"
            st.metric(agua_label, f"{agua_proyecto_total:,.0f} Litros")
            
            if total_arboles_registrados > 0:
                col_deshacer, col_limpiar = st.columns(2)
                col_deshacer.button("↩️ Deshacer Último Lote", on_click=deshacer_ultimo_lote, help="Elimina la última fila añadida a la tabla.")
                col_limpiar.button("🗑️ Limpiar Inventario Total", on_click=limpiar_inventario, help="Elimina todas las entradas y reinicia el cálculo.")
                
                col_excel, _ = st.columns([1, 4])
                excel_data = generar_excel_memoria(
                    df_inventario_completo.copy(), 
                    st.session_state.proyecto, 
                    st.session_state.hectareas, 
                    total_arboles_registrados, 
                    co2e_proyecto_ton, 
                    agua_proyecto_total, 
                    costo_proyecto_total
                )
                col_excel.download_button(
                    label="📥 Descargar Excel",
                    data=excel_data,
                    file_name=f'Reporte_CO2e_NBS_{pd.Timestamp.today().strftime("%Y%m%d")}.xlsx',
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Genera un archivo Excel con el resumen, el detalle de cada lote y la evidencia del cálculo."
                )

        st.markdown("---")
        st.subheader("Inventario Detallado (Lotes)")
        
        if df_inventario_completo.empty:
            st.info("No hay lotes registrados. Use el formulario superior para empezar.")
        else:
            # Se excluye solo la columna 'Detalle Cálculo' de la visualización
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
        # Gráficos (Se mantiene igual, solo usa el DF recalculado)
        st.markdown("## 📈 Visor de Gráficos")
        if df_inventario_completo.empty:
            st.warning("No hay datos en el inventario para generar gráficos.")
        else:
            df_graficos = df_inventario_completo.groupby('Especie').agg(
                Total_CO2e_Ton=('CO2e Lote (Ton)', 'sum'),
                Total_Costo_S=('Costo Total Lote (S/)', 'sum'),
                Consumo_Agua_Total_L=('Consumo Agua Total Lote (L)', 'sum'),
                Conteo_Arboles=('Cantidad', 'sum')
            ).reset_index()

            st.subheader("Análisis de Costos y Riego")
            col_costo, col_agua = st.columns(2)
            
            with col_costo:
                fig_costo = px.bar(df_graficos, x='Especie', y='Total_Costo_S', title='Costo Total (Acumulado) por Especie (Soles)', color='Total_Costo_S', color_continuous_scale=px.colors.sequential.Sunset)
                col_costo.plotly_chart(fig_costo, use_container_width=True)
            
            with col_agua:
                fig_agua = px.bar(df_graficos, x='Especie', y='Consumo_Agua_Total_L', title='Consumo Agua Anual por Especie (Litros)', color='Consumo_Agua_Total_L', color_continuous_scale=px.colors.sequential.Agsunset)
                col_agua.plotly_chart(fig_agua, use_container_width=True)
                
            st.markdown("---")
            st.subheader("Análisis de Captura de Carbono")
            col_graf1, col_graf2 = st.columns(2)
            
            fig_co2e = px.bar(df_graficos, x='Especie', y='Total_CO2e_Ton', title='CO2e Capturado por Especie (Ton)', color='Total_CO2e_Ton', color_continuous_scale=px.colors.sequential.Viridis)
            fig_arboles = px.pie(df_graficos, values='Conteo_Arboles', names='Especie', title='Conteo de Árboles por Especie', hole=0.3, color_discrete_sequence=px.colors.sequential.Plasma)
            
            with col_graf1:
                st.plotly_chart(fig_co2e, use_container_width=True)
            with col_graf2:
                st.plotly_chart(fig_arboles, use_container_width=True)


    # --- MODIFICACIÓN CLAVE: Detalle Técnico (Ahora muestra la tabla de resumen del JSON) ---
    with tab3:
        st.markdown("## 🔬 Detalle Técnico de Cálculo por Lote")
        if df_inventario_completo.empty:
            st.warning("No hay datos en el inventario para mostrar el detalle técnico. El detalle completo y descargable se encuentra en el archivo Excel (pestaña '📥 Descargar Excel').")
        else:
            lotes_info = [
                f"Lote {i+1}: {row['Especie']} ({row['Cantidad']} árboles)" 
                for i, row in enumerate(st.session_state.inventario_list) 
            ]
            
            lote_seleccionado = st.selectbox("Seleccione el Lote para el Detalle:", lotes_info)
            lote_index = lotes_info.index(lote_seleccionado)
            
            fila_lote = df_inventario_completo.iloc[lote_index]
            detalle_json = fila_lote['Detalle Cálculo']
            
            st.markdown(f"### Resumen de Fórmulas y Evidencia para {lote_seleccionado}")
            st.info("⚠️ Para el detalle completo con todas las fórmulas de sustitución, **descargue el archivo Excel** (Sección 1) que incluye una hoja por lote con la evidencia del cálculo de biomasa y carbono.")
            
            try:
                # [FIX: CORRECCIÓN DE ERROR JSON] Se verifica que el dato sea string antes de cargar el JSON.
                if not isinstance(detalle_json, str):
                    st.error(f"Error: El detalle técnico para el lote '{lote_seleccionado}' no es un formato de texto válido. Por favor, **elimine y re-agregue el lote** para corregir si el problema persiste.")
                    return
                    
                detalle_dict = json.loads(detalle_json)
                
                # Crear tabla de resumen para Streamlit (más simple que el Excel)
                data_resumen = []
                
                # Inputs
                for item in detalle_dict.get('Inputs', []):
                    data_resumen.append({'Paso': f"Input: {item['Métrica']}", 'Resultado': item['Valor'], 'Unidad': item['Unidad']})
                
                # Resultados clave (AGB, BGB, Biomasa, Carbono, CO2e)
                resultados_clave = {
                    'AGB_Aerea_kg': 'Biomasa Aérea (AGB)', 
                    'BGB_Subterranea_kg': 'Biomasa Subterránea (BGB)',
                    'Biomasa_Total_kg': 'Biomasa Total', 
                    'Carbono_kg': 'Carbono Capturado',
                    'CO2e_kg': 'CO2e Capturado (Unitario)'
                }
                
                for key, label in resultados_clave.items():
                    # Obtener el último paso, que es el resultado
                    resultado_item = detalle_dict.get(key, [])[-1]
                    data_resumen.append({'Paso': label, 'Resultado': resultado_item['Valor'], 'Unidad': resultado_item['Unidad']})
                
                df_resumen_calculo = pd.DataFrame(data_resumen)
                st.dataframe(df_resumen_calculo, use_container_width=True)
                
            except json.JSONDecodeError:
                st.error("Error al cargar el detalle técnico para este lote. Verifique que los valores de DAP, Altura y Densidad sean mayores a cero.")
            
    with tab4: # El antiguo tab5 (Equivalencias Ambientales) ahora es tab4
        # Equivalencias Ambientales (Se mantiene igual)
        render_equivalencias_ambientales(co2e_proyecto_ton)


# [FIX: POTENCIAL MÁXIMO V2] Función principal de Potencial Máximo, usando datos de la especie
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
        DAP_Max=('DAP Potencial (cm)', 'first'), # Usar el DAP Máximo de la especie
        Altura_Max=('Altura Potencial (m)', 'first'), # Usar la Altura Máxima de la especie
        Tiempo_Max=('Tiempo Máximo (años)', 'first') # Nuevo campo
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
    
    # --- GRÁFICA DE CAPTURA MÁXIMA VS TIEMPO DE CRECIMIENTO ---
    st.markdown("---")
    st.subheader("Gráfica: Captura de Carbono Potencial vs. Tiempo Máximo de Crecimiento")
    
    # Filtrar especies que tienen Tiempo Máximo y CO2e Potencial > 0
    df_grafico = df_agrupado[(df_agrupado['Tiempo_Max'] > 0) & (df_agrupado['Total_CO2e_Potencial'] > 0)].copy()

    if df_grafico.empty:
        st.warning("No hay datos suficientes (Tiempo Máximo o CO2e Potencial > 0) para generar la gráfica.")
    else:
        # Usamos la Cantidad Total como color/tamaño para añadir otra dimensión al análisis
        fig = px.scatter(
            df_grafico,
            x='Tiempo_Max',
            y='Total_CO2e_Potencial',
            size='Total_Cantidad', # El tamaño del punto refleja la cantidad de árboles
            color='DAP_Max', # El color refleja el DAP máximo
            hover_name='Especie',
            text='Especie', # Mostrar el nombre de la especie en el gráfico
            title='Potencial Máximo de Captura de CO₂e por Especie y Tiempo de Madurez',
            labels={
                'Tiempo_Max': 'Tiempo Máximo de Crecimiento (Años)',
                'Total_CO2e_Potencial': 'CO₂e Potencial Total (Ton)',
                'DAP_Max': 'DAP Máximo (cm)'
            }
        )
        
        # Ajustes de layout para mejor lectura de las etiquetas de texto
        fig.update_traces(textposition='top center')
        fig.update_layout(height=500)
        
        st.plotly_chart(fig, use_container_width=True)

    render_equivalencias_ambientales(co2e_potencial_total)


def render_gap_cpassa():
    """Análisis de brecha (GAP) entre la captura del proyecto y la Huella de Carbono Corporativa (HCC)."""
    st.title("3. GAP (Análisis de Brecha) vs. Huella Corporativa (CPSSA)")
    
    df_inventario_completo = recalcular_inventario_completo(st.session_state.inventario_list)
    co2e_proyecto_ton = get_co2e_total_seguro(df_inventario_completo)
    
    co2e_proyecto_miles_ton = co2e_proyecto_ton / 1000.0
    
    if co2e_proyecto_miles_ton <= 0:
        st.warning("⚠️ El inventario del proyecto debe tener CO2e registrado (sección 1) para realizar este análisis.")
        return
        
    st.subheader("Selección de Sede y Análisis")
    
    sede_sel = st.selectbox("Seleccione la Sede (Huella Corporativa)", list(HUELLA_CORPORATIVA.keys()))
    
    emisiones_sede_miles_ton = HUELLA_CORPORATIVA[sede_sel]
    
    st.markdown("---")
    
    col_sede, col_proyecto = st.columns(2)
    
    with col_sede:
        st.metric(f"Emisiones Anuales de '{sede_sel}' (Miles de Ton CO2e)", f"{emisiones_sede_miles_ton:,.2f} Miles tCO₂e")
        
    with col_proyecto:
        st.metric("Captura de CO₂e del Proyecto (Miles de Ton CO2e)", f"{co2e_proyecto_miles_ton:,.2f} Miles tCO₂e")

    st.markdown("---")
    
    brecha_miles_ton = emisiones_sede_miles_ton - co2e_proyecto_miles_ton
    porcentaje_compensado = (co2e_proyecto_miles_ton / emisiones_sede_miles_ton) * 100 if emisiones_sede_miles_ton > 0 else 0
    
    st.subheader("Resultado del Análisis de Brecha (GAP)")
    
    st.metric(
        "Gap (Emisiones - Captura)", 
        f"**{brecha_miles_ton:,.2f} Miles tCO₂e**", 
        delta=f"{porcentaje_compensado:,.2f}% Compensado",
        delta_color="inverse" if porcentaje_compensado > 100 else "normal"
    )
    
    if brecha_miles_ton > 0:
        st.warning(f"⚠️ Su captura de carbono actual cubre el **{porcentaje_compensado:,.2f}%** de las emisiones de **{sede_sel}**. Se requiere una captura adicional de **{brecha_miles_ton:,.2f} Miles tCO₂e** para compensar totalmente.")
    elif brecha_miles_ton <= 0:
        st.success(f"✅ ¡Felicidades! La captura de carbono del proyecto **supera** las emisiones de **{sede_sel}** en **{-brecha_miles_ton:,.2f} Miles tCO₂e**.")
        
    # Se utiliza Plotly Go para un Funnel más visual
    data_funnel = [
        ('Emisiones de la Sede', emisiones_sede_miles_ton),
        ('Captura del Proyecto', co2e_proyecto_miles_ton),
    ]

    # Ajuste para visualizar la brecha como una "diferencia" en el flujo
    if brecha_miles_ton > 0:
        data_funnel.append(('Brecha (Emisiones Pendientes)', brecha_miles_ton))
        labels = [f'Emisiones de {sede_sel}', 'Captura del Proyecto', 'Brecha (Emisiones Pendientes)']
        values = [emisiones_sede_miles_ton, co2e_proyecto_miles_ton, brecha_miles_ton]
        colors = ['red', 'green', 'lightcoral']
    else:
        labels = [f'Emisiones de {sede_sel}', 'Captura del Proyecto']
        values = [emisiones_sede_miles_ton, co2e_proyecto_miles_ton]
        colors = ['red', 'green']
    
    fig_gap = go.Figure(data=[go.Funnel(
        y=labels,
        x=values,
        textinfo="value+percent initial",
        marker={"color": colors},
        connector={"line": {"color": "gray", "dash": "dot", "width": 2}}
    )])
    
    fig_gap.update_layout(
        title_text='Flujo de Emisiones vs. Captura de Carbono (Miles tCO₂e)',
        yaxis_title="Métrica",
        xaxis_title="Valor (Miles tCO₂e)"
    )
    st.plotly_chart(fig_gap, use_container_width=True)
    
    
def render_gestion_especie():
    """Permite al usuario ver y editar los coeficientes de las especies."""
    st.title("4. Gestión de Datos de Especies y Factores")
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
            # [FIX: POTENCIAL MÁXIMO V2] Adición de DAP Máximo, Altura Máxima y Tiempo Máximo (bibliografía)
            "DAP Máximo (cm)": st.column_config.NumberColumn("DAP Máximo (cm)", format="%.1f", help="DAP máximo por literatura o madurez. Usado en la sección 2.", min_value=0.0),
            "Altura Máxima (m)": st.column_config.NumberColumn("Altura Máxima (m)", format="%.1f", help="Altura máxima por literatura o madurez. Usada en la sección 2.", min_value=0.0),
            "Tiempo Máximo (años)": st.column_config.NumberColumn("Tiempo Máximo (años)", format="%.0f", help="Tiempo de madurez o rotación de la especie. Usado en la sección 2.", min_value=0)
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


def main_app():
    """Define la estructura de la barra lateral y el contenido principal."""
    inicializar_estado_de_sesion()
    
    df_inventario_completo = recalcular_inventario_completo(st.session_state.inventario_list)
    co2e_total_sidebar = get_co2e_total_seguro(df_inventario_completo)
    
    # 1. Barra Lateral (Sidebar)
    with st.sidebar:
        st.title("🌳 Plataforma de Gestión NBS")
        st.markdown("---")
        st.subheader("Menú de Navegación")
        
        # Nuevas opciones de menú
        options = [
            "1. Cálculo de Progreso", 
            "2. Potencial Máximo", 
            "3. GAP CPSSA", 
            "4. Gestión de Especie" 
        ]
        
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
        "**Solicitar cambios y/o actualizaciones al Área de Cambio Climático**"
    )
    st.caption(
        "Para dudas y consultas adicionales, escribir al: **ftrujillo@cpsaa.com.pe**"
    )

if __name__ == "__main__":
    main_app()