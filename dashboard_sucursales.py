import streamlit as st
import pandas as pd
import requests
from io import BytesIO

st.set_page_config(page_title="Monitor Sucursales", page_icon="🛞", layout="wide")
st.markdown('<h1 style="text-align:center; color:#1f77b4;">🛞 Monitor de Actividad por Sucursal</h1>', unsafe_allow_html=True)

DRIVE_ID = "1J9bDGe1bp0K-3Ms4cx9uI5f3qyq-NBgL"
DRIVE_URL = f"https://drive.google.com/uc?export=download&id={DRIVE_ID}"

@st.cache_data(ttl=3600)
def cargar_datos():
    r = requests.get(DRIVE_URL)
    sheets = pd.read_excel(BytesIO(r.content), sheet_name=None, engine='openpyxl')
    general = sheets['General']
    sm      = sheets['Mestro San Martín']
    beccar  = sheets['Maestro Beccar']
    base    = sheets['Base']
    return general, sm, beccar, base

def limpiar(df):
    df = df.copy()
    df['Meses de stock'] = pd.to_numeric(df['Meses de stock'], errors='coerce')
    df['Promedio'] = pd.to_numeric(df['Promedio'], errors='coerce').fillna(0)
    df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0)
    return df

with st.spinner("Cargando datos desde Drive..."):
    try:
        general, sm, beccar, base = cargar_datos()
        general = limpiar(general)
        sm      = limpiar(sm)
        beccar  = limpiar(beccar)
    except Exception as e:
        st.error(f"Error cargando el archivo: {e}")
        st.stop()

MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

tab1, tab2, tab3, tab4 = st.tabs(["🚨 Alertas", "📊 Actividad Mensual", "🔍 Comparativa Sucursales", "📦 Stock Crítico"])

# ── TAB 1: ALERTAS ─────────────────────────────────────────────────────────────
with tab1:
    st.subheader("🚨 Alertas Automáticas")
    umbral_stock = st.slider("Umbral meses de stock crítico", 1, 6, 3)

    col1, col2, col3 = st.columns(3)

    criticos = general[(general['Meses de stock'] < umbral_stock) & (general['Meses de stock'] > 0) & (general['Promedio'] > 0) & (general['Stock'] > 0)].copy()
    criticos = criticos.sort_values('Meses de stock')
    col1.metric("⚠️ Productos stock crítico (General)", len(criticos))

    sin_stock = general[(general['Stock'] == 0) & (general['Promedio'] > 0)].copy()
    col2.metric("🔴 Sin stock con demanda activa", len(sin_stock))

    no_rotan = general[(general['Promedio'] == 0) & (general['Stock'] > 0)].copy()
    col3.metric("💤 Con stock sin rotación", len(no_rotan))

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**⚠️ Stock crítico — menos de {} meses**".format(umbral_stock))
        if len(criticos) > 0:
            st.dataframe(criticos[['Descripción','Marca ','Promedio','Stock','Meses de stock']].head(20),
                         hide_index=True, use_container_width=True)
        else:
            st.success("Sin productos en alerta.")

    with col_b:
        st.markdown("**🔴 Sin stock pero con demanda**")
        if len(sin_stock) > 0:
            st.dataframe(sin_stock[['Descripción','Marca ','Promedio','Stock']].head(20),
                         hide_index=True, use_container_width=True)
        else:
            st.success("Sin productos en esta situación.")

    st.divider()
    st.markdown("**💤 Con stock pero sin rotación**")
    if len(no_rotan) > 0:
        st.dataframe(no_rotan[['Descripción','Marca ','Stock']].sort_values('Stock', ascending=False),
                     hide_index=True, use_container_width=True, height=400)
    else:
        st.success("Sin productos en esta situación.")

