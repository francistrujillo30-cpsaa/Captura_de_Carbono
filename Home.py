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

# NUEVAS CONSTANTES PARA COSTOS (SOLICITUD DEL USUARIO)
PRECIO_AGUA_POR_M3 = 3.0 # Precio fijo del m3 de agua en Perú (3 Soles)
FACTOR_L_A_M3 = 1000 # 1 m3 = 1000 Litros

# BASE DE DATOS INICIAL DE DENSIDADES, AGUA Y COSTO
# Valores por defecto para simulación y gestión
DENSIDADES_BASE = {
    'Eucalipto Torrellana (Corymbia torelliana)': {'Densidad': 0.46, 'Agua_L_Anio': 1500, 'Precio_Plantón': 5.00}, 
    'Majoe (Hibiscus tiliaceus)': {'Densidad': 0.57, 'Agua_L_Anio': 1200, 'Precio_Plantón': 5.00}, # ACTUALIZADO A S/ 5.00
    'Molle (Schinus molle)': {'Densidad': 0.44, 'Agua_L_Anio': 900, 'Precio_Plantón': 6.00},
    'Algarrobo (Prosopis pallida)': {'Densidad': 0.53, 'Agua_L_Anio': 800, 'Precio_Plantón': 4.00},
}


# FACTORES DE CRECIMIENTO INICIAL (Valores por defecto para simulación)
FACTORES_CRECIMIENTO = {
    'Eucalipto Torrellana (Corymbia torelliana)': {'DAP': 0.05, 'Altura': 0.05, 'Agua': 0.0},
    'Majoe (Hibiscus tiliaceus)': {'DAP': 0.08, 'Altura': 0.06, 'Agua': 0.0},
    'Molle (Schinus molle)': {'DAP': 0.06, 'Altura': 0.07, 'Agua': 0.0},
    'Algarrobo (Prosopis pallida)': {'DAP': 0.04, 'Altura': 0.04, 'Agua': 0.0},
    'Factor Manual': {'DAP': 0.05, 'Altura': 0.05, 'Agua': 0.0}
}


# HUELLA DE CARBONO CORPORATIVA POR SEDE (EN MILES DE tCO2e)
# Fuente: Informe Final Huella de Carbono Corporativa 2024
HUELLA_CORPORATIVA = {
    # CEMENTOS PACASMAYO S.A.A.
    "Planta Pacasmayo": 1265.15,      # 1,265,154.79 tCO2e
    "Planta Piura": 595.76,          # 595,763.31 tCO2e
    "Oficina Lima": 0.613,           # 612.81 tCO2e
    "Cantera Tembladera": 0.361,     # 361.15 tCO2e
    "Cantera Cerro Pintura": 0.425,  # 425.43 tCO2e
    "Cantera Virrilá": 0.433,        # 432.69 tCO2e
    "Cantera Bayóvar 4": 0.029,      # 29.03 tCO2e
    "Cantera Bayóvar 9": 0.041,      # 40.66 tCO2e
    "Almacén Salaverry": 0.0038,     # 3.80 tCO2e
    "Almacén Piura": 0.0053,         # 5.32 tCO2e
    
    # CEMENTOS SELVA S.A.C.
    "Planta Rioja": 264.63,          # 264,627.26 tCO2e
    "Cantera Tioyacu": 0.198,        # 197.94 tCO2e
    
    # DINO S.R.L.
    "DINO Cajamarca": 2.193,         # 2,192.56 tCO2e
    "DINO Chiclayo": 3.293,          # 3,293.47 tCO2e
    "DINO Chimbote": 1.708,          # 1,708.21 tCO2e
    "DINO Moche": 3.336,             # 3,336.06 tCO2e
    "DINO Piura": 1.004,             # 1,003.88 tCO2e
    "DINO Pacasmayo": 1.188,         # 1,188.45 tCO2e
    "DINO Trujillo": 1.954,          # 1,954.46 tCO2e
    "DINO Almacén Paita": 0.0074,    # 7.44 tCO2e
    
    # DISAC
    "DISAC Tarapoto": 0.708          # 708.38 tCO2e
}


# --- DEFINICIÓN DE TIPOS DE COLUMNAS (Añadidas nuevas métricas de entrada) ---
df_columns_types = {
    'Especie': str, 'Cantidad': int, 'DAP (cm)': float, 'Altura (m)': float, 
    'Densidad (ρ)': float, 'Años Plantados': int, 'Consumo Agua Unitario (L/año)': float, 
    'Precio Plantón Unitario (S/)': float, # CAMBIO DE $ A S/
    'Detalle Cálculo': str 
}
df_columns_numeric = ['Cantidad', 'DAP (cm)', 'Altura (m)', 'Densidad (ρ)', 'Años Plantados', 'Consumo Agua Unitario (L/año)', 'Precio Plantón Unitario (S/)'] # CAMBIO DE $ A S/

# (Añadidas nuevas métricas de salida)
columnas_salida = ['Biomasa Lote (Ton)', 'Carbono Lote (Ton)', 'CO2e Lote (Ton)', 'Consumo Agua Total Lote (L)', 'Costo Total Lote (S/)'] # CAMBIO DE $ A S/

