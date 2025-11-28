import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Calculadora de Captura de Carbono", layout="wide", page_icon="🌳")

# --- FACTORES DE CONVERSIÓN ---
FACTOR_CARBONO = 0.47
FACTOR_CO2E = 3.67
FACTOR_BGB_SECO = 0.28

# --- BASE DE DATOS Y ESTRUCTURA DE INPUTS ---
DENSIDADES = {
    'Eucalipto (E. globulus)': 0.76,
    'Cedro (C. odorata)': 0.48,
    'Caoba (S. macrophylla)': 0.54,
    'Pino (P. patula)': 0.43,
    'Ficus (F. benghalensis)': 0.50,
    'Palmera (varias)': 0.35,
    'Roble Andino': 0.65,
    'Densidad Manual (g/cm³)': 0.0
}

# --- FUNCIONES DE CÁLCULO INDIVIDUAL ---
def calcular_co2_arbol(rho, dap_cm, altura_m):
    """
    Calcula CO2e individual usando Chave 2014 (Bosques Secos) y tus factores.
    """
    if rho <= 0 or dap_cm <= 0 or altura_m <= 0:
        return 0, 0, 0, 0
        
    # Ecuación de Chave et al. (2014) para BOSQUES SECOS (AGB en kg)
    agb_kg = 0.112 * ((rho * (dap_cm**2) * altura_m)**0.916)
    bgb_kg = agb_kg * FACTOR_BGB_SECO 
    biomasa_total = agb_kg + bgb_kg
    carbono_total = biomasa_total * FACTOR_CARBONO
    co2e_total = carbono_total * FACTOR_CO2E
    
    return agb_kg, bgb_kg, biomasa_total, co2e_total

# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
if 'inventario_df' not in st.session_state:
    st.session_state.inventario_df = pd.DataFrame(columns=[
        'Especie', 'Cantidad', 'DAP (cm)', 'Altura (m)', 'Densidad (ρ)',
        'Biomasa Lote (kg)', 'Carbono Lote (kg)', 'CO2e Lote (kg)'
    ])
if 'proyecto' not in st.session_state:
    st.session_state.proyecto = ""
if 'hectareas' not in st.session_state:
    st.session_state.hectareas = 0.0
if 'total_co2e_kg' not in st.session_state:
    st.session_state.total_co2e_kg = 0.0

# --- FUNCIONES DE MANEJO DE INVENTARIO ---

def agregar_lote():
    # Obtener valores del formulario y realizar el cálculo
    especie = st.session_state.especie_sel
    cantidad = st.session_state.cantidad_input
    dap = st.session_state.dap_slider
    altura = st.session_state.altura_slider
    
    # Manejo de densidad 
    if especie == 'Densidad Manual (g/cm³)' and 'densidad_manual_input' in st.session_state and st.session_state.densidad_manual_input > 0:
        rho = st.session_state.densidad_manual_input
    elif especie != 'Densidad Manual (g/cm³)':
        rho = DENSIDADES[especie]
    else:
        st.error("Por favor, ingrese un valor de Densidad válido o una Cantidad de árboles > 0.")
        return

    if cantidad <= 0 or dap <= 0 or altura <= 0:
        st.error("Todos los campos (Cantidad, DAP, Altura) deben ser mayores a cero.")
        return

    # Cálculo
    agb_uni, bgb_uni, biomasa_uni, co2e_uni = calcular_co2_arbol(rho, dap, altura)
    biomasa_lote = biomasa_uni * cantidad
    carbono_lote = biomasa_lote * FACTOR_CARBONO
    co2e_lote = co2e_uni * cantidad

    # Crear y añadir nueva fila al DataFrame
    nueva_fila = pd.DataFrame([{
        'Especie': especie, 'Cantidad': cantidad, 'DAP (cm)': dap, 'Altura (m)': altura, 'Densidad (ρ)': rho,
        'Biomasa Lote (kg)': biomasa_lote, 'Carbono Lote (kg)': carbono_lote, 'CO2e Lote (kg)': co2e_lote
    }])
    st.session_state.inventario_df = pd.concat([st.session_state.inventario_df, nueva_fila], ignore_index=True)
    st.session_state.total_co2e_kg = st.session_state.inventario_df['CO2e Lote (kg)'].sum()
    
    # Limpiar inputs para el siguiente lote
    st.session_state.cantidad_input = 0
    st.session_state.dap_slider = 0.0
    st.session_state.altura_slider = 0.0

