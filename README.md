# Biblioteca Villalta – Catalogo Libri

## Come avviare

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Struttura

| File | Descrizione |
|------|-------------|
| `book.py` | Classi `Book` e `Book_Collection` |
| `app.py`  | Interfaccia Streamlit |
| `libri-biblioteca-villalta.xlsx` | Catalogo di partenza |

## Gestione delle copie

Se inserisci un libro già presente (stesso autore + titolo),
il sistema **incrementa automaticamente il contatore di copie**