# --- FUNCIÓN CRÍTICA: DINÁMICA DE ESPECIES (Actualizada) ---
def get_current_species_info():
    """
    Genera un diccionario de información de especies (Densidad, Agua, Precio) 
    fusionando las especies base con las especies añadidas/modificadas por el usuario.
    """
    # 1. Info inicial
    current_info = {
        name: {'Densidad': data['Densidad'], 'Agua_L_Anio': data['Agua_L_Anio'], 'Precio_Plantón': data['Precio_Plantón']}
        for name, data in DENSIDADES_BASE.items()
    }
    
    # 2. Obtener la data de la tabla de gestión de especies (persistencia)
    df_bd = st.session_state.especies_bd.copy()
    
    # 3. Incorporar/sobreescribir con datos de la BD del usuario
    if not df_bd.empty:
        df_unique_info = df_bd.drop_duplicates(subset=['Especie'], keep='last')
        
        for _, row in df_unique_info.iterrows():
            especie_name = row['Especie']
            
            # Asegurar la conversión segura de los nuevos campos
            densidad_val = pd.to_numeric(row.get('Densidad (g/cm³)', 0.0), errors='coerce') 
            agua_val = pd.to_numeric(row.get('Consumo Agua (L/año)', 0.0), errors='coerce')
            precio_val = pd.to_numeric(row.get('Precio Plantón (S/)', 0.0), errors='coerce') # USANDO NUEVO NOMBRE DE COLUMNA S/
            
            if pd.notna(densidad_val) and densidad_val > 0:
                current_info[especie_name] = {
                    'Densidad': densidad_val,
                    'Agua_L_Anio': agua_val if pd.notna(agua_val) and agua_val >= 0 else 0.0,
                    'Precio_Plantón': precio_val if pd.notna(precio_val) and precio_val >= 0 else 0.0
                }
    
    # 4. Añadir la opción de datos manuales
    current_info['Densidad/Datos Manuales'] = {'Densidad': 0.0, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 0.0}
    
    return current_info


# --- FUNCIONES DE CÁLCULO Y MANEJO DE INVENTARIO ---

def calcular_co2_arbol(rho, dap_cm, altura_m):
    """Calcula la biomasa, carbono y CO2e por árbol en KILOGRAMOS."""
    detalle = ""
    # Evita la división por cero o logaritmos de cero
    if rho <= 0 or dap_cm <= 0 or altura_m <= 0:
        detalle = "ERROR: Valores de entrada (DAP, Altura o Densidad) deben ser mayores a cero."
        return 0, 0, 0, 0, detalle
        
    # Calcular AGB (Above-Ground Biomass) en kg
    # Fórmula: AGB = 0.112 × (ρ × D² × H)^0.916 (Chave et al. 2014)
    agb_kg = AGB_FACTOR_A * ((rho * (dap_cm**2) * altura_m)**AGB_FACTOR_B)
    
    # Calcular BGB (Below-Ground Biomass) en kg
    bgb_kg = agb_kg * FACTOR_BGB_SECO
    
    # Biomasa total (AGB + BGB)
    biomasa_total = agb_kg + bgb_kg
    
    # Carbono total
    carbono_total = biomasa_total * FACTOR_CARBONO
    
    # CO2 equivalente
    co2e_total = carbono_total * FACTOR_CO2E
    
    # Generación del detalle técnico para la pestaña 3
    detalle += f"## 1. Biomasa Aérea (AGB) por Árbol\n"
    detalle += f"**Fórmula (kg):** `{AGB_FACTOR_A} * (ρ * DAP² * H)^{AGB_FACTOR_B}` (Chave 2014)\n"
    detalle += f"**Resultado AGB (kg):** `{agb_kg:.4f}`\n\n"
    detalle += f"## 2. Biomasa Subterránea (BGB)\n"
    detalle += f"**Fórmula (kg):** `AGB * {FACTOR_BGB_SECO}`\n"
    detalle += f"**Resultado BGB (kg):** `{bgb_kg:.4f}`\n\n"
    detalle += f"## 3. Biomasa Total (AGB + BGB)\n"
    detalle += f"**Resultado Biomasa Total (kg):** `{biomasa_total:.4f}`\n\n"
    detalle += f"## 4. Carbono Capturado (C)\n"
    detalle += f"**Fórmula (kg):** `Biomasa Total * {FACTOR_CARBONO}`\n"
    detalle += f"**Resultado Carbono (kg):** `{carbono_total:.4f}`\n\n"
    detalle += f"## 5. CO2 Equivalente Capturado (CO2e)\n"
    detalle += f"**Fórmula (kg):** `Carbono * {FACTOR_CO2E}`\n"
    detalle += f"**Resultado CO2e (kg):** `{co2e_total:.4f}`"
    
    return agb_kg, bgb_kg, biomasa_total, co2e_total, detalle


