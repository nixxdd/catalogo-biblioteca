import numpy as np
from typing import List
import re
import pandas as pd

class Book:

  def __init__(self, authors : str | List[str], title : str, copies : int, genre : str):
    if isinstance(authors, str):
            self.authors = [authors]
    else:
        self.authors = list(authors)

    self.title = title
    self.genre = genre
    self.copies = copies
    self.key = self.book_id()

  def set_authors(self, authors : str | List[str]):
    if isinstance(authors, str):
            self.authors = [authors]
    else:
        self.authors = list(authors)
    self.key = self.book_id() 

  def set_title(self, title : str):
    self.title = title
    self.key = self.book_id()

  def set_copies(self, copies : int):
    self.copies = copies

  def get_authors(self):
    return self.authors

  def get_title(self):
    return self.title
  
  def get_copies(self):
    return self.copies

  def book_id(self):
    #  the surname of the first author, the first word of the title, and the year of publication
    surname = self.authors[0].split()[0] if self.authors else "unknown"
    clean_title = re.sub(r"[^\w]", "", self.title.lower())
    return f"{surname.lower()}_{clean_title}"
  
  def __repr__(self) -> str:
    return f"Book({self.key!r}, copies={self.copies})"


class Book_Collection:
  def __init__(self):
    self.books = {}

  def insert_book(self, book : Book):
    if book.key in self.books:
      self.books[book.key].copies += book.copies
      return f"Libro già presente, copie aggiornate a {self.books[book.key].copies}"
    
    self.books[book.key] = book
    return f"Libro inserito nella collezione: {book.title}"

  def delete_book(self, key : str):
    if key in self.books:
      title = self.books[key].title
      del self.books[key]
      return f"Libro {title} ({key}) eliminato"
    else:
      return f"Libro con chiave {key} non trovato"

  def find_by_author(self, surname : str):
    surname = surname.lower()
    found_books = [book for book in self.books.values() if any(surname in author.lower() for author in book.authors)]
    return found_books
  
  def find_by_title(self, title : str):
    title = title.lower()
    found_books = [book for book in self.books.values() if title in book.title.lower()]
    return found_books

  def save_to_csv(self, filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        f.write("autori,titolo,genere,copie,chiave\n")
        for book in self.books.values():
            authors_str = ";".join(book.authors)
            f.write(
                f"{authors_str},{book.title},{book.genre},"
                f"{book.copies},{book.key}\n"   
            )

  def show_collection(self) -> None:
    for book in self.books.values():
        print(f"[{book.key}]  {book.title}  —  {', '.join(book.authors)}"
                f"  ({book.copies} cop.)")
        
  def to_dataframe(self):
    """Restituisce la collezione come pandas DataFrame."""
    rows = []
    for b in self.books.values():
        rows.append({
            "Autore": ", ".join(b.authors),
            "Titolo": b.title,
            "Genere": b.genre,
            "Copie": b.copies,
            "Chiave": b.key,
        })
    return pd.DataFrame(rows)


