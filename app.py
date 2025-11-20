import streamlit as st
import pandas as pd
from datetime import datetime
import os
import re
import qrcode
from io import BytesIO

# Función segura para forzar rerun sólo si la API existe
def safe_rerun():
    """Intenta forzar un rerun si la función está disponible en la versión de Streamlit."""
    if hasattr(st, "experimental_rerun"):
        try:
            st.experimental_rerun()
        except Exception:
            # Silenciar cualquier error para evitar romper la app
            pass

# ==============================
# CONFIGURACIÓN GENERAL
# ==============================
st.set_page_config(
    page_title="MiniClub Mini Golf",
    page_icon="⛳",
    layout="centered"
)

USERS_FILE = "usuarios.csv"
SCORES_FILE = "scores.csv"

# ==============================
# CONFIG GOOGLE SHEETS
# ==============================
USE_GOOGLE_SHEETS = True
GOOGLE_CREDS_FILE = "service_account.json"
GOOGLE_SHEET_NAME = "MiniClub_Scores"
GOOGLE_WORKSHEET = "Scores"

# Intentamos importar librerías de Google Sheets
if USE_GOOGLE_SHEETS:
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        USE_GOOGLE_SHEETS = False


# ==============================
# INICIALIZAR ARCHIVOS LOCALES
# ==============================
def init_files():
    """Crea archivos CSV de usuarios y scores si no existen."""
    # Usuarios
    if not os.path.exists(USERS_FILE):
        cols_users = ["email", "nombre", "nickname", "fecha_registro"]
        pd.DataFrame(columns=cols_users).to_csv(USERS_FILE, index=False)

    # Scores
    if not os.path.exists(SCORES_FILE):
        cols_scores = ["fecha", "email", "nombre_mostrar"] + \
                      [f"hoyo_{i}" for i in range(1, 15)] + ["total"]
        pd.DataFrame(columns=cols_scores).to_csv(SCORES_FILE, index=False)


init_files()


# ==============================
# FUNCIONES GOOGLE SHEETS
# ==============================
def get_gsheet_client():
    """Devuelve cliente de gspread si está configurado."""
    if not USE_GOOGLE_SHEETS:
        return None
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        creds = Credentials.from_service_account_file(
            GOOGLE_CREDS_FILE,
            scopes=scopes
        )

        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.sidebar.warning(f"Error conectando a Google Sheets: {e}")
        return None


def append_to_gsheet(row_list):
    """Agrega una fila a Google Sheets (si está habilitado)."""
    if not USE_GOOGLE_SHEETS:
        return
    client = get_gsheet_client()
    if client is None:
        return
    try:
        sheet = client.open(GOOGLE_SHEET_NAME).worksheet(GOOGLE_WORKSHEET)
        sheet.append_row(row_list, value_input_option="USER_ENTERED")
    except Exception as e:
        st.sidebar.warning(f"Error al escribir en Google Sheets: {e}")


# ==============================
# SESIÓN Y USUARIOS
# ==============================
if "user" not in st.session_state:
    st.session_state["user"] = None  # dict con email, nombre, nickname

def load_users():
    try:
        return pd.read_csv(USERS_FILE)
    except Exception:
        return pd.DataFrame(columns=["email", "nombre", "nickname", "fecha_registro"])


def save_users(df):
    df.to_csv(USERS_FILE, index=False)


def login_or_register(email, nombre="", nickname=""):
    """Crea o actualiza usuario y lo guarda en sesión."""
    df = load_users()
    email = email.strip().lower()

    if email in df["email"].values:
        # Usuario existente: actualizamos datos opcionales
        user_row = df[df["email"] == email].iloc[0].to_dict()
        if nombre.strip():
            user_row["nombre"] = nombre.strip()
        if nickname.strip():
            user_row["nickname"] = nickname.strip()
        df.loc[df["email"] == email, ["nombre", "nickname"]] = [
            user_row.get("nombre", ""), user_row.get("nickname", "")
        ]
        save_users(df)
    else:
        # Usuario nuevo
        fecha_registro = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nueva = {
            "email": email,
            "nombre": nombre.strip(),
            "nickname": nickname.strip(),
            "fecha_registro": fecha_registro
        }
        df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
        save_users(df)
        user_row = nueva

    st.session_state["user"] = user_row
    return user_row