# --- FUNCIÓN DE RECÁLCULO SEGURO (CRÍTICA - Actualizada) ---
def recalcular_inventario_completo(inventario_list):
    """
    Toma la lista de entradas (List[Dict]) y genera un DataFrame completo y limpio, 
    incluyendo CO2e, Consumo de Agua y Costo Total (Plantones + Agua).
    """
    if not inventario_list:
        return pd.DataFrame(columns=list(df_columns_types.keys()) + columnas_salida).astype({**df_columns_types, **dict.fromkeys(columnas_salida, float)})

    # Crear DF base y limpiar tipos
    df_base = pd.DataFrame(inventario_list)
    df_calculado = df_base.copy()
    
    # Asegurar que todas las columnas numéricas sean números (incluyendo las nuevas)
    for col in df_columns_numeric:
        df_calculado[col] = pd.to_numeric(df_calculado[col], errors='coerce').fillna(0)
    
    resultados_calculo = []
    
    for _, row in df_calculado.iterrows():
        rho = row['Densidad (ρ)']
        dap = row['DAP (cm)']
        altura = row['Altura (m)']
        cantidad = row['Cantidad']
        años = row['Años Plantados']
        consumo_agua_uni = row['Consumo Agua Unitario (L/año)'] 
        precio_planton_uni = row['Precio Plantón Unitario (S/)'] # USANDO NUEVO NOMBRE DE COLUMNA S/
        
        # 1. Cálculo de CO2e (Biomasa, Carbono, CO2e por árbol en kg)
        _, _, biomasa_uni_kg, co2e_uni_kg, _ = calcular_co2_arbol(rho, dap, altura)
        
        # 2. Conversión a TONELADAS y Lote
        biomasa_lote_ton = (biomasa_uni_kg * cantidad) / FACTOR_KG_A_TON
        carbono_lote_ton = (biomasa_uni_kg * FACTOR_CARBONO * cantidad) / FACTOR_KG_A_TON
        co2e_lote_ton = (co2e_uni_kg * cantidad) / FACTOR_KG_A_TON
        
        # 3. Cálculo de Métricas Ambientales/Financieras (ACTUALIZADO)
        
        # Consumo de agua acumulado (L)
        consumo_agua_lote = consumo_agua_uni * cantidad * años
        
        # Costo de Plantones
        costo_plantones_lote = precio_planton_uni * cantidad
        
        # Costo de Agua (Litros a m3, luego m3 a Soles)
        costo_agua_lote = (consumo_agua_lote / FACTOR_L_A_M3) * PRECIO_AGUA_POR_M3 
        
        # Costo Total del Lote (Plantones + Agua)
        costo_total_lote = costo_plantones_lote + costo_agua_lote
        
        resultados_calculo.append({
            'Biomasa Lote (Ton)': float(biomasa_lote_ton), 
            'Carbono Lote (Ton)': float(carbono_lote_ton), 
            'CO2e Lote (Ton)': float(co2e_lote_ton),
            'Consumo Agua Total Lote (L)': float(consumo_agua_lote), 
            'Costo Total Lote (S/)': float(costo_total_lote) # CAMBIO DE $ A S/
        })

    df_salidas = pd.DataFrame(resultados_calculo).astype(float)
    df_final = pd.concat([df_calculado.reset_index(drop=True), df_salidas.reset_index(drop=True)], axis=1)

    return df_final

def get_co2e_total_seguro(df_calculado):
    """Calcula la suma total de CO2e Lote (Ton) de forma segura a partir del DF calculado."""
    if df_calculado.empty or 'CO2e Lote (Ton)' not in df_calculado.columns:
        return 0.0
    co2e_col = pd.to_numeric(df_calculado['CO2e Lote (Ton)'], errors='coerce').fillna(0)
    return co2e_col.sum()

def get_costo_total_seguro(df_calculado):
    """Calcula la suma total del Costo Total Lote (S/) de forma segura."""
    if df_calculado.empty or 'Costo Total Lote (S/)' not in df_calculado.columns:
        return 0.0
    costo_col = pd.to_numeric(df_calculado['Costo Total Lote (S/)'], errors='coerce').fillna(0)
    return costo_col.sum()

def get_agua_total_seguro(df_calculado):
    """Calcula la suma total del Consumo Agua Total Lote (L) de forma segura."""
    if df_calculado.empty or 'Consumo Agua Total Lote (L)' not in df_calculado.columns:
        return 0.0
    agua_col = pd.to_numeric(df_calculado['Consumo Agua Total Lote (L)'], errors='coerce').fillna(0)
    return agua_col.sum()


# --- FUNCIONES DE MANEJO DE ESTADO ---

def agregar_lote():
    
    # 1. Obtener info dinámica de especies
    current_species_info = get_current_species_info() 
    
    # 2. Obtener valores de entrada
    especie = st.session_state.especie_sel
    cantidad = st.session_state.cantidad_input
    dap = st.session_state.dap_slider
    altura = st.session_state.altura_slider
    años = st.session_state.anos_plantados_input
    
    # 3. Obtener valores de densidad, agua y precio
    rho = 0.0
    consumo_agua_unitario = 0.0
    precio_planton_unitario = 0.0
    
    if especie == 'Densidad/Datos Manuales':
        rho = st.session_state.densidad_manual_input
        consumo_agua_unitario = st.session_state.consumo_agua_manual_input
        precio_planton_unitario = st.session_state.precio_planton_manual_input
    elif especie in current_species_info:
        info = current_species_info[especie]
        rho = info['Densidad']
        consumo_agua_unitario = info['Agua_L_Anio']
        precio_planton_unitario = info['Precio_Plantón'] # El precio_plantón es el valor en Soles
        
    # CRÍTICA: Validaciones
    if cantidad <= 0 or dap <= 0 or altura <= 0 or rho <= 0 or años < 0 or consumo_agua_unitario < 0 or precio_planton_unitario < 0:
        st.error("Por favor, asegúrate de que Cantidad, DAP, Altura y Densidad sean mayores a cero, y los valores de Años, Agua y Precio sean mayores o iguales a cero.")
        return

    # 4. Cálculo de CO2e (para obtener el detalle)
    _, _, _, co2e_uni_kg, detalle_calculo = calcular_co2_arbol(rho, dap, altura)
    
    # 5. Construir la nueva fila dict con las nuevas columnas
    nueva_fila_dict = {
        'Especie': especie, 
        'Cantidad': int(cantidad), 
        'DAP (cm)': float(dap), 
        'Altura (m)': float(altura), 
        'Densidad (ρ)': float(rho),
        'Años Plantados': int(años),
        'Consumo Agua Unitario (L/año)': float(consumo_agua_unitario),
        'Precio Plantón Unitario (S/)': float(precio_planton_unitario), # CAMBIO DE $ A S/
        'Detalle Cálculo': detalle_calculo
    }
    
    st.session_state.inventario_list.append(nueva_fila_dict)
    
    # Resetear inputs para la siguiente entrada 
    st.session_state.cantidad_input = 0
    st.session_state.dap_slider = 0.0
    st.session_state.altura_slider = 0.0
    st.session_state.anos_plantados_input = 0 
    
    # Mantener la especie seleccionada
    current_keys = list(current_species_info.keys())
    if 'especie_sel' in st.session_state and st.session_state.especie_sel in current_keys:
        st.session_state.especie_sel = st.session_state.especie_sel
    elif current_keys:
        st.session_state.especie_sel = current_keys[0]
    
    st.rerun() 
    
