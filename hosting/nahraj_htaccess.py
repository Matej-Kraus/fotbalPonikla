#!/usr/bin/env python3
"""Jednorázově nastaví na hostingu přesměrování tabulek na GitHub Pages.

Spouští se z Macu, odkud hosting spojení pouští:

    cd /Users/mates/fotbalPonikla
    .venv/bin/python hosting/nahraj_htaccess.py

Na heslo se skript zeptá sám a nevypíše ho — nezůstane tedy
ani v historii shellu.

Skript stávající .htaccess nejdřív stáhne, řádky k němu jen přidá,
ukáže výsledek a nahraje ho teprve po potvrzení.
"""

import ftplib
import getpass
import io
import os
import sys

HOST = os.environ.get("FTP_HOST", "tjponikla.cz")
USER = os.environ.get("FTP_USER", "admin.tjponikla.cz")
PASS = os.environ.get("FTP_PASS")

PAGES = "https://matej-kraus.github.io/fotbalPonikla"
MARKER = "# --- tabulky z GitHub Pages (spravuje repozitář fotbalPonikla) ---"
BLOK = f"""{MARKER}
Redirect 302 /tabulka.html {PAGES}/tabulka.html
Redirect 302 /nadhazenici.html {PAGES}/nadchazejici_zapasy.html
"""


def pripoj() -> ftplib.FTP:
    """Zkusí FTPS a pak plain FTP, pasivně i aktivně."""
    posledni = None
    for popis, use_tls, passive in [
        ("FTPS (AUTH TLS)", True, True),
        ("FTP pasivní", False, True),
        ("FTP aktivní", False, False),
    ]:
        try:
            if use_tls:
                ftp = ftplib.FTP_TLS()
                ftp.connect(HOST, 21, timeout=30)
                ftp.auth()
                ftp.login(USER, PASS)
                ftp.prot_p()
            else:
                ftp = ftplib.FTP()
                ftp.connect(HOST, 21, timeout=30)
                ftp.login(USER, PASS)
            ftp.set_pasv(passive)
            ftp.voidcmd("NOOP")
            print(f"✅ připojeno přes {popis}")
            return ftp
        except Exception as e:
            print(f"✗ {popis}: {type(e).__name__}: {e}")
            posledni = e
    raise SystemExit(f"Nepodařilo se připojit k {HOST}: {posledni!r}")


def najdi_root(ftp: ftplib.FTP) -> str:
    """Najde adresář, ve kterém leží index.html webu."""
    for cesta in (".", "web", "public_html", "www"):
        try:
            if cesta != ".":
                ftp.cwd("/")
                ftp.cwd(cesta)
            else:
                ftp.cwd("/")
            if "index.html" in ftp.nlst():
                print(f"✅ document root: {ftp.pwd()}")
                return ftp.pwd()
        except Exception:
            continue
    raise SystemExit("Nenašel jsem adresář s index.html — uprav skript ručně.")


def main():
    global PASS
    if not PASS:
        if not sys.stdin.isatty():
            raise SystemExit(
                "Chybí heslo a nejsem na terminálu. Spusť skript přímo v terminálu, "
                "nebo nastav FTP_PASS."
            )
        PASS = getpass.getpass(f"FTP heslo pro {USER} (nevypíše se): ")
    if not PASS:
        raise SystemExit("Nezadal jsi heslo, nic se nedělo.")

    ftp = pripoj()
    try:
        root = najdi_root(ftp)
        ftp.cwd(root)

        stavajici = ""
        if ".htaccess" in ftp.nlst():
            buf = io.BytesIO()
            ftp.retrbinary("RETR .htaccess", buf.write)
            stavajici = buf.getvalue().decode("utf-8", "replace")
            print(f"\n── stávající .htaccess ({len(stavajici)} B)")
            print(stavajici.rstrip() or "(prázdný)")
            zaloha = "htaccess-zaloha.txt"
            with open(zaloha, "w", encoding="utf-8") as f:
                f.write(stavajici)
            print(f"   záloha uložena do {zaloha}")
        else:
            print("\n── na hostingu .htaccess není, vytvoří se nový")

        if MARKER in stavajici:
            print("\nPřesměrování už je nastavené, není co měnit.")
            return

        novy = (stavajici.rstrip() + "\n\n" if stavajici.strip() else "") + BLOK

        print("\n── jak bude .htaccess vypadat po úpravě")
        print("─" * 60)
        print(novy.rstrip())
        print("─" * 60)

        if input("\nNahrát na hosting? [ano/ne] ").strip().lower() not in ("ano", "a", "y", "yes"):
            print("Nic se nenahrálo.")
            return

        data = novy.encode("utf-8")
        ftp.storbinary("STOR .htaccess", io.BytesIO(data))
        if ftp.size(".htaccess") != len(data):
            raise SystemExit("Velikost po nahrání nesouhlasí, zkontroluj to ručně.")
        print("✅ .htaccess nahrán")
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()

    print(
        "\nZkontroluj to takhle (musí vypsat týmy, ne 'Sezóna ještě nezačala'):\n"
        "  curl -sL https://tjponikla.cz/tabulka.html | grep -c '<tr>'"
    )


if __name__ == "__main__":
    sys.exit(main())