def deshacer_ultimo_lote():
    if not st.session_state.inventario_df.empty:
        st.session_state.inventario_df = st.session_state.inventario_df.iloc[:-1]
        st.session_state.total_co2e_kg = st.session_state.inventario_df['CO2e Lote (kg)'].sum()
        st.experimental_rerun()

def limpiar_inventario():
    st.session_state.inventario_df = pd.DataFrame(columns=[
        'Especie', 'Cantidad', 'DAP (cm)', 'Altura (m)', 'Densidad (ρ)',
        'Biomasa Lote (kg)', 'Carbono Lote (kg)', 'CO2e Lote (kg)'
    ])
    st.session_state.total_co2e_kg = 0.0
    st.experimental_rerun()

# -------------------------------------------------
# --- FUNCIÓN PRINCIPAL DE LA APLICACIÓN ---
# -------------------------------------------------

def main_app():
    
    st.title("🌳 Calculadora de Captura de Carbono")
    
    # --- INFORMACIÓN DEL PROYECTO (Siempre visible) ---
    st.subheader("📋 Información del Proyecto")
    col_proj, col_hectareas = st.columns([2, 1])

    with col_proj:
        nombre_proyecto = st.text_input("Nombre del Proyecto (Opcional)", value=st.session_state.proyecto, placeholder="Ej: Reforestación Bosque Seco 2024", key='proyecto_input')
        st.session_state.proyecto = nombre_proyecto

    with col_hectareas:
        hectareas = st.number_input("Hectáreas (ha)", min_value=0.0, value=st.session_state.hectareas, step=0.1, key='hectareas_input', help="Dejar en 0 si no se aplica o no se conoce el dato.")
        st.session_state.hectareas = hectareas

    if st.session_state.proyecto:
        st.markdown(f"**Proyecto Actual:** *{st.session_state.proyecto}*")
    st.divider()

    # --- NAVEGACIÓN POR PESTAÑAS (TABS) ---
    tab1, tab2 = st.tabs(["➕ Cálculo de CO2 (Entrada de Datos)", "📈 Visor de Gráficos y Análisis"])

    # =================================================
    # PESTAÑA 1: CÁLCULO DE CO2 (ENTRADA Y REGISTRO)
    # =================================================
    with tab1:
        st.markdown("## 1. Registro y Acumulación de Inventario")

        col_input, col_totales = st.columns([1, 2])

        with col_input:
            st.subheader("Entrada de Lote por Especie")
            
            with st.form("lote_form", clear_on_submit=False):
                
                # Selector de Especie
                especie_sel = st.selectbox("Especie / Tipo de Árbol", list(DENSIDADES.keys()), key='especie_sel')
                
                # Densidad instantánea
                if especie_sel == 'Densidad Manual (g/cm³)':
                    st.number_input("Densidad de madera (ρ, g/cm³)", min_value=0.1, max_value=1.5, value=0.5, step=0.01, key='densidad_manual_input')
                else:
                    rho_value = DENSIDADES[especie_sel]
                    st.info(f"Densidad de la madera seleccionada: **{rho_value} g/cm³**")
                
                st.markdown("---")
                
                st.number_input("Cantidad de Árboles (n)", min_value=0, step=1, key='cantidad_input')
                
                # Sliders para DAP y Altura (Sin 'value' inicial para evitar advertencias de Session State)
                st.slider("DAP promedio (cm)", min_value=0.0, max_value=150.0, step=1.0, key='dap_slider', help="Diámetro a la Altura del Pecho. 🌳")
                st.slider("Altura promedio (m)", min_value=0.0, max_value=50.0, step=0.1, key='altura_slider', help="Altura total del árbol. 🌲")
                
                st.form_submit_button("➕ Añadir Lote al Inventario", on_click=agregar_lote)

        with col_totales:
            st.subheader("Inventario Acumulado")
            
            total_arboles_registrados = st.session_state.inventario_df['Cantidad'].sum()
            
            if total_arboles_registrados > 0:
                
                # Botones de edición
                col_deshacer, col_limpiar = st.columns(2)
                col_deshacer.button("↩️ Deshacer Último Lote", on_click=deshacer_ultimo_lote, help="Elimina la última fila añadida a la tabla.")
                col_limpiar.button("🗑️ Limpiar Inventario Total", on_click=limpiar_inventario, help="Elimina todas las entradas y reinicia el cálculo.")

                st.markdown("---")
                
                st.caption("Detalle de los Lotes Añadidos:")
                st.dataframe(st.session_state.inventario_df.drop(columns=['Carbono Lote (kg)']), use_container_width=True, hide_index=True)
                
                st.success("¡Inventario listo! Ve a la pestaña 'Visor de Gráficos y Análisis' para ver los resultados.")

            else:
                st.info("Añade el primer lote de árboles para iniciar el inventario.")
    
    # =================================================
    # PESTAÑA 2: VISOR DE GRÁFICOS Y ANÁLISIS
    # =================================================
    with tab2:
        st.markdown("## 2. Resultados Clave y Visualización")

        if st.session_state.inventario_df.empty:
            st.warning("⚠️ No hay datos registrados. Por favor, vuelve a la pestaña 'Cálculo de CO2' e ingresa los lotes.")
        else:
            df_inventario = st.session_state.inventario_df
            total_co2e_kg = st.session_state.total_co2e_kg
            hectareas = st.session_state.hectareas
            
            total_arboles_registrados = df_inventario['Cantidad'].sum()
            biomasa_total = df_inventario['Biomasa Lote (kg)'].sum()
            co2e_ton = total_co2e_kg / 1000

            # -------------------------------------------------
            # INDICADORES CLAVE (KPIs)
            # -------------------------------------------------
            st.subheader("✅ Indicadores Clave del Proyecto")
            kpi1, kpi2, kpi3 = st.columns(3)
            
            kpi1.metric("Número de Árboles", f"{total_arboles_registrados:.0f}")
            kpi2.metric("Biomasa Total", f"{biomasa_total:.2f} kg")
            kpi3.metric("CO2e Capturado", f"**{co2e_ton:.2f} Toneladas**", delta="Total del Proyecto", delta_color="normal")

            # Métrica por Hectárea (Opcional)
            if hectareas > 0:
                co2e_per_ha = total_co2e_kg / hectareas
                st.metric("CO2e por Hectárea", f"**{co2e_per_ha:.2f} kg/ha**", help="CO2 Capturado Total / Hectáreas")
                
            st.markdown("---")
            
            # -------------------------------------------------
            # GRÁFICOS DE DISTRIBUCIÓN
            # -------------------------------------------------
            st.subheader("📊 Análisis de Distribución y Captura")
            
            df_graficos = df_inventario.groupby('Especie').agg(
                Total_CO2e_kg=('CO2e Lote (kg)', 'sum'),
                Conteo_Arboles=('Cantidad', 'sum')
            ).reset_index()

            col_graf1, col_graf2 = st.columns(2)

            with col_graf1:
                # Gráfico: CO2e por Especie (¿Cuál captura más carbono?)
                fig_co2e = px.bar(df_graficos, x='Especie', y='Total_CO2e_kg', 
                                  title='CO2e Capturado por Especie (kg)',
                                  labels={'Especie': 'Especie', 'Total_CO2e_kg': 'CO2e Capturado (kg)'},
                                  color='Total_CO2e_kg',
                                  color_continuous_scale=px.colors.sequential.Viridis)
                st.plotly_chart(fig_co2e, use_container_width=True)
            
            with col_graf2:
                # Gráfico: Conteo de Árboles por Especie (CORREGIDO: Usando Plasma en lugar de RdYlGn)
                fig_arboles = px.pie(df_graficos, values='Conteo_Arboles', names='Especie', 
                                     title='Conteo de Árboles por Especie',
                                     hole=0.3,
                                     color_discrete_sequence=px.colors.sequential.Plasma) # <--- CORRECCIÓN A PLASMA
                st.plotly_chart(fig_arboles, use_container_width=True)


            # -------------------------------------------------
            # INDICADORES AMBIENTALES
            # -------------------------------------------------
            st.markdown("---")
            st.subheader("🌍 Equivalencias Ambientales")
            autos_anio = co2e_ton / 4.6 
            hogares_anio = co2e_ton / 10.0
            
            c1, c2 = st.columns(2)
            c1.info(f"🚗 Compensación de **{autos_anio:.1f} autos** fuera de circulación por un año.")
            c2.success(f"🏠 Compensación de **{hogares_anio:.1f} hogares** sin consumo eléctrico por un año.")

    # --- FOOTER (Común para ambas pestañas) ---
    st.caption("Fórmula: AGB = 0.112 × (ρ × D² × H)^0.916 | Chave et al. (2014) - Bosques Secos. Factores C=0.47, BGB=0.28.")

# --- LÍNEA VITAL DE EJECUCIÓN ---
if __name__ == '__main__':
    main_app()