#!/usr/bin/env python3
"""
rytm-przypomnien.py — silnik decyzyjny „kiedy przypomnieć zasady".

KROK 1: skrypt niczego nie wstrzykuje. Liczy zapełnienie kontekstu i mówi,
czy w tej turze wypadałoby przypomnieć zasady. Wypisuje jedną linię diagnostyczną.

Pomysł: zamiast liczyć tury (co wymaga pamiętania stanu między wywołaniami),
patrzymy na PRZEKROCZENIE PROGU zapełnienia kontekstu. Dwa ostatnie wpisy
`usage` w transkrypcie mówią, gdzie byliśmy poprzednio i gdzie jesteśmy teraz.
Transkrypt jest więc pamięcią — żadnego pliku stanu nie trzeba.

Progi są coraz gęstsze (25, 45, 60, 72, 81, 88, 93, 97), więc na początku sesji
przypomnienie pada rzadko, a pod koniec często. Dokładnie o to chodziło.

ZASADA NACZELNA: nigdy nie wywalaj się i zawsze wychodź z kodem 0. Hook, który
psuje turę, jest gorszy niż brak hooka.
"""

import json
import os
import re
import sys

PROGI_DOMYSLNE = [25, 45, 60, 72, 81, 88, 93, 97]
OKNO_DOMYSLNE = 200_000
SETTINGS = os.path.expanduser("~/.claude/settings.json")


def czytaj_progi():
    """Progi z RYTM_PROGI albo domyślne. Zwraca (progi, czy_byl_blad)."""
    surowe = os.environ.get("RYTM_PROGI", "").strip()
    if not surowe:
        return PROGI_DOMYSLNE, False
    try:
        progi = sorted({float(x) for x in surowe.split(",") if x.strip() != ""})
        if not progi:
            return PROGI_DOMYSLNE, True
        return progi, False
    except ValueError:
        return PROGI_DOMYSLNE, True


def czytaj_okno():
    """
    Rozmiar okna kontekstu. Kolejność: zmienna środowiskowa, settings.json,
    wartość domyślna. Zwraca (okno, źródło).
    """
    env = os.environ.get("RYTM_OKNO", "").strip()
    if env:
        try:
            wartosc = int(env)
            if wartosc > 0:
                return wartosc, "env"
        except ValueError:
            pass

    # settings.json ma pole "model" w rodzaju "opus[1m]" — przyrostek to okno.
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            model = json.load(f).get("model", "")
        dopasowanie = re.search(r"\[(\d+(?:\.\d+)?)\s*([mk])\]", str(model), re.I)
        if dopasowanie:
            liczba = float(dopasowanie.group(1))
            mnoznik = 1_000_000 if dopasowanie.group(2).lower() == "m" else 1_000
            wartosc = int(liczba * mnoznik)
            if wartosc > 0:
                return wartosc, "settings.json"
    except Exception:
        pass

    return OKNO_DOMYSLNE, "domyślne"


def dwa_ostatnie_usage(sciezka):
    """
    Zwraca (poprzednio, teraz) w tokenach.

    „teraz"      = ostatni wpis usage w pliku.
    „poprzednio" = ostatni wpis usage PRZED ostatnią wiadomością użytkownika,
                   czyli stan kontekstu przy poprzednim odpaleniu hooka.

    Dlaczego nie przedostatni wpis: na jedną turę przypada kilka wpisów usage
    (kolejne kroki asystenta, często zduplikowane), więc przedostatni bywa
    identyczny z ostatnim. Przy takim porównaniu progi przekroczone w środku
    tury przepadały. Okna liczone od granicy tury stykają się bez luk.

    Czytamy strumieniowo — plik bywa wielomegabajtowy.
    """
    teraz = None            # ostatni wpis usage
    przed_granica = None    # wartość „teraz" zapamiętana na ostatniej granicy tury
    with open(sciezka, encoding="utf-8", errors="replace") as f:
        for wiersz in f:
            wiersz = wiersz.strip()
            if not wiersz:
                continue
            if '"usage"' not in wiersz and '"user"' not in wiersz:
                continue
            try:
                d = json.loads(wiersz)
            except Exception:
                continue

            # Wpisy podagentów mierzą ICH kontekst, nie nasz — na wszelki
            # wypadek je pomijamy. W przejrzanych transkryptach takich wpisów
            # z polem usage nie było, ale to tania polisa.
            if d.get("isSidechain"):
                continue

            if d.get("type") == "user":
                # UWAGA: wyniki narzędzi też mają type="user". Prawdziwa
                # wiadomość człowieka ma treść w postaci zwykłego napisu,
                # wynik narzędzia — listy z blokiem tool_result. Bez tego
                # rozróżnienia każde wywołanie narzędzia udawało nową turę
                # i progi przekroczone w jej trakcie przepadały.
                tresc = (d.get("message") or {}).get("content")
                if not isinstance(tresc, str) or d.get("isMeta") is True:
                    continue
                # Granica tury: to, co widzieliśmy do tej pory, jest stanem
                # sprzed bieżącej tury.
                przed_granica = teraz
                continue

            wiadomosc = d.get("message")
            if not isinstance(wiadomosc, dict):
                continue
            usage = wiadomosc.get("usage")
            if not isinstance(usage, dict):
                continue
            suma = 0
            for pole in ("input_tokens",
                         "cache_creation_input_tokens",
                         "cache_read_input_tokens"):
                wartosc = usage.get(pole, 0)
                if isinstance(wartosc, (int, float)):
                    suma += int(wartosc)
            teraz = suma
    return przed_granica, teraz


