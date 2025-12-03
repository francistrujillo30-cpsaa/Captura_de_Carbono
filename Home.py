import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go 
import io
import json
import re # Necesario para la limpieza del detalle técnico

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Plataforma de Gestión NBS", layout="wide", page_icon="🌳")

# --- CONSTANTES GLOBALES Y BASES DE DATOS ---
FACTOR_CARBONO = 0.47
FACTOR_CO2E = 3.67
FACTOR_BGB_SECO = 0.28
AGB_FACTOR_A = 0.112  # Constante original del proyecto (Su "Chave Factor A")
AGB_FACTOR_B = 0.916  # Constante original del proyecto (Su "Chave Factor B")
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
HUELLA_CORPORATIVA = {
    'Sede A': 120, 
    'Sede B': 80, 
    'Sede C': 50,
}

# --- DEFINICIÓN DE TIPOS DE COLUMNAS ---
df_columns_types = {
    'ID': 'int64',
    'Lote': 'object',
    'Especie': 'object',
    'Densidad (ρ)': 'float64',
    'DAP (cm)': 'float64',
    'Altura (m)': 'float64',
    'Cantidad': 'int64',
    'AGB (kg)': 'float64',
    'BGB (kg)': 'float64',
    'Biomasa Total (kg)': 'float64',
    'Carbono Total (kg)': 'float64',
    'CO2e Total (kg)': 'float64',
    'CO2e Total (Ton)': 'float64',
    'Detalle Cálculo': 'object' # JSON string
}
df_columns_numeric = ['Densidad (ρ)', 'DAP (cm)', 'Altura (m)', 'Cantidad']
columnas_salida = ['ID', 'Lote', 'Especie', 'Densidad (ρ)', 'DAP (cm)', 'Altura (m)', 'Cantidad', 
                   'AGB (kg)', 'BGB (kg)', 'Biomasa Total (kg)', 'Carbono Total (kg)', 
                   'CO2e Total (kg)', 'CO2e Total (Ton)', 'Detalle Cálculo']

# --- FUNCIÓN CRÍTICA: DINÁMICA DE ESPECIES ---
def get_current_species_info():
    """Combina la base de datos fija con las especies añadidas en la sesión."""
    current_info = DENSIDADES_BASE.copy()
    if 'especies_adicionales' in st.session_state and st.session_state.especies_adicionales is not None:
        current_info.update(st.session_state.especies_adicionales)
    
    # Añadir opción manual
    current_info['Densidad/Datos Manuales'] = {'Densidad': 0.5, 'Agua_L_Anio': 1000, 'Precio_Plantón': 5.00, 'DAP_Max': 30.0, 'Altura_Max': 20.0, 'Tiempo_Max_Anios': 25}
    return current_info

# --- FUNCIONES DE CÁLCULO Y MANEJO DE INVENTARIO ---

def get_co2e_total_seguro(df):
    """Calcula la suma total de CO2e (Ton) de forma segura."""
    if df is not None and not df.empty and 'CO2e Total (Ton)' in df.columns:
        return df['CO2e Total (Ton)'].sum()
    return 0.0

def get_costo_total_seguro(df, current_species_info):
    """Calcula el costo total de los plantones de forma segura."""
    if df is None or df.empty:
        return 0.0
    
    costo_total = 0.0
    for _, row in df.iterrows():
        especie = row['Especie']
        cantidad = row['Cantidad']
        info = current_species_info.get(especie)
        
        if info:
            precio_unitario = info.get('Precio_Plantón', 0.0)
            costo_total += cantidad * precio_unitario
        elif especie == 'Densidad/Datos Manuales':
            # Intentar obtener el precio del estado de sesión si se ingresó manualmente
            precio_unitario = st.session_state.get('precio_planton_input', 5.00) 
            costo_total += cantidad * precio_unitario
            
    return costo_total

def get_agua_total_seguro(df, current_species_info):
    """Calcula el consumo total de agua (L/año) de forma segura."""
    if df is None or df.empty:
        return 0.0
    
    agua_total = 0.0
    for _, row in df.iterrows():
        especie = row['Especie']
        cantidad = row['Cantidad']
        info = current_species_info.get(especie)
        
        if info:
            agua_unitario = info.get('Agua_L_Anio', 0.0)
            agua_total += cantidad * agua_unitario
        elif especie == 'Densidad/Datos Manuales':
            # Usar un valor por defecto si es manual
            agua_unitario = 1000.0
            agua_total += cantidad * agua_unitario
            
    return agua_total

