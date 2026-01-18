import streamlit as st
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random
import os

# ==========================================
# 1. НАСТРОЙКИ СТРАНИЦЫ И СТИЛИ (CSS)
# ==========================================

# Путь к иконке
icon_path = "icons/icon.png"
page_icon = icon_path if os.path.exists(icon_path) else None

st.set_page_config(
    page_title="Ads.txt Validator", 
    layout="wide", 
    page_icon=page_icon
)

# ПРИНУДИТЕЛЬНЫЙ ДИЗАЙН: Только ЧБ + #21aeb3
st.markdown("""
    <style>
    /* 1. Глобальный фон и текст */
    .stApp {
        background-color: #1e1e1e; /* Темно-серый фон */
        color: #e0e0e0;
    }
    
    /* 2. Заголовки */
    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #ffffff !important;
    }
    
    /* 3. Поля ввода (TextArea) */
    .stTextArea textarea {
        background-color: #2d2d2d !important;
        color: #ffffff !important;
        border: 1px solid #444 !important;
    }
    .stTextArea textarea:focus {
        border-color: #21aeb3 !important;
        box-shadow: 0 0 0 1px #21aeb3 !important;
    }
    
    /* 4. Кнопки (Primary) */
    div.stButton > button {
        background-color: #21aeb3 !important;
        color: white !important;
        border: none !important;
        font-weight: bold !important;
        transition: 0.3s;
    }
    div.stButton > button:hover {
        background-color: #1a8a8e !important; /* Чуть темнее при наведении */
        border: 1px solid #ffffff !important;
    }
    div.stButton > button:active {
        background-color: #21aeb3 !important;
    }

    /* 5. Убираем красный цвет из стандартных алертов (Errors/Warnings) */
    div[data-baseweb="notification"] {
        background-color: #2d2d2d !important;
        border: 1px solid #21aeb3 !important; /* Вместо красной рамки - наша */
        color: #ffffff !important;
    }
    /* Иконки внутри алертов */
    div[data-baseweb="notification"] svg {
        fill: #21aeb3 !important;
    }
    
    /* 6. Таблицы */
    div[data-testid="stDataFrame"] {
        background-color: #2d2d2d;
    }
    
    /* 7. Радио-кнопки и чекбоксы */
    .stRadio label, .stCheckbox label {
        color: #e0e0e0 !important;
    }
    /* Акцент при выборе радио-кнопки */
    div[role="radiogroup"] > div[aria-checked="true"] {
        background-color: #21aeb3 !important;
    }

    /* 8. Прогресс-бар */
    .stProgress > div > div > div > div {
        background-color: #21aeb3 !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Ads.txt / App-ads.txt Validator")

# ==========================================
# 2. ФУНКЦИИ ЛОГИКИ (BACKEND)
# ==========================================

LIVE_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': LIVE_UA,
        'Accept': 'text/plain,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Cache-Control': 'no-cache',
    })
    return s

def fetch_file_content(domain, filename):
    session = get_session()
    domain_clean = domain.strip().replace("https://", "").replace("http://", "").split("/")[0]
    
    urls = [
        f"https://{domain_clean}/{filename}",
        f"http://{domain_clean}/{filename}"
    ]
    
    last_error = "Unknown error"

    for url in urls:
        try:
            # Надежная задержка
            time.sleep(random.uniform(0.5, 1.5))
            
            response = session.get(url, timeout=15, allow_redirects=True)
            if response.status_code == 200:
                return response.text, "OK", False
            
            last_error = f"HTTP {response.status_code}"
            
        except requests.exceptions.SSLError:
            try:
                time.sleep(1)
                response = session.get(url, timeout=15, allow_redirects=True, verify=False)
                if response.status_code == 200:
                    return response.text, "OK (SSL Warning)", False
            except Exception as e:
                last_error = str(e)
        except Exception as e:
            last_error = str(e)
            
    return None, f"Not accessible: {last_error}", True

def parse_ads_file(content):
    parsed_lines = []
    if not content:
        return parsed_lines

    for line in content.splitlines():
        clean_line = line.split('#')[0].strip()
        if not clean_line:
            continue
        
        parts = [p.strip() for p in clean_line.split(',')]
        if len(parts) >= 2:
            parsed_lines.append({
                'domain': parts[0].lower(),
                'id': parts[1].lower(),
                'type': parts[2].upper() if len(parts) > 2 else None,
            })
    return parsed_lines

def parse_reference_line(line):
    parts = [p.strip() for p in line.split(',')]
    if len(parts) < 2:
        return None
    
    return {
        'domain': parts[0].lower(),
        'id': parts[1].lower(),
        'type': parts[2].upper() if len(parts) > 2 else None,
        'original': line
    }

def validate_domain(target_domain, filename, references):
    content, status_msg, is_error = fetch_file_content(target_domain, filename)
    
    results = []
    
    if is_error:
        for ref in references:
            results.append({
                "URL": target_domain,
                "File": filename,
                "Result": "Error",
                "Details": status_msg,
                "Reference": ref['original']
            })
        return results

    file_records = parse_ads_file(content)
    
    for ref in references:
        ref_domain = ref['domain']
        ref_id = ref['id']
        ref_type = ref['type']
        
        match_status = "Not found"
        details = "No matching Domain+ID pair"
        
        for record in file_records:
            if record['domain'] == ref_domain and record['id'] == ref_id:
                if not ref_type:
                    match_status = "Valid"
                    details = "Matched by Domain + ID"
                    break
                
                if record['type'] == ref_type:
                    match_status = "Valid"
                    details = "Full match"
                    break
                else:
                    match_status = "Partially matched"
                    details = f"Type mismatch: found {record['type']}, expected {ref_type}"
                    # Не прерываем, ищем дальше
        
        results.append({
            "URL": target_domain,
            "File": filename,
            "Result": match_status,
            "Details": details,
            "Reference": ref['original']
        })
        
    return results

# ==========================================
# 3. ИНТЕРФЕЙС (UI)
# ==========================================

st.subheader("Settings")
col_settings, col_dummy = st.columns([1, 4])
with col_settings:
    file_type = st.radio(
        "File Type",
        ("ads.txt", "app-ads.txt")
    )

st.markdown("---")

st.subheader("Input Data")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Target Websites**")
    target_input = st.text_area(
        "Label hidden", 
        height=300,
        placeholder="example.com\nmygame.site",
        label_visibility="collapsed"
    )

with col2:
    st.markdown("**Reference Lines (Rules)**")
    ref_input = st.text_area(
        "Label hidden", 
        height=300, 
        placeholder="onetag.com, 5d0d72448d8bfb0, DIRECT",
        label_visibility="collapsed"
    )

start_btn = st.button("Start Validation")

# ==========================================
# 4. ОБРАБОТКА И ВЫВОД (EXECUTION)
# ==========================================

if start_btn:
    if not target_input or not ref_input:
        st.error("Please fill both windows.")
    else:
        targets = [t.strip() for t in target_input.splitlines() if t.strip()]
        
        references = []
        raw_refs = [r.strip() for r in ref_input.splitlines() if r.strip()]
        for r in raw_refs:
            parsed = parse_reference_line(r)
            if parsed:
                references.append(parsed)

        if not references:
            st.warning("No valid reference lines found.") # Теперь это будет серым, не желтым/красным
            st.stop()

        progress_bar = st.progress(0)
        status_text = st.empty()
        all_results = []
        
        # 5 потоков для надежности
        MAX_WORKERS = 5 
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {
                executor.submit(validate_domain, url, file_type, references): url 
                for url in targets
            }
            
            for i, future in enumerate(as_completed(future_to_url)):
                url = future_to_url[future]
                try:
                    data = future.result()
                    all_results.extend(data)
                except Exception as e:
                    all_results.append({
                        "URL": url, "File": file_type, 
                        "Result": "System Error", "Details": str(e), 
                        "Reference": "-"
                    })
                
                progress = (i + 1) / len(targets)
                progress_bar.progress(progress)
                status_text.text(f"Checking: {url} ...")

        progress_bar.empty()
        status_text.empty()
        
        st.markdown("---")
        st.subheader("Results")
        
        df = pd.DataFrame(all_results)
        cols_order = ["URL", "File", "Result", "Details", "Reference"]
        df = df[cols_order]

        # Логика цветов таблицы (Убрали красный!)
        def color_status(val):
            if val == "Valid":
                # Успех: Наш фирменный цвет
                return 'background-color: #21aeb3; color: white' 
            elif val == "Partially matched":
                # Частично: Черный фон, цветной текст
                return 'background-color: #000000; color: #21aeb3; font-weight: bold'
            elif val == "Not found":
                # Не найдено: Темно-серый (нейтральный)
                return 'background-color: #383838; color: #aaaaaa'
            elif val == "Error":
                # Ошибка сети: Тоже серый, но другой оттенок
                return 'background-color: #2d2d2d; color: #888888'
            return ''

        st.dataframe(
            df.style.map(color_status, subset=['Result']),
            use_container_width=True,
            height=600
        )
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="report.csv",
            mime="text/csv",
        )
