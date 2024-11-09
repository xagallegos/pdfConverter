import streamlit as st
import pdfplumber
import pandas as pd
from io import StringIO, BytesIO
import requests
import datetime as dt
from datetime import datetime, timedelta
import json
import csv
from stqdm import stqdm

def save_json(data: list):
    buffer = BytesIO()
    buffer.write(json.dumps(data, ensure_ascii=False, indent=4).encode('utf-8'))
    buffer.seek(0)
    return buffer


def save_csv(data: list):
    text_buffer = StringIO()
    fieldnames = data[0].keys()
    writer = csv.DictWriter(text_buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)

    buffer = BytesIO()
    buffer.write(text_buffer.getvalue().encode("utf-8"))
    buffer.seek(0)
    return buffer


def fetch_and_filter_data(start_date: datetime, end_date: datetime, keys: list[str]) -> list:
    """
    Fetches data from the API from start_date to end_date, filters it by 'clavesih',
    and saves each day's filtered data into a JSON file.

    Parameters:
    - start_date (datetime): The starting date as a datetime object.
    - end_date (datetime): The ending date as a datetime object.
    - output_dir (str): Directory where JSON files will be saved.

    Returns:
    - historic_data (list)
    """
    delta = timedelta(days=1)

    current_date = start_date
    historic_data = []

    date_range = (end_date - current_date).days + 1
    pb = stqdm(total=date_range, desc="Progress")
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        url = f"https://sinav30.conagua.gob.mx:8080/PresasPG/presas/reporte/{date_str}"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Filter the data by 'clavesih'
            filtered_data = [entry for entry in data if entry.get('clavesih') in keys]

            if filtered_data:
                # Save the filtered data to a JSON file
                historic_data.extend(filtered_data)
                #print(f"\tSuccesfully fetched data for {date_str}")
            else:
                pass
                #print(f"No matching data for {date_str}. Data not fetched.")

        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for {date_str}: {e}")
        except ValueError:
            print(f"Invalid JSON received for {date_str}")
        except IOError as e:
            print(f"Error saving data for {date_str}: {e}")

        current_date += delta
        pb.update(1)

    return historic_data


def scraping_tab():
    date_range = st.date_input("Rango de fechas a extraer",
                                            value = (datetime.now() - timedelta(days=31), datetime.now()),
                                            format = "DD/MM/YYYY")
    
    col1, col2 = st.columns(2)

    with col1:
        selected_keys = st.multiselect("Claves", options=['CPEJL','CRNJL','CRTJL','CUQJL',
                                                                            'EGCJL','LCLJL','LDCJL','REDJL',
                                                                            'SA1JL','SRSJL','TCTJL','ACHZC',
                                                                            'ESLJL','ESTJL','HRTJL','POLJL',
                                                                            'TENJL','TMLJL','TRJCM','VCVJL',
                                                                            'VEGJL','BBAJL','CHLJL','CHLMC'])
    with col2:
        file_format = st.radio("Formato", options=["CSV", "JSON"], horizontal=True)


    if st.button("Extraer Datos:"):
        if len(date_range) != 2:
            st.error("Selecciona un rango de fechas")
        elif not selected_keys:
            st.warning("Selecciona claves para filtrar")
        elif date_range[1] - date_range[0] > timedelta(days=365):
            st.error("Selecciona un rango menor o igual a 1 año.")
        else:
            # Fetch data
            data = fetch_and_filter_data(start_date=date_range[0], end_date=date_range[1], keys=selected_keys)
            
            # Save data according to the selected file format
            if file_format == "CSV":
                file = save_csv(data)
            else:
                file = save_json(data)
                
            # Provide a download link for the saved file
            filename = "data.csv" if file_format == "CSV" else "data.json"
            st.download_button(label="Descargar",
                               data=file,
                               file_name=filename)


@st.cache_data
def save_xlsx(dfs: list[pd.DataFrame]):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer) as writer:
        for i,df in enumerate(dfs):
            df.to_excel(writer, sheet_name=f"Sheet{i+1}")
    buffer.seek(0)
    return buffer


