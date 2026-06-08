#!/usr/bin/env python3
"""
╔══════════════════════════════════════════╗
║   UMBREONPAY — API UNIFICADA v3.0        ║
║   Flask + PostgreSQL + Monero RPC        ║
║   Transações cripto reais                ║
╚══════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2, hashlib, secrets, os, random
from datetime import datetime
from monero_service import MoneroService

app = Flask(__name__)
CORS(app)

# Banco Supabase
DB_HOST = "db.fvnyxxcicytfetikqkxe.supabase.co"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "UmbreonPay2026!@#X9JNFDYHCFIJVD57HD6UJFTIIBFY7JBFYUIHF"
DB_PORT = "5432"

monero = MoneroService()

def conectar():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT)

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
    return jsonify({"ok":True,"mensagem":f"Pix de R$ {valor:.2f} enviado!","taxa":taxa})

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
    return jsonify({"ok":True,"mensagem":f"Depósito de R$ {valor:.2f} recebido!","taxa":taxa,"liquido":liquido})

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
    return jsonify({"ok":True,"mensagem":f"Saque de R$ {valor:.2f} realizado!","taxa":taxa})

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
# CRIPTO (MONERO REAL)
# ═══════════════════════════════════════

@app.route('/api/crypto/cotacao')
def cotacao():
    return jsonify({"XMR":{"BRL":1200.00,"USD":240.00},"BTC":{"BRL":350000.00,"USD":70000.00}})

@app.route('/api/crypto/carteira', methods=['POST'])
def criar_carteira():
    """Cria uma carteira Monero real para o cliente"""
    data = request.json
    cpf = data.get('cpf','')
    resultado = monero.gerar_carteira()
    return jsonify({"ok":True,"endereco":resultado['endereco'],"seed":resultado['seed']})

@app.route('/api/crypto/saldo', methods=['POST'])
def saldo_crypto():
    data = request.json
    endereco = data.get('endereco','')
    resultado = monero.consultar_saldo(endereco)
    return jsonify(resultado)

@app.route('/api/crypto/enviar', methods=['POST'])
def enviar_crypto():
    data = request.json
    origem = data.get('origem','')
    destino = data.get('destino','')
    valor = float(data.get('valor',0))
    resultado = monero.enviar_transacao(origem,destino,valor)
    return jsonify(resultado)

# ═══════════════════════════════════════
# METAS
# ═══════════════════════════════════════

@app.route('/api/metas', methods=['POST'])
def metas_listar():
    data = request.json
    cpf = data.get('cpf','')
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT id,nome,valor_meta,valor_atual FROM metas WHERE cliente_id=%s",(cpf,))
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
    c.execute("INSERT INTO metas (cliente_id,nome,valor_meta) VALUES(%s,%s,%s)",(cpf,nome,valor))
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
    c.execute("SELECT saldo_brl FROM clientes WHERE cpf=%s",(cpf,))
    r = c.fetchone()
    if not r or r[0] < valor:
        conn.close()
        return jsonify({"erro":"Saldo insuficiente"}),400
    novo = r[0] - valor
    c.execute("UPDATE clientes SET saldo_brl=%s WHERE cpf=%s",(novo,cpf))
    c.execute("INSERT INTO vault (cliente_id,valor,tempo_espera) VALUES(%s,%s,%s)",(cpf,valor,horas))
    conn.commit()
    conn.close()
    return jsonify({"ok":True,"mensagem":f"R$ {valor:.2f} depositado no Vault! ({horas}h de espera)"})

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
    c.execute("SELECT id FROM clientes WHERE codigo_afiliado=%s",(codigo,))
    r = c.fetchone()
    if r:
        c.execute("UPDATE clientes SET saldo_brl = saldo_brl + 50 WHERE id=%s",(r[0],))
        conn.commit()
        conn.close()
        return jsonify({"ok":True,"mensagem":"Indicação registrada! R$ 50 creditados."})
    conn.close()
    return jsonify({"erro":"Código inválido"}),404

# ═══════════════════════════════════════
# SISTEMA
# ═══════════════════════════════════════

@app.route('/')
def home():
    return jsonify({"app":"UmbreonPay API","versao":"3.0","banco":"PostgreSQL","cripto":"Monero RPC","status":"online"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