# --- FUNCIÓN CRÍTICA: CÁLCULO DE BIOMASA ---
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
        
    # 2. Cálculo de AGB (Above-Ground Biomass) en kg
    # La Ecuación implementada es la de Ley de Potencia: AGB = A * (rho * D^2 * H)^B
    # Sustitución: AGB = AGB_FACTOR_A * ((rho * (dap_cm**2) * altura_m)**AGB_FACTOR_B)
    
    # Para mantener la compatibilidad con la notación logarítmica que se usa en la regresión
    # y la forma exponencial que se ha estado discutiendo, se usa la siguiente estructura:
    # AGB = exp( ln(AGB_FACTOR_A) + AGB_FACTOR_B * ln(rho * D^2 * H) )
    # PERO, dado que los valores de AGB_FACTOR_A y AGB_FACTOR_B son de su proyecto, 
    # se mantiene la interpretación original del usuario (Y = A * X^B)

    # --------------------------------------------------------------------------------
    # NOTA CRÍTICA: Se usa la fórmula: AGB = A * (rho * D^2 * H)^B para reflejar 
    # la interpretación potencial simple de las constantes 0.112 y 0.916 del proyecto.
    # --------------------------------------------------------------------------------
    agb_kg = AGB_FACTOR_A * ((rho * (dap_cm**2) * altura_m)**AGB_FACTOR_B)

    # 3. Cálculo de BGB (Below-Ground Biomass) en kg
    bgb_kg = agb_kg * FACTOR_BGB_SECO
    
    # 4. Biomasa total (AGB + BGB)
    biomasa_total = agb_kg + bgb_kg
    
    # 5. Carbono total
    carbono_total = biomasa_total * FACTOR_CARBONO
    
    # 6. CO2 equivalente
    co2e_total = carbono_total * FACTOR_CO2E
    
    # 7. Generación del detalle técnico
    detalle_calculo = {
        "Inputs": [
            {"Métrica": "Densidad (ρ)", "Valor": rho, "Unidad": "g/cm³"},
            {"Métrica": "DAP (D)", "Valor": dap_cm, "Unidad": "cm"},
            {"Métrica": "Altura (H)", "Valor": altura_m, "Unidad": "m"}
        ],
        "AGB_Aerea_kg": [
            {"Paso": "Fórmula (Ecuación Base)", "Ecuación": f"AGB = {AGB_FACTOR_A} × (ρ × D² × H)^{AGB_FACTOR_B}"},
            {"Paso": "Sustitución", "Ecuación": f"AGB = {AGB_FACTOR_A:.3f} × ({rho:.3f} × {dap_cm:.2f}² × {altura_m:.2f})^{AGB_FACTOR_B:.3f}"},
            {"Paso": "Resultado AGB", "Valor": agb_kg, "Unidad": "kg"}
        ],
        "BGB_Subterranea_kg": [
            {"Paso": "Fórmula", "Ecuación": f"BGB = AGB × {FACTOR_BGB_SECO}"},
            {"Paso": "Resultado BGB", "Valor": bgb_kg, "Unidad": "kg"}
        ],
        "Biomasa_Total_kg": [
            {"Paso": "Fórmula", "Ecuación": "BT = AGB + BGB"},
            {"Paso": "Resultado BT", "Valor": biomasa_total, "Unidad": "kg"}
        ],
        "Carbono_Total_kg": [
            {"Paso": "Fórmula", "Ecuación": f"C = BT × {FACTOR_CARBONO}"},
            {"Paso": "Resultado Carbono", "Valor": carbono_total, "Unidad": "kg"}
        ],
        "CO2e_Total_kg": [
            {"Paso": "Fórmula", "Ecuación": f"CO2e = C × {FACTOR_CO2E}"},
            {"Paso": "Resultado CO2e", "Valor": co2e_total, "Unidad": "kg"}
        ]
    }
    
    # El CO2e total en kg, se retorna para el cálculo del lote/proyecto
    return agb_kg, bgb_kg, biomasa_total, co2e_total, json.dumps(detalle_calculo)


