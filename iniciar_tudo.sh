#!/bin/bash
echo "╔══════════════════════════════════════════╗"
echo "║   UMBREONPAY — INICIANDO APIs            ║"
echo "╚══════════════════════════════════════════╝"
echo ""

cd ~/umbreonpay/api

# Iniciar cada API em background
python3 api_auth.py &
echo "🔐 Auth: http://localhost:8080"

python3 api_transacoes.py &
echo "💰 Transações: http://localhost:8081"

python3 api_crypto.py &
echo "🪙 Crypto: http://localhost:8082"

echo ""
echo "✅ Todas as APIs rodando!"
echo "📡 Acesse o site: https://robertoalgusto.github.io/umbreonpay-site/"
echo ""
echo "Pressione Ctrl+C para parar todas."

wait
