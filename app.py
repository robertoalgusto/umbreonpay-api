#!/usr/bin/env python3
"""
╔══════════════════════════════════════════╗
║   UMBREONPAY — API UNIFICADA             ║
║   Flask + PostgreSQL (Supabase)          ║
║   Banco persistente 24/7                 ║
╚══════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2, hashlib, secrets, os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Banco de dados Supabase
DB_HOST = "db.fvnyxxcicytfetikqkxe.supabase.co"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "UmbreonPay2026!@#X9JNFDYHCFIJVD57HD6UJFTIIBFY7JBFYUIHF"
DB_PORT = "5432"

def conectar():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME,
        user=DB_USER, password=DB_PASS, port=DB_PORT
    )

def iniciar_banco():
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id TEXT PRIMARY KEY,
            nome TEXT, cpf TEXT UNIQUE, email TEXT UNIQUE,
            senha_hash TEXT, saldo_brl REAL DEFAULT 0,
            saldo_xmr REAL DEFAULT 0, nivel TEXT DEFAULT 'Sombra',
            codigo_afiliado TEXT UNIQUE,
            criado_em TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS transacoes (
            id SERIAL PRIMARY KEY,
            cliente_id TEXT, tipo TEXT, valor REAL, taxa REAL,
            descricao TEXT, data TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS metas (
            id SERIAL PRIMARY KEY,
            cliente_id TEXT, nome TEXT, valor_meta REAL, valor_atual REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS vault (
            id SERIAL PRIMARY KEY,
            cliente_id TEXT, valor REAL, tempo_espera INTEGER,
            solic_data TIMESTAMP DEFAULT NOW(), status TEXT DEFAULT 'ativo'
        );
    """)
    conn.commit()
    conn.close()
    print("✅ Banco iniciado!")

# ═══════════════════════════════════════
# AUTENTICAÇÃO
# ═══════════════════════════════════════

@app.route('/api/auth/cadastrar', methods=['POST'])
def cadastrar():
    data = request.json
    nome = data.get('nome','')
    cpf = data.get('cpf','')
    email = data.get('email','')
    senha = hashlib.sha256(data.get('senha','').encode()).hexdigest()
    codigo = 'UB-REF-' + secrets.token_hex(4).upper()

    if not all([nome, cpf, email, senha]):
        return jsonify({"erro":"Todos os campos são obrigatórios"}),400

    try:
        conn = conectar()
        c = conn.cursor()
        c.execute("INSERT INTO clientes (id,nome,cpf,email,senha_hash,codigo_afiliado) VALUES(%s,%s,%s,%s,%s,%s)",
                 (cpf,nome,cpf,email,senha,codigo))
        conn.commit()
        conn.close()
        return jsonify({"ok":True,"mensagem":"Conta criada com sucesso!","codigo_afiliado":codigo})
    except psycopg2.errors.UniqueViolation:
        conn.close()
        return jsonify({"erro":"CPF ou email já cadastrado"}),400
    except Exception as e:
        return jsonify({"erro":str(e)}),500

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    cpf = data.get('cpf','')
    senha = hashlib.sha256(data.get('senha','').encode()).hexdigest()

    try:
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT nome,saldo_brl,saldo_xmr,nivel,codigo_afiliado FROM clientes WHERE cpf=%s AND senha_hash=%s",(cpf,senha))
        r = c.fetchone()
        conn.close()

        if r:
            return jsonify({"ok":True,"nome":r[0],"saldo_brl":float(r[1]),"saldo_xmr":float(r[2]),"nivel":r[3],"codigo_afiliado":r[4]})
        return jsonify({"erro":"CPF ou senha incorretos"}),401
    except Exception as e:
        return jsonify({"erro":str(e)}),500

# ═══════════════════════════════════════
# TRANSAÇÕES
# ═══════════════════════════════════════