# --- FUNCIÓN DE RECÁLCULO SEGURO (CRÍTICA) ---
def recalcular_inventario_completo(df_inventario, current_species_info):
    """Aplica la función de cálculo a todo el DataFrame y actualiza el CO2e."""
    if df_inventario is None or df_inventario.empty:
        return pd.DataFrame(columns=columnas_salida)

    df_inventario = df_inventario.copy()

    # Asegurar que las columnas numéricas sean float
    for col in df_columns_numeric:
        df_inventario[col] = pd.to_numeric(df_inventario[col], errors='coerce').fillna(0)

    resultados_calculo = []

    for index, row in df_inventario.iterrows():
        # Obtener Densidad
        especie = row['Especie']
        rho = row['Densidad (ρ)'] # Intentar usar el valor del inventario
        
        # Si la especie no es manual, sobreescribir rho con el valor de la base de datos
        if especie in current_species_info and especie != 'Densidad/Datos Manuales':
            rho = current_species_info[especie]['Densidad']
            
        # Variables de entrada
        dap_cm = row['DAP (cm)']
        altura_m = row['Altura (m)']
        cantidad = row['Cantidad']
        
        # Cálculo unitario
        agb_kg, bgb_kg, biomasa_total_kg, co2e_uni_kg, detalle = calcular_co2_arbol(rho, dap_cm, altura_m)
        
        # Cálculo por lote
        co2e_lote_ton = (co2e_uni_kg * cantidad) / FACTOR_KG_A_TON
        
        resultados_calculo.append({
            'ID': row['ID'],
            'Lote': row['Lote'],
            'Especie': especie,
            'Densidad (ρ)': rho,
            'DAP (cm)': dap_cm,
            'Altura (m)': altura_m,
            'Cantidad': cantidad,
            'AGB (kg)': agb_kg * cantidad,
            'BGB (kg)': bgb_kg * cantidad,
            'Biomasa Total (kg)': biomasa_total_kg * cantidad,
            'Carbono Total (kg)': co2e_uni_kg * cantidad / FACTOR_CO2E, # Vuelve a Carbono
            'CO2e Total (kg)': co2e_uni_kg * cantidad,
            'CO2e Total (Ton)': co2e_lote_ton,
            'Detalle Cálculo': detalle
        })
        
    df_recalculado = pd.DataFrame(resultados_calculo, columns=columnas_salida)
    return df_recalculado


# --- FUNCIÓN DE CÁLCULO DE POTENCIAL MÁXIMO (CRÍTICA) ---
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
            # Para datos manuales, usar DAP/Altura máxima por defecto (si la especie manual está en info)
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
            'Lote': row['Lote'],
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

# --- FUNCIONES DE RENDERIZACIÓN DE PÁGINAS (Streamlit) ---

