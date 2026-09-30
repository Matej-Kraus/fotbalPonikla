#!/usr/bin/env python3
"""Dočasný průzkum: kam na hostingu patří tabulka.html. Jen čte, nic nemění."""

import os
import sys

import paramiko

HOST = os.environ.get("FTP_HOST") or "tjponikla.cz"
USER = os.environ["FTP_USER"]
PASS = os.environ["FTP_PASS"]

transport = paramiko.Transport((HOST, 22))
transport.connect(username=USER, password=PASS)
sftp = paramiko.SFTPClient.from_transport(transport)

print("domovský adresář:", sftp.normalize("."))

print("-- obsah domovského adresáře")
for attr in sorted(sftp.listdir_attr("."), key=lambda a: a.filename)[:40]:
    kind = "d" if (attr.st_mode or 0) & 0o40000 else "-"
    print(f"   {kind} {attr.filename}  {attr.st_size}B")

for cand in ("web", "public_html", "www", "sub", "domains"):
    try:
        sftp.stat(cand)
    except IOError:
        continue
    print(f"-- {cand}/ (html, js a static)")
    try:
        for attr in sorted(sftp.listdir_attr(cand), key=lambda a: a.filename):
            if attr.filename.endswith((".html", ".js", ".json")) or attr.filename == "static":
                print(f"   {cand}/{attr.filename}  {attr.st_size}B")
    except IOError as e:
        print(f"   nelze vylistovat: {e}", file=sys.stderr)

sftp.close()
transport.close()
