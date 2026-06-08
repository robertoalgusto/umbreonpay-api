#!/usr/bin/env python3
"""
╔══════════════════════════════════════════╗
║   UMBREONPAY — API UNIFICADA             ║
║   Flask + SQLite + CORS                  ║
║   Fly.io Ready                           ║
╚══════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, hashlib, secrets, os, random, json
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB = os.path.expanduser("~/umbreonpay/umbreonpay.db")

def conectar():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

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
        c.execute("INSERT INTO clientes (id,nome,cpf,email,senha_hash,codigo_afiliado) VALUES(?,?,?,?,?,?)",
                 (cpf,nome,cpf,email,senha,codigo))
        conn.commit()
        conn.close()
        return jsonify({"ok":True,"mensagem":"Conta criada com sucesso!","codigo_afiliado":codigo})
    except sqlite3.IntegrityError:
        return jsonify({"erro":"CPF ou email já cadastrado"}),400

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    cpf = data.get('cpf','')
    senha = hashlib.sha256(data.get('senha','').encode()).hexdigest()

    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT nome,saldo_brl,saldo_xmr,nivel,codigo_afiliado FROM clientes WHERE cpf=? AND senha_hash=?",(cpf,senha))
    r = c.fetchone()
    conn.close()

    if r:
        return jsonify({"ok":True,"nome":r[0],"saldo_brl":r[1],"saldo_xmr":r[2],"nivel":r[3],"codigo_afiliado":r[4]})
    return jsonify({"erro":"CPF ou senha incorretos"}),401

@app.route('/api/auth/recuperar', methods=['POST'])
def recuperar():
    data = request.json
    email = data.get('email','')
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT email FROM clientes WHERE email=?",(email,))
    r = c.fetchone()
    conn.close()
    if r:
        return jsonify({"ok":True,"mensagem":"Link de recuperação enviado para seu email"})
    return jsonify({"erro":"Email não encontrado"}),404

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
    c.execute("SELECT saldo_brl FROM clientes WHERE cpf=?",(cpf,))
    r = c.fetchone()
    if not r or r[0] < valor:
        conn.close()
        return jsonify({"erro":"Saldo insuficiente"}),400
    taxa = valor * 0.015
    novo = r[0] - valor - taxa
    c.execute("UPDATE clientes SET saldo_brl=? WHERE cpf=?",(novo,cpf))
    c.execute("INSERT INTO transacoes (cliente_id,tipo,valor,taxa,descricao) VALUES(?,?,?,?,?)",
             (cpf,'pix_enviado',valor,taxa,f'Pix enviado: R$ {valor:.2f}'))
    conn.commit()
    conn.close()
    return jsonify({"ok":True,"mensagem":f"Pix de R$ {valor:.2f} enviado! Taxa: R$ {taxa:.2f}"})

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
    c.execute("UPDATE clientes SET saldo_brl = saldo_brl + ? WHERE cpf=?",(liquido,cpf))
    c.execute("INSERT INTO transacoes (cliente_id,tipo,valor,taxa,descricao) VALUES(?,?,?,?,?)",
             (cpf,'deposito',valor,taxa,f'Depósito: R$ {valor:.2f} (líquido: R$ {liquido:.2f})'))
    conn.commit()
    conn.close()
    return jsonify({"ok":True,"mensagem":f"Depósito de R$ {valor:.2f} recebido! Taxa: R$ {taxa:.2f}","liquido":liquido})

@app.route('/api/saque', methods=['POST'])
def saque():
    data = request.json
    cpf = data.get('cpf','')
    valor = float(data.get('valor',0))
    taxa = valor * 0.15
    total = valor + taxa
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT saldo_brl FROM clientes WHERE cpf=?",(cpf,))
    r = c.fetchone()
    if not r or r[0] < total:
        conn.close()
        return jsonify({"erro":"Saldo insuficiente"}),400
    novo = r[0] - total
    c.execute("UPDATE clientes SET saldo_brl=? WHERE cpf=?",(novo,cpf))
    c.execute("INSERT INTO transacoes (cliente_id,tipo,valor,taxa,descricao) VALUES(?,?,?,?,?)",
             (cpf,'saque',valor,taxa,f'Saque: R$ {valor:.2f}'))
    conn.commit()
    conn.close()
    return jsonify({"ok":True,"mensagem":f"Saque de R$ {valor:.2f} realizado! Taxa: R$ {taxa:.2f}"})

@app.route('/api/extrato', methods=['POST'])
def extrato():
    data = request.json
    cpf = data.get('cpf','')
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT tipo,valor,taxa,descricao,data FROM transacoes WHERE cliente_id=? ORDER BY data DESC LIMIT 20",(cpf,))
    rows = c.fetchall()
    conn.close()
    ext = [{"tipo":r[0],"valor":r[1],"taxa":r[2],"descricao":r[3],"data":r[4]} for r in rows]
    return jsonify({"ok":True,"extrato":ext})

# ═══════════════════════════════════════
# CRIPTO
# ═══════════════════════════════════════

@app.route('/api/crypto/cotacao')
def cotacao():
    return jsonify({
        "XMR":{"BRL":1200.00,"USD":240.00},
        "BTC":{"BRL":350000.00,"USD":70000.00},
        "ETH":{"BRL":12000.00,"USD":2400.00},
        "USDT":{"BRL":5.00,"USD":1.00}
    })

# ═══════════════════════════════════════
# METAS
# ═══════════════════════════════════════

@app.route('/api/metas', methods=['POST'])
def metas_listar():
    data = request.json
    cpf = data.get('cpf','')
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT id,nome,valor_meta,valor_atual FROM metas WHERE cliente_id=?",(cpf,))
    rows = c.fetchall()
    conn.close()
    metas = [{"id":r[0],"nome":r[1],"valor_meta":r[2],"valor_atual":r[3]} for r in rows]
    return jsonify({"ok":True,"metas":metas})

@app.route('/api/metas/criar', methods=['POST'])
def metas_criar():
    data = request.json
    cpf = data.get('cpf','')
    nome = data.get('nome','')
    valor = float(data.get('valor',0))
    conn = conectar()
    c = conn.cursor()
    c.execute("INSERT INTO metas (cliente_id,nome,valor_meta) VALUES(?,?,?)",(cpf,nome,valor))
    conn.commit()
    conn.close()
    return jsonify({"ok":True,"mensagem":f"Meta '{nome}' criada!"})

# ═══════════════════════════════════════
# VAULT
# ═══════════════════════════════════════

@app.route('/api/vault/depositar', methods=['POST'])
def vault_depositar():
    data = request.json
    cpf = data.get('cpf','')
    valor = float(data.get('valor',0))
    horas = int(data.get('horas',72))
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT saldo_brl FROM clientes WHERE cpf=?",(cpf,))
    r = c.fetchone()
    if not r or r[0] < valor:
        conn.close()
        return jsonify({"erro":"Saldo insuficiente"}),400
    novo_saldo = r[0] - valor
    c.execute("UPDATE clientes SET saldo_brl=? WHERE cpf=?",(novo_saldo,cpf))
    c.execute("INSERT INTO vault (cliente_id,valor,tempo_espera,solic_data) VALUES(?,?,?,datetime('now'))",
             (cpf,valor,horas))
    conn.commit()
    conn.close()
    return jsonify({"ok":True,"mensagem":f"R$ {valor:.2f} depositado no Vault! Tempo de espera: {horas}h"})

@app.route('/api/vault/status', methods=['POST'])
def vault_status():
    data = request.json
    cpf = data.get('cpf','')
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT SUM(valor) FROM vault WHERE cliente_id=? AND status='ativo'",(cpf,))
    r = c.fetchone()
    conn.close()
    return jsonify({"ok":True,"saldo_vault":r[0] or 0})

# ═══════════════════════════════════════
# AFILIADOS
# ═══════════════════════════════════════

@app.route('/api/afiliados/indicar', methods=['POST'])
def afiliados_indicar():
    data = request.json
    cpf = data.get('cpf','')
    codigo = data.get('codigo','')
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT id FROM clientes WHERE codigo_afiliado=?",(codigo,))
    r = c.fetchone()
    if r:
        c.execute("UPDATE clientes SET saldo_brl = saldo_brl + 50 WHERE id=?",(r[0],))
        conn.commit()
        conn.close()
        return jsonify({"ok":True,"mensagem":"Indicação registrada! R$ 50 creditados."})
    conn.close()
    return jsonify({"erro":"Código de afiliado inválido"}),404

# ═══════════════════════════════════════
# SISTEMA
# ═══════════════════════════════════════

@app.route('/')
def home():
    return jsonify({"app":"UmbreonPay API","versao":"1.0","status":"online","rotas":[
        "/api/auth/cadastrar","/api/auth/login","/api/auth/recuperar",
        "/api/pix/enviar","/api/deposito","/api/saque","/api/extrato",
        "/api/crypto/cotacao","/api/metas","/api/vault","/api/afiliados"
    ]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
