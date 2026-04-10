import re
import pandas as pd
import streamlit as st
from book import Book, Book_Collection
import gspread
from google.oauth2.service_account import Credentials
import io

EXCEL_PATH = "libri-biblioteca-villalta.xlsx"
EXPORT_PATH = "catalogo_aggiornato.xlsx"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _parse_copies(title: str) -> tuple[str, int]:
    """Estrae il numero di copie dal titolo, es. 'Il giocatore (x2)' → ('Il giocatore', 2)."""
    m = re.search(r"\(x(\d+)\)", title, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        clean = re.sub(r"\s*\(x\d+\)", "", title, flags=re.IGNORECASE).strip()
        return clean, n
    return title.strip(), 1

def load_from_excel(path: str) -> Book_Collection:
    """Legge Foglio2 dell'Excel e restituisce una Book_Collection popolata."""
    df = pd.read_excel(path, sheet_name="Foglio2", header=None, usecols=[0, 1, 2])
    df.columns = ["autore", "titolo", "genere"]
    df = df.dropna(subset=["autore", "titolo"])

    collection = Book_Collection()
    for _, row in df.iterrows():
        title, copies = _parse_copies(str(row["titolo"]))
        book = Book(
            authors=str(row["autore"]).strip(),
            title=title,
            genre=str(row["genere"]).strip() if pd.notna(row["genere"]) else "",
            copies=copies,
        )
        collection.insert_book(book)
    return collection

def save_to_excel(collection: Book_Collection, path: str) -> None:
    df = collection.to_dataframe()
    df.to_excel(path, index=False)


########
# Google Sheets integrationn
#######

def get_gsheet():
    """Connessione al Google Sheet, cached per tutta la sessione"""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["sheet_id"]).sheet1


def load_from_gsheet(sheet) -> Book_Collection:
    records = sheet.get_all_records()   # → lista di dict {Autore, Titolo, Genere, Copie}
    collection = Book_Collection()
    for r in records:
        if not r.get("Titolo"):
            continue
        book = Book(
            authors=str(r["Autore"]),
            title=str(r["Titolo"]),
            genre=str(r.get("Genere", "")),
            copies=int(r.get("Copie", 1) or 1),
        )
        collection.insert_book(book)
    return collection


def save_to_gsheet(collection: Book_Collection, sheet) -> None:
    df = collection.to_dataframe()[["Autore", "Titolo", "Genere", "Copie"]]
    sheet.clear()
    sheet.update([df.columns.tolist()] + df.values.tolist())


## streamlit app

@st.cache_resource
def get_sheet_and_collection():
    sheet = get_gsheet()
    collection = load_from_gsheet(sheet)
    return sheet, collection


def main():
    # configura la pagina HTML
    st.set_page_config(
        page_title="Catalogo Biblioteca Villalta",
        page_icon="📚",
        layout="wide"
    )

    sheet, collection = get_sheet_and_collection()

    with st.sidebar:
        st.title("Catalogo Biblioteca Villalta")
        st.markdown("Sito per la gestione del catalogo dei libri della biblioteca di Villalta")
        st.markdown("---")

        st.divider()

        page = st.radio(
            "Sezione",
            ["Visualizza Catalogo", "Aggiungi Libro", "Rimuovi Libro", "Esporta Catalogo"],
            label_visibility="collapsed"
        )

        st.divider()
        st.metric("Titoli distinti", len(collection.books))
        total_copies = sum(b.copies for b in collection.books.values())
        st.metric("Copie totali", total_copies)

    if page in ["Aggiungi libro", "Rimuovi libro"]:
        if not st.session_state.get("authenticated", False):
            st.warning("Password per modificare il catalogo")
            pwd = st.text_input("Password", type="password", key="pwd_sidebar")
            if st.button("Entra"):
                if pwd == st.secrets["app_password"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Password errata")
            st.stop()

    if page == "Visualizza Catalogo":
        st.header("Catalogo dei Libri")

        df = collection.to_dataframe()
        if df.empty:
            st.info("La collezione è vuota.")
            return
        
        # filtri
        col1, col2, col3 = st.columns([2, 2, 2])
        with col1:
            search = st.text_input("Cerca per titolo o autore", "")
        with col2:
            genres = ["Tutti"] + sorted(df["Genere"].dropna().unique().tolist())
            genre_filter = st.selectbox("Genere", genres)
        with col3:
            only_multiple = st.checkbox("Solo libri con più copie")

        filtered = df.copy()
        if search:
            mask = (
                filtered["Titolo"].str.contains(search, case=False, na=False)
                | filtered["Autore"].str.contains(search, case=False, na=False)
            )
            filtered = filtered[mask]
        if genre_filter != "Tutti":
            filtered = filtered[filtered["Genere"] == genre_filter]
        if only_multiple:
            filtered = filtered[filtered["Copie"] > 1]

        st.caption(f"{len(filtered)} risultati")
        st.dataframe(
            filtered[["Autore", "Titolo", "Genere", "Copie"]],
            use_container_width=True,
            hide_index=True,
            height=520,
        )

    elif page == "Aggiungi Libro":
        st.header("Aggiungi un Nuovo Libro")
        st.caption(
            "Se il libro esiste già (stesso autore e titolo) "
            "le copie verranno incrementate automaticamente."
        )
        
        with st.form("add_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Titolo *")
                authors_raw = st.text_input(
                    "Autore/i *",
                    help="Per più autori separali con il punto e virgola: es. Autore A; Autore B",
                )
            with col2:
                genre = st.text_input("Genere")
                copies = st.number_input("Copie da aggiungere", min_value=1, value=1, step=1)

            submitted = st.form_submit_button("Aggiungi", type="primary")

            if submitted:
                if not title.strip() or not authors_raw.strip():
                    st.error("Titolo e autore sono obbligatori.")
                else:
                    authors = [a.strip() for a in authors_raw.split(";") if a.strip()]
                    new_book = Book(authors=authors, title=title.strip(), genre=genre.strip(), copies=copies)
                    msg = collection.insert_book(new_book)
                    save_to_gsheet(collection, sheet)   # ← salva su Google Sheets
                    st.success(msg)
                    get_sheet_and_collection.clear()
                    st.rerun()

    elif page == "Rimuovi Libro":
        st.header("Rimuovi un Libro")
        
        df = collection.to_dataframe()
        if df.empty:
            st.info("La collezione è vuota.")
            return
        
        options = {
            f"{row['Titolo']} — {row['Autore']} ({row['Copie']} cop.)": row["Chiave"]
            for _, row in df.iterrows()
        }

        selected_label = st.selectbox("Seleziona un libro da rimuovere", list(options.keys()))

        if st.button("🗑️ Elimina", type="secondary"):
            key = options[selected_label]
            msg = collection.delete_book(key)
            save_to_gsheet(collection, sheet)       # ← salva su Google Sheets
            st.success(msg)
            get_sheet_and_collection.clear()
            st.rerun()

    
    elif page == "Esporta Catalogo":
        st.header("Esporta Catalogo Aggiornato")
        st.markdown(
            "Clicca il pulsante qui sotto per scaricare un file Excel aggiornato "
            "con i libri attualmente presenti nella collezione."
        )
        
        df = collection.to_dataframe()
        st.dataframe(df, use_container_width=True, hide_index=True)

        import io
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Catalogo")
        st.download_button(
            label="Scarica come Excel",
            data=buf.getvalue(),
            file_name="catalogo_biblioteca_villalta.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

if __name__ == "__main__":
    main()
        