def deshacer_ultimo_lote():
    if st.session_state.inventario_list:
        st.session_state.inventario_list.pop() 
        st.rerun()

def limpiar_inventario():
    st.session_state.inventario_list = [] 
    st.rerun()

def reiniciar_app_completo():
    """Borra completamente todos los elementos del estado de sesión."""
    keys_to_delete = list(st.session_state.keys())
    for key in keys_to_delete:
        del st.session_state[key]
    st.rerun()

    
# --- FUNCIÓN DE DESCARGA DE EXCEL (Actualizada) ---
def generar_excel_memoria(df_inventario, proyecto, hectareas, total_arboles, total_co2e_ton, total_agua_l, total_costo):
    fecha = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    df_para_excel = df_inventario.copy()
    try:
        # Quitar columnas de detalle y carbono intermedio. Se usa el nuevo nombre de la columna.
        cols_drop = ['Detalle Cálculo', 'Carbono Lote (Ton)', 'Consumo Agua Unitario (L/año)', 'Precio Plantón Unitario (S/)']
        df_para_excel = df_para_excel.drop(columns=[col for col in cols_drop if col in df_para_excel.columns])
    except:
        pass 
        
    df_para_excel.to_excel(writer, sheet_name='Inventario Detallado', index=False)
    
    df_resumen = pd.DataFrame({
        'Métrica': ['Proyecto', 'Fecha', 'Hectáreas (ha)', 'Total Árboles', 'CO2e Total (Ton)', 'CO2e Total (kg)', 'Consumo Agua Total (L)', 'Costo Total (S/)'], # CAMBIO DE $ A S/
        'Valor': [
            proyecto if proyecto else "Sin Nombre",
            fecha,
            f"{hectareas:.1f}",
            f"{total_arboles:.0f}",
            f"{total_co2e_ton:.2f}", 
            f"{total_co2e_ton * FACTOR_KG_A_TON:.2f}",
            f"{total_agua_l:,.0f}", 
            f"S/{total_costo:,.2f}" # CAMBIO DE $ A S/
        ]
    })
    df_resumen.to_excel(writer, sheet_name='Resumen Proyecto', index=False)
    
    writer.close()
    processed_data = output.getvalue()
    return processed_data


# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN (CRÍTICA PARA LA PERSISTENCIA - Actualizada) ---
def inicializar_estado_de_sesion():
    if 'inventario_list' not in st.session_state:
        st.session_state.inventario_list = [] 
    
    # CRÍTICO: Inicialización robusta del DF de especies persistente
    if 'especies_bd' not in st.session_state: 
        # Columnas necesarias para la edición y persistencia (Añadido Precio Plantón en S/)
        df_cols = ['Especie', 'DAP (cm)', 'Altura (m)', 'Consumo Agua (L/año)', 'Densidad (g/cm³)', 'Precio Plantón (S/)'] # CAMBIO
        
        # Pre-poblar con las especies iniciales (Usando el nuevo DENSIDADES_BASE)
        initial_data = []
        for name, data in DENSIDADES_BASE.items():
            initial_data.append({
                'Especie': name, 
                'DAP (cm)': 0.0, 
                'Altura (m)': 0.0, 
                'Consumo Agua (L/año)': data['Agua_L_Anio'],
                'Densidad (g/cm³)': data['Densidad'],
                'Precio Plantón (S/)': data['Precio_Plantón'] # USANDO NUEVO NOMBRE DE COLUMNA S/
            })
        
        st.session_state.especies_bd = pd.DataFrame(initial_data, columns=df_cols)
        
    # Variables del proyecto
    if 'proyecto' not in st.session_state: st.session_state.proyecto = ""
    if 'hectareas' not in st.session_state: st.session_state.hectareas = 0.0
    
    # Variables de Inputs 
    if 'dap_slider' not in st.session_state: st.session_state.dap_slider = 0.0
    if 'altura_slider' not in st.session_state: st.session_state.altura_slider = 0.0
    if 'cantidad_input' not in st.session_state: st.session_state.cantidad_input = 0
    if 'anos_plantados_input' not in st.session_state: st.session_state.anos_plantados_input = 0 
    
    # Variables manuales (Actualizadas para incluir agua y precio)
    if 'densidad_manual_input' not in st.session_state: st.session_state.densidad_manual_input = 0.5 
    if 'consumo_agua_manual_input' not in st.session_state: st.session_state.consumo_agua_manual_input = 0.0 
    if 'precio_planton_manual_input' not in st.session_state: st.session_state.precio_planton_manual_input = 0.0 
    
    # Inicialización de especie seleccionada con la lista dinámica
    current_species_info = get_current_species_info()
    current_keys = list(current_species_info.keys())
    
    if 'especie_sel' not in st.session_state or st.session_state.especie_sel not in current_keys: 
        st.session_state.especie_sel = current_keys[0] if current_keys else ""
        
    # NUEVO: Estado para manejar la navegación por botones
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "1. Cálculo de Captura"


    # Defensa contra versiones antiguas:
    if 'inventario_df' in st.session_state:
        del st.session_state.inventario_df
        st.warning("⚠️ Se detectó y eliminó una variable de sesión antigua (inventario_df). Se forzará un reinicio.")
        st.rerun()
        
inicializar_estado_de_sesion()

# -------------------------------------------------
# --- SECCIONES DE LA APLICACIÓN (RENDER) ---
# -------------------------------------------------

