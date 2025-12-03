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
AGB_FACTOR_A = 0.112 # Constante original del proyecto
AGB_FACTOR_B = 0.916 # Constante original del proyecto
FACTOR_KG_A_TON = 1000 # Constante para conversión

# CONSTANTES PARA COSTOS 
PRECIO_AGUA_POR_M3 = 3.0 # Precio fijo del m3 de agua en Perú (3 Soles)
FACTOR_L_A_M3 = 1000 # 1 m3 = 1000 Litros

# BASE DE DATOS INICIAL DE DENSIDADES, AGUA Y COSTO
# [FIX: POTENCIAL MÁXIMO V2] Adición de DAP Máximo, Altura Máxima y Tiempo Máximo (bibliografía)
DENSIDADES_BASE = {
    'Eucalipto Torrellana (Corymbia torelliana)': {'Densidad': 0.46, 'Agua_L_Anio': 1500, 'Precio_Plantón': 5.00, 'DAP_Max': 45.0, 'Altura_Max': 35.0, 'Tiempo_Max_Anios': 20}, 
    'Majoe (Hibiscus tiliaceus)': {'Densidad': 0.57, 'Agua_L_Anio': 1200, 'Precio_Plantón': 5.00, 'DAP_Max': 25.0, 'Altura_Max': 15.0, 'Tiempo_Max_Anios': 15}, 
    'Molle (Schinus molle)': {'Densidad': 0.44, 'Agua_L_Anio': 900, 'Precio_Plantón': 6.00, 'DAP_Max': 30.0, 'Altura_Max': 20.0, 'Tiempo_Max_Anios': 25},
    'Algarrobo (Prosopis pallida)': {'Densidad': 0.53, 'Agua_L_Anio': 800, 'Precio_Plantón': 4.00, 'DAP_Max': 40.0, 'Altura_Max': 18.0, 'Tiempo_Max_Anios': 30},
}


# HUELLA DE CARBONO CORPORATIVA POR SEDE (EN MILES DE tCO2e)
# ... (rest of HUELLA_CORPORATIVA remains unchanged) ...

# --- DEFINICIÓN DE TIPOS DE COLUMNAS ---
# ... (df_columns_types, df_columns_numeric, columnas_salida remain unchanged) ...

# --- FUNCIÓN CRÍTICA: DINÁMICA DE ESPECIES ---
# ... (get_current_species_info remains unchanged) ...

# --- FUNCIONES DE CÁLCULO Y MANEJO DE INVENTARIO ---
# ... (get_co2e_total_seguro, get_costo_total_seguro, get_agua_total_seguro remain unchanged) ...


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
    # [CORRECCIÓN V3: Usando fórmula potencial simple A*(V^B) con constantes del proyecto]
    # Fórmula: AGB = AGB_FACTOR_A × (ρ × D² × H)^AGB_FACTOR_B 
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
            # ATENCIÓN: Se ajusta la descripción para reflejar la fórmula potencial implementada
            {"Paso": "Fórmula (Modelo Potencial)", "Ecuación": f"AGB = {AGB_FACTOR_A} × (ρ × D² × H)^{AGB_FACTOR_B}"},
            {"Paso": "Sustitución", "Ecuación": f"AGB = {AGB_FACTOR_A:.3f} × ({rho:.3f} × {dap_cm:.2f}² × {altura_m:.2f})^{AGB_FACTOR_B:.3f}"},
            {"Paso": "Resultado AGB", "Valor": agb_kg, "Unidad": "kg"}
        ],
        "BGB_Subterranea_kg": [
# ... (rest of the detail_calculo remains unchanged) ...
# ... (rest of calcular_co2_arbol remains unchanged) ...
    
    return agb_kg, bgb_kg, biomasa_total, co2e_total, json.dumps(detalle_calculo)


# --- FUNCIÓN DE RECÁLCULO SEGURO (CRÍTICA) ---
# ... (recalcular_inventario_completo remains unchanged) ...

# [FIX: POTENCIAL MÁXIMO V2] Función que usa valores max de la especie
def calcular_potencial_maximo_lotes(inventario_list, current_species_info):
    """
    Calcula el CO2e potencial máximo utilizando los valores máximos de DAP y Altura 
    propios de cada especie en los lotes del inventario, usando la misma Ecuación de Biomasa.
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
        dap = 0.0 # DAP Potencial (Max)
        altura = 0.0 # Altura Potencial (Max)
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
             # ESTE LLAMADO USA EL DAP POTENCIAL Y LA ALTURA POTENCIAL
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

# ... (rest of the code remains unchanged) ...