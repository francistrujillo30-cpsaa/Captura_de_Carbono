import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go 
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

# NUEVAS CONSTANTES PARA COSTOS 
PRECIO_AGUA_POR_M3 = 3.0 # Precio fijo del m3 de agua en Perú (3 Soles)
FACTOR_L_A_M3 = 1000 # 1 m3 = 1000 Litros

# BASE DE DATOS INICIAL DE DENSIDADES, AGUA Y COSTO
DENSIDADES_BASE = {
    'Eucalipto Torrellana (Corymbia torelliana)': {'Densidad': 0.46, 'Agua_L_Anio': 1500, 'Precio_Plantón': 5.00}, 
    'Majoe (Hibiscus tiliaceus)': {'Densidad': 0.57, 'Agua_L_Anio': 1200, 'Precio_Plantón': 5.00}, 
    'Molle (Schinus molle)': {'Densidad': 0.44, 'Agua_L_Anio': 900, 'Precio_Plantón': 6.00},
    'Algarrobo (Prosopis pallida)': {'Densidad': 0.53, 'Agua_L_Anio': 800, 'Precio_Plantón': 4.00},
}


# FACTORES DE CRECIMIENTO INICIAL 
FACTORES_CRECIMIENTO = {
    'Eucalipto Torrellana (Corymbia torelliana)': {'DAP': 0.05, 'Altura': 0.05, 'Agua': 0.0},
    'Majoe (Hibiscus tiliaceus)': {'DAP': 0.08, 'Altura': 0.06, 'Agua': 0.0},
    'Molle (Schinus molle)': {'DAP': 0.06, 'Altura': 0.07, 'Agua': 0.0},
    'Algarrobo (Prosopis pallida)': {'DAP': 0.04, 'Altura': 0.04, 'Agua': 0.0},
    'Factor Manual': {'DAP': 0.05, 'Altura': 0.05, 'Agua': 0.0}
}


# HUELLA DE CARBONO CORPORATIVA POR SEDE (EN MILES DE tCO2e)
HUELLA_CORPORATIVA = {
    "Planta Pacasmayo": 1265.15,      
    "Planta Piura": 595.76,          
    "Oficina Lima": 0.613,           
    "Cantera Tembladera": 0.361,     
    "Planta Rioja": 264.63,          
    "DINO Cajamarca": 2.193,         
    "DINO Chiclayo": 3.293,          
    "DINO Chimbote": 1.708,          
    "DINO Moche": 3.336,             
    "DINO Piura": 1.004,             
}


# --- DEFINICIÓN DE TIPOS DE COLUMNAS (Incluye Lat/Lon solo para el DF interno, no para la exportación/visualización) ---
df_columns_types = {
    'Especie': str, 'Cantidad': int, 'DAP (cm)': float, 'Altura (m)': float, 
    'Densidad (ρ)': float, 'Años Plantados': int, 'Consumo Agua Unitario (L/año)': float, 
    'Precio Plantón Unitario (S/)': float, 
    'Detalle Cálculo': str,
    'Latitud': float, 
    'Longitud': float 
}
df_columns_numeric = ['Cantidad', 'DAP (cm)', 'Altura (m)', 'Densidad (ρ)', 'Años Plantados', 'Consumo Agua Unitario (L/año)', 'Precio Plantón Unitario (S/)', 'Latitud', 'Longitud'] 

columnas_salida = ['Biomasa Lote (Ton)', 'Carbono Lote (Ton)', 'CO2e Lote (Ton)', 'Consumo Agua Total Lote (L)', 'Costo Total Lote (S/)'] 