def render_calculadora_y_graficos():
    # ... (código para la página "1. Cálculo de Progreso" se mantiene igual) ...
    st.title("🌳 1. Cálculo de Progreso de Captura (Inventario Actual)")
    
    # 1. Inicialización de Sesión
    if 'inventario_df' not in st.session_state:
        st.session_state.inventario_df = pd.DataFrame(columns=columnas_salida)
        
    if 'next_id' not in st.session_state:
        st.session_state.next_id = 1
        
    if 'proyecto' not in st.session_state:
        st.session_state.proyecto = ""
        
    if 'current_species_info' not in st.session_state:
        st.session_state.current_species_info = get_current_species_info()

    if 'precio_planton_input' not in st.session_state:
        st.session_state.precio_planton_input = 5.00 # Valor por defecto

    # 2. Entrada de Nombre del Proyecto
    st.session_state.proyecto = st.text_input("Nombre del Proyecto:", value=st.session_state.proyecto)

    # 3. Formulario de Ingreso de Datos
    st.header("Añadir Lote al Inventario")
    
    with st.form("form_agregar_lote", clear_on_submit=True):
        col_lote, col_especie, col_densidad = st.columns([1, 2, 1])
        
        # Especies disponibles
        especies_disponibles = list(st.session_state.current_species_info.keys())
        
        lote_input = col_lote.text_input("Lote/Ubicación", value=f"Lote {st.session_state.next_id}")
        especie_select = col_especie.selectbox("Especie", especies_disponibles)
        
        rho_val = st.session_state.current_species_info.get(especie_select, {}).get('Densidad', 0.5)
        densidad_input = col_densidad.number_input(
            "Densidad (g/cm³)", 
            min_value=0.001, 
            value=rho_val, 
            step=0.01, 
            format="%.3f",
            disabled=(especie_select != 'Densidad/Datos Manuales')
        )
        
        col_dap, col_altura, col_cantidad, col_precio_pl = st.columns(4)
        
        dap_input = col_dap.number_input("DAP (cm)", min_value=0.1, value=10.0, step=0.1, format="%.2f")
        altura_input = col_altura.number_input("Altura (m)", min_value=0.1, value=5.0, step=0.1, format="%.2f")
        cantidad_input = col_cantidad.number_input("Cantidad de Árboles", min_value=1, value=100, step=1)
        
        # Input de precio para datos manuales
        if especie_select == 'Densidad/Datos Manuales':
            st.session_state.precio_planton_input = col_precio_pl.number_input(
                "Precio Plantón Unitario (S/)",
                min_value=0.0,
                value=st.session_state.precio_planton_input,
                step=0.1,
                format="%.2f",
                key='precio_planton_input'
            )
        else:
            col_precio_pl.text_input(
                "Precio Plantón Unitario (S/)", 
                value=st.session_state.current_species_info.get(especie_select, {}).get('Precio_Plantón', 5.00), 
                disabled=True
            )
        
        submit_button = st.form_submit_button("➕ Agregar Lote")
        
        if submit_button:
            # Asegurarse de usar la densidad correcta: manual si es seleccionada, o la de la base
            rho_final = densidad_input if especie_select == 'Densidad/Datos Manuales' else st.session_state.current_species_info.get(especie_select, {}).get('Densidad', densidad_input)
            
            # 1. Calcular CO2e para el árbol unitario (en kg)
            agb_unitario, bgb_unitario, biomasa_total_unitario, co2e_unitario, detalle_json = calcular_co2_arbol(
                rho=rho_final, 
                dap_cm=dap_input, 
                altura_m=altura_input
            )
            
            # 2. Calcular CO2e total del lote (en Ton y kg)
            co2e_lote_ton = (co2e_unitario * cantidad_input) / FACTOR_KG_A_TON
            
            nuevo_registro = pd.DataFrame([{
                'ID': st.session_state.next_id,
                'Lote': lote_input,
                'Especie': especie_select,
                'Densidad (ρ)': rho_final,
                'DAP (cm)': dap_input,
                'Altura (m)': altura_input,
                'Cantidad': cantidad_input,
                'AGB (kg)': agb_unitario * cantidad_input,
                'BGB (kg)': bgb_unitario * cantidad_input,
                'Biomasa Total (kg)': biomasa_total_unitario * cantidad_input,
                'Carbono Total (kg)': (co2e_unitario * cantidad_input) / FACTOR_CO2E,
                'CO2e Total (kg)': co2e_unitario * cantidad_input,
                'CO2e Total (Ton)': co2e_lote_ton,
                'Detalle Cálculo': detalle_json
            }])
            
            st.session_state.inventario_df = pd.concat([st.session_state.inventario_df, nuevo_registro], ignore_index=True)
            st.session_state.next_id += 1
            st.success(f"Lote '{lote_input}' agregado exitosamente. CO2e: {co2e_lote_ton:,.2f} Ton.")

    # 4. Mostrar, editar y eliminar Inventario
    st.subheader("Inventario de Lotes Registrados")
    
    if not st.session_state.inventario_df.empty:
        # Convertir a formato de edición (data editor)
        df_display = st.session_state.inventario_df.copy()
        df_display = df_display.drop(columns=['Detalle Cálculo', 'Carbono Total (kg)', 'Biomasa Total (kg)', 'AGB (kg)', 'BGB (kg)', 'CO2e Total (kg)'])
        df_display['CO2e Total (Ton)'] = df_display['CO2e Total (Ton)'].apply(lambda x: f"{x:,.2f}")
        df_display = df_display.set_index('ID')
        
        edited_df = st.data_editor(
            df_display, 
            column_config={
                "CO2e Total (Ton)": st.column_config.TextColumn("CO2e Total (Ton)", disabled=True),
                "Lote": st.column_config.TextColumn("Lote", width='small'),
                "Especie": st.column_config.TextColumn("Especie", disabled=True),
                "Densidad (ρ)": st.column_config.NumberColumn("Densidad (ρ)", format="%.3f", disabled=True),
                "DAP (cm)": st.column_config.NumberColumn("DAP (cm)", format="%.2f"),
                "Altura (m)": st.column_config.NumberColumn("Altura (m)", format="%.2f"),
                "Cantidad": st.column_config.NumberColumn("Cantidad", format="%d"),
            },
            key="inventario_editor",
            use_container_width=True,
            num_rows="dynamic"
        )
        
        # Limpieza y conversión del DataFrame editado para el recálculo
        df_final_edit = edited_df.reset_index()
        # El DataFrame de sesión debe ser re-creado a partir del editor (aunque es más complejo por las especies)
        
        if st.button("🔁 Recalcular Inventario (Tras Edición)", type="primary"):
            # Para el recálculo, se debe reconstruir el DataFrame completo, incluyendo las columnas de cálculo
            
            # 1. Crear una lista de diccionarios con los datos editados
            edited_data_list = df_final_edit.to_dict('records')
            
            # 2. Reconstruir el DF de sesión usando la función de recálculo
            st.session_state.inventario_df = recalcular_inventario_completo(
                pd.DataFrame(edited_data_list), 
                st.session_state.current_species_info
            )
            st.rerun()

        # Botón para borrar un lote (usando el ID)
        col_borrar, col_descarga = st.columns([1, 4])
        id_a_borrar = col_borrar.number_input("ID del Lote a Eliminar", min_value=1, max_value=st.session_state.next_id - 1, step=1, value=1)
        if col_borrar.button("🗑️ Eliminar Lote"):
            if id_a_borrar in st.session_state.inventario_df['ID'].values:
                st.session_state.inventario_df = st.session_state.inventario_df[st.session_state.inventario_df['ID'] != id_a_borrar]
                st.session_state.inventario_df = st.session_state.inventario_df.reset_index(drop=True)
                st.session_state.inventario_df['ID'] = range(1, len(st.session_state.inventario_df) + 1)
                st.session_state.next_id = len(st.session_state.inventario_df) + 1
                st.success(f"Lote ID {id_a_borrar} eliminado.")
                st.rerun()
            else:
                st.warning(f"No se encontró el Lote con ID {id_a_borrar}.")
                
        # Botón de Descarga
        csv_download = st.session_state.inventario_df.to_csv(index=False).encode('utf-8')
        col_descarga.download_button(
            label="Descargar Inventario (CSV)",
            data=csv_download,
            file_name=f'{st.session_state.proyecto.replace(" ", "_")}_inventario_progreso.csv',
            mime='text/csv',
            use_container_width=True
        )

    # 5. Dashboard de Resultados
    st.header("Dashboard de Progreso")
    df_actual = st.session_state.inventario_df

    if not df_actual.empty:
        
        co2e_total = get_co2e_total_seguro(df_actual)
        costo_total = get_costo_total_seguro(df_actual, st.session_state.current_species_info)
        agua_total = get_agua_total_seguro(df_actual, st.session_state.current_species_info)
        
        col_co2, col_costo, col_agua = st.columns(3)
        
        col_co2.metric("CO2e Total Capturado (Progreso)", f"{co2e_total:,.2f} Ton")
        col_costo.metric("Costo Estimado de Plantones", f"S/ {costo_total:,.2f}")
        col_agua.metric("Consumo de Agua Estimado", f"{agua_total/FACTOR_L_A_M3:,.2f} m³/año")
        
        st.markdown("---")
        
        # Gráficos
        col_graf_1, col_graf_2 = st.columns(2)
        
        # Gráfico de CO2e por Especie
        df_co2_especie = df_actual.groupby('Especie')['CO2e Total (Ton)'].sum().reset_index()
        df_co2_especie = df_co2_especie.sort_values(by='CO2e Total (Ton)', ascending=False)
        fig_co2_especie = px.bar(
            df_co2_especie,
            x='Especie',
            y='CO2e Total (Ton)',
            title='CO2e Capturado por Especie',
            template='plotly_white'
        )
        col_graf_1.plotly_chart(fig_co2_especie, use_container_width=True)
        
        # Gráfico de Biomasa por Lote
        df_biomasa_lote = df_actual.groupby('Lote')['Biomasa Total (kg)'].sum().reset_index()
        df_biomasa_lote = df_biomasa_lote.sort_values(by='Biomasa Total (kg)', ascending=False)
        fig_biomasa_lote = px.pie(
            df_biomasa_lote,
            values='Biomasa Total (kg)',
            names='Lote',
            title='Distribución de Biomasa por Lote (kg)',
            hole=0.3
        )
        col_graf_2.plotly_chart(fig_biomasa_lote, use_container_width=True)

        # 6. Detalle Técnico (Primer Lote)
        st.markdown("---")
        st.subheader("Detalle Técnico del Primer Lote Registrado")
        try:
            detalle_lote_json = df_actual['Detalle Cálculo'].iloc[0]
            detalle_lote = json.loads(detalle_lote_json)
            
            st.json(detalle_lote)
        except Exception:
            st.info("No hay detalles técnicos disponibles o el JSON es inválido.")
            
    else:
        st.info("El inventario está vacío. Agregue un lote para ver el dashboard.")


