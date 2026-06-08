#!/usr/bin/env python3
"""Banco de dados do UmbreonPay"""
import sqlite3, os, hashlib, secrets
from datetime import datetime

DB = os.path.expanduser("~/umbreonpay/umbreonpay.db")

def conectar():
    return sqlite3.connect(DB)

def criar_tabelas():
    conn = conectar()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS clientes (
            id TEXT PRIMARY KEY,
            nome TEXT, cpf TEXT UNIQUE, email TEXT UNIQUE,
            senha_hash TEXT, saldo_brl REAL DEFAULT 0,
            saldo_xmr REAL DEFAULT 0, nivel TEXT DEFAULT 'Sombra',
            codigo_afiliado TEXT UNIQUE, criado_em TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id TEXT, tipo TEXT, valor REAL, taxa REAL,
            descricao TEXT, data TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS carteiras_tws (
            id INTEGER PRIMARY KEY, nome TEXT UNIQUE, saldo_xmr REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS metas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id TEXT, nome TEXT, valor_meta REAL, valor_atual REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS vault (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id TEXT, valor REAL, tempo_espera INTEGER,
            solic_data TEXT, status TEXT DEFAULT 'ativo'
        );
    """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    criar_tabelas()
    print("✅ Banco criado!")