def login_user(email):
    """Loguea un usuario existente (sin crear)."""
    df = load_users()
    email = email.strip().lower()
    if email in df["email"].values:
        user_row = df[df["email"] == email].iloc[0].to_dict()
        st.session_state["user"] = user_row
        return user_row
    return None


def logout_user():
    """Cierra sesión y limpia keys relevantes."""
    st.session_state["user"] = None
    # limpiar inputs de hoyos si existen
    for i in range(1, 15):
        key = f"hoyo_{i}"
        if key in st.session_state:
            del st.session_state[key]
    # solicitar cambio de menú al próximo rerun (no tocar 'menu' si el widget ya existe)
    st.session_state["menu_request"] = "Iniciar sesión / Registro"
    st.sidebar.info("Sesión cerrada.")
    safe_rerun()


def get_display_name(user):
    """Determina cómo mostrar el nombre del usuario."""
    if not user:
        return ""
    if isinstance(user, dict) and user.get("nickname"):
        return user["nickname"]
    if isinstance(user, dict) and user.get("nombre"):
        return user["nombre"]
    if isinstance(user, dict):
        return user.get("email", "")
    return ""


# util: validación básica de email
EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")


# ==============================
# HEADER CON LOGO
# ==============================
logo_path = "logo_miniclub.png"  # pon aquí el nombre de tu archivo de logo

cols_header = st.columns([1, 3])
with cols_header[0]:
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
with cols_header[1]:
    st.title("MiniClub ⛳")
    st.write("Portal de jugadores y sistema de puntaje para Mini Golf (14 hoyos).")

st.divider()


# ==============================
# SIDEBAR (USUARIO + MENÚ)
# ==============================
st.sidebar.header("Cuenta")

if st.session_state["user"] is None:
    st.sidebar.info("No hay sesión iniciada.")
else:
    u = st.session_state["user"]
    st.sidebar.success(f"Conectado: {get_display_name(u)}")
    st.sidebar.write(u.get("email", ""))
    if st.sidebar.button("Cerrar sesión"):
        logout_user()

st.sidebar.header("Menú")

# Si hay una solicitud de cambio de menú la aplicamos antes de crear el widget
if "menu_request" in st.session_state:
    st.session_state["menu"] = st.session_state.pop("menu_request")

# asegurar que existe la key en session_state para poder controlarla desde el código
if "menu" not in st.session_state:
    st.session_state["menu"] = "Iniciar sesión / Registro"

# vinculamos el radio a session_state usando key="menu"
menu = st.sidebar.radio(
    "Ir a:",
    ["Iniciar sesión / Registro", "Registrar puntaje", "Ver ranking"],
    key="menu"
)


# ==============================
# PANTALLA: LOGIN / REGISTRO (pestañas)
# ==============================
if menu == "Iniciar sesión / Registro":
    st.subheader("Acceso")

    tab1, tab2 = st.tabs(["Entrar", "Registrarse"])

    with tab1:
        st.write("Si ya estás registrado entra con tu correo.")
        with st.form("form_entrar", clear_on_submit=False):
            email_login = st.text_input("Correo electrónico")
            submit_login = st.form_submit_button("Entrar")
            if submit_login:
                if not email_login.strip():
                    st.error("Ingresa tu correo electrónico.")
                elif not EMAIL_RE.match(email_login.strip()):
                    st.error("Correo electrónico inválido.")
                else:
                    user = login_user(email_login)
                    if user:
                        st.success(f"Bienvenido, {get_display_name(user)}")
                        # pedir cambio de pantalla de forma segura
                        st.session_state["menu_request"] = "Registrar puntaje"
                        safe_rerun()
                    else:
                        st.warning("Usuario no encontrado. Ve a 'Registrarse' para crear una cuenta.")

    with tab2:
        st.write("Crea una nueva cuenta (solo correo + opcionales).")
        with st.form("form_registrar", clear_on_submit=True):
            email_reg = st.text_input("Correo electrónico *", key="reg_email")
            nombre_reg = st.text_input("Nombre (opcional)", key="reg_nombre")
            nick_reg = st.text_input("Nickname / apodo (opcional)", key="reg_nick")
            submit_reg = st.form_submit_button("Registrarme")
            if submit_reg:
                if not email_reg.strip():
                    st.error("El correo electrónico es obligatorio.")
                elif not EMAIL_RE.match(email_reg.strip()):
                    st.error("Correo electrónico inválido.")
                else:
                    user = login_or_register(email_reg, nombre_reg, nick_reg)
                    st.success(f"Usuario creado. Bienvenido, {get_display_name(user)}")
                    # pedir cambio de pantalla de forma segura
                    st.session_state["menu_request"] = "Registrar puntaje"
                    safe_rerun()

