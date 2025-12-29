import telebot
import pandas as pd
import pandas_ta as ta
import requests
import time
from datetime import datetime, timedelta
from threading import Thread

# ================= CONFIGURAÇÕES =================
TOKEN = "8528452206:AAFNVsv5rLEtOjz0Bp6xTfA5EQsC-J2-plc"
CHAT_ID = "6433711187"

ATIVOS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT",
    "SOLUSDT", "ADAUSDT", "XRPUSDT",
    "AVAXUSDT", "LINKUSDT", "DOTUSDT"
]

TIMEFRAME = "5m"
SCORE_MINIMO = 6

# ================= BOT =================
bot = telebot.TeleBot(TOKEN)

pre_alertas = {}
operacoes = []
stats = {"WIN": 0, "LOSS": 0}

# ================= DADOS BINANCE =================
def get_klines(symbol, limit=200):
    url = (
        f"https://api.binance.com/api/v3/klines"
        f"?symbol={symbol}&interval={TIMEFRAME}&limit={limit}"
    )
    data = requests.get(url, timeout=10).json()

    df = pd.DataFrame(data, columns=[
        "t","o","h","l","c","v","ct","q","n","tb","tq","i"
    ])
    df[["o","h","l","c","v"]] = df[["o","h","l","c","v"]].astype(float)
    return df

# ================= ESTRATÉGIAS =================
def calcular_score(df):
    score = 0
    direcao = None

    rsi = ta.rsi(df["c"], 14).iloc[-1]
    ema200 = ta.ema(df["c"], 200).iloc[-1]
    macd = ta.macd(df["c"]).iloc[-1]
    atr = ta.atr(df["h"], df["l"], df["c"], 14).iloc[-1]
    atr_pct = (atr / df["c"].iloc[-1]) * 100
    preco = df["c"].iloc[-1]

    # Estratégia 1 — RSI + Tendência
    if rsi < 30 and preco > ema200:
        score += 2
        direcao = "COMPRA"

    if rsi > 70 and preco < ema200:
        score += 2
        direcao = "VENDA"

    # Estratégia 2 — MACD
    if macd["MACDh_12_26_9"] > 0 and direcao == "COMPRA":
        score += 2
    if macd["MACDh_12_26_9"] < 0 and direcao == "VENDA":
        score += 2

    # Estratégia 3 — Volatilidade mínima
    if atr_pct >= 0.30:
        score += 2

    return score, direcao, atr_pct, preco

# ================= LOOP DE ANÁLISE =================
def live():
    print("🚀 ROBÔ QUANT INSTITUCIONAL ATIVO")

    while True:
        for ativo in ATIVOS:
            try:
                df = get_klines(ativo)
                score, direcao, atr_pct, preco = calcular_score(df)

                if not direcao:
                    continue

                chave = f"{ativo}_{datetime.now().strftime('%H%M')}"

                # PRÉ-ALERTA
                if score >= SCORE_MINIMO - 1 and chave not in pre_alertas:
                    msg = (
                        f"⚠️ PRÉ-ALERTA\n"
                        f"ATIVO: {ativo}\n"
                        f"POSSÍVEL DIREÇÃO: {direcao}\n"
                        f"SCORE: {score}\n"
                        f"ATR%: {atr_pct:.2f}%\n"
                        f"Entrada estimada em ~5 minutos"
                    )
                    bot.send_message(CHAT_ID, msg)
                    pre_alertas[chave] = True

                # ALERTA OFICIAL
                if score >= SCORE_MINIMO:
                    expiracao = datetime.now() + timedelta(minutes=5)

                    msg = (
                        f"🚨 ALERTA OFICIAL\n"
                        f"ATIVO: {ativo}\n"
                        f"DIREÇÃO: {direcao}\n"
                        f"SCORE: {score}/8\n"
                        f"ATR%: {atr_pct:.2f}%\n"
                        f"PREÇO: {preco}"
                    )
                    bot.send_message(CHAT_ID, msg)

                    operacoes.append({
                        "ativo": ativo,
                        "direcao": direcao,
                        "entrada": preco,
                        "expira": expiracao
                    })

                time.sleep(2)

            except Exception as e:
                print("Erro em", ativo, ":", e)

        time.sleep(30)

# ================= MONITOR DE RESULTADOS =================
def monitor():
    while True:
        agora = datetime.now()

        for op in operacoes[:]:
            if agora >= op["expira"]:
                df = get_klines(op["ativo"], 2)
                preco_final = df["c"].iloc[-1]

                win = (
                    preco_final > op["entrada"]
                    if op["direcao"] == "COMPRA"
                    else preco_final < op["entrada"]
                )

                resultado = "WIN" if win else "LOSS"
                stats[resultado] += 1

                msg = (
                    f"📊 RESULTADO\n"
                    f"ATIVO: {op['ativo']}\n"
                    f"DIREÇÃO: {op['direcao']}\n"
                    f"RESULTADO: {resultado}\n"
                    f"ENTRADA: {op['entrada']}\n"
                    f"SAÍDA: {preco_final}\n"
                    f"PLACAR: {stats['WIN']}W / {stats['LOSS']}L"
                )
                bot.send_message(CHAT_ID, msg)

                operacoes.remove(op)

        time.sleep(15)

# ================= START =================
if __name__ == "__main__":
    Thread(target=live, daemon=True).start()
    Thread(target=monitor, daemon=True).start()

    # Mantém o processo vivo (local ou nuvem)
    while True:
        time.sleep(60)
