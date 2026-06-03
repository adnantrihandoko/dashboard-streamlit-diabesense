import streamlit as st
import pandas as pd
import plotly.express as px
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

st.set_page_config(page_title="DiabeSense Dashboard", layout="wide")
st.title("📊 DiabeSense - Dashboard Analisis Risiko Diabetes")
st.caption("Terhubung ke database: Neon.tech (Cloud) Production | Data screening risiko diabetes")

# ==================== FUNGSI MAPPING ====================
def map_age_group(age_group):
    """Mapping age_group ke rentang usia"""
    if pd.isna(age_group):
        return 'Tidak diketahui'
    age_map = {
        1: '<30',
        2: '30-39',
        3: '40-49', 
        4: '50-59',
        5: '60-69',
        6: '70-79',
        7: '80+',
        8: 'Tidak diketahui',
        9: 'Tidak diketahui',
        13: 'Tidak diketahui'
    }
    return age_map.get(age_group, 'Tidak diketahui')

def map_gender(gender):
    """Mapping gender dari 0/1 ke teks"""
    if pd.isna(gender):
        return 'Tidak diketahui'
    return 'Perempuan' if gender == 1 else 'Laki-laki'

def map_risk(risk):
    """Mapping risk dari low/medium/high ke Bahasa Indonesia"""
    if pd.isna(risk):
        return 'Tidak diketahui'
    risk_map = {
        'low': 'Rendah',
        'medium': 'Sedang',
        'high': 'Tinggi'
    }
    return risk_map.get(risk, risk)

def map_boolean(value):
    """Mapping boolean 0/1 ke Ya/Tidak"""
    if pd.isna(value):
        return 'Tidak diketahui'
    return 'Ya' if value == 1 else 'Tidak'

