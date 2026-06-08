#!/usr/bin/env python3
"""API de Autenticação UmbreonPay"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, hashlib, secrets, sqlite3, os, re

DB = os.path.expanduser("~/umbreonpay/umbreonpay.db")

def conectar():
    return sqlite3.connect(DB)

class AuthAPI(BaseHTTPRequestHandler):
    def _send(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_POST(self):
        try:
            length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(length))
        except:
            self._send({"erro":"JSON inválido"},400)
            return

        if self.path == '/api/auth/cadastrar':
            self.cadastrar(body)
        elif self.path == '/api/auth/login':
            self.login(body)
        elif self.path == '/api/auth/recuperar':
            self.recuperar(body)
        else:
            self._send({"erro":"Rota não encontrada"},404)

    def cadastrar(self, data):
        nome = data.get('nome','')
        cpf = data.get('cpf','')
        email = data.get('email','')
        senha = hashlib.sha256(data.get('senha','').encode()).hexdigest()

        if not all([nome, cpf, email, senha]):
            self._send({"erro":"Todos os campos são obrigatórios"},400)
            return

        codigo = 'UB-REF-' + secrets.token_hex(4).upper()

        try:
            conn = conectar()
            c = conn.cursor()
            c.execute("INSERT INTO clientes (id,nome,cpf,email,senha_hash,codigo_afiliado) VALUES(?,?,?,?,?,?)",
                     (cpf,nome,cpf,email,senha,codigo))
            conn.commit()
            conn.close()
            self._send({"ok":True,"mensagem":"Conta criada!","codigo_afiliado":codigo})
        except sqlite3.IntegrityError:
            self._send({"erro":"CPF ou email já cadastrado"},400)

    def login(self, data):
        cpf = data.get('cpf','')
        senha = hashlib.sha256(data.get('senha','').encode()).hexdigest()

        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT nome,saldo_brl,saldo_xmr,nivel,codigo_afiliado FROM clientes WHERE cpf=? AND senha_hash=?",
                 (cpf,senha))
        r = c.fetchone()
        conn.close()

        if r:
            self._send({"ok":True,"nome":r[0],"saldo_brl":r[1],"saldo_xmr":r[2],"nivel":r[3],"codigo_afiliado":r[4]})
        else:
            self._send({"erro":"CPF ou senha incorretos"},401)

    def recuperar(self, data):
        email = data.get('email','')
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT email FROM clientes WHERE email=?",(email,))
        r = c.fetchone()
        conn.close()
        if r:
            self._send({"ok":True,"mensagem":"Link enviado para seu email"})
        else:
            self._send({"erro":"Email não encontrado"},404)

def iniciar(porta=8080):
    server = HTTPServer(('0.0.0.0',porta), AuthAPI)
    print(f"🔐 API Auth rodando na porta {porta}")
    server.serve_forever()

if __name__ == "__main__":
    iniciar()
