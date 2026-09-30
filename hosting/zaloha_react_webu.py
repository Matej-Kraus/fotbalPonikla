#!/usr/bin/env python3
"""Stáhne z hostingu celý zkompilovaný React web do zálohy.

Ta aplikace nikde jinde neexistuje — zdrojové kódy nejsou ani na disku,
ani na GitHubu. Tohle je poslední věc, která potřebuje FTP přístup.

Spouští se z Macu, odkud hosting spojení pouští:

    cd /Users/mates/fotbalPonikla
    .venv/bin/python hosting/zaloha_react_webu.py

Na heslo se skript zeptá sám a nevypíše ho. Stahuje jen, nic nemění.
Výsledek je vedle repozitáře v ../tjponikla-react-build-<datum>/.
"""

import ftplib
import getpass
import os
import sys
from datetime import datetime
from pathlib import Path

HOST = os.environ.get("FTP_HOST", "tjponikla.cz")
USER = os.environ.get("FTP_USER", "admin.tjponikla.cz")
PASS = os.environ.get("FTP_PASS")

CIL = Path(__file__).resolve().parent.parent.parent / (
    "tjponikla-react-build-" + datetime.now().strftime("%Y%m%d")
)

# Hosting je sdílený, tak ať se to nerozjede do nekonečna.
MAX_HLOUBKA = 6
MAX_SOUBORU = 3000


def pripoj() -> ftplib.FTP:
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
    for cesta in (".", "web", "public_html", "www"):
        try:
            ftp.cwd("/")
            if cesta != ".":
                ftp.cwd(cesta)
            if "index.html" in ftp.nlst():
                print(f"✅ document root: {ftp.pwd()}")
                return ftp.pwd()
        except Exception:
            continue
    raise SystemExit("Nenašel jsem adresář s index.html.")


class Pocitadlo:
    souboru = 0
    bajtu = 0


def je_adresar(ftp: ftplib.FTP, jmeno: str) -> bool:
    puvodni = ftp.pwd()
    try:
        ftp.cwd(jmeno)
        ftp.cwd(puvodni)
        return True
    except Exception:
        return False


def stahni(ftp: ftplib.FTP, kam: Path, hloubka: int = 0):
    if hloubka > MAX_HLOUBKA:
        print(f"   … {kam} — hlouběji už nejdu")
        return
    kam.mkdir(parents=True, exist_ok=True)
    try:
        polozky = ftp.nlst()
    except Exception as e:
        print(f"   ⚠️  {ftp.pwd()}: {e}")
        return

    for jmeno in polozky:
        if jmeno in (".", ".."):
            continue
        if Pocitadlo.souboru >= MAX_SOUBORU:
            print("   ⚠️  dosažen limit počtu souborů, končím")
            return
        if je_adresar(ftp, jmeno):
            puvodni = ftp.pwd()
            try:
                ftp.cwd(jmeno)
                stahni(ftp, kam / jmeno, hloubka + 1)
            finally:
                ftp.cwd(puvodni)
        else:
            cil = kam / jmeno
            try:
                with open(cil, "wb") as f:
                    ftp.retrbinary(f"RETR {jmeno}", f.write)
                Pocitadlo.souboru += 1
                Pocitadlo.bajtu += cil.stat().st_size
                print(f"   {cil.relative_to(CIL)}  {cil.stat().st_size}B")
            except Exception as e:
                print(f"   ⚠️  {jmeno}: {e}")
                cil.unlink(missing_ok=True)


def main():
    global PASS
    if not PASS:
        if not sys.stdin.isatty():
            raise SystemExit("Chybí heslo a nejsem na terminálu. Spusť to v terminálu.")
        PASS = getpass.getpass(f"FTP heslo pro {USER} (nevypíše se): ")
    if not PASS:
        raise SystemExit("Nezadal jsi heslo, nic se nedělo.")

    ftp = pripoj()
    try:
        ftp.cwd(najdi_root(ftp))
        print(f"\n📥 stahuju do {CIL}")
        stahni(ftp, CIL)
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()

    mb = Pocitadlo.bajtu / 1024 / 1024
    print(f"\n✅ hotovo: {Pocitadlo.souboru} souborů, {mb:.1f} MB")
    print(f"   uloženo v {CIL}")
    if not (CIL / "index.html").exists():
        print("   ⚠️  index.html v záloze není — zkontroluj výstup výše.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
