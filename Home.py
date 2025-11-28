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

# --- BASE DE DATOS DE DENSIDADES ---
DENSIDADES = {
    'Eucalipto (E. globulus)': 0.76,
    'Cedro (C. odorata)': 0.48,
    'Caoba (S. macrophylla)': 0.54,
    'Pino (P. patula)': 0.43,
    'Ficus (F. benghalensis)': 0.50,
    'Palmera (varias)': 0.35,
    'Roble Andino': 0.65,
    'Meijo': 0.60,
    'Algarrobo': 0.80,
    'Torrellana': 0.55,
    'Palmera hawaii': 0.35,
    'Hibiscus tiliaceus (Majao)': 0.65, 
    'Densidad Manual (g/cm³)': 0.0
}

# --- FACTORES DE CRECIMIENTO ANUAL PROMEDIO (Para la simulación) ---
# Estos factores son simplificados para la simulación. Se aplican como porcentaje anual.
FACTORES_CRECIMIENTO = {
    'Eucalipto (E. globulus)': {'DAP': 0.15, 'Altura': 0.12}, # Rápido
    'Pino (P. patula)': {'DAP': 0.10, 'Altura': 0.08}, # Moderado
    'Caoba (S. macrophylla)': {'DAP': 0.05, 'Altura': 0.05}, # Lento
    'Hibiscus tiliaceus (Majao)': {'DAP': 0.08, 'Altura': 0.07}, # Moderado
    'Algarrobo': {'DAP': 0.06, 'Altura': 0.05}, # Moderado/Lento
    'Factor Manual': {'DAP': 0.05, 'Altura': 0.05} # Por defecto
}

# --- FUNCIONES DE CÁLCULO INDIVIDUAL ---
def calcular_co2_arbol(rho, dap_cm, altura_m):
    """
    Calcula CO2e individual y devuelve el detalle de los cálculos.
    """
    detalle = ""
    if rho <= 0 or dap_cm <= 0 or altura_m <= 0:
        detalle = "ERROR: Valores de entrada (DAP, Altura o Densidad) deben ser mayores a cero."
        return 0, 0, 0, 0, detalle
        
    # 1. Biomasa Aérea Bruta (AGB)
    agb_kg = 0.112 * ((rho * (dap_cm**2) * altura_m)**0.916)
    
    # Detalle para la pestaña técnica
    base = rho * (dap_cm**2) * altura_m
    potencia = base**0.916
    detalle += f"## 1. Biomasa Aérea (AGB) por Árbol\n"
    detalle += f"**Fórmula (kg):** `0.112 * (ρ * DAP² * H)^0.916` (Chave 2014)\n"
    detalle += f"**Sustitución:** `0.112 * ({rho} * {dap_cm}² * {altura_m})^{0.916}`\n"
    detalle += f"**Resultado AGB (kg):** `{agb_kg:.4f}`\n\n"
    
    # 2. Biomasa Subterránea (BGB)
    bgb_kg = agb_kg * FACTOR_BGB_SECO 
    biomasa_total = agb_kg + bgb_kg
    
    # 3. Carbono Total
    carbono_total = biomasa_total * FACTOR_CARBONO
    
    # 4. CO2 Equivalente (CO2e)
    co2e_total = carbono_total * FACTOR_CO2E
    
    return agb_kg, bgb_kg, biomasa_total, co2e_total, detalle

# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
if 'inventario_df' not in st.session_state:
    st.session_state.inventario_df = pd.DataFrame(columns=[
        'Especie', 'Cantidad', 'DAP (cm)', 'Altura (m)', 'Densidad (ρ)',
        'Biomasa Lote (kg)', 'Carbono Lote (kg)', 'CO2e Lote (kg)', 'Detalle Cálculo'
    ])
# [Resto de inicializaciones omitidas para brevedad...]