# Bloquear otras pantallas si no hay usuario logueado
if menu != "Iniciar sesión / Registro" and st.session_state["user"] is None:
    st.warning("Primero inicia sesión o regístrate en la pestaña 'Iniciar sesión / Registro'.")
    st.stop()

user = st.session_state.get("user") if isinstance(st.session_state.get("user"), dict) else None
display_name = get_display_name(user)
user_email = user.get("email") if user else ""


# ==============================
# PANTALLA: REGISTRAR PUNTAJE
# ==============================
if menu == "Registrar puntaje":
    st.subheader("📝 Registrar puntaje de partida")
    st.write(f"Jugador: **{display_name}** ({user_email})")

    st.info("Ingresa los golpes por cada hoyo (1 a 14). Usa el formulario para guardar.")
    golpes = []
    cols = st.columns(4)

    # Usar form para agrupar inputs
    with st.form("form_puntaje"):
        for i in range(1, 15):
            col = cols[(i - 1) % 4]
            with col:
                valor = st.number_input(
                    f"Hoyo {i}",
                    min_value=1,
                    max_value=20,
                    value=3,
                    key=f"hoyo_{i}"
                )
                golpes.append(valor)

        submit_puntaje = st.form_submit_button("Guardar puntaje")
        if submit_puntaje:
            total = sum(golpes)
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Guardar en CSV local
            df_scores = pd.read_csv(SCORES_FILE)
            nueva_fila = [fecha, user_email, display_name] + golpes + [total]
            df_scores.loc[len(df_scores)] = nueva_fila
            df_scores.to_csv(SCORES_FILE, index=False)

            # Guardar también en Google Sheets (si está activo)
            append_to_gsheet(nueva_fila)

            st.success(f"Puntaje guardado. Total: **{total} golpes** para {display_name}.")

    st.markdown("Si querés cerrar sesión rápido, usá el botón en la barra lateral.")


# ==============================
# PANTALLA: VER RANKING
# ==============================
elif menu == "Ver ranking":
    st.subheader("🏆 Ranking de jugadores")

    df = pd.read_csv(SCORES_FILE)

    if df.empty:
        st.info("Todavía no hay partidas registradas.")
    else:
        df["fecha_dt"] = pd.to_datetime(df["fecha"])

        filtro = st.selectbox(
            "Mostrar ranking de:",
            ["Histórico", "Hoy", "Últimos 7 días", "Últimos 30 días"]
        )

        ahora = datetime.now()
        if filtro == "Hoy":
            df = df[df["fecha_dt"].dt.date == ahora.date()]
        elif filtro == "Últimos 7 días":
            df = df[df["fecha_dt"] >= ahora - pd.Timedelta(days=7)]
        elif filtro == "Últimos 30 días":
            df = df[df["fecha_dt"] >= ahora - pd.Timedelta(days=30)]

        if df.empty:
            st.info("No hay registros en este rango de tiempo.")
        else:
            df = df.sort_values("total")  # menor total = mejor posición
            df["pos"] = range(1, len(df) + 1)

            mostrar = df[["pos", "fecha", "nombre_mostrar", "email", "total"]].head(50)
            st.write("Menor número de golpes = mejor posición.")
            st.dataframe(mostrar, hide_index=True)

# ==============================
# ACCESO RÁPIDO (QR)
# ==============================
import qrcode
from io import BytesIO

def make_qr_bytes(url: str, box_size: int = 6):
    qr = qrcode.QRCode(border=2, box_size=box_size)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# antes de mostrar el QR, decide la url (buscar en secrets o usar fallback)
url_qr = st.secrets.get("APP_URL", "https://proyectominiclub-deandre99.streamlit.app")

qr_buf = make_qr_bytes(url_qr, box_size=6)

with st.sidebar:
    st.markdown("### Acceso rápido (QR)")
    st.image(qr_buf, width=160)
    st.caption(url_qr)