@app.route('/api/pix/enviar', methods=['POST'])
def pix_enviar():
    data = request.json
    cpf = data.get('cpf','')
    valor = float(data.get('valor',0))
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT saldo_brl FROM clientes WHERE cpf=%s",(cpf,))
    r = c.fetchone()
    if not r or r[0] < valor:
        conn.close()
        return jsonify({"erro":"Saldo insuficiente"}),400
    taxa = valor * 0.015
    novo = r[0] - valor - taxa
    c.execute("UPDATE clientes SET saldo_brl=%s WHERE cpf=%s",(novo,cpf))
    c.execute("INSERT INTO transacoes (cliente_id,tipo,valor,taxa,descricao) VALUES(%s,%s,%s,%s,%s)",
             (cpf,'pix_enviado',valor,taxa,f'Pix enviado: R$ {valor:.2f}'))
    conn.commit()
    conn.close()
    return jsonify({"ok":True,"mensagem":f"Pix de R$ {valor:.2f} enviado!"})

@app.route('/api/deposito', methods=['POST'])
def deposito():
    data = request.json
    cpf = data.get('cpf','')
    valor = float(data.get('valor',0))
    titularidade = data.get('titularidade','propria')
    taxa = 0 if titularidade == 'propria' else valor * 0.25
    liquido = valor - taxa
    conn = conectar()
    c = conn.cursor()
    c.execute("UPDATE clientes SET saldo_brl = saldo_brl + %s WHERE cpf=%s",(liquido,cpf))
    c.execute("INSERT INTO transacoes (cliente_id,tipo,valor,taxa,descricao) VALUES(%s,%s,%s,%s,%s)",
             (cpf,'deposito',valor,taxa,f'Depósito: R$ {valor:.2f}'))
    conn.commit()
    conn.close()
    return jsonify({"ok":True,"mensagem":f"Depósito de R$ {valor:.2f} recebido!"})

@app.route('/api/saque', methods=['POST'])
def saque():
    data = request.json
    cpf = data.get('cpf','')
    valor = float(data.get('valor',0))
    taxa = valor * 0.15
    total = valor + taxa
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT saldo_brl FROM clientes WHERE cpf=%s",(cpf,))
    r = c.fetchone()
    if not r or r[0] < total:
        conn.close()
        return jsonify({"erro":"Saldo insuficiente"}),400
    novo = r[0] - total
    c.execute("UPDATE clientes SET saldo_brl=%s WHERE cpf=%s",(novo,cpf))
    c.execute("INSERT INTO transacoes (cliente_id,tipo,valor,taxa,descricao) VALUES(%s,%s,%s,%s,%s)",
             (cpf,'saque',valor,taxa,f'Saque: R$ {valor:.2f}'))
    conn.commit()
    conn.close()
    return jsonify({"ok":True,"mensagem":f"Saque de R$ {valor:.2f} realizado!"})

@app.route('/api/extrato', methods=['POST'])
def extrato():
    data = request.json
    cpf = data.get('cpf','')
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT tipo,valor,taxa,descricao,data FROM transacoes WHERE cliente_id=%s ORDER BY data DESC LIMIT 20",(cpf,))
    rows = c.fetchall()
    conn.close()
    ext = [{"tipo":r[0],"valor":float(r[1]),"taxa":float(r[2]),"descricao":r[3],"data":str(r[4])} for r in rows]
    return jsonify({"ok":True,"extrato":ext})

# ═══════════════════════════════════════
# CRIPTO
# ═══════════════════════════════════════

@app.route('/api/crypto/cotacao')
def cotacao():
    return jsonify({"XMR":{"BRL":1200.00,"USD":240.00},"BTC":{"BRL":350000.00,"USD":70000.00}})

# ═══════════════════════════════════════
# SISTEMA
# ═══════════════════════════════════════

@app.route('/')
def home():
    return jsonify({"app":"UmbreonPay API","versao":"2.0","banco":"PostgreSQL (Supabase)","status":"online"})

if __name__ == '__main__':
    iniciar_banco()
    app.run(host='0.0.0.0', port=8080)
