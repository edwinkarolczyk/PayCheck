# PayCheck

PayCheck to prosta aplikacja desktopowa do porównywania listy zobowiązań z Excela z wyciągiem bankowym CSV/XLSX.

## PayCheck 0.1.0

Pierwsza wersja obsługuje:
- import zobowiązań z `.xlsx`,
- import wyciągu bankowego z `.csv` lub `.xlsx`,
- dopasowanie po dacie, przybliżonej kwocie i nazwie kontrahenta,
- statusy `OPŁACONA`, `DO SPRAWDZENIA`, `BRAK`,
- regulowaną tolerancję daty i kwoty,
- eksport wyniku do Excela.

## Oczekiwane kolumny

PayCheck rozpoznaje popularne nazwy kolumn automatycznie.

### Zobowiązania
- kontrahent / odbiorca / firma
- kwota / do zapłaty / wartość
- termin / data płatności / data
- opcjonalnie: nr faktury / faktura / numer

### Wyciąg
- odbiorca / kontrahent / nazwa
- kwota / wartość
- data operacji / data księgowania / data
- opcjonalnie: tytuł / opis

## Uruchomienie

```bash
pip install -r requirements.txt
python app.py
```

Projekt jest rozwijany etapami. Wersja 0.1.0 nie łączy się bezpośrednio z bankiem i nie modyfikuje źródłowego wyciągu bankowego.