# --- 1. CÁLCULO Y GRÁFICOS (Actualizada)
def render_calculadora_y_graficos():
    st.title("🌳 1. Cálculo de Captura de Carbono, Inversión y Recursos")
    
    # Obtener la lista dinámica de información de especies aquí
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
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Datos y Registro", "📈 Visor de Gráficos", "🔬 Detalle Técnico", "🚀 Potencial de Crecimiento"])

    with tab1:
        st.markdown("## 1.1 Registro y Acumulación de Inventario")
        col_input, col_totales = st.columns([1, 2])
        
        with col_input:
            st.subheader("Entrada de Lote por Especie")
            
            with st.form("lote_form", clear_on_submit=False):
                # Usar la lista dinámica de especies
                especie_keys = list(current_species_info.keys())
                # Asegurar que la especie seleccionada siga siendo válida si existe
                default_index = especie_keys.index(st.session_state.especie_sel) if st.session_state.especie_sel in especie_keys else 0
                especie_sel = st.selectbox("Especie / Tipo de Árbol", especie_keys, key='especie_sel', index=default_index)
                
                # Obtener la información de la especie seleccionada (con valores por defecto si no existe)
                default_info = current_species_info.get(especie_sel, {'Densidad': 0.0, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 0.0})
                
                if especie_sel == 'Densidad/Datos Manuales':
                    # Inputs manuales para Densidad, Agua y Precio
                    st.number_input("Densidad de madera (ρ, g/cm³)", min_value=0.1, max_value=1.5, value=st.session_state.densidad_manual_input, step=0.01, key='densidad_manual_input')
                    st.number_input("Consumo Agua Anual por Árbol (L/año)", min_value=0.0, value=st.session_state.consumo_agua_manual_input, step=1.0, key='consumo_agua_manual_input', help="Consumo promedio anual de agua por árbol.") 
                    st.number_input("Precio por Plantón (S/)", min_value=0.0, value=st.session_state.precio_planton_manual_input, step=0.01, format="%.2f", key='precio_planton_manual_input', help="Costo unitario de compra o producción del plantón.") # CAMBIO DE $ A S/
                else:
                    # Mostrar info de la BD
                    st.markdown("##### Información de la Base de Datos Histórica")
                    col_info1, col_info2, col_info3 = st.columns(3)
                    col_info1.info(f"Densidad (ρ): **{default_info['Densidad']} g/cm³**")
                    col_info2.info(f"Consumo Agua (L/año): **{default_info['Agua_L_Anio']} L**") 
                    col_info3.info(f"Precio Plantón: **S/ {default_info['Precio_Plantón']:.2f}**") # CAMBIO DE $ A S/
                    st.caption("ℹ️ Estos valores pueden ser modificados en la sección **'5. Gestión de Especie'**.")
                
                st.markdown("---")
                
                # Inputs del lote (Cantidades y Tiempos)
                col_cant, col_anos = st.columns(2)
                with col_cant:
                    st.number_input("Cantidad de Árboles (n)", min_value=0, step=1, key='cantidad_input', value=st.session_state.cantidad_input)
                with col_anos:
                    st.number_input("Años desde la plantación", min_value=0, step=1, key='anos_plantados_input', value=st.session_state.anos_plantados_input, help="Permite calcular el consumo de agua acumulado.") 
                
                st.slider("DAP promedio (cm)", min_value=0.0, max_value=100.0, step=1.0, key='dap_slider', help="Diámetro a la Altura del Pecho. 🌳", value=min(st.session_state.dap_slider, 100.0))
                st.slider("Altura promedio (m)", min_value=0.0, max_value=50.0, step=1.0, key='altura_slider', help="Altura total del árbol. 🌲", value=float(int(st.session_state.altura_slider)))
                
                st.form_submit_button("➕ Añadir Lote al Inventario", on_click=agregar_lote)

        with col_totales:
            st.subheader("Inventario Acumulado")
            
            total_arboles_registrados = sum(item['Cantidad'] for item in st.session_state.inventario_list)
            
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
                
                with col_excel:
                    st.download_button(
                        label="Descargar Reporte Excel 💾",
                        data=excel_data,
                        file_name=f"Reporte_NBS_{st.session_state.proyecto if st.session_state.proyecto else 'Inventario'}_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="Descarga el inventario y el resumen del proyecto actual."
                    )
                    
                st.markdown("---")
                st.caption("Detalle de los Lotes Añadidos (Unidades en Toneladas, Litros y Soles):")
                # Mostrar el DataFrame sin las columnas de detalle y carbono
                columnas_a_mostrar = [
                    'Especie', 'Cantidad', 'Años Plantados', 'DAP (cm)', 'Altura (m)', 'Densidad (ρ)',
                    'CO2e Lote (Ton)', 'Consumo Agua Total Lote (L)', 'Costo Total Lote (S/)' # CAMBIO DE $ A S/
                ]
                if isinstance(df_inventario_completo, pd.DataFrame):
                     st.dataframe(df_inventario_completo[columnas_a_mostrar], use_container_width=True, hide_index=True)
                else:
                    st.dataframe(df_inventario_completo, use_container_width=True, hide_index=True)
                
            else:
                st.info("Añade el primer lote de árboles para iniciar el inventario.")
                
    with tab2: # Visor de Gráficos (Actualizada)
        st.markdown("## 1.2 Resultados Clave y Visualización")
        if df_inventario_completo.empty:
            st.warning("⚠️ No hay datos registrados.")
        else:
            df_inventario = df_inventario_completo.copy()
            
            total_arboles_registrados = df_inventario['Cantidad'].sum()
            biomasa_total_ton = df_inventario['Biomasa Lote (Ton)'].sum()

            st.subheader("✅ Indicadores Clave del Proyecto")
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("CO2e Capturado", f"**{co2e_proyecto_ton:,.2f} Ton**", delta="Total del Proyecto", delta_color="normal")
            kpi2.metric("Consumo Agua Total Acumulado", f"**{agua_proyecto_total:,.0f} Litros**", help="Litros totales consumidos por el proyecto (Agua/año * Cantidad * Años)") 
            kpi3.metric("Inversión Total del Proyecto", f"**S/ {costo_proyecto_total:,.2f}**", help="Incluye el costo de plantones y el costo acumulado de agua (3 S/ por m³).") # CAMBIO DE $ A S/
            
            # Indicadores adicionales para contexto
            kpi4, kpi5, _ = st.columns(3)
            kpi4.metric("Número de Árboles", f"{total_arboles_registrados:.0f}")
            kpi5.metric("Biomasa Total", f"{biomasa_total_ton:,.2f} Ton")

            
            df_graficos = df_inventario.groupby('Especie').agg(
                Total_CO2e_Ton=('CO2e Lote (Ton)', 'sum'),
                Conteo_Arboles=('Cantidad', 'sum'),
                Consumo_Agua_Total_L=('Consumo Agua Total Lote (L)', 'sum'), 
                Costo_Total_Lote=('Costo Total Lote (S/)', 'sum') # USANDO NUEVO NOMBRE DE COLUMNA S/
            ).reset_index()

            st.markdown("---")
            st.subheader("Análisis de Inversión y Recursos (Litros y Soles)")
            col_costo, col_agua = st.columns(2)

            with col_costo:
                fig_costo = px.bar(df_graficos, x='Especie', y='Costo_Total_Lote', title='Inversión Total por Especie (S/)', color='Costo_Total_Lote', color_continuous_scale=px.colors.sequential.Sunset) # CAMBIO DE $ A S/
                col_costo.plotly_chart(fig_costo, use_container_width=True)

            with col_agua:
                fig_agua = px.bar(df_graficos, x='Especie', y='Consumo_Agua_Total_L', title='Consumo Agua Acumulado por Especie (Litros)', color='Consumo_Agua_Total_L', color_continuous_scale=px.colors.sequential.Agsunset)
                col_agua.plotly_chart(fig_agua, use_container_width=True)
                
            st.markdown("---")
            st.subheader("Análisis de Captura de Carbono")
            col_graf1, col_graf2 = st.columns(2)
            
            fig_co2e = px.bar(df_graficos, x='Especie', y='Total_CO2e_Ton', title='CO2e Capturado por Especie (Ton)', color='Total_CO2e_Ton', color_continuous_scale=px.colors.sequential.Viridis)
            fig_arboles = px.pie(df_graficos, values='Conteo_Arboles', names='Especie', title='Conteo de Árboles por Especie', hole=0.3, color_discrete_sequence=px.colors.sequential.Plasma) 
            
            with col_graf1: st.plotly_chart(fig_co2e, use_container_width=True)
            with col_graf2: st.plotly_chart(fig_arboles, use_container_width=True)


    with tab3: # Detalle Técnico 
        st.markdown("## 1.3 Detalle Técnico del Lote (Cálculo en kg)")
        if not st.session_state.inventario_list: st.info("Aún no hay lotes de árboles registrados.")
        else:
            # Usar el inventario_list directamente para acceder al detalle de cálculo
            lotes_info = [
                f"Lote {i+1}: {row['Especie']} ({row['Cantidad']} árboles) - DAP: {row['DAP (cm)']:.1f} cm" 
                for i, row in enumerate(st.session_state.inventario_list)
            ]
            lote_seleccionado_index = st.selectbox("Seleccione el Lote para Inspeccionar el Cálculo:", options=range(len(lotes_info)), format_func=lambda x: lotes_info[x], key='detalle_lote_select')
            st.markdown("---")
            detalle_lote = st.session_state.inventario_list[lote_seleccionado_index]['Detalle Cálculo']
            st.markdown(f"### Detalles del Lote {lote_seleccionado_index + 1}: {lotes_info[lote_seleccionado_index]}")
            st.code(detalle_lote, language='markdown')

    with tab4: # Potencial de Crecimiento
        st.markdown("## 1.4 Simulación de Potencial de Captura a Largo Plazo")
        if df_inventario_completo.empty: st.info("Por favor, registre al menos un lote de árboles para iniciar la simulación.")
        else:
            df_inventario = df_inventario_completo 
            
            # CORRECCIÓN: Usar enumerate para iterar sobre la lista de diccionarios
            lotes_info = [
                f"Lote {i+1}: {row['Especie']} ({row['Cantidad']} árboles) - DAP Inicial: {row['DAP (cm)']:.1f} cm" 
                for i, row in enumerate(st.session_state.inventario_list) 
            ]
            lote_sim_index = st.selectbox("Seleccione el Lote para la Proyección de Crecimiento:", options=range(len(lotes_info)), format_func=lambda x: lotes_info[x], key='sim_lote_select')
            
            # Usar iloc para seleccionar la fila correcta del DF calculado
            lote_seleccionado = df_inventario.iloc[[lote_sim_index]]
            especie_sim = lote_seleccionado['Especie'].iloc[0]

            col_anios, col_factores = st.columns([1, 2])
            with col_anios: anios_simulacion = st.slider("Años de Proyección", min_value=1, max_value=50, value=20, step=1)
                
            with col_factores:
                # Usar factor_inicial basado en las especies por defecto, si no existe, usar 'Factor Manual'
                factor_inicial = FACTORES_CRECIMIENTO.get(especie_sim, FACTORES_CRECIMIENTO.get('Factor Manual', {'DAP': 0.05, 'Altura': 0.05, 'Agua': 0.0}))
                
                st.markdown(f"### Factores de Crecimiento Anual (Especie: **{especie_sim}**)")
                st.caption("Estos factores se basan en valores por defecto. Para usar data real, refine la información en la sección **'5. Gestión de Especie'**.")
                
                factor_dap_input = st.number_input("Tasa de Crecimiento Anual DAP (%)", min_value=0.01, max_value=0.30, value=factor_inicial['DAP'], step=0.01, format="%.2f", key='factor_dap_sim')
                factor_altura_input = st.number_input("Tasa de Crecimiento Anual Altura (%)", min_value=0.01, max_value=0.30, value=factor_inicial['Altura'], step=0.01, format="%.2f", key='factor_alt_sim')
                max_dap_input = st.number_input("DAP Máximo de Madurez (cm)", min_value=10.0, max_value=300.0, value=100.0, step=10.0)
                max_altura_input = st.number_input("Altura Máxima de Madurez (m)", min_value=5.0, max_value=100.0, value=30.0, step=5.0)

            # NOTE: La función simular_crecimiento debe ser definida o ignorada, ya que no estaba en el código anterior. Asumo que está definida fuera o que la usé en el bloque anterior y no la incluí en el paste. Para que el código compile, añado una simulación simple.
            
            # --- SIMULACIÓN DE CRECIMIENTO (AÑADIDA PARA COMPLETITUD) ---
            def simular_crecimiento(lote_df, anios, factor_dap, factor_altura, max_dap, max_alt):
                if lote_df.empty: return pd.DataFrame()
                
                # Obtener valores iniciales
                cant = lote_df['Cantidad'].iloc[0]
                rho = lote_df['Densidad (ρ)'].iloc[0]
                dap_i = lote_df['DAP (cm)'].iloc[0]
                alt_i = lote_df['Altura (m)'].iloc[0]
                
                # Datos para la proyección
                data = []
                for anio in range(1, anios + 1):
                    # Aplicar factor de crecimiento, limitado por el máximo de madurez
                    dap_n = min(dap_i * (1 + factor_dap)**anio, max_dap)
                    alt_n = min(alt_i * (1 + factor_altura)**anio, max_alt)
                    
                    # Recalcular CO2e (por lote) en Ton
                    _, _, _, co2e_uni_kg, _ = calcular_co2_arbol(rho, dap_n, alt_n)
                    co2e_lote_ton = (co2e_uni_kg * cant) / FACTOR_KG_A_TON
                    
                    data.append({'Año': anio, 'DAP (cm)': dap_n, 'Altura (m)': alt_n, 'CO2e Acumulado (Ton)': co2e_lote_ton})
                
                return pd.DataFrame(data)
            # --- FIN SIMULACIÓN ---
            
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


