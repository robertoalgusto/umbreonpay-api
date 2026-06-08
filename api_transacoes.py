#!/usr/bin/env python3
"""
╔══════════════════════════════════════════╗
║   UMBREONPAY — API DE TRANSAÇÕES         ║
║   Pix, Depósito, Saque, Extrato          ║
╚══════════════════════════════════════════╝
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json, sqlite3, os, random, hashlib, secrets
from datetime import datetime

DB = os.path.expanduser("~/umbreonpay/umbreonpay.db")

def conectar():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

class TransAPI(BaseHTTPRequestHandler):
    def _send(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self._send({})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length)) if length > 0 else {}
        except:
            self._send({"erro":"JSON inválido"}, 400)
            return

        if self.path == '/api/pix/enviar':
            self.pix_enviar(body)
        elif self.path == '/api/deposito':
            self.deposito(body)
        elif self.path == '/api/saque':
            self.saque(body)
        elif self.path == '/api/extrato':
            self.extrato(body)
        elif self.path == '/api/transacoes/todas':
            self.todas_transacoes(body)
        else:
            self._send({"erro":"Rota não encontrada"}, 404)

    def pix_enviar(self, data):
        cpf = data.get('cpf','')
        valor = float(data.get('valor',0))
        if valor <= 0:
            self._send({"erro":"Valor inválido"}, 400)
            return
        
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT saldo_brl FROM clientes WHERE cpf=? OR id=?",(cpf,cpf))
        r = c.fetchone()
        if not r or r[0] < valor:
            conn.close()
            self._send({"erro":"Saldo insuficiente"}, 400)
            return
        
        taxa = round(valor * 0.015, 2)
        total = valor + taxa
        novo_saldo = r[0] - total
        
        c.execute("UPDATE clientes SET saldo_brl=? WHERE cpf=? OR id=?",(novo_saldo,cpf,cpf))
        c.execute("INSERT INTO transacoes (cliente_id,tipo,valor,taxa,descricao) VALUES(?,?,?,?,?)",
                 (cpf,'pix_enviado',valor,taxa,f'Pix enviado — R$ {valor:.2f} + taxa R$ {taxa:.2f}'))
        conn.commit()
        conn.close()
        
        self._send({"ok":True,"mensagem":f"Pix de R$ {valor:.2f} enviado!","taxa":taxa,"total":total,"novo_saldo":novo_saldo})

    def deposito(self, data):
        cpf = data.get('cpf','')
        valor = float(data.get('valor',0))
        titularidade = data.get('titularidade','propria')
        
        if valor <= 0:
            self._send({"erro":"Valor inválido"}, 400)
            return
        
        taxa = 0 if titularidade == 'propria' else round(valor * 0.25, 2)
        liquido = valor - taxa
        
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT saldo_brl FROM clientes WHERE cpf=? OR id=?",(cpf,cpf))
        r = c.fetchone()
        if not r:
            conn.close()
            self._send({"erro":"Cliente não encontrado"}, 404)
            return
        
        novo_saldo = r[0] + liquido
        c.execute("UPDATE clientes SET saldo_brl=? WHERE cpf=? OR id=?",(novo_saldo,cpf,cpf))
        c.execute("INSERT INTO transacoes (cliente_id,tipo,valor,taxa,descricao) VALUES(?,?,?,?,?)",
                 (cpf,'deposito',valor,taxa,f'Depósito — R$ {valor:.2f} (líquido R$ {liquido:.2f})'))
        conn.commit()
        conn.close()
        
        self._send({"ok":True,"mensagem":f"Depósito de R$ {valor:.2f} recebido!","taxa":taxa,"liquido":liquido,"novo_saldo":novo_saldo})

    def saque(self, data):
        cpf = data.get('cpf','')
        valor = float(data.get('valor',0))
        
        if valor <= 0:
            self._send({"erro":"Valor inválido"}, 400)
            return
        
        taxa = round(valor * 0.15, 2)
        total = valor + taxa
        
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT saldo_brl FROM clientes WHERE cpf=? OR id=?",(cpf,cpf))
        r = c.fetchone()
        if not r or r[0] < total:
            conn.close()
            self._send({"erro":"Saldo insuficiente"}, 400)
            return
        
        novo_saldo = r[0] - total
        c.execute("UPDATE clientes SET saldo_brl=? WHERE cpf=? OR id=?",(novo_saldo,cpf,cpf))
        c.execute("INSERT INTO transacoes (cliente_id,tipo,valor,taxa,descricao) VALUES(?,?,?,?,?)",
                 (cpf,'saque',valor,taxa,f'Saque — R$ {valor:.2f} + taxa R$ {taxa:.2f}'))
        conn.commit()
        conn.close()
        
        self._send({"ok":True,"mensagem":f"Saque de R$ {valor:.2f} realizado!","taxa":taxa,"total":total,"novo_saldo":novo_saldo})

    def extrato(self, data):
        cpf = data.get('cpf','')
        limite = int(data.get('limite', 20))
        
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT tipo,valor,taxa,descricao,data FROM transacoes WHERE cliente_id=? ORDER BY data DESC LIMIT ?",(cpf,limite))
        rows = c.fetchall()
        conn.close()
        
        ext = [{"tipo":r[0],"valor":r[1],"taxa":r[2],"descricao":r[3],"data":r[4]} for r in rows]
        self._send({"ok":True,"extrato":ext,"total":len(ext)})

    def todas_transacoes(self, data):
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT cliente_id,tipo,valor,taxa,descricao,data FROM transacoes ORDER BY data DESC LIMIT 100")
        rows = c.fetchall()
        conn.close()
        
        trans = [{"cliente":r[0],"tipo":r[1],"valor":r[2],"taxa":r[3],"descricao":r[4],"data":r[5]} for r in rows]
        self._send({"ok":True,"transacoes":trans,"total":len(trans)})

def iniciar(porta=8081):
    server = HTTPServer(('0.0.0.0',porta), TransAPI)
    print(f"💰 API Transações rodando na porta {porta}")
    server.serve_forever()

if __name__ == "__main__":
    iniciar()