def render_potencial_maximo():
    st.title("📈 2. Cálculo de CO₂e Potencial Máximo")
    st.markdown("""
        Esta sección proyecta la máxima captura de CO₂e que el inventario actual podría alcanzar 
        al utilizar las dimensiones máximas (DAP y Altura) registradas en la base de datos para cada especie.
        
        **Fórmula Utilizada:** Es la misma Ecuación de Biomasa Aérea del inventario, pero sustituyendo DAP y H 
        por $DAP_{Max}$ y $Altura_{Max}$.
    """)
    
    # 1. Validación y Obtención de Datos
    if 'inventario_df' not in st.session_state or st.session_state.inventario_df.empty:
        st.warning("No hay lotes registrados. Por favor, agregue lotes en la sección '1. Cálculo de Progreso' para calcular el potencial máximo.")
        return
        
    df_inventario = st.session_state.inventario_df.copy()
    current_species_info = st.session_state.current_species_info
    
    inventario_list = df_inventario.to_dict('records')
    
    # 2. Cálculo del Potencial Máximo
    df_potencial = calcular_potencial_maximo_lotes(inventario_list, current_species_info)
    
    if df_potencial.empty:
        st.error("No se pudo calcular el potencial máximo. Revise los datos de su inventario.")
        return

    # 3. Mostrar Resultados
    
    co2e_progreso = get_co2e_total_seguro(df_inventario)
    co2e_potencial = df_potencial['CO2e Lote Potencial (Ton)'].sum()
    
    col_prog, col_pot, col_gap = st.columns(3)
    
    col_prog.metric("CO2e Inventario (Progreso)", f"{co2e_progreso:,.2f} Ton")
    col_pot.metric("CO2e Potencial Máximo", f"{co2e_potencial:,.2f} Ton")
    
    gap_porcentaje = (co2e_progreso / co2e_potencial) * 100 if co2e_potencial > 0 else 0
    col_gap.metric("Gap de Progreso", f"{gap_porcentaje:,.2f}%", help="Porcentaje de CO2e capturado respecto al máximo potencial.")
    
    st.markdown("---")

    # 4. Tabla de Detalle del Potencial
    st.subheader("Detalle del Potencial Máximo por Lote")
    
    df_display = df_potencial.copy()
    df_display = df_display.drop(columns=['Detalle Cálculo'])
    df_display['CO2e Lote Potencial (Ton)'] = df_display['CO2e Lote Potencial (Ton)'].apply(lambda x: f"{x:,.2f}")
    
    st.dataframe(
        df_display,
        column_config={
            "CO2e Lote Potencial (Ton)": st.column_config.TextColumn("CO2e Potencial (Ton)"),
            "DAP Potencial (cm)": st.column_config.TextColumn("DAP Max. (cm)", help="Valor máximo utilizado en el cálculo."),
            "Altura Potencial (m)": st.column_config.TextColumn("Altura Max. (m)", help="Valor máximo utilizado en el cálculo."),
            "Tiempo Máximo (años)": st.column_config.TextColumn("Tiempo Max. (años)", help="Años estimados para alcanzar el DAP y Altura máxima."),
        },
        use_container_width=True
    )
    
    # 5. Gráfico de Comparación
    st.subheader("Comparación Progreso vs. Potencial por Especie")
    
    df_progreso_lote = df_inventario.groupby('Especie')['CO2e Total (Ton)'].sum().reset_index().rename(columns={'CO2e Total (Ton)': 'Progreso'})
    df_potencial_lote = df_potencial.groupby('Especie')['CO2e Lote Potencial (Ton)'].apply(lambda x: pd.to_numeric(x.str.replace(',', ''), errors='coerce').sum()).reset_index().rename(columns={'CO2e Lote Potencial (Ton)': 'Potencial'})
    
    df_comparacion = pd.merge(df_progreso_lote, df_potencial_lote, on='Especie', how='outer').fillna(0)
    df_comparacion = df_comparacion.set_index('Especie').stack().reset_index().rename(columns={'level_1': 'Tipo', 0: 'CO2e (Ton)'})
    
    fig_comp = px.bar(
        df_comparacion,
        x='Especie',
        y='CO2e (Ton)',
        color='Tipo',
        barmode='group',
        title='Captura de CO2e: Progreso Actual vs. Potencial Máximo',
        template='plotly_white'
    )
    st.plotly_chart(fig_comp, use_container_width=True)
    
    # 6. Detalle Técnico del Primer Lote (Potencial)
    st.markdown("---")
    st.subheader("Detalle Técnico del Cálculo Potencial del Primer Lote")
    try:
        detalle_lote_json = df_potencial['Detalle Cálculo'].iloc[0]
        detalle_lote = json.loads(detalle_lote_json)
        
        # Muestra que los inputs son los valores máximos
        st.json(detalle_lote)
    except Exception:
        st.info("No hay detalles técnicos disponibles para el cálculo potencial.")
        
    # Botón de Descarga
    csv_download = df_potencial.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Descargar Detalle de Potencial Máximo (CSV)",
        data=csv_download,
        file_name=f'{st.session_state.proyecto.replace(" ", "_")}_potencial_maximo.csv',
        mime='text/csv',
        use_container_width=True
    )