# --- 2. GESTIÓN DE MEMORIAS (RETIRADA) ---
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
    
    df_inventario_completo = recalcular_inventario_completo(st.session_state.inventario_list)
    co2e_proyecto_ton = get_co2e_total_seguro(df_inventario_completo)
    
    # Convertimos la captura del proyecto de Toneladas a Miles de Toneladas para la comparación
    # CORRECCIÓN: el factor de conversión es 1000
    co2e_proyecto_miles_ton = co2e_proyecto_ton / 1000.0 
    
    if co2e_proyecto_miles_ton <= 0:
        st.warning("⚠️ El inventario del proyecto debe tener CO2e registrado (sección 1) para realizar este análisis.")
        return

    st.subheader("Selección de Sede y Análisis")
    
    sede_sel = st.selectbox("Seleccione la Sede (Huella Corporativa)", list(HUELLA_CORPORATIVA.keys()))
    
    # El valor ya está en Miles de tCO2e
    emisiones_sede_miles_ton = HUELLA_CORPORATIVA[sede_sel] 
    
    st.markdown("---")
    
    col_sede, col_proyecto = st.columns(2)
    
    with col_sede:
        st.metric(f"Emisiones Anuales de '{sede_sel}' (**Miles de Ton CO2e**)", f"**{emisiones_sede_miles_ton:,.2f} Miles Ton**", help="Valor extraído del Informe de Huella de Carbono Corporativa 2024, en Miles de Toneladas.")
    
    with col_proyecto:
        st.metric("Captura Total del Proyecto (**Miles de Ton CO2e**)", f"**{co2e_proyecto_miles_ton:,.2f} Miles Ton**", delta="Total del Inventario Actual (convertido)")
        
    if emisiones_sede_miles_ton > 0:
        porcentaje_mitigacion = (co2e_proyecto_miles_ton / emisiones_sede_miles_ton) * 100
        
        st.subheader("Resultado del GAP de Mitigación")
        
        st.progress(min(100, int(porcentaje_mitigacion)))
        
        if porcentaje_mitigacion >= 100:
            st.success(f"¡Mitigación Completa! El proyecto compensa el **{porcentaje_mitigacion:,.2f}%** de las emisiones de '{sede_sel}'.")
        else:
            st.info(f"El proyecto compensa el **{porcentaje_mitigacion:,.2f}%** de las emisiones anuales de '{sede_sel}'.")

        co2e_restante = max(0, emisiones_sede_miles_ton - co2e_proyecto_miles_ton)
        st.metric("CO2e Restante por Mitigar (Miles de Ton)", f"**{co2e_restante:,.2f} Miles Ton**")