def dane_hooka():
    """Wczytuje dane hooka ze standardowego wejścia — raz, z zapamiętaniem."""
    if not hasattr(dane_hooka, "_cache"):
        dane = {}
        if not sys.stdin.isatty():
            try:
                surowe = sys.stdin.read()
                if surowe.strip():
                    odczyt = json.loads(surowe)
                    if isinstance(odczyt, dict):
                        dane = odczyt
            except Exception:
                dane = {}
        dane_hooka._cache = dane
    return dane_hooka._cache


def sciezka_transkryptu(argv):
    """Ścieżka z --transcript albo z danych hooka na standardowym wejściu."""
    if "--transcript" in argv:
        i = argv.index("--transcript")
        if i + 1 < len(argv):
            return argv[i + 1]
        return None
    return dane_hooka().get("transcript_path") or None


def procent_udawany(nazwa):
    surowe = os.environ.get(nazwa, "").strip()
    if not surowe:
        return None
    try:
        return float(surowe)
    except ValueError:
        return None


def policz(argv):
    """Zwraca słownik z pełną diagnozą. Nie rzuca wyjątków w górę."""
    wynik = {
        "teraz_tokeny": None,
        "poprzednio_tokeny": None,
        "okno": None,
        "zrodlo_okna": None,
        "teraz_procent": None,
        "poprzednio_procent": None,
        "progi": None,
        "przekroczone": [],
        "wstrzyknac": False,
        "tryb_udawany": False,
        "blad": None,
    }

    progi, progi_blad = czytaj_progi()
    wynik["progi"] = progi
    if progi_blad:
        wynik["blad"] = "RYTM_PROGI nieczytelne — użyto domyślnych"

    okno, zrodlo = czytaj_okno()
    wynik["okno"] = okno
    wynik["zrodlo_okna"] = zrodlo

    udawany = procent_udawany("RYTM_UDAWANY_PROCENT")
    if udawany is not None:
        # Tryb testowy: udajemy dowolne zapełnienie, żeby sprawdzić zachowanie
        # przy 60% czy 90% bez prowadzenia wielogodzinnej rozmowy.
        udawany_poprz = procent_udawany("RYTM_UDAWANY_POPRZEDNI_PROCENT") or 0.0
        wynik["tryb_udawany"] = True
        wynik["teraz_procent"] = udawany
        wynik["poprzednio_procent"] = udawany_poprz
        wynik["teraz_tokeny"] = int(okno * udawany / 100)
        wynik["poprzednio_tokeny"] = int(okno * udawany_poprz / 100)
    else:
        sciezka = sciezka_transkryptu(argv)
        if not sciezka:
            wynik["blad"] = "brak danych wejściowych"
            return wynik
        if not os.path.isfile(sciezka):
            wynik["blad"] = "brak pliku transkryptu"
            return wynik
        try:
            poprzednio, teraz = dwa_ostatnie_usage(sciezka)
        except Exception as e:
            wynik["blad"] = f"nie dało się odczytać transkryptu: {e}"
            return wynik
        if teraz is None:
            wynik["blad"] = "brak danych o tokenach"
            return wynik
        # Jeden wpis = początek sesji, więc „poprzednio" to zero.
        poprzednio = poprzednio or 0
        wynik["teraz_tokeny"] = teraz
        wynik["poprzednio_tokeny"] = poprzednio
        wynik["teraz_procent"] = 100.0 * teraz / okno
        wynik["poprzednio_procent"] = 100.0 * poprzednio / okno

    # Przekroczony próg = leży w przedziale (poprzednio, teraz].
    # Gdy zapełnienie spadło (po zagęszczeniu kontekstu), przedział jest pusty
    # i nic nie wstrzykujemy — dopiero ponowny wzrost odpali progi na nowo.
    p_teraz = wynik["teraz_procent"]
    p_poprz = wynik["poprzednio_procent"]
    wynik["przekroczone"] = [g for g in progi if p_poprz < g <= p_teraz]
    wynik["wstrzyknac"] = bool(wynik["przekroczone"])
    return wynik


