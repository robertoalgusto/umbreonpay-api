#!/usr/bin/env python3
"""
╔══════════════════════════════════════════╗
║   UMBREONPAY — API UNIFICADA v4.0 FINAL  ║
║   Flask + PostgreSQL + Monero + Mixer    ║
║   Anti-MED + Fragmentação                ║
╚══════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2, hashlib, secrets, os, random, time
from datetime import datetime
from monero_service import MoneroService
from mixer_service import MixerService, AntiMED

app = Flask(__name__)
CORS(app)

DB_HOST = "db.fvnyxxcicytfetikqkxe.supabase.co"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "UmbreonPay2026!@#X9JNFDYHCFIJVD57HD6UJFTIIBFY7JBFYUIHF"
DB_PORT = "5432"

monero = MoneroService()
mixer = MixerService()
antimed = AntiMED()

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
        return jsonify({"erro":"Campos obrigatórios"}),400
    try:
        conn = conectar()
        c = conn.cursor()
        c.execute("INSERT INTO clientes (id,nome,cpf,email,senha_hash,codigo_afiliado) VALUES(%s,%s,%s,%s,%s,%s)",
                 (cpf,nome,cpf,email,senha,codigo))
        conn.commit()
        conn.close()
        return jsonify({"ok":True,"mensagem":"Conta criada!","codigo_afiliado":codigo})
    except psycopg2.errors.UniqueViolation:
        return jsonify({"erro":"CPF ou email já cadastrado"}),400

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    cpf = data.get('cpf','')
    senha = hashlib.sha256(data.get('senha','').encode()).hexdigest()
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT nome,saldo_brl,saldo_xmr,nivel,codigo_afiliado FROM clientes WHERE cpf=%s AND senha_hash=%s",(cpf,senha))
    r = c.fetchone()
    conn.close()
    if r:
        return jsonify({"ok":True,"nome":r[0],"saldo_brl":float(r[1]),"saldo_xmr":float(r[2]),"nivel":r[3],"codigo_afiliado":r[4]})
    return jsonify({"erro":"CPF ou senha incorretos"}),401

# ═══════════════════════════════════════
# TRANSAÇÕES COM MIXER + ANTI-MED
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
    
    # ANTI-MED: tri-assinatura
    tri = antimed.tri_assinatura(cpf, valor, "destino")
    contrato = antimed.contrato_aceitacao(cpf, valor, "destino")
    
    # MIXER: fragmentar valor
    fragmentos = mixer.fragmentar(valor)
    
    c.execute("UPDATE clientes SET saldo_brl=%s WHERE cpf=%s",(novo,cpf))
    c.execute("INSERT INTO transacoes (cliente_id,tipo,valor,taxa,descricao) VALUES(%s,%s,%s,%s,%s)",
             (cpf,'pix_enviado',valor,taxa,f'Pix: R$ {valor:.2f} | Anti-MED: {tri["tx_hash"][:12]}'))
    conn.commit()
    conn.close()
    
    return jsonify({
        "ok":True,
        "mensagem":f"Pix de R$ {valor:.2f} enviado!",
        "taxa":taxa,
        "anti_med":tri,
        "contrato":contrato,
        "fragmentos":len(fragmentos),
        "irreversivel":True
    })

@app.route('/api/deposito', methods=['POST'])
def deposito():
    data = request.json
    cpf = data.get('cpf','')
    valor = float(data.get('valor',0))
    titularidade = data.get('titularidade','propria')
    taxa = 0 if titularidade == 'propria' else valor * 0.25
    liquido = valor - taxa
    
    # Gerar volume fantasma para confundir
    fantasmas = mixer.volume_fantasma()
    
    conn = conectar()
    c = conn.cursor()
    c.execute("UPDATE clientes SET saldo_brl = saldo_brl + %s WHERE cpf=%s",(liquido,cpf))
    c.execute("INSERT INTO transacoes (cliente_id,tipo,valor,taxa,descricao) VALUES(%s,%s,%s,%s,%s)",
             (cpf,'deposito',valor,taxa,f'Depósito: R$ {valor:.2f} | Fantasmas: {len(fantasmas)}'))
    conn.commit()
    conn.close()
    
    return jsonify({
        "ok":True,
        "mensagem":f"Depósito de R$ {valor:.2f} recebido!",
        "taxa":taxa,
        "liquido":liquido,
        "fantasmas":len(fantasmas),
        "privacidade":"Volume fantasma ativado"
    })

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
    
    # Anti-MED no saque
    tri = antimed.tri_assinatura(cpf, valor, "saque")
    
    # Delay aleatório
    delay = mixer.delay_aleatorio()
    
    c.execute("UPDATE clientes SET saldo_brl=%s WHERE cpf=%s",(novo,cpf))
    c.execute("INSERT INTO transacoes (cliente_id,tipo,valor,taxa,descricao) VALUES(%s,%s,%s,%s,%s)",
             (cpf,'saque',valor,taxa,f'Saque: R$ {valor:.2f} | Delay: {delay}s'))
    conn.commit()
    conn.close()
    
    return jsonify({
        "ok":True,
        "mensagem":f"Saque de R$ {valor:.2f} realizado!",
        "taxa":taxa,
        "anti_med":tri,
        "delay_segundos":delay,
        "irreversivel":True
    })

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
    return jsonify({"XMR":{"BRL":1200.00},"BTC":{"BRL":350000.00}})

@app.route('/api/crypto/carteira', methods=['POST'])
def criar_carteira():
    data = request.json
    resultado = monero.gerar_carteira()
    return jsonify({"ok":True,"endereco":resultado['endereco'],"seed":resultado['seed']})

# ═══════════════════════════════════════
# METAS
# ═══════════════════════════════════════

@app.route('/api/metas', methods=['POST'])
def metas_listar():
    data = request.json; cpf = data.get('cpf','')
    conn = conectar(); c = conn.cursor()
    c.execute("SELECT id,nome,valor_meta,valor_atual FROM metas WHERE cliente_id=%s",(cpf,))
    rows = c.fetchall(); conn.close()
    return jsonify({"ok":True,"metas":[{"id":r[0],"nome":r[1],"valor_meta":r[2],"valor_atual":r[3]} for r in rows]})

# ═══════════════════════════════════════
# VAULT
# ═══════════════════════════════════════

@app.route('/api/vault/depositar', methods=['POST'])
def vault_depositar():
    data = request.json; cpf = data.get('cpf',''); valor = float(data.get('valor',0))
    horas = int(data.get('horas',72))
    conn = conectar(); c = conn.cursor()
    c.execute("SELECT saldo_brl FROM clientes WHERE cpf=%s",(cpf,))
    r = c.fetchone()
    if not r or r[0] < valor: conn.close(); return jsonify({"erro":"Saldo insuficiente"}),400
    c.execute("UPDATE clientes SET saldo_brl=%s WHERE cpf=%s",(r[0]-valor,cpf))
    c.execute("INSERT INTO vault (cliente_id,valor,tempo_espera) VALUES(%s,%s,%s)",(cpf,valor,horas))
    conn.commit(); conn.close()
    return jsonify({"ok":True,"mensagem":f"R$ {valor:.2f} no Vault! ({horas}h)"})

# ═══════════════════════════════════════
# AFILIADOS
# ═══════════════════════════════════════

@app.route('/api/afiliados/indicar', methods=['POST'])
def afiliados_indicar():
    data = request.json; codigo = data.get('codigo','')
    conn = conectar(); c = conn.cursor()
    c.execute("SELECT id FROM clientes WHERE codigo_afiliado=%s",(codigo,))
    r = c.fetchone()
    if r:
        c.execute("UPDATE clientes SET saldo_brl = saldo_brl + 50 WHERE id=%s",(r[0],))
        conn.commit(); conn.close()
        return jsonify({"ok":True,"mensagem":"R$ 50 creditados!"})
    conn.close(); return jsonify({"erro":"Código inválido"}),404

# ═══════════════════════════════════════
# MIXER (ENDPOINT DIRETO)
# ═══════════════════════════════════════

@app.route('/api/mixer/executar', methods=['POST'])
def executar_mixer():
    data = request.json
    valor = float(data.get('valor',1000))
    ciclos = int(data.get('ciclos',10))
    trans = mixer.mixer(valor, ciclos)
    fragmentos = mixer.fragmentar(valor)
    fantasmas = mixer.volume_fantasma()
    return jsonify({
        "ok":True,
        "mixer_transacoes":len(trans),
        "fragmentos":len(fragmentos),
        "fantasmas":len(fantasmas),
        "privacidade":"Máxima"
    })

@app.route('/')
def home():
    return jsonify({
        "app":"UmbreonPay API",
        "versao":"4.0 FINAL",
        "banco":"PostgreSQL",
        "cripto":"Monero RPC",
        "mixer":"Ativo",
        "anti_med":"Ativo",
        "status":"online"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