# --- 5. GESTIÓN DE ESPECIE (Actualizada) ---
def render_gestion_especie():
    st.title("🌿 5. Gestión de Datos de Crecimiento de Especies")
    st.markdown("Edite, **agregue o elimine** entradas en la Base de Datos Histórica. Los cambios en la **Densidad (g/cm³)**, el **Consumo de Agua (L/año)** y el **Precio Plantón (S/)** se aplicarán automáticamente a la calculadora.") # CAMBIO DE $ A S/
    st.info("⚠️ **IMPORTANTE:** Al guardar, la última entrada de cada especie será la utilizada en la sección de Cálculo.")

    st.subheader("Base de Datos Histórica de Especies (Editable)")

    # El DF ya viene pre-poblado con las especies base si es la primera vez
    df_base = st.session_state.especies_bd.copy().fillna(0) 

    # 2. El Widget de Edición de Datos
    df_edit = st.data_editor(
        df_base, 
        num_rows="dynamic", # Permite agregar y eliminar filas
        use_container_width=True,
        column_config={
            "Especie": st.column_config.TextColumn("Especie", help="Nombre de la nueva especie o una existente", required=True),
            "Densidad (g/cm³)": st.column_config.NumberColumn("Densidad (g/cm³)", format="%.2f", help="Densidad real de la madera (ρ).", min_value=0.1, max_value=1.5, required=True),
            "Consumo Agua (L/año)": st.column_config.NumberColumn("Consumo Agua (L/año)", format="%.0f", help="Consumo de agua promedio por árbol anualmente.", min_value=0.0), 
            "Precio Plantón (S/)": st.column_config.NumberColumn("Precio Plantón (S/)", format="%.2f", help="Costo unitario de compra o producción del plantón.", min_value=0.0), # CAMBIO DE $ A S/
            "DAP (cm)": st.column_config.NumberColumn("DAP (cm)", format="%.2f", help="Diámetro a la altura del pecho", min_value=0.0),
            "Altura (m)": st.column_config.NumberColumn("Altura (m)", format="%.2f", help="Altura total del árbol", min_value=0.0),
        }
    )
    
    # 3. Guardar los cambios
    if st.button("💾 Guardar Cambios en la BD Histórica"):
        
        # Validar y filtrar filas: Debe tener nombre de especie y Densidad > 0
        df_edit_clean = df_edit.replace('', pd.NA).dropna(subset=['Especie'])
        
        # CRÍTICO: Asegurar que Densidad sea > 0 y la Especie no esté vacía.
        df_validas = df_edit_clean[
            (df_edit_clean['Especie'].astype(str).str.strip() != "") & 
            (pd.to_numeric(df_edit_clean['Densidad (g/cm³)'], errors='coerce').fillna(0) > 0)
        ].copy()
        
        if df_validas.empty and not df_edit.empty:
            st.warning("No se guardaron cambios. Asegúrate de ingresar un nombre de Especie y una Densidad de madera (g/cm³) mayor a cero en cada fila.")
            return
        
        # Aseguramos que los tipos de datos sean correctos antes de guardar
        df_validas['Especie'] = df_validas['Especie'].astype(str)
        # Asegurar las nuevas columnas
        cols_numeric_to_save = ['DAP (cm)', 'Altura (m)', 'Consumo Agua (L/año)', 'Densidad (g/cm³)', 'Precio Plantón (S/)'] # USANDO NUEVO NOMBRE DE COLUMNA S/
        for col in cols_numeric_to_save:
            df_validas[col] = pd.to_numeric(df_validas[col], errors='coerce').fillna(0)


        # CRÍTICO: Sobreescribir la variable de sesión con el DataFrame editado y limpio
        st.session_state.especies_bd = df_validas.sort_values(by=['Especie']).reset_index(drop=True)
        st.success(f"Base de Datos Histórica actualizada. Se registraron **{len(st.session_state.especies_bd)}** entradas válidas.")
        
        st.rerun()

    st.markdown("---")
    st.caption("Estructura de la Base de Datos Histórica Completa (Persistente):")
    st.dataframe(st.session_state.especies_bd, use_container_width=True, hide_index=True)

