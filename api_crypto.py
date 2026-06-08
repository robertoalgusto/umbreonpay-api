#!/usr/bin/env python3
"""API de Criptomoedas UmbreonPay"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os, subprocess

MONERO_CLI = os.path.expanduser("~/monero-aarch64-linux-android-v0.18.5.0/monero-wallet-cli")
CARTEIRA = os.path.expanduser("~/monero-aarch64-linux-android-v0.18.5.0/carteira_principal_umb")

class CryptoAPI(BaseHTTPRequestHandler):
    def _send(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        if self.path == '/api/crypto/cotacao':
            self.cotacao()
        elif self.path == '/api/crypto/endereco':
            self.endereco()
        else:
            self._send({"erro":"Rota não encontrada"},404)

    def cotacao(self):
        # Simulação (no futuro: puxar da API da Binance/CoinGecko)
        self._send({"XMR":{"BRL":1200.00,"USD":240.00},"BTC":{"BRL":350000.00,"USD":70000.00}})

    def endereco(self):
        try:
            result = subprocess.run([MONERO_CLI,"--wallet-file",CARTEIRA,"--command","address"],
                                  capture_output=True,text=True,timeout=10)
            for line in result.stdout.split('\n'):
                if line.strip().startswith('4'):
                    self._send({"ok":True,"endereco":line.strip()})
                    return
            self._send({"erro":"Endereço não encontrado"},500)
        except:
            self._send({"erro":"Carteira offline"},500)

def iniciar(porta=8082):
    server = HTTPServer(('0.0.0.0',porta), CryptoAPI)
    print(f"🪙 API Crypto rodando na porta {porta}")
    server.serve_forever()

if __name__ == "__main__":
    iniciar()