# --- FUNCIÓN CRÍTICA: DINÁMICA DE ESPECIES ---
def get_current_species_info():
    """
    Genera un diccionario de información de especies (Densidad, Agua, Precio) 
    fusionando las especies base con las especies añadidas/modificadas por el usuario.
    """
    current_info = {
        name: {'Densidad': data['Densidad'], 'Agua_L_Anio': data['Agua_L_Anio'], 'Precio_Plantón': data['Precio_Plantón']}
        for name, data in DENSIDADES_BASE.items()
    }
    
    df_bd = st.session_state.get('especies_bd', pd.DataFrame())
    if df_bd.empty:
        current_info['Densidad/Datos Manuales'] = {'Densidad': 0.0, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 0.0}
        return current_info
        
    df_unique_info = df_bd.drop_duplicates(subset=['Especie'], keep='last')
    
    for _, row in df_unique_info.iterrows():
        especie_name = row['Especie']
        
        # Asegurar la conversión segura de los nuevos campos
        densidad_val = pd.to_numeric(row.get('Densidad (g/cm³)', 0.0), errors='coerce') 
        agua_val = pd.to_numeric(row.get('Consumo Agua (L/año)', 0.0), errors='coerce')
        # El precio del plantón se mantiene en la BD de especies, pero el usuario lo sobrescribe en el form de lote.
        precio_val = pd.to_numeric(row.get('Precio Plantón (S/)', 0.0), errors='coerce') 
        
        if pd.notna(densidad_val) and densidad_val > 0:
            current_info[especie_name] = {
                'Densidad': densidad_val,
                'Agua_L_Anio': agua_val if pd.notna(agua_val) and agua_val >= 0 else 0.0,
                'Precio_Plantón': precio_val if pd.notna(precio_val) and precio_val >= 0 else 0.0
            }
    
    current_info['Densidad/Datos Manuales'] = {'Densidad': 0.0, 'Agua_L_Anio': 0.0, 'Precio_Plantón': 0.0}
    
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
    """Calcula la suma total de consumo de agua."""
    if df.empty or 'Consumo Agua Total Lote (L)' not in df.columns:
        return 0.0
    return df['Consumo Agua Total Lote (L)'].sum()


def calcular_co2_arbol(rho, dap_cm, altura_m):
    """Calcula la biomasa, carbono y CO2e por árbol en KILOGRAMOS y genera el detalle con fórmulas."""
    detalle = ""
    
    # 1. Validación de entradas
    if rho <= 0 or dap_cm <= 0 or altura_m <= 0:
        detalle = "ERROR: Valores de entrada (DAP, Altura o Densidad) deben ser mayores a cero para el cálculo."
        return 0.0, 0.0, 0.0, 0.0, detalle
        
    # Calcular AGB (Above-Ground Biomass) en kg
    # Fórmula: AGB = 0.112 × (ρ × D² × H)^0.916 (Chave et al. 2014)
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
    
    # Generación del detalle técnico para la pestaña 3
    detalle += f"### Valores de Entrada\n"
    detalle += f"* **Densidad (ρ):** `{rho:.3f} g/cm³`\n"
    detalle += f"* **DAP (D):** `{dap_cm:.2f} cm`\n"
    detalle += f"* **Altura (H):** `{altura_m:.2f} m`\n\n"
    
    detalle += f"## 1. Biomasa Aérea (AGB) por Árbol\n"
    detalle += f"**Fórmula (kg):** $AGB = {AGB_FACTOR_A} \\times (\\rho \\times D^2 \\times H)^{AGB_FACTOR_B}$ (Chave et al. 2014)\n"
    detalle += f"**Sustitución:** $AGB = {AGB_FACTOR_A:.3f} \\times ({rho:.3f} \\times {dap_cm:.2f}^2 \\times {altura_m:.2f})^{AGB_FACTOR_B:.3f}$\n"
    detalle += f"**Resultado AGB (kg):** `{agb_kg:.4f}`\n\n"
    
    detalle += f"## 2. Biomasa Subterránea (BGB)\n"
    detalle += f"**Fórmula (kg):** $BGB = AGB \\times {FACTOR_BGB_SECO}$\n"
    detalle += f"**Sustitución:** $BGB = {agb_kg:.4f} \\times {FACTOR_BGB_SECO}$\n"
    detalle += f"**Resultado BGB (kg):** `{bgb_kg:.4f}`\n\n"
    
    detalle += f"## 3. Biomasa Total (AGB + BGB)\n"
    detalle += f"**Fórmula (kg):** $Biomasa Total = AGB + BGB$\n"
    detalle += f"**Sustitución:** $Biomasa Total = {agb_kg:.4f} + {bgb_kg:.4f}$\n"
    detalle += f"**Resultado Biomasa Total (kg):** `{biomasa_total:.4f}`\n\n"
    
    detalle += f"## 4. Carbono Capturado (C)\n"
    detalle += f"**Fórmula (kg):** $C = Biomasa Total \\times {FACTOR_CARBONO}$\n"
    detalle += f"**Sustitución:** $C = {biomasa_total:.4f} \\times {FACTOR_CARBONO}$\n"
    detalle += f"**Resultado Carbono (kg):** `{carbono_total:.4f}`\n\n"
    
    detalle += f"## 5. CO2 Equivalente Capturado (CO2e)\n"
    detalle += f"**Fórmula (kg):** $CO2e = C \\times {FACTOR_CO2E}$\n"
    detalle += f"**Sustitución:** $CO2e = {carbono_total:.4f} \\times {FACTOR_CO2E}$\n"
    detalle += f"**Resultado CO2e (kg):** `{co2e_total:.4f}`"
    
    return agb_kg, bgb_kg, biomasa_total, co2e_total, detalle