# ── TAB 2: ACTIVIDAD MENSUAL ───────────────────────────────────────────────────
with tab2:
    st.subheader("📊 Actividad Mensual por Sucursal")

    col1, col2 = st.columns(2)
    with col1:
        anio = st.selectbox("Año", sorted(base['Año'].unique(), reverse=True))
    with col2:
        vendedor_opts = ["Todos"] + sorted(base['Vendedor'].dropna().astype(str).unique().tolist())
        vendedor = st.selectbox("Vendedor", vendedor_opts)

    base_f = base[base['Año'] == anio].copy()
    if vendedor != "Todos":
        base_f = base_f[base_f['Vendedor'] == vendedor]

    resumen = base_f.groupby(['Mes2', 'IP Actividad']).agg(
        Cantidad=('Cantidad', 'sum'),
        Importe=('Importe ML', 'sum')
    ).reset_index()

    resumen_pivot = resumen.pivot_table(index='Mes2', columns='IP Actividad', values='Importe', aggfunc='sum').fillna(0)
    resumen_pivot = resumen_pivot.reindex([m for m in [f'0{i}_{n}' if i < 10 else f'{i}_{n}' for i, n in enumerate(MESES, 1)] if m in resumen_pivot.index])

    st.markdown("**Importe por mes**")
    st.bar_chart(resumen_pivot)

    tabla_mes = base_f.groupby('Mes2').agg(
        Unidades=('Cantidad', 'sum'),
        Importe=('Importe ML', 'sum'),
        Clientes=('Cliente', 'nunique')
    ).reset_index()
    tabla_mes.columns = ['Mes', 'Unidades', 'Importe ($)', 'Clientes únicos']
    st.dataframe(tabla_mes, hide_index=True, use_container_width=True)

# ── TAB 3: COMPARATIVA SUCURSALES ─────────────────────────────────────────────
with tab3:
    st.subheader("🔍 Comparativa San Martín vs Beccar")

    comp = sm[['Código Porducto','Descripción','Promedio','Stock','Meses de stock']].merge(
        beccar[['Código Porducto','Promedio','Stock','Meses de stock']],
        on='Código Porducto', suffixes=(' SM', ' Beccar')
    )
    comp = comp[(comp['Promedio SM'] > 0) | (comp['Promedio Beccar'] > 0)]
    comp['Diferencia'] = comp['Promedio Beccar'] - comp['Promedio SM']
    comp = comp.sort_values('Diferencia', key=abs, ascending=False)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🏆 Vende más en Beccar que en SM**")
        mas_beccar = comp[comp['Diferencia'] > 0].head(15)
        st.dataframe(mas_beccar[['Descripción','Promedio SM','Promedio Beccar','Diferencia']].round(2),
                     hide_index=True, use_container_width=True)
    with col2:
        st.markdown("**🏆 Vende más en SM que en Beccar**")
        mas_sm = comp[comp['Diferencia'] < 0].head(15)
        st.dataframe(mas_sm[['Descripción','Promedio SM','Promedio Beccar','Diferencia']].round(2),
                     hide_index=True, use_container_width=True)

    st.divider()
    st.markdown("**Productos que venden en una sucursal pero no en la otra**")
    solo_beccar = comp[(comp['Promedio SM'] == 0) & (comp['Promedio Beccar'] > 0)]
    solo_sm     = comp[(comp['Promedio Beccar'] == 0) & (comp['Promedio SM'] > 0)]
    c1, c2 = st.columns(2)
    c1.markdown(f"Solo en Beccar: **{len(solo_beccar)}** productos")
    c1.dataframe(solo_beccar[['Descripción','Promedio Beccar']].head(10), hide_index=True, use_container_width=True)
    c2.markdown(f"Solo en SM: **{len(solo_sm)}** productos")
    c2.dataframe(solo_sm[['Descripción','Promedio SM']].head(10), hide_index=True, use_container_width=True)

# ── TAB 4: STOCK CRÍTICO ──────────────────────────────────────────────────────
with tab4:
    st.subheader("📦 Stock por Sucursal")

    sucursal = st.selectbox("Ver sucursal", ["General", "San Martín", "Beccar"])
    df_sel = {'General': general, 'San Martín': sm, 'Beccar': beccar}[sucursal]
    df_sel = df_sel[df_sel['Promedio'] > 0].copy()

    umbral2 = st.slider("Mostrar productos con menos de X meses de stock", 1, 24, 6, key="stock2")
    df_fil = df_sel[df_sel['Meses de stock'] < umbral2].sort_values('Meses de stock')

    st.metric("Productos bajo umbral", len(df_fil))
    st.dataframe(df_fil[['Descripción','Marca ','Promedio','Stock','Meses de stock']].round(2),
                 hide_index=True, use_container_width=True, height=500)

    csv_bytes = df_fil.to_csv(index=False, sep=';').encode('utf-8-sig')
    st.download_button("📥 Descargar lista", csv_bytes, f"stock_critico_{sucursal}.csv", "text/csv")
