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

# BASE DE DATOS INICIAL DE DENSIDADES (Valores por defecto para selección rápida)
# Valores de densidad (ρ) en g/cm³ basados en revisión bibliográfica
DENSIDADES_BASE = {
    'Eucalipto (Eucalyptus globulus)': 0.76, 
    'Torrellana': 0.55,
    'Majoe (Hibiscus tiliaceus)': 0.65,
    'Molle (Schinus molle)': 0.50,
    'Algarrobo (Prosopis pallida)': 0.80,
}

# FACTORES DE CRECIMIENTO INICIAL (Valores por defecto para simulación)
FACTORES_CRECIMIENTO = {
    'Eucalipto (Eucalyptus globulus)': {'DAP': 0.15, 'Altura': 0.12, 'Agua': 0.0},
    'Torrellana': {'DAP': 0.05, 'Altura': 0.05, 'Agua': 0.0},
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


# --- DEFINICIÓN DE TIPOS DE COLUMNAS ---
df_columns_types = {
    'Especie': str, 'Cantidad': int, 'DAP (cm)': float, 'Altura (m)': float, 
    'Densidad (ρ)': float, 'Detalle Cálculo': str 
}
df_columns_numeric = ['Cantidad', 'DAP (cm)', 'Altura (m)', 'Densidad (ρ)']
columnas_salida = ['Biomasa Lote (Ton)', 'Carbono Lote (Ton)', 'CO2e Lote (Ton)']

# --- FUNCIÓN CRÍTICA: DINÁMICA DE ESPECIES ---
def get_current_densidades():
    """
    Genera un diccionario de densidades de madera fusionando las especies base 
    con las especies añadidas/modificadas por el usuario en la gestión.
    """
    current_densities = DENSIDADES_BASE.copy()
    
    # 1. Obtener la data de la tabla de gestión de especies (persistencia)
    df_bd = st.session_state.especies_bd.copy()
    
    # 2. Asegurar que la columna de Densidad exista y haya datos válidos
    if 'Densidad (g/cm³)' in df_bd.columns and not df_bd.empty:
        # Tomar la última densidad registrada para cada especie
        df_unique_densities = df_bd.drop_duplicates(subset=['Especie'], keep='last')[['Especie', 'Densidad (g/cm³)']]
        
        for _, row in df_unique_densities.iterrows():
            especie_name = row['Especie']
            densidad_val = pd.to_numeric(row['Densidad (g/cm³)'], errors='coerce')
            
            if pd.notna(densidad_val) and densidad_val > 0:
                # 3. Sobreescribir o añadir la densidad definida por el usuario
                current_densities[especie_name] = densidad_val
    
    # 4. Añadir la opción de densidad manual al final
    current_densities['Densidad Manual (g/cm³)'] = 0.0
    
    return current_densities

# --- FUNCIONES DE CÁLCULO Y MANEJO DE INVENTARIO ---

def calcular_co2_arbol(rho, dap_cm, altura_m):
    """Calcula la biomasa, carbono y CO2e por árbol en KILOGRAMOS."""
    detalle = ""
    # Evita la división por cero o logaritmos de cero
    if rho <= 0 or dap_cm <= 0 or altura_m <= 0:
        detalle = "ERROR: Valores de entrada (DAP, Altura o Densidad) deben ser mayores a cero."
        return 0, 0, 0, 0, detalle
        
    # Calcular AGB (Above-Ground Biomass) en kg
    agb_kg = AGB_FACTOR_A * ((rho * (dap_cm**2) * altura_m)**AGB_FACTOR_B)
    
    # Calcular BGB (Below-Ground Biomass) en kg
    bgb_kg = agb_kg * FACTOR_BGB_SECO
    
    # Biomasa total (AGB + BGB)
    biomasa_total = agb_kg + bgb_kg
    
    # Carbono total
    carbono_total = biomasa_total * FACTOR_CARBONO
    
    # CO2 equivalente
    co2e_total = carbono_total * FACTOR_CO2E
    
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


# --- FUNCIÓN DE RECÁLCULO SEGURO (CRÍTICA) ---
def recalcular_inventario_completo(inventario_list):
    """
    Toma la lista de entradas (List[Dict]) y genera un DataFrame completo y limpio.
    """
    if not inventario_list:
        return pd.DataFrame(columns=list(df_columns_types.keys()) + columnas_salida).astype({**df_columns_types, **dict.fromkeys(columnas_salida, float)})

    # Crear DF base y limpiar tipos
    df_base = pd.DataFrame(inventario_list)
    df_calculado = df_base.copy()
    
    for col in df_columns_numeric:
        df_calculado[col] = pd.to_numeric(df_calculado[col], errors='coerce').fillna(0)
    
    resultados_calculo = []
    
    for _, row in df_calculado.iterrows():
        rho = row['Densidad (ρ)']
        dap = row['DAP (cm)']
        altura = row['Altura (m)']
        cantidad = row['Cantidad']
        
        _, _, biomasa_uni_kg, co2e_uni_kg, _ = calcular_co2_arbol(rho, dap, altura)
        
        # Convertir a TONELADAS
        biomasa_lote_ton = (biomasa_uni_kg * cantidad) / FACTOR_KG_A_TON
        carbono_lote_ton = (biomasa_uni_kg * FACTOR_CARBONO * cantidad) / FACTOR_KG_A_TON
        co2e_lote_ton = (co2e_uni_kg * cantidad) / FACTOR_KG_A_TON
        
        resultados_calculo.append({
            'Biomasa Lote (Ton)': float(biomasa_lote_ton), 
            'Carbono Lote (Ton)': float(carbono_lote_ton), 
            'CO2e Lote (Ton)': float(co2e_lote_ton),
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


def simular_crecimiento(df_inicial, anios_simulacion, factor_dap, factor_altura, max_dap=100, max_altura=30):
    """Simula el crecimiento y calcula el CO2e en TONELADAS."""
    resultados = []
    if df_inicial.empty: return pd.DataFrame()

    rho = df_inicial['Densidad (ρ)'].iloc[0]
    cantidad_arboles = df_inicial['Cantidad'].iloc[0]

    dap_actual = df_inicial['DAP (cm)'].iloc[0]
    altura_actual = df_inicial['Altura (m)'].iloc[0]

    for anio in range(1, anios_simulacion + 1):
        # Aplicar crecimiento y limitar por valores máximos
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


# --- FUNCIONES DE MANEJO DE ESTADO ---

def agregar_lote():
    
    # 1. Obtener densidades actuales, incluyendo las añadidas por el usuario
    current_densities = get_current_densidades()
    
    # 2. Obtener valores de entrada
    especie = st.session_state.especie_sel
    cantidad = st.session_state.cantidad_input
    dap = st.session_state.dap_slider
    altura = st.session_state.altura_slider
    
    rho = 0.0
    # Manejar la densidad manual
    if especie == 'Densidad Manual (g/cm³)' and 'densidad_manual_input' in st.session_state and st.session_state.densidad_manual_input > 0:
        rho = st.session_state.densidad_manual_input
    elif especie in current_densities: # Usar la densidad dinámica
        rho = current_densities[especie]
    
    if cantidad <= 0 or dap <= 0 or altura <= 0 or rho <= 0:
        st.error("Por favor, asegúrate de que Cantidad, DAP, Altura y Densidad sean mayores a cero.")
        return

    _, _, _, _, detalle_calculo = calcular_co2_arbol(rho, dap, altura)
    
    nueva_fila_dict = {
        'Especie': especie, 
        'Cantidad': int(cantidad), 
        'DAP (cm)': float(dap), 
        'Altura (m)': float(altura), 
        'Densidad (ρ)': float(rho),
        'Detalle Cálculo': detalle_calculo
    }
    
    st.session_state.inventario_list.append(nueva_fila_dict)
    
    # Resetear inputs para la siguiente entrada (Opcional)
    st.session_state.cantidad_input = 0
    st.session_state.dap_slider = 0.0
    st.session_state.altura_slider = 0.0
    
    # Mantener la especie seleccionada
    current_keys = list(current_densities.keys())
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

    
# --- FUNCIÓN DE DESCARGA DE EXCEL ---
def generar_excel_memoria(df_inventario, proyecto, hectareas, total_arboles, total_co2e_ton):
    fecha = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    df_para_excel = df_inventario.copy()
    try:
        if 'Detalle Cálculo' in df_para_excel.columns:
            df_para_excel = df_para_excel.drop(columns=['Detalle Cálculo'])
    except:
        pass 
        
    df_para_excel.to_excel(writer, sheet_name='Inventario Detallado (Ton)', index=False)
    
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
    
    # Se debe cerrar el escritor antes de obtener el valor
    writer.close()
    processed_data = output.getvalue()
    return processed_data


# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN (CRÍTICA PARA LA PERSISTENCIA) ---
def inicializar_estado_de_sesion():
    if 'inventario_list' not in st.session_state:
        st.session_state.inventario_list = [] 
    
    # CRÍTICO: Inicialización robusta del DF de especies persistente
    if 'especies_bd' not in st.session_state: 
        # Columnas necesarias para la edición y persistencia (SIN 'Año')
        df_cols = ['Especie', 'DAP (cm)', 'Altura (m)', 'Consumo Agua (L/año)', 'Densidad (g/cm³)']
        
        # Pre-poblar con las especies iniciales
        initial_data = []
        for name, rho in DENSIDADES_BASE.items():
            if rho > 0:
                initial_data.append({
                    'Especie': name, 
                    'DAP (cm)': 0.0, 
                    'Altura (m)': 0.0, 
                    'Consumo Agua (L/año)': 0.0,
                    'Densidad (g/cm³)': rho
                })
        
        st.session_state.especies_bd = pd.DataFrame(initial_data, columns=df_cols)
        
    # Variables del proyecto
    if 'proyecto' not in st.session_state: st.session_state.proyecto = ""
    if 'hectareas' not in st.session_state: st.session_state.hectareas = 0.0
    
    # Variables de Inputs 
    if 'dap_slider' not in st.session_state: st.session_state.dap_slider = 0.0
    if 'altura_slider' not in st.session_state: st.session_state.altura_slider = 0.0
    if 'cantidad_input' not in st.session_state: st.session_state.cantidad_input = 0
    if 'densidad_manual_input' not in st.session_state: st.session_state.densidad_manual_input = 0.5 
    
    # Inicialización de especie seleccionada con la lista dinámica
    current_densities = get_current_densidades()
    current_keys = list(current_densities.keys())
    
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

# --- 1. CÁLCULO Y GRÁFICOS
def render_calculadora_y_graficos():
    st.title("🌳 1. Cálculo de Captura de Carbono")
    
    # Obtener la lista dinámica de densidades aquí
    current_densities = get_current_densidades()
    
    df_inventario_completo = recalcular_inventario_completo(st.session_state.inventario_list)
    co2e_proyecto_ton = get_co2e_total_seguro(df_inventario_completo)

    # --- INFORMACIÓN DEL PROYECTO ---
    st.subheader("📋 Información del Proyecto")
    col_proj, col_hectareas = st.columns([2, 1])

    with col_proj:
        # Nota: 'key' permite a Streamlit manejar el estado. El 'value' inicial es solo para el primer render.
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
                especie_keys = list(current_densities.keys())
                # Asegurar que la especie seleccionada siga siendo válida si existe
                default_index = especie_keys.index(st.session_state.especie_sel) if st.session_state.especie_sel in especie_keys else 0
                especie_sel = st.selectbox("Especie / Tipo de Árbol", especie_keys, key='especie_sel', index=default_index)
                
                if especie_sel == 'Densidad Manual (g/cm³)':
                    st.number_input("Densidad de madera (ρ, g/cm³)", min_value=0.1, max_value=1.5, value=st.session_state.densidad_manual_input, step=0.01, key='densidad_manual_input')
                else:
                    rho_value = current_densities.get(especie_sel, 0.0)
                    st.info(f"Densidad de la madera: **{rho_value} g/cm³**")
                    st.caption("ℹ️ Esta densidad es la que está registrada en la Base de Datos Histórica (Sección 5).")
                
                st.markdown("---")
                
                # Inputs del lote
                st.number_input("Cantidad de Árboles (n)", min_value=0, step=1, key='cantidad_input', value=st.session_state.cantidad_input)
                st.slider("DAP promedio (cm)", min_value=0.0, max_value=150.0, step=1.0, key='dap_slider', help="Diámetro a la Altura del Pecho. 🌳", value=st.session_state.dap_slider)
                st.slider("Altura promedio (m)", min_value=0.0, max_value=50.0, step=0.1, key='altura_slider', help="Altura total del árbol. 🌲", value=st.session_state.altura_slider)
                
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
                    co2e_proyecto_ton 
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
                # Mostrar el DataFrame sin las columnas de detalle y carbono (que es un intermedio de CO2e)
                if isinstance(df_inventario_completo, pd.DataFrame) and 'Carbono Lote (Ton)' in df_inventario_completo.columns:
                     st.dataframe(df_inventario_completo.drop(columns=['Carbono Lote (Ton)', 'Detalle Cálculo']), use_container_width=True, hide_index=True)
                else:
                    st.dataframe(df_inventario_completo, use_container_width=True, hide_index=True)
                
            else:
                st.info("Añade el primer lote de árboles para iniciar el inventario.")
                
    with tab2: # Visor de Gráficos
        st.markdown("## 1.2 Resultados Clave y Visualización")
        if df_inventario_completo.empty:
            st.warning("⚠️ No hay datos registrados.")
        else:
            df_inventario = df_inventario_completo.copy()
            
            total_arboles_registrados = df_inventario['Cantidad'].sum()
            biomasa_total_ton = df_inventario['Biomasa Lote (Ton)'].sum()

            st.subheader("✅ Indicadores Clave del Proyecto")
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Número de Árboles", f"{total_arboles_registrados:.0f}")
            kpi2.metric("Biomasa Total", f"{biomasa_total_ton:,.2f} Ton")
            kpi3.metric("CO2e Capturado", f"**{co2e_proyecto_ton:,.2f} Toneladas**", delta="Total del Proyecto", delta_color="normal")
            
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
            
            # Usar el inventario_list directamente para obtener información
            lotes_info = [
                f"Lote {i+1}: {row['Especie']} ({row['Cantidad']} árboles) - DAP Inicial: {row['DAP (cm)']:.1f} cm" 
                for i, row in st.session_state.inventario_list # CORREGIDO: Usar st.session_state.inventario_list (una lista de diccionarios)
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
    co2e_proyecto_miles_ton = co2e_proyecto_ton / FACTOR_KG_A_TON 
    
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

# --- 5. GESTIÓN DE ESPECIE (CORREGIDA) ---
def render_gestion_especie():
    st.title("🌿 5. Gestión de Datos de Crecimiento de Especies")
    st.markdown("Edite, **agregue o elimine** entradas en la Base de Datos Histórica. Los cambios en la **Densidad (g/cm³)** se aplicarán automáticamente a la calculadora.")
    st.info("⚠️ **IMPORTANTE:** La Densidad de madera (ρ) es el valor crítico para el cálculo de biomasa. Al guardar, la última densidad registrada para una especie se usará en la sección de Cálculo.")

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
            # 'Año' ha sido eliminado. DAP/Altura se mantienen como datos de referencia.
            "DAP (cm)": st.column_config.NumberColumn("DAP (cm)", format="%.2f", help="Diámetro a la altura del pecho", min_value=0.0),
            "Altura (m)": st.column_config.NumberColumn("Altura (m)", format="%.2f", help="Altura total del árbol", min_value=0.0),
            "Consumo Agua (L/año)": st.column_config.NumberColumn("Consumo Agua (L/año)", format="%.2f", help="Consumo promedio de agua", min_value=0.0)
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
        cols_numeric_to_save = ['DAP (cm)', 'Altura (m)', 'Consumo Agua (L/año)', 'Densidad (g/cm³)']
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
    
    # 1. Asegurar el estado de la página actual (inicializado en inicializar_estado_de_sesion)
    
    df_inventario_completo = recalcular_inventario_completo(st.session_state.inventario_list)
    co2e_total_sidebar = get_co2e_total_seguro(df_inventario_completo)
    
    st.sidebar.title("Menú de Navegación")
    
    # Botón de Reinicio (Se mantiene)
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
            # CORRECCIÓN: Usar 'primary' si está seleccionado, 'secondary' si no lo está.
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
    
    st.caption("Fórmula: AGB = 0.112 × (ρ × D² × H)^0.916 | Chave et al. (2014). Factores C=0.47, BGB=0.28, CO2e=3.67. Unidades en Toneladas.")

# --- LÍNEA VITAL DE EJECUCIÓN ---
if __name__ == '__main__':
    main_app()