# -------------------------------------------------
# --- FUNCIÓN PRINCIPAL DE LA APLICACIÓN (MENU DE BOTONES) ---
# -------------------------------------------------
def main_app():
    
    # 1. Asegurar el estado de la página actual 
    
    df_inventario_completo = recalcular_inventario_completo(st.session_state.inventario_list)
    co2e_total_sidebar = get_co2e_total_seguro(df_inventario_completo)
    
    st.sidebar.title("Menú de Navegación")
    
    # Botón de Reinicio 
    st.sidebar.button("🚨 Reiniciar App (Limpieza Total)", on_click=reiniciar_app_completo, help="¡Usar solo si hay errores persistentes! Borra todo el estado de la sesión.", type="primary")

    st.sidebar.markdown("---")
    
    # Opciones de menú
    menu_options = [
        "1. Cálculo de Captura", 
        "3. Mapa", 
        "4. GAP CPSSA", 
        "5. Gestión de Especie"
    ]
    
    # 2. Reemplazar st.selectbox con Botones de Navegación
    for option in menu_options:
        # Se verifica si la opción actual es la seleccionada para darle un estilo visual diferente
        is_selected = (st.session_state.current_page == option)
        
        if st.sidebar.button(
            option, 
            key=f"nav_{option}", 
            use_container_width=True,
            # Usar 'primary' si está seleccionado, 'secondary' si no lo está.
            type=("primary" if is_selected else "secondary") 
        ):
            # 3. Al hacer clic, cambiar el estado y forzar la re-ejecución
            st.session_state.current_page = option 
            st.rerun() 

    # Métricas en el sidebar
    st.sidebar.markdown("---")
    st.sidebar.caption("Proyecto: " + (st.session_state.proyecto if st.session_state.proyecto else "Sin nombre"))
    st.sidebar.metric("CO2e Inventario Total", f"{co2e_total_sidebar:,.2f} Ton") 
    
    # 4. Renderizar la página basada en el estado de sesión
    selection = st.session_state.current_page 
    
    if selection == "1. Cálculo de Captura":
        render_calculadora_y_graficos()
    elif selection == "3. Mapa":
        render_mapa()
    elif selection == "4. GAP CPSSA":
        render_gap_cpassa()
    elif selection == "5. Gestión de Especie":
        render_gestion_especie()
    
    # Información de contacto (Solicitud anterior)
    st.caption("---")
    st.caption(
        "**Solicitar cambios al Area de Cambio Climático.**"
    )
    st.caption(
        "**Para soporte y dudas adicionales escribir al:** `ftrujillo@cpsaa.com.pe`"
    )

# --- LÍNEA VITAL DE EJECUCIÓN ---
if __name__ == '__main__':
    main_app()