def linia(w):
    if w["blad"] and w["teraz_procent"] is None:
        return f"[RYTM: ⚠ {w['blad']} — cisza]"
    czolo = "⚠ TRYB UDAWANY · " if w["tryb_udawany"] else ""
    if w["przekroczone"]:
        progi_txt = "progi przekroczone: " + ", ".join(
            f"{g:g}" for g in w["przekroczone"]) + " · WSTRZYKNIJ"
    else:
        progi_txt = "brak progu · cisza"
    return (f"[RYTM: {czolo}{w['teraz_procent']:.1f}% "
            f"({w['teraz_tokeny']}/{w['okno']} tok, okno: {w['zrodlo_okna']}) · "
            f"poprzednio {w['poprzednio_procent']:.1f}% · {progi_txt}]")


def zapisz_log(w, argv):
    """
    Dopisuje jeden wiersz JSON do dziennika. Tylko na czas testów — pozwala
    obejrzeć po fakcie, jak hook zachowywał się w cudzej sesji.
    Awaria zapisu nie może zatrzymać hooka, więc wszystko idzie w try.
    """
    try:
        import datetime
        katalog = os.path.expanduser("~/.claude/state")
        os.makedirs(katalog, exist_ok=True)
        wpis = {
            "czas": datetime.datetime.now().isoformat(timespec="seconds"),
            "sesja": (dane_hooka().get("session_id") or "?")[:8],
            "teraz_tokeny": w.get("teraz_tokeny"),
            "poprzednio_tokeny": w.get("poprzednio_tokeny"),
            "okno": w.get("okno"),
            "teraz_procent": (round(w["teraz_procent"], 2)
                              if w.get("teraz_procent") is not None else None),
            "poprzednio_procent": (round(w["poprzednio_procent"], 2)
                                   if w.get("poprzednio_procent") is not None else None),
            "progi": w.get("progi"),
            "przekroczone": w.get("przekroczone"),
            "wstrzyknac": w.get("wstrzyknac"),
            "blad": w.get("blad"),
        }
        with open(os.path.join(katalog, "rytm-log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(wpis, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    argv = sys.argv[1:]
    try:
        w = policz(argv)
    except Exception as e:
        w = None
        awaria = str(e)
    else:
        awaria = None

    if w is None:
        if "--json" in argv:
            print(json.dumps({"blad": f"awaria: {awaria}", "wstrzyknac": False},
                             ensure_ascii=False))
        else:
            print(f"[RYTM: ⚠ awaria: {awaria} — cisza]")
        return

    if "--log" in argv:
        zapisz_log(w, argv)

    if "--decyzja" in argv:
        # Tryb dla wrappera: samo TAK/NIE, bez diagnostyki.
        # Przy błędzie odczytu mówimy TAK — cisza jest groźniejsza niż nadmiar.
        if w.get("blad") and w.get("teraz_procent") is None:
            print("TAK")
        else:
            print("TAK" if w["wstrzyknac"] else "NIE")
        return

    if "--json" in argv:
        print(json.dumps(w, ensure_ascii=False))
    else:
        print(linia(w))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Ostateczna siatka bezpieczeństwa — hook nigdy nie psuje tury.
        pass
    sys.exit(0)