# --- FUNCIÓN DE RECÁLCULO SEGURO (CRÍTICA) ---
def recalcular_inventario_completo(inventario_list):
    """
    Toma la lista de entradas (List[Dict]) y genera un DataFrame completo y limpio, 
    incluyendo CO2e, Consumo de Agua y Costo Total (Plantones + Agua).
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
    
    # 2. FIX CRÍTICO: Asegurar que todas las columnas de entrada requeridas existan
    required_input_cols = list(df_columns_types.keys())
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
    
    for _, row in df_calculado.iterrows():
        rho = row['Densidad (ρ)']
        dap = row['DAP (cm)']
        altura = row['Altura (m)']
        cantidad = row['Cantidad']
        consumo_agua_uni = row['Consumo Agua Unitario (L/año)'] 
        precio_planton_uni = row['Precio Plantón Unitario (S/)'] 
        
        # 1. Cálculo de CO2e (Biomasa, Carbono, CO2e por árbol en kg)
        _, _, biomasa_uni_kg, co2e_uni_kg, detalle = calcular_co2_arbol(rho, dap, altura)
        
        # 2. Conversión a TONELADAS y Lote
        biomasa_lote_ton = (biomasa_uni_kg * cantidad) / FACTOR_KG_A_TON
        carbono_lote_ton = (biomasa_uni_kg * FACTOR_CARBONO * cantidad) / FACTOR_KG_A_TON
        co2e_lote_ton = (co2e_uni_kg * cantidad) / FACTOR_KG_A_TON

        # 3. Costo y Agua
        costo_planton_lote = cantidad * precio_planton_uni
        consumo_agua_lote_l = cantidad * consumo_agua_uni
        costo_total_lote = costo_planton_lote # Costo total del lote solo incluye plantones por ahora
        
        resultados_calculo.append({
            'Biomasa Lote (Ton)': biomasa_lote_ton,
            'Carbono Lote (Ton)': carbono_lote_ton,
            'CO2e Lote (Ton)': co2e_lote_ton,
            'Consumo Agua Total Lote (L)': consumo_agua_lote_l,
            'Costo Total Lote (S/)': costo_total_lote, 
            'Detalle Cálculo': detalle
        })

    # 4. Unir los resultados
    df_resultados = pd.DataFrame(resultados_calculo)
    df_final = pd.concat([df_calculado.reset_index(drop=True), df_resultados], axis=1)
    
    # 5. Aplicar tipos de datos para las columnas de salida
    dtype_map = {col: float for col in columnas_salida if col in df_final.columns}
    df_final = df_final.astype(dtype_map)

    return df_final


# --- MANEJO DE ESTADO DE SESIÓN Y UTILIDADES ---

def inicializar_estado_de_sesion():
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "1. Cálculo de Captura"
    if 'inventario_list' not in st.session_state:
        st.session_state.inventario_list = []
    if 'especies_bd' not in st.session_state:
        df_cols = ['Especie', 'DAP (cm)', 'Altura (m)', 'Consumo Agua (L/año)', 'Densidad (g/cm³)', 'Precio Plantón (S/)'] 
        data_rows = [
            (name, 5.0, 5.0, data['Agua_L_Anio'], data['Densidad'], data['Precio_Plantón']) # DAP y Altura iniciales como float
            for name, data in DENSIDADES_BASE.items()
        ]
        df_bd_inicial = pd.DataFrame(data_rows, columns=df_cols)
        st.session_state.especies_bd = df_bd_inicial
    if 'lotes_mapa' not in st.session_state:
        st.session_state.lotes_mapa = []
    if 'proyecto' not in st.session_state:
        st.session_state.proyecto = "Proyecto Reforestación CPSSA"
    if 'hectareas' not in st.session_state:
        st.session_state.hectareas = 0.0
        
    # Inicialización de inputs del formulario (Asegurar que DAP y Altura sean enteros aquí)
    if 'especie_seleccionada' not in st.session_state: st.session_state.especie_seleccionada = list(DENSIDADES_BASE.keys())[0]
    if 'cantidad_input' not in st.session_state: st.session_state.cantidad_input = 100
    if 'dap_slider' not in st.session_state: st.session_state.dap_slider = 5
    if 'altura_slider' not in st.session_state: st.session_state.altura_slider = 5
    if 'anios_plantados_input' not in st.session_state: st.session_state.anios_plantados_input = 5
    if 'densidad_manual_input' not in st.session_state: st.session_state.densidad_manual_input = 0.5
    if 'consumo_agua_manual_input' not in st.session_state: st.session_state.consumo_agua_manual_input = 1000.0
    if 'precio_planton_input' not in st.session_state: st.session_state.precio_planton_input = 5.0 
    if 'latitud_input' not in st.session_state: st.session_state.latitud_input = -8.0
    if 'longitud_input' not in st.session_state: st.session_state.longitud_input = -77.0


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
    # Usamos los valores de los sliders, que ahora son enteros, pero los forzamos a float para el cálculo
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
        'DAP (cm)': float(dap), # Lo almacenamos como float para mantener la coherencia con el modelo de datos
        'Altura (m)': float(altura), # Lo almacenamos como float para mantener la coherencia con el modelo de datos
        'Densidad (ρ)': float(rho),
        'Años Plantados': int(años),
        'Consumo Agua Unitario (L/año)': float(consumo_agua_unitario),
        'Precio Plantón Unitario (S/)': float(precio_planton_unitario), 
        'Detalle Cálculo': detalle_calculo,
        'Latitud': st.session_state.latitud_input,
        'Longitud': st.session_state.longitud_input,
    }
    
    st.session_state.inventario_list.append(nuevo_lote)
    
    tooltip_mapa = f"{especie} ({int(cantidad)} árboles, {dap}cm DAP)"
    st.session_state.lotes_mapa.append({'lat': st.session_state.latitud_input, 'lon': st.session_state.longitud_input, 'tooltip': tooltip_mapa})
    
    st.success(f"Lote de {cantidad} árboles de {especie} añadido.")


def deshacer_ultimo_lote():
    """Elimina el último lote añadido."""
    if st.session_state.inventario_list:
        st.session_state.inventario_list.pop()
        if st.session_state.lotes_mapa:
            st.session_state.lotes_mapa.pop()
        st.success("Último lote eliminado.")
    else:
        st.warning("El inventario está vacío.")

def limpiar_inventario():
    """Limpia todo el inventario."""
    st.session_state.inventario_list = []
    st.session_state.lotes_mapa = []
    st.success("Inventario completamente limpiado.")


def generar_excel_memoria(df_inventario, proyecto, hectareas, total_arboles, total_co2e_ton, total_agua_l, total_costo):
    """Genera el archivo Excel en memoria con el resumen y el inventario detallado."""
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # 1. Definir columnas a excluir (Lat/Lon y Detalle Cálculo)
    cols_to_drop = ['Latitud', 'Longitud', 'Detalle Cálculo']
    df_inventario_download = df_inventario.drop(columns=cols_to_drop, errors='ignore')

    df_inventario_download.to_excel(writer, sheet_name='Inventario Detallado', index=False)
    
    df_resumen = pd.DataFrame({
        'Métrica': ['Proyecto', 'Fecha', 'Hectáreas (ha)', 'Total Árboles', 'CO2e Total (Ton)', 'CO2e Total (Kg)', 'Agua Total (L)', 'Costo Total (S/)'], 
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
    df_resumen.to_excel(writer, sheet_name='Resumen Proyecto', index=False)
    writer.close()
    processed_data = output.getvalue()
    return processed_data

# --- FUNCIONES DE VISUALIZACIÓN ---

def render_calculadora_y_graficos():
    """Función principal para la sección de cálculo y gráficos."""
    st.title("1. Cálculo de Captura de Carbono, Inversión y Recursos")

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
        st.markdown("## 1. Registro de Lotes")
        col_form, col_totales = st.columns([2, 1])

        with col_form:
            st.markdown("### Datos del Nuevo Lote")
            with st.form("form_lote", clear_on_submit=True):
                
                # 1. Especie, Cantidad y Precio Plantón (Ahora variable)
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
                
                # Si la especie cambia (y no es la primera ejecución), se precarga el precio
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

                # 2. Datos Físicos (DAP y Altura) - CORREGIDO: sin decimales
                col_dap, col_altura = st.columns(2)
                
                # DAP: Se fuerza a entero con step=1 y el valor inicial
                col_dap.slider(
                    "DAP promedio (cm)", 
                    min_value=0, max_value=50, 
                    step=1, # CORRECCIÓN: Ahora es entero
                    key='dap_slider', 
                    help="Diámetro a la altura del pecho. 🌳", 
                    value=int(st.session_state.dap_slider) # Se asegura que el valor sea entero
                )
                # Altura: Se fuerza a entero con step=1 y el valor inicial
                col_altura.slider(
                    "Altura promedio (m)", 
                    min_value=0, max_value=50, 
                    step=1, # CORRECCIÓN: Ahora es entero
                    key='altura_slider', 
                    help="Altura total del árbol. 🌲", 
                    value=int(st.session_state.altura_slider) # Se asegura que el valor sea entero
                )
                
                # 3. Años Plantados
                st.number_input("Años Plantados (Edad del lote)", min_value=0, value=st.session_state.anios_plantados_input, step=1, key='anios_plantados_input')

                # 4. Datos de Densidad/Agua (Manual si aplica)
                if especie_sel == 'Densidad/Datos Manuales':
                    st.markdown("---")
                    st.markdown("##### ✍️ Ingrese Datos Manuales de Densidad y Consumo de Agua")
                    col_dens, col_agua = st.columns(2)
                    col_dens.number_input("Densidad (ρ) (g/cm³)", min_value=0.001, value=st.session_state.densidad_manual_input, step=0.05, format="%.3f", key='densidad_manual_input')
                    col_agua.number_input("Consumo Agua Unitario (L/año)", min_value=0.0, value=st.session_state.consumo_agua_manual_input, step=100.0, key='consumo_agua_manual_input')
                else:
                    st.info(f"Usando valores por defecto para {especie_sel}: Densidad: **{current_species_info[especie_sel]['Densidad']} g/cm³** | Agua: **{current_species_info[especie_sel]['Agua_L_Anio']} L/año**.")
                    
                # 5. Coordenadas (Para el Mapa)
                st.markdown("---")
                st.markdown("##### 🗺️ Coordenadas (Usadas solo para el Mapa)")
                col_lat, col_lon = st.columns(2)
                col_lat.number_input("Latitud", format="%.5f", key='latitud_input', value=st.session_state.latitud_input, step=0.01)
                col_lon.number_input("Longitud", format="%.5f", key='longitud_input', value=st.session_state.longitud_input, step=0.01)

                st.form_submit_button("➕ Añadir Lote al Inventario", on_click=agregar_lote)

        with col_totales:
            st.subheader("Inventario Acumulado")
            total_arboles_registrados = sum(item.get('Cantidad', 0) for item in st.session_state.inventario_list)
            
            st.metric("🌳 Total Árboles Registrados", f"{total_arboles_registrados:,.0f} Árboles")
            st.metric("🌱 Captura CO₂e (Anual)", f"{co2e_proyecto_ton:,.2f} Toneladas")
            st.metric("💰 Costo Total (Plantones)", f"S/{costo_proyecto_total:,.2f}")
            st.metric("💧 Consumo Agua Total (Anual)", f"{agua_proyecto_total:,.0f} Litros")
            
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
                    file_name=f'Reporte_CO2e_CPSSA_{pd.Timestamp.today().strftime("%Y%m%d")}.xlsx',
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Genera un archivo Excel con el resumen y el detalle de cada lote. **Excluye Latitud/Longitud.**"
                )

        st.markdown("---")
        st.subheader("Inventario Detallado (Lotes)")
        
        if df_inventario_completo.empty:
            st.info("No hay lotes registrados. Use el formulario superior para empezar.")
        else:
            # EXCLUYE Latitud y Longitud de la visualización en pantalla
            cols_to_drop = [col for col in ['Detalle Cálculo', 'Latitud', 'Longitud'] if col in df_inventario_completo.columns]
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
        st.markdown("## 2. Visor de Gráficos")
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
                fig_costo = px.bar(df_graficos, x='Especie', y='Total_Costo_S', title='Costo Total (Plantones) por Especie (Soles)', color='Total_Costo_S', color_continuous_scale=px.colors.sequential.Sunset)
                col_costo.plotly_chart(fig_costo, use_container_width=True)
            
            with col_agua:
                fig_agua = px.bar(df_graficos, x='Especie', y='Consumo_Agua_Total_L', title='Consumo Agua Acumulado por Especie (Litros)', color='Consumo_Agua_Total_L', color_continuous_scale=px.colors.sequential.Agsunset)
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


    with tab3:
        st.markdown("## 3. Detalle Técnico de Cálculo por Lote")
        if df_inventario_completo.empty:
            st.warning("No hay datos en el inventario para mostrar el detalle técnico.")
        else:
            # CORRECCIÓN: Se usa el inventario_list para asegurar la correspondencia con los índices del selectbox
            lotes_info = [
                f"Lote {i+1}: {row['Especie']} ({row['Cantidad']} árboles)" 
                for i, row in enumerate(st.session_state.inventario_list) # Se itera sobre la lista original
            ]
            
            lote_seleccionado = st.selectbox("Seleccione el Lote para el Detalle:", lotes_info)
            lote_index = lotes_info.index(lote_seleccionado)
            
            # Se usa el DataFrame completo, que contiene la columna 'Detalle Cálculo'
            fila_lote = df_inventario_completo.iloc[lote_index]
            detalle_markdown = fila_lote['Detalle Cálculo']
            
            st.markdown(f"### Detalles Técnicos y Fórmulas para {lote_seleccionado}")
            st.markdown(detalle_markdown)


    with tab4:
        st.markdown("## 4. Simulación de Crecimiento (Años)")
        if df_inventario_completo.empty:
            st.warning("No hay datos en el inventario para simular el crecimiento.")
        else:
            # CORRECCIÓN: Se usa el inventario_list para asegurar la correspondencia con los índices del selectbox
            lotes_info = [
                f"Lote {i+1}: {row['Especie']} ({row['Cantidad']} árboles)" 
                for i, row in enumerate(st.session_state.inventario_list) # Se itera sobre la lista original
            ]

            lote_sim_index_str = st.selectbox("Seleccione el Lote para la Proyección:", lotes_info)
            index_df = lotes_info.index(lote_sim_index_str)
            
            # Se usa el DataFrame completo para obtener los datos de la fila
            lote_df = df_inventario_completo.iloc[[index_df]]
            
            especie_actual = lote_df['Especie'].iloc[0]
            
            # Uso de .get con un valor por defecto si no existe la clave
            factores_base = FACTORES_CRECIMIENTO.get(especie_actual, FACTORES_CRECIMIENTO['Factor Manual'])
            
            st.subheader("Parámetros de Proyección de Crecimiento")
            
            col_anios, col_dap_f, col_alt_f = st.columns(3)
            anios = col_anios.slider("Años a proyectar:", min_value=5, max_value=30, value=15, step=5)
            factor_dap = col_dap_f.slider("Factor Crecimiento DAP (% anual)", min_value=0.01, max_value=0.10, value=factores_base['DAP'], step=0.01, format="%.2f")
            factor_altura = col_alt_f.slider("Factor Crecimiento Altura (% anual)", min_value=0.01, max_value=0.10, value=factores_base['Altura'], step=0.01, format="%.2f")

            # --- SIMULACIÓN DE CRECIMIENTO ---
            def simular_crecimiento(lote_df, anios, factor_dap, factor_altura, max_dap=100.0, max_alt=50.0):
                if lote_df.empty: return pd.DataFrame()
                
                # Obtener valores iniciales (aseguramos que sean float para el cálculo)
                cant = lote_df['Cantidad'].iloc[0]
                rho = lote_df['Densidad (ρ)'].iloc[0]
                dap_i = lote_df['DAP (cm)'].iloc[0]
                alt_i = lote_df['Altura (m)'].iloc[0]
                
                data = []
                for anio in range(1, anios + 1):
                    # Aplicar factor de crecimiento, limitado por el máximo de madurez
                    dap_n = min(dap_i * (1 + factor_dap)**anio, max_dap)
                    alt_n = min(alt_i * (1 + factor_altura)**anio, max_alt)
                    
                    # Recalcular CO2e con los nuevos valores
                    _, _, _, co2e_uni_kg, _ = calcular_co2_arbol(rho, dap_n, alt_n)
                    co2e_lote_ton = (co2e_uni_kg * cant) / FACTOR_KG_A_TON
                    
                    data.append({
                        'Año': anio,
                        'DAP (cm)': dap_n,
                        'Altura (m)': alt_n,
                        'CO2e Lote (Ton)': co2e_lote_ton
                    })
                
                return pd.DataFrame(data)
                
            df_proyeccion = simular_crecimiento(lote_df, anios, factor_dap, factor_altura)
            
            if not df_proyeccion.empty:
                st.markdown("---")
                st.subheader(f"Proyección de Crecimiento para {lote_sim_index_str}")
                
                fig_co2e_proj = px.line(df_proyeccion, x='Año', y='CO2e Lote (Ton)', title='Captura Proyectada de CO₂e', markers=True)
                st.plotly_chart(fig_co2e_proj, use_container_width=True)
                
                fig_dap_alt = go.Figure()
                fig_dap_alt.add_trace(go.Scatter(x=df_proyeccion['Año'], y=df_proyeccion['DAP (cm)'], mode='lines+markers', name='DAP (cm)'))
                fig_dap_alt.add_trace(go.Scatter(x=df_proyeccion['Año'], y=df_proyeccion['Altura (m)'], mode='lines+markers', name='Altura (m)'))
                fig_dap_alt.update_layout(title='Crecimiento de DAP y Altura', xaxis_title='Año', yaxis_title='Medida')
                st.plotly_chart(fig_dap_alt, use_container_width=True)
            else:
                st.warning("Simulación no ejecutada o lote sin datos.")


def render_mapa():
    """Muestra la ubicación de los lotes en un mapa interactivo."""
    st.title("3. Mapa de Ubicación de Lotes")
    
    if not st.session_state.lotes_mapa:
        st.info("Aún no se han añadido lotes con coordenadas. Use la sección '1. Cálculo de Captura' para añadir lotes y verlos aquí.")
        return

    df_lotes = pd.DataFrame(st.session_state.lotes_mapa)
    lat_centro = df_lotes['lat'].mean()
    lon_centro = df_lotes['lon'].mean()

    m = folium.Map(location=[lat_centro, lon_centro], zoom_start=6)

    for index, row in df_lotes.iterrows():
        folium.Marker(
            [row['lat'], row['lon']], 
            tooltip=row['tooltip'],
            icon=folium.Icon(color="green", icon="tree", prefix="fa")
        ).add_to(m)

    st.markdown("### Ubicaciones Geográficas de Lotes Plantados")
    folium_static(m)


def render_gap_cpassa():
    """Análisis de brecha (GAP) entre la captura del proyecto y la Huella de Carbono Corporativa (HCC)."""
    st.title("4. GAP (Análisis de Brecha) vs. Huella Corporativa (CPSSA)")
    
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
        st.metric(f"Emisiones Anuales de '{sede_sel}' (**Miles de Ton CO2e**)", f"**{emisiones_sede_miles_ton:,.2f} Miles tCO₂e**")
        
    with col_proyecto:
        st.metric("Captura de CO₂e del Proyecto (**Miles de Ton CO2e**)", f"**{co2e_proyecto_miles_ton:,.2f} Miles tCO₂e**")

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
        
    df_comparacion = pd.DataFrame({
        'Categoría': [f'Emisiones de {sede_sel}', 'Captura del Proyecto', 'Brecha (GAP)'],
        'Valor (Miles tCO₂e)': [emisiones_sede_miles_ton, co2e_proyecto_miles_ton, brecha_miles_ton],
        'Tipo': ['Emisiones', 'Captura', 'Diferencia']
    })
    
    fig_gap = px.bar(
        df_comparacion, 
        y='Categoría', 
        x='Valor (Miles tCO₂e)', 
        color='Tipo', 
        orientation='h',
        title='Comparación: Emisiones vs. Captura de Carbono'
    )
    st.plotly_chart(fig_gap, use_container_width=True)
    
    
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
            "Precio Plantón (S/)": st.column_config.NumberColumn("Precio Plantón (S/)", format="%.2f", help="Costo unitario de compra o producción del plantón. Este es el valor por defecto que se precarga en el formulario de lote, pero el usuario puede cambiarlo en la sección 1.", min_value=0.0), 
            "DAP (cm)": st.column_config.NumberColumn("DAP (cm)", format="%.2f", help="Diámetro a la altura del pecho", min_value=0.0),
            "Altura (m)": st.column_config.NumberColumn("Altura (m)", format="%.2f", help="Altura total del árbol", min_value=0.0),
            "Consumo Agua (L/año)": st.column_config.NumberColumn("Consumo Agua (L/año)", format="%.0f", help="Consumo de agua anual por árbol", min_value=0.0),
            "Densidad (g/cm³)": st.column_config.NumberColumn("Densidad (g/cm³)", format="%.3f", help="Densidad de la madera (ρ)", min_value=0.001)
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
        
        options = [
            "1. Cálculo de Captura", 
            "3. Mapa",
            "4. GAP CPSSA",
            "5. Gestión de Especie"
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
        st.metric("CO2e Inventario Total", f"{co2e_total_sidebar:,.2f} Ton") 
        
        st.markdown("---")
        if st.button("🔄 Reiniciar Aplicación (Borrar Datos de Sesión)", type="secondary"):
            reiniciar_app_completo()
    
    # 2. Renderizar la página basada en el estado de sesión
    selection = st.session_state.current_page 
    
    if selection == "1. Cálculo de Captura":
        render_calculadora_y_graficos()
    elif selection == "3. Mapa":
        render_mapa()
    elif selection == "4. GAP CPSSA":
        render_gap_cpassa()
    elif selection == "5. Gestión de Especie":
        render_gestion_especie()
    
    # Pie de página actualizado (solicitud del usuario)
    st.caption("---")
    st.caption(
        "**Solicitar cambios y/o actualizaciones al Área de Cambio Climático**"
    )
    st.caption(
        "Para dudas y consultas adicionales, escribir al: **ftrujillo@cpsaa.com.pe**"
    )

if __name__ == "__main__":
    main_app()