def format(df: pd.DataFrame, template: str) -> list[pd.DataFrame]:
    try:
        if template == option1:
            if df.shape[1] != 13:
                raise KeyError(f"Expected 13 columnns, got {df.shape[1]}")
            
            namo, almac, llen = 2, 4, -1

            df.drop(df.shape[0]-1, inplace=True)

            df.iloc[:, almac] = df.iloc[:, almac].astype(float)
            df.iloc[:, namo] = df.iloc[:, namo].astype(float)

            df.iloc[:, llen] = (df.iloc[:, almac] / df.iloc[:, namo] * 100).round(2)

            n = df.shape[0] 
            df.loc[n] = None

            df.iloc[n, almac] = round(df.iloc[:, almac].sum(), 3)
            df.iloc[n, llen] = round(df.iloc[:, llen].mean(), 1)

            output = [df]

        elif template == option2:
            if df.shape[1] != 19:
                raise KeyError(f"Expected 19 columnns, got {df.shape[1]}")
            
            df1 = df.copy().iloc[:,:5]
            df1.dropna(how="all", inplace=True)

            sep = df.iloc[:,12:].isna().all(axis=1).idxmax()
            df2 = pd.concat([df.iloc[:,5:12], df.iloc[:sep,12:]]).copy().dropna(how="all").reset_index(drop=True)

            df3 = df.iloc[sep:,12:].copy().dropna(how="all").reset_index(drop=True).drop([0,1]).reset_index(drop=True)

            output = [df1, df2, df3]

        else:
            output = []

        return output
    except KeyError as e:
        st.error(f"El archivo no sigue el formato esperado para el {template}")
        #st.write(F"Detalles: {e}")
        return []


def converter_tab():
    template = st.radio("Selecciona el tipo de archivo",
                        options = [option1, option2],
                        index=None)

    uploaded_file = st.file_uploader("Selecciona el archivo a convertir",
                                        help = "help is gonna be written here",
                                        type="pdf", accept_multiple_files=False)
    file_name = uploaded_file.name[:-4] if uploaded_file else None

    click = st.button("Convertir", disabled = (not uploaded_file) and (template is None))

    if click:
        if file_name in st.session_state:
            st.warning("Archivo ya convertido, puedes volver a descargarlo.\n\
                       Si no se trata de un archivo convertido previamente, borra el caché.")
        else:
            pdf = pdfplumber.open(uploaded_file)
            table = pdf.pages[0].extract_table()

            df = pd.DataFrame(table[2:], columns=table[0:2])
            index = df.columns
            df.columns = pd.MultiIndex.from_arrays([pd.Series(index.get_level_values(0)).ffill().str.replace("\n", " "),
                                            index.get_level_values(1).str.replace("\n", " ")])
            
            df = df.replace("", None).map(lambda x: x.replace("\n", " ") if isinstance(x, str) else x)

            output_tables = format(df, template)
            if output_tables:
                st.session_state[file_name] = output_tables

    if file_name in st.session_state:
        cola, colb, colc = st.columns([0.6,0.2,0.2])
        with cola:
            st.markdown(f":material/table_chart: {file_name}")
        with colc:
            preview = st.toggle(label="Preview", value=False, key=f"preview_{file_name})")
        with colb:
            st.download_button(label="Descargar",
                                data = save_xlsx(st.session_state[file_name]),
                                key = f"download_{file_name})",
                                file_name = f"{file_name}.xlsx",
                                use_container_width=True)

        if preview:
            cols = st.columns(len(st.session_state[file_name]))
            for col, t in zip(cols, st.session_state[file_name]):
                with col:
                    st.write(t)


st.set_page_config(page_title="PDF Converter", layout="wide")

tab1, tab2, tab3 = st.tabs(["Scraping", "Convertidor PDF", "-"])

with tab1:
    st.title("Data Scraping")
    scraping_tab()

with tab2:
    st.title("PDF Converter")

    option1 = "Reporte de Presas de Jalisco"
    option2 = "Reporte de Hidrometría y Climatología"

    converter_tab()