def render_gap_cpassa():
    # ... (código para la página "3. GAP CPSSA" se mantiene igual) ...
    st.title("📊 3. GAP CPSSA: Análisis de Brecha de Captura")
    st.markdown("""
        Esta sección compara el CO₂e total capturado (progreso) contra la Huella de Carbono
        declarada por la empresa por sede, calculando la brecha (GAP) en la meta de neutralidad.
    """)
    
    if 'inventario_df' not in st.session_state or st.session_state.inventario_df.empty:
        st.warning("No hay lotes registrados. Por favor, agregue lotes en la sección '1. Cálculo de Progreso'.")
        return
        
    df_inventario = st.session_state.inventario_df
    co2e_total_progreso = get_co2e_total_seguro(df_inventario)

    st.subheader("Huella de Carbono por Sede (Miles de Ton CO₂e)")
    
    # DataFrame de la huella
    df_huella = pd.DataFrame(list(HUELLA_CORPORATIVA.items()), columns=['Sede', 'Huella (Miles Ton)'])
    df_huella['Huella (Ton)'] = df_huella['Huella (Miles Ton)'] * 1000
    huella_total_corporativa = df_huella['Huella (Ton)'].sum()
    
    # Brecha (GAP)
    df_huella['Captura (Ton)'] = co2e_total_progreso
    df_huella['Huella Remanente (Ton)'] = df_huella['Huella (Ton)'] - df_huella['Captura (Ton)']
    df_huella['GAP (%)'] = (df_huella['Captura (Ton)'] / df_huella['Huella (Ton)']) * 100
    df_huella['GAP (%)'] = df_huella['GAP (%)'].clip(upper=100) # El progreso máximo es 100% del GAP

    st.dataframe(
        df_huella.drop(columns=['Huella (Miles Ton)']),
        column_config={
            "Huella (Ton)": st.column_config.NumberColumn("Huella (Ton)", format="%,.0f"),
            "Captura (Ton)": st.column_config.NumberColumn("Captura (Ton)", format="%,.0f"),
            "Huella Remanente (Ton)": st.column_config.NumberColumn("Huella Remanente (Ton)", format="%,.0f"),
            "GAP (%)": st.column_config.ProgressColumn("Progreso en Neutralidad (%)", format="%.2f%%", min_value=0, max_value=100)
        },
        use_container_width=True
    )
    
    st.markdown("---")
    
    col_cap, col_gap_total = st.columns(2)
    
    col_cap.metric("CO2e Capturado Total", f"{co2e_total_progreso:,.2f} Ton")
    col_cap.metric("Huella de Carbono Total", f"{huella_total_corporativa:,.2f} Ton")
    
    gap_porcentaje_corp = (co2e_total_progreso / huella_total_corporativa) * 100 if huella_total_corporativa > 0 else 0
    col_gap_total.metric(
        "Progreso en Meta de Neutralidad Corporativa", 
        f"{gap_porcentaje_corp:,.2f}%",
        delta=f"{co2e_total_progreso - huella_total_corporativa:,.2f} Ton restantes" if co2e_total_progreso < huella_total_corporativa else "Meta Superada"
    )
    
    # Gráfico de Brecha
    st.subheader("Gráfico de Brecha de Neutralidad")
    
    # Creamos un DF para el gráfico de barras apiladas
    df_plot_gap = df_huella[['Sede', 'Huella Remanente (Ton)', 'Captura (Ton)']].melt(
        id_vars='Sede',
        var_name='Tipo',
        value_name='CO2e (Ton)'
    )
    
    fig_gap = px.bar(
        df_plot_gap,
        x='Sede',
        y='CO2e (Ton)',
        color='Tipo',
        title='CO2e Capturado vs. Huella Remanente por Sede',
        barmode='stack',
        color_discrete_map={'Captura (Ton)': 'green', 'Huella Remanente (Ton)': 'red'},
        template='plotly_white'
    )
    
    st.plotly_chart(fig_gap, use_container_width=True)

