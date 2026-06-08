#!/usr/bin/env python3
"""
╔══════════════════════════════════════════╗
║   UMBREONPAY — API UNIFICADA v4.1        ║
║   Flask + PostgreSQL + Mixer + Anti-MED  ║
╚══════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2, hashlib, secrets, os, random
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Banco — usa variáveis de ambiente
DB_HOST = os.environ.get('DB_HOST', 'db.fvnyxxcicytfetikqkxe.supabase.co')
DB_NAME = os.environ.get('DB_NAME', 'postgres')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASS = os.environ.get('DB_PASS', '')
DB_PORT = os.environ.get('DB_PORT', '5432')

def conectar():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME,
        user=DB_USER, password=DB_PASS, port=DB_PORT
    )

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
        return jsonify({"erro":"Campos obrigatórios"}),400

    try:
        conn = conectar()
        c = conn.cursor()
        c.execute("INSERT INTO clientes (id,nome,cpf,email,senha_hash,codigo_afiliado) VALUES(%s,%s,%s,%s,%s,%s)",
                 (cpf,nome,cpf,email,senha,codigo))
        conn.commit()
        conn.close()
        return jsonify({"ok":True,"mensagem":"Conta criada!","codigo_afiliado":codigo})
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
        c.execute("SELECT nome,saldo_brl FROM clientes WHERE cpf=%s AND senha_hash=%s",(cpf,senha))
        r = c.fetchone()
        conn.close()
        if r:
            return jsonify({"ok":True,"nome":r[0],"saldo_brl":float(r[1])})
        return jsonify({"erro":"CPF ou senha incorretos"}),401
    except Exception as e:
        return jsonify({"erro":str(e)}),500

@app.route('/')
def home():
    return jsonify({"app":"UmbreonPay API","versao":"4.1","status":"online","db_host":DB_HOST})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