# ==================== LOAD DATA ====================
@st.cache_data(ttl=60)
def load_data():
    """Load data dari database dengan LEFT JOIN"""
    conn = psycopg2.connect(DATABASE_URL)
    
    # Menggunakan LEFT JOIN agar data 31 Mei yang tidak punya assessment_inputs tetap muncul
    query = """
    SELECT 
        a.created_at,
        a.id AS assessment_id,
        ai.age_group,
        ai.gender,
        ai.bmi_real AS bmi,
        ai.hypertension,
        ai.high_cholesterol,
        ai.exercise,
        ai.smoker,
        pr.risk,
        pr.probability,
        pr.model_version
    FROM assessments a
    LEFT JOIN assessment_inputs ai ON a.id = ai.assessment_id
    LEFT JOIN prediction_results pr ON a.id = pr.assessment_id
    WHERE pr.risk IS NOT NULL
    ORDER BY a.created_at DESC
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    if not df.empty:
        # Apply mapping
        df['age_range'] = df['age_group'].apply(map_age_group)
        df['gender_text'] = df['gender'].apply(map_gender)
        df['risk_text'] = df['risk'].apply(map_risk)
        df['risk_level'] = df['risk']
        
        # Konversi nilai numerik ke keterangan
        df['hypertension_text'] = df['hypertension'].apply(map_boolean)
        df['high_cholesterol_text'] = df['high_cholesterol'].apply(map_boolean)
        df['smoker_text'] = df['smoker'].apply(map_boolean)
        df['exercise_text'] = df['exercise'].apply(map_boolean)
        
        # Format created_at ke string yang lebih rapi
        df['created_at_str'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
    
    return df

# ==================== LOAD DATA ====================
try:
    df = load_data()
    
    if df.empty:
        st.warning("⚠️ Belum ada data assessment. Silakan lakukan screening terlebih dahulu.")
        st.info("Data akan muncul setelah user mengisi form screening melalui aplikasi web.")
        st.stop()
    
    # ==================== METRICS UTAMA ====================
    st.subheader("📈 Ringkasan Assessment")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total = len(df)
    with col1:
        st.metric("📋 Total Assessment", total)
    
    # Hitung risiko (abaikan yang Tidak diketahui)
    risk_valid = df[df['risk_text'] != 'Tidak diketahui']
    if not risk_valid.empty:
        risk_counts = risk_valid['risk_text'].value_counts()
        high = risk_counts.get('Tinggi', 0)
        medium = risk_counts.get('Sedang', 0)
        low = risk_counts.get('Rendah', 0)
        
        with col2:
            st.metric("🔴 Risiko Tinggi", f"{high} ({high/total*100:.1f}%)")
        with col3:
            st.metric("🟠 Risiko Sedang", f"{medium} ({medium/total*100:.1f}%)")
        with col4:
            st.metric("🟢 Risiko Rendah", f"{low} ({low/total*100:.1f}%)")
    else:
        with col2:
            st.metric("🔴 Risiko Tinggi", "0")
        with col3:
            st.metric("🟠 Risiko Sedang", "0")
        with col4:
            st.metric("🟢 Risiko Rendah", "0")
    
    # ==================== SIDEBAR FILTER ====================
    st.sidebar.header("🔍 Filter Data")
    
    # Filter jenis kelamin
    gender_options = df['gender_text'].unique().tolist()
    selected_genders = st.sidebar.multiselect("Jenis Kelamin:", gender_options, default=gender_options)
    df_filtered = df[df['gender_text'].isin(selected_genders)]
    
    # Filter risiko
    risk_options = df['risk_text'].unique().tolist()
    if 'Tidak diketahui' in risk_options:
        risk_options.remove('Tidak diketahui')
    selected_risks = st.sidebar.multiselect("Kategori Risiko:", risk_options, default=risk_options)
    df_filtered = df_filtered[df_filtered['risk_text'].isin(selected_risks)]
    
    # Filter rentang usia
    age_options = [age for age in df['age_range'].unique() if age != 'Tidak diketahui']
    selected_ages = st.sidebar.multiselect("Rentang Usia:", age_options, default=age_options)
    df_filtered = df_filtered[df_filtered['age_range'].isin(selected_ages)]
    
    # ==================== VISUALISASI ====================
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("🥧 Distribusi Risiko Keseluruhan")
        risk_valid_filtered = df_filtered[df_filtered['risk_text'] != 'Tidak diketahui']
        if not risk_valid_filtered.empty:
            risk_counts = risk_valid_filtered['risk_text'].value_counts().reset_index()
            risk_counts.columns = ['Kategori Risiko', 'Jumlah']
            fig_pie = px.pie(
                risk_counts, 
                values='Jumlah', 
                names='Kategori Risiko',
                title='Proporsi Risiko Diabetes',
                color='Kategori Risiko',
                color_discrete_map={'Tinggi': '#e74c3c', 'Sedang': '#f39c12', 'Rendah': '#2ecc71'}
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Belum ada data risiko yang valid")
    
    with col_right:
        st.subheader("📊 Jumlah Assessment per Rentang Usia")
        age_valid = df_filtered[df_filtered['age_range'] != 'Tidak diketahui']
        if not age_valid.empty:
            age_counts = age_valid['age_range'].value_counts().sort_index().reset_index()
            age_counts.columns = ['Rentang Usia', 'Jumlah']
            fig_bar = px.bar(
                age_counts, 
                x='Rentang Usia', 
                y='Jumlah',
                title='Assessment per Rentang Usia',
                color='Jumlah',
                text='Jumlah',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Belum ada data usia yang valid")
    
    # Proporsi risiko per usia
    st.subheader("📉 Proporsi Risiko per Rentang Usia")
    age_risk_valid = df_filtered[(df_filtered['age_range'] != 'Tidak diketahui') & (df_filtered['risk_text'] != 'Tidak diketahui')]
    if not age_risk_valid.empty:
        risk_by_age = pd.crosstab(age_risk_valid['age_range'], age_risk_valid['risk_text'])
        fig_stacked = px.bar(
            risk_by_age,
            title='Distribusi Risiko per Rentang Usia',
            barmode='stack',
            labels={'value': 'Jumlah', 'age_range': 'Rentang Usia', 'variable': 'Kategori Risiko'},
            color_discrete_map={'Tinggi': '#e74c3c', 'Sedang': '#f39c12', 'Rendah': '#2ecc71'}
        )
        fig_stacked.update_layout(legend_title_text='Kategori Risiko')
        st.plotly_chart(fig_stacked, use_container_width=True)
    else:
        st.info("Belum ada data yang cukup untuk menampilkan proporsi risiko per usia")
    
    # ==================== DATA LENGKAP ====================
    st.subheader("📋 Data Lengkap Assessment")
    
    # Siapkan kolom untuk ditampilkan
    display_df = df_filtered[[
        'created_at_str', 'gender_text', 'age_range', 'bmi', 
        'hypertension_text', 'high_cholesterol_text', 
        'smoker_text', 'exercise_text', 'risk_text', 'probability'
    ]].copy()
    
    display_df.columns = [
        'Waktu', 'Jenis Kelamin', 'Rentang Usia', 'BMI',
        'Hipertensi', 'Kolesterol Tinggi', 'Perokok', 'Olahraga',
        'Risiko', 'Probabilitas'
    ]
    
    # Format probabilitas ke persentase
    display_df['Probabilitas'] = display_df['Probabilitas'].apply(
        lambda x: f"{x*100:.1f}%" if pd.notna(x) else '-'
    )
    
    st.dataframe(display_df, use_container_width=True)
    
    # ==================== DOWNLOAD BUTTON ====================
    csv = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Data (CSV)",
        data=csv,
        file_name="diabesense_assessment_data.csv",
        mime="text/csv"
    )
    
    # ==================== INFO ====================
    with st.expander("ℹ️ Info Database"):
        st.write(f"**Total data di database:** {len(df)} baris")
        st.write(f"**Data setelah filter:** {len(df_filtered)} baris")
        
        # Tampilkan rentang tanggal
        if 'created_at' in df.columns:
            min_date = pd.to_datetime(df['created_at']).min()
            max_date = pd.to_datetime(df['created_at']).max()
            st.write(f"**Periode data:** {min_date.strftime('%Y-%m-%d %H:%M')} s/d {max_date.strftime('%Y-%m-%d %H:%M')}")
        
        # Tampilkan statistik singkat
        st.write("**Statistik data:**")
        st.write(f"- Data dengan gender diketahui: {len(df[df['gender_text'] != 'Tidak diketahui'])} baris")
        st.write(f"- Data dengan usia diketahui: {len(df[df['age_range'] != 'Tidak diketahui'])} baris")
        st.write(f"- Data dengan risiko valid: {len(df[df['risk_text'] != 'Tidak diketahui'])} baris")
    
except Exception as e:
    st.error(f"❌ Error: {str(e)}")
    st.info("""
    **Troubleshooting:**
    1. Pastikan koneksi internet stabil
    2. Cek apakah database cloud berjalan
    3. Pastikan environment variable DATABASE_URL sudah benar
    4. Coba jalankan: `python cek_database.py` untuk verifikasi
    """)