def render_gestion_especie():
    # ... (código para la página "4. Gestión de Especie" se mantiene igual) ...
    st.title("⚙️ 4. Gestión de Parámetros de Especie")
    st.markdown("""
        Aquí puede ver y editar los parámetros de las especies utilizados en la fórmula de biomasa, 
        así como añadir nuevas especies a la base de datos.
    """)
    
    # 1. Inicialización de Especies Adicionales
    if 'especies_adicionales' not in st.session_state:
        st.session_state.especies_adicionales = {}
        
    current_species_info = get_current_species_info()

    # 2. Tabla de Especies Actuales
    st.subheader("Base de Datos de Especies Actual")
    
    df_especies = pd.DataFrame(current_species_info).T
    df_especies['Especie'] = df_especies.index
    df_especies = df_especies.reset_index(drop=True)
    
    df_display = df_especies.drop(columns=['Precio_Plantón'])
    
    st.dataframe(
        df_display,
        column_config={
            "Especie": st.column_config.TextColumn("Especie"),
            "Densidad": st.column_config.NumberColumn("Densidad (ρ) g/cm³", format="%.3f"),
            "Agua_L_Anio": st.column_config.NumberColumn("Agua L/año", format="%.0f"),
            "DAP_Max": st.column_config.NumberColumn("DAP Max (cm)", format="%.1f"),
            "Altura_Max": st.column_config.NumberColumn("Altura Max (m)", format="%.1f"),
            "Tiempo_Max_Anios": st.column_config.NumberColumn("Tiempo Max (años)", format="%d"),
        },
        use_container_width=True
    )
    
    # 3. Formulario para Añadir Nueva Especie
    st.subheader("Añadir Nueva Especie")
    with st.form("form_nueva_especie", clear_on_submit=True):
        nombre_especie = st.text_input("Nombre de la Nueva Especie (Ej: Capirona)", max_chars=100)
        
        col_den, col_agua, col_precio = st.columns(3)
        densidad_nueva = col_den.number_input("Densidad (g/cm³)", min_value=0.001, max_value=1.5, value=0.5, step=0.01, format="%.3f")
        agua_nueva = col_agua.number_input("Consumo de Agua (L/año)", min_value=1, value=1000, step=100)
        precio_nuevo = col_precio.number_input("Precio Plantón (S/)", min_value=0.01, value=5.00, step=0.1, format="%.2f")
        
        st.markdown("---")
        st.markdown("**Parámetros Máximos para Cálculo Potencial**")
        col_dap_max, col_alt_max, col_tiempo_max = st.columns(3)
        dap_max_nueva = col_dap_max.number_input("DAP Máximo (cm)", min_value=1.0, value=30.0, step=1.0, format="%.1f")
        altura_max_nueva = col_alt_max.number_input("Altura Máxima (m)", min_value=1.0, value=20.0, step=1.0, format="%.1f")
        tiempo_max_nueva = col_tiempo_max.number_input("Tiempo Máximo (años)", min_value=1, value=20, step=1)
        
        submit_nueva = st.form_submit_button("➕ Guardar Nueva Especie")
        
        if submit_nueva:
            if nombre_especie and nombre_especie not in current_species_info:
                st.session_state.especies_adicionales[nombre_especie] = {
                    'Densidad': densidad_nueva,
                    'Agua_L_Anio': agua_nueva,
                    'Precio_Plantón': precio_nuevo,
                    'DAP_Max': dap_max_nueva,
                    'Altura_Max': altura_max_nueva,
                    'Tiempo_Max_Anios': tiempo_max_nueva,
                }
                st.session_state.current_species_info = get_current_species_info()
                st.success(f"Especie '{nombre_especie}' añadida exitosamente.")
                st.rerun()
            elif nombre_especie in current_species_info:
                st.error("Esa especie ya existe. Por favor, use un nombre diferente.")
            else:
                st.error("Por favor, ingrese un nombre para la especie.")
                
    # 4. Eliminar Especie
    st.subheader("Eliminar Especie Adicional")
    if st.session_state.especies_adicionales:
        especies_add_list = list(st.session_state.especies_adicionales.keys())
        especie_a_eliminar = st.selectbox("Seleccione la especie adicional a eliminar:", especies_add_list)
        if st.button("🗑️ Eliminar Especie"):
            del st.session_state.especies_adicionales[especie_a_eliminar]
            st.session_state.current_species_info = get_current_species_info()
            st.success(f"Especie '{especie_a_eliminar}' eliminada.")
            st.rerun()
    else:
        st.info("No hay especies adicionales para eliminar.")


def reiniciar_app_completo():
    """Limpia todos los datos de sesión y reinicia la aplicación."""
    for key in list(st.session_state.keys()):
        if key not in ['current_page', 'current_species_info']:
            del st.session_state[key]
    st.session_state.current_page = "1. Cálculo de Progreso" # Volver a la página inicial
    st.rerun()

# --- FUNCIÓN PRINCIPAL DE LA APLICACIÓN ---

def main_app():
    # 1. Sidebar de navegación y Métricas
    opciones = ["1. Cálculo de Progreso", "2. Potencial Máximo", "3. GAP CPSSA", "4. Gestión de Especie"]
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = opciones[0]
        
    if 'inventario_df' not in st.session_state:
        st.session_state.inventario_df = pd.DataFrame(columns=columnas_salida)

    # Calcular CO2e total para la métrica del sidebar
    co2e_total_sidebar = get_co2e_total_seguro(st.session_state.inventario_df)

    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/C_%C3%A1rbol_simple.svg/1200px-C_%C3%A1rbol_simple.svg.png", width=100)
        st.title("Menu NBS 🌳")
        st.markdown("---")

        for option in opciones:
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

if __name__ == "__main__":
    main_app()