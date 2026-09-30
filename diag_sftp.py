#!/usr/bin/env python3
"""Dočasný průzkum: kam na hostingu patří tabulka.html. Jen čte, nic nemění."""

import logging
import os
import sys

import paramiko

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout,
                    format="%(levelname)s %(name)s: %(message)s")

HOST = os.environ.get("FTP_HOST") or "tjponikla.cz"
USER = os.environ["FTP_USER"]
PASS = os.environ["FTP_PASS"]


def explore(sftp):
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


print("=== pokus A: SSHClient.open_sftp ===")
try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=22, username=USER, password=PASS,
                   look_for_keys=False, allow_agent=False, timeout=30)
    explore(client.open_sftp())
    client.close()
    print("pokus A: OK")
    sys.exit(0)
except Exception as e:
    print(f"pokus A selhal: {type(e).__name__}: {e}")

print("=== pokus B: Transport + invoke_subsystem ručně ===")
try:
    t = paramiko.Transport((HOST, 22))
    t.connect(username=USER, password=PASS)
    print("autentizace prošla:", t.is_authenticated())
    chan = t.open_session(timeout=30)
    chan.invoke_subsystem("sftp")
    explore(paramiko.SFTPClient(chan))
    t.close()
    print("pokus B: OK")
except Exception as e:
    print(f"pokus B selhal: {type(e).__name__}: {e}")
    sys.exit(1)