# --- FUNCIONES DE MANEJO DE INVENTARIO (omitidas para brevedad, no hay cambios funcionales) ---
def agregar_lote():
    # ... (CÓDIGO DE agregar_lote) ...
    especie = st.session_state.especie_sel
    cantidad = st.session_state.cantidad_input
    dap = st.session_state.dap_slider
    altura = st.session_state.altura_slider
    
    rho = 0.0
    if especie == 'Densidad Manual (g/cm³)' and 'densidad_manual_input' in st.session_state and st.session_state.densidad_manual_input > 0:
        rho = st.session_state.densidad_manual_input
    elif especie != 'Densidad Manual (g/cm³)':
        rho = DENSIDADES[especie]

    if cantidad <= 0 or dap <= 0 or altura <= 0 or rho <= 0:
        st.error("Por favor, asegúrate de que Cantidad, DAP, Altura y Densidad sean mayores a cero.")
        return

    # Cálculo MODIFICADO para obtener el detalle
    agb_uni, bgb_uni, biomasa_uni, co2e_uni, detalle_calculo = calcular_co2_arbol(rho, dap, altura)
    
    biomasa_lote = biomasa_uni * cantidad
    carbono_lote = biomasa_lote * FACTOR_CARBONO 
    co2e_lote = carbono_lote * FACTOR_CO2E 

    nueva_fila = pd.DataFrame([{
        'Especie': especie, 'Cantidad': cantidad, 'DAP (cm)': dap, 'Altura (m)': altura, 'Densidad (ρ)': rho,
        'Biomasa Lote (kg)': biomasa_lote, 'Carbono Lote (kg)': carbono_lote, 'CO2e Lote (kg)': co2e_lote,
        'Detalle Cálculo': detalle_calculo
    }])
    st.session_state.inventario_df = pd.concat([st.session_state.inventario_df, nueva_fila], ignore_index=True)
    st.session_state.total_co2e_kg = st.session_state.inventario_df['CO2e Lote (kg)'].sum()
    
    st.session_state.cantidad_input = 0
    st.session_state.dap_slider = 0.0
    st.session_state.altura_slider = 0.0
    st.session_state.especie_sel = list(DENSIDADES.keys())[0]

def deshacer_ultimo_lote():
    if not st.session_state.inventario_df.empty:
        st.session_state.inventario_df = st.session_state.inventario_df.iloc[:-1]
        st.session_state.total_co2e_kg = st.session_state.inventario_df['CO2e Lote (kg)'].sum()
        st.experimental_rerun()

def limpiar_inventario():
    st.session_state.inventario_df = pd.DataFrame(columns=[
        'Especie', 'Cantidad', 'DAP (cm)', 'Altura (m)', 'Densidad (ρ)',
        'Biomasa Lote (kg)', 'Carbono Lote (kg)', 'CO2e Lote (kg)', 'Detalle Cálculo'
    ])
    st.session_state.total_co2e_kg = 0.0
    st.experimental_rerun()
# -------------------------------------------------

# --- FUNCIÓN DE SIMULACIÓN DE CRECIMIENTO (NUEVA) ---
def simular_crecimiento(df_inicial, anios_simulacion, factor_dap, factor_altura, max_dap=100, max_altura=30):
    
    resultados = []
    
    # Asegurarse de que el DataFrame no esté vacío
    if df_inicial.empty:
        return pd.DataFrame()

    # Obtener la densidad, que no cambia con el crecimiento
    rho = df_inicial['Densidad (ρ)'].iloc[0]
    cantidad_arboles = df_inicial['Cantidad'].iloc[0]

    # Tomar el DAP y Altura inicial
    dap_actual = df_inicial['DAP (cm)'].iloc[0]
    altura_actual = df_inicial['Altura (m)'].iloc[0]

    # Simular año por año
    for anio in range(1, anios_simulacion + 1):
        
        # 1. Aplicar crecimiento (modelando la detención al alcanzar el límite)
        if dap_actual < max_dap:
            dap_actual *= (1 + factor_dap)
        else:
            dap_actual = max_dap
            
        if altura_actual < max_altura:
            altura_actual *= (1 + factor_altura)
        else:
            altura_actual = max_altura
            
        
        # 2. Recalcular CO2e con las nuevas dimensiones
        _, _, _, co2e_uni, _ = calcular_co2_arbol(rho, dap_actual, altura_actual)
        co2e_lote_anual = co2e_uni * cantidad_arboles
        
        # 3. Guardar el resultado
        resultados.append({
            'Año': anio,
            'DAP (cm)': dap_actual,
            'Altura (m)': altura_actual,
            'CO2e Lote (kg)': co2e_lote_anual,
            'CO2e Acumulado (Ton)': sum(r['CO2e Lote (kg)'] for r in resultados) / 1000 if anio > 1 else co2e_lote_anual / 1000
        })

    return pd.DataFrame(resultados)


# -------------------------------------------------
# --- FUNCIÓN PRINCIPAL DE LA APLICACIÓN ---
# -------------------------------------------------
def main_app():
    
    st.title("🌳 Calculadora de Captura de Carbono")
    
    # --- INFORMACIÓN DEL PROYECTO ---
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
    # ¡MODIFICADO: Añadida la cuarta pestaña!
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Cálculo de CO2 (Datos)", "📈 Visor de Gráficos", "🔬 Detalle Técnico", "🚀 Potencial de Crecimiento"])

    # =================================================
    # PESTAÑA 1: CÁLCULO DE CO2 (ENTRADA Y REGISTRO)
    # =================================================
    with tab1:
        st.markdown("## 1. Registro y Acumulación de Inventario")
        # [CÓDIGO DE LA PESTAÑA 1 OMITIDO PARA BREVEDAD, ES EL MISMO QUE ANTES]
        col_input, col_totales = st.columns([1, 2])

        with col_input:
            st.subheader("Entrada de Lote por Especie")
            
            with st.form("lote_form", clear_on_submit=False):
                
                especie_sel = st.selectbox("Especie / Tipo de Árbol", list(DENSIDADES.keys()), key='especie_sel')
                
                if especie_sel == 'Densidad Manual (g/cm³)':
                    st.number_input("Densidad de madera (ρ, g/cm³)", min_value=0.1, max_value=1.5, value=0.5, step=0.01, key='densidad_manual_input')
                else:
                    rho_value = DENSIDADES[especie_sel]
                    st.info(f"Densidad de la madera seleccionada: **{rho_value} g/cm³**")
                
                st.markdown("---")
                
                st.number_input("Cantidad de Árboles (n)", min_value=0, step=1, key='cantidad_input')
                
                st.slider("DAP promedio (cm)", min_value=0.0, max_value=150.0, step=1.0, key='dap_slider', help="Diámetro a la Altura del Pecho. 🌳")
                st.slider("Altura promedio (m)", min_value=0.0, max_value=50.0, step=0.1, key='altura_slider', help="Altura total del árbol. 🌲")
                
                st.form_submit_button("➕ Añadir Lote al Inventario", on_click=agregar_lote)

        with col_totales:
            st.subheader("Inventario Acumulado")
            
            total_arboles_registrados = st.session_state.inventario_df['Cantidad'].sum()
            
            if total_arboles_registrados > 0:
                
                col_deshacer, col_limpiar = st.columns(2)
                col_deshacer.button("↩️ Deshacer Último Lote", on_click=deshacer_ultimo_lote, help="Elimina la última fila añadida a la tabla.")
                col_limpiar.button("🗑️ Limpiar Inventario Total", on_click=limpiar_inventario, help="Elimina todas las entradas y reinicia el cálculo.")

                st.markdown("---")
                
                st.caption("Detalle de los Lotes Añadidos:")
                st.dataframe(st.session_state.inventario_df.drop(columns=['Carbono Lote (kg)', 'Detalle Cálculo']), use_container_width=True, hide_index=True)
                
                st.success("¡Inventario listo! Ve a la pestaña 'Potencial de Crecimiento' para iniciar la simulación.")

            else:
                st.info("Añade el primer lote de árboles para iniciar el inventario.")

    # =================================================
    # PESTAÑA 2: VISOR DE GRÁFICOS Y ANÁLISIS (SIN CAMBIOS)
    # =================================================
    with tab2:
        # [CÓDIGO DE LA PESTAÑA 2 OMITIDO PARA BREVEDAD, ES EL MISMO QUE ANTES]
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

            st.subheader("✅ Indicadores Clave del Proyecto")
            kpi1, kpi2, kpi3 = st.columns(3)
            
            kpi1.metric("Número de Árboles", f"{total_arboles_registrados:.0f}")
            kpi2.metric("Biomasa Total", f"{biomasa_total:.2f} kg")
            kpi3.metric("CO2e Capturado", f"**{co2e_ton:.2f} Toneladas**", delta="Total del Proyecto", delta_color="normal")

            if hectareas > 0:
                co2e_per_ha = total_co2e_kg / hectareas
                st.metric("CO2e por Hectárea", f"**{co2e_per_ha:.2f} kg/ha**", help="CO2 Capturado Total / Hectáreas")
                
            st.markdown("---")
            
            st.subheader("📊 Análisis de Distribución y Captura")
            
            df_graficos = df_inventario.groupby('Especie').agg(
                Total_CO2e_kg=('CO2e Lote (kg)', 'sum'),
                Conteo_Arboles=('Cantidad', 'sum')
            ).reset_index()

            col_graf1, col_graf2 = st.columns(2)

            with col_graf1:
                fig_co2e = px.bar(df_graficos, x='Especie', y='Total_CO2e_kg', 
                                  title='CO2e Capturado por Especie (kg)',
                                  labels={'Especie': 'Especie', 'Total_CO2e_kg': 'CO2e Capturado (kg)'},
                                  color='Total_CO2e_kg',
                                  color_continuous_scale=px.colors.sequential.Viridis)
                st.plotly_chart(fig_co2e, use_container_width=True)
            
            with col_graf2:
                fig_arboles = px.pie(df_graficos, values='Conteo_Arboles', names='Especie', 
                                     title='Conteo de Árboles por Especie',
                                     hole=0.3,
                                     color_discrete_sequence=px.colors.sequential.Plasma) 
                st.plotly_chart(fig_arboles, use_container_width=True)


            st.markdown("---")
            st.subheader("🌍 Equivalencias Ambientales")
            autos_anio = co2e_ton / 4.6 
            hogares_anio = co2e_ton / 10.0
            
            c1, c2 = st.columns(2)
            c1.info(f"🚗 Compensación de **{autos_anio:.1f} autos** fuera de circulación por un año.")
            c2.success(f"🏠 Compensación de **{hogares_anio:.1f} hogares** sin consumo eléctrico por un año.")

    # =================================================
    # PESTAÑA 3: DETALLE TÉCNICO (SIN CAMBIOS)
    # =================================================
    with tab3:
        # [CÓDIGO DE LA PESTAÑA 3 OMITIDO PARA BREVEDAD, ES EL MISMO QUE ANTES]
        st.markdown("## 🔬 Detalle Técnico de los Cálculos (Paso a Paso)")
        st.warning("Esta sección muestra el desglose del cálculo para **un solo árbol** dentro de cada lote. Los valores totales en las otras pestañas están multiplicados por la cantidad de árboles del lote.")

        if st.session_state.inventario_df.empty:
            st.info("Aún no hay lotes de árboles registrados para mostrar el detalle técnico.")
        else:
            
            lotes_info = [
                f"Lote {i+1}: {row['Especie']} ({row['Cantidad']} árboles)" 
                for i, row in st.session_state.inventario_df.iterrows()
            ]
            
            lote_seleccionado_index = st.selectbox(
                "Seleccione el Lote para Inspeccionar el Cálculo:",
                options=range(len(lotes_info)),
                format_func=lambda x: lotes_info[x]
            )
            
            st.markdown("---")
            
            detalle_lote = st.session_state.inventario_df.iloc[lote_seleccionado_index]['Detalle Cálculo']
            
            st.markdown(f"### Detalles del Lote {lote_seleccionado_index + 1}: {lotes_info[lote_seleccionado_index]}")
            st.code(detalle_lote, language='markdown')

    # =================================================
    # PESTAÑA 4: POTENCIAL DE CRECIMIENTO (NUEVA PESTAÑA)
    # =================================================
    with tab4:
        st.markdown("## 🚀 Simulación de Potencial de Captura a Largo Plazo")
        st.warning("Esta simulación se aplica a **un solo lote de árboles** y utiliza una tasa de crecimiento porcentual anual simplificada.")

        if st.session_state.inventario_df.empty:
            st.info("Por favor, registre al menos un lote de árboles en la primera pestaña para iniciar la simulación.")
        else:
            df_inventario = st.session_state.inventario_df
            
            # 1. Selector de Lote
            lotes_info = [
                f"Lote {i+1}: {row['Especie']} ({row['Cantidad']} árboles) - DAP Inicial: {row['DAP (cm)']:.1f} cm" 
                for i, row in df_inventario.iterrows()
            ]
            lote_sim_index = st.selectbox(
                "Seleccione el Lote para la Proyección de Crecimiento:",
                options=range(len(lotes_info)),
                format_func=lambda x: lotes_info[x]
            )
            lote_seleccionado = df_inventario.iloc[[lote_sim_index]]
            especie_sim = lote_seleccionado['Especie'].iloc[0]

            st.markdown("---")
            
            # 2. Parámetros de Simulación
            col_anios, col_factores = st.columns([1, 2])
            
            with col_anios:
                anios_simulacion = st.slider("Años de Proyección", min_value=1, max_value=50, value=20, step=1)
                
            with col_factores:
                
                # Asignar factores iniciales basados en la especie seleccionada
                factor_inicial = FACTORES_CRECIMIENTO.get(especie_sim, FACTORES_CRECIMIENTO['Factor Manual'])
                
                # Inputs para modificar los factores
                st.markdown(f"### Factores de Crecimiento Anual (Especie: **{especie_sim}**)")
                
                factor_dap_input = st.number_input("Tasa de Crecimiento Anual DAP (%)", 
                                                    min_value=0.01, max_value=0.30, 
                                                    value=factor_inicial['DAP'], step=0.01,
                                                    format="%.2f", key='factor_dap_sim')
                
                factor_altura_input = st.number_input("Tasa de Crecimiento Anual Altura (%)", 
                                                      min_value=0.01, max_value=0.30, 
                                                      value=factor_inicial['Altura'], step=0.01,
                                                      format="%.2f", key='factor_alt_sim')
                
                # Límites Máximos
                max_dap_input = st.number_input("DAP Máximo de Madurez (cm)", min_value=10.0, max_value=300.0, value=100.0, step=10.0)
                max_altura_input = st.number_input("Altura Máxima de Madurez (m)", min_value=5.0, max_value=100.0, value=30.0, step=5.0)

            # 3. Ejecutar Simulación
            df_simulacion = simular_crecimiento(
                lote_seleccionado, 
                anios_simulacion, 
                factor_dap_input, 
                factor_altura_input,
                max_dap_input,
                max_altura_input
            )

            st.markdown("---")
            st.subheader(f"Resultados de la Simulación a {anios_simulacion} Años")

            # 4. Visualización de Resultados
            if not df_simulacion.empty:
                
                co2e_final = df_simulacion['CO2e Acumulado (Ton)'].iloc[-1]
                st.metric("Potencial de Captura Total (Toneladas CO2e)", f"**{co2e_final:.2f} Ton**")
                
                # Gráfico de Proyección
                fig_proj = px.line(df_simulacion, x='Año', y='CO2e Acumulado (Ton)', 
                                    title='Captura Acumulada de CO2e vs. Tiempo',
                                    labels={'CO2e Acumulado (Ton)': 'CO2e Acumulado (Ton)', 'Año': 'Año'},
                                    markers=True)
                st.plotly_chart(fig_proj, use_container_width=True)

                st.caption("Detalle Anual de la Simulación:")
                st.dataframe(df_simulacion, use_container_width=True, hide_index=True)


    # --- FOOTER (Común para todas las pestañas) ---
    st.caption("Fórmula: AGB = 0.112 × (ρ × D² × H)^0.916 | Chave et al. (2014) - Bosques Secos. Factores C=0.47, BGB=0.28, CO2e=3.67 (44/12).")

# --- LÍNEA VITAL DE EJECUCIÓN ---
if __name__ == '__main__':
    main_app()