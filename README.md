# jev-trader

Análise de mercado em tempo real usando o [Jev](https://typesafe.ai) (System One model da TypeSafe) via [Vercel AI Gateway](https://vercel.com/ai-gateway).

Dois módulos por enquanto:

- **Sentimento de notícias** ([sentiment.py](sentiment.py) / [sentiment.mjs](sentiment.mjs)) — classifica manchetes por relevância e intensidade de sentimento (bearish → bullish).
- **Sinal de compra/venda** ([signals/](signals/)) — para uma cesta de ativos (FX, metais, energia, juros, crypto) via dados do MetaTrader5, gera viés direcional (`comprar`/`vender`/`manter`) com força e convicção.

Um módulo de volatilidade/opções (IV, put wall, call wall, gamma flip, open interest) está planejado, ainda não implementado.

**Não tem interface gráfica ainda** — tudo roda via linha de comando (`signal_demo.py`, `sentiment.py`). Um dashboard web simples é um próximo passo natural, se fizer sentido.

## Arquitetura

```
Python (sinal/indicadores, cliente MT5)
   │  HTTP local (POST /evaluate)
   ▼
bridge/server.mjs (Node)  ──►  Vercel AI Gateway  ──►  Jev
   │
   ▼ (Linux/macOS apenas)
rpyc  ──►  Python dentro do Wine  ──►  MetaTrader5  ──►  Terminal MT5
```

O pacote oficial `MetaTrader5` só existe para Windows, por isso o bridge Node existe (pra falar com o Jev a partir do Python) e por isso o Linux precisa da ponte extra via Wine.

## Pré-requisitos

- Node.js 18+
- Python 3.11+
- Conta no [Vercel AI Gateway](https://vercel.com/ai-gateway) com uma `AI_GATEWAY_API_KEY` (Settings → API Keys)
- Para dados reais de mercado: uma conta MetaTrader5 (demo serve) numa corretora qualquer
- [Ollama](https://ollama.com) local é opcional — só foi usado durante o desenvolvimento como sub-agente de codificação/testes, não é necessário para rodar o projeto

## Setup

### 1. Bridge Jev (Node)

```bash
npm install
export AI_GATEWAY_API_KEY="sua-chave-do-vercel-ai-gateway"
node bridge/server.mjs
```

Isso sobe um servidor HTTP local em `http://127.0.0.1:8787` que expõe o Jev pro lado Python. Deixe rodando numa aba de terminal separada.

Por padrão ele espaça as chamadas reais ao Jev em **10 segundos** (pra não estourar rate limit do free tier do Gateway). Pra mudar:

```bash
# via variável de ambiente, antes de subir o servidor
export JEV_MIN_INTERVAL_MS=3000

# ou em tempo real, sem reiniciar
curl -X POST http://127.0.0.1:8787/config -d '{"minIntervalMs": 3000}'
curl http://127.0.0.1:8787/config   # ver o valor atual
```

### 2. Python

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3. Testar sem dados reais (nenhuma conta MT5 necessária)

```bash
# sentimento de notícias (Node)
node sentiment.mjs

# sinal de compra/venda com dados sintéticos (Python)
.venv/bin/python signal_demo.py
```

### 4. Testes automatizados

```bash
.venv/bin/python -m pytest tests/ -v
```

Não dependem de rede nem do bridge — usam dados sintéticos e mockam a resposta do Jev.

## Dados reais de mercado (MetaTrader5)

### Windows

O caminho simples: o pacote oficial funciona direto.

1. Instale e abra o terminal MetaTrader5, faça login na sua conta (demo ou real).
2. `.venv\Scripts\pip install MetaTrader5`
3. Rode `python signal_demo.py --mt5` com o terminal aberto e logado.

A classe `MT5MarketDataProvider` detecta o Windows automaticamente e usa o pacote direto, sem precisar de bridge nenhuma.

### Linux (via Wine)

Não existe pacote `MetaTrader5` pra Linux — a solução é rodar um Python *dentro* do Wine só pra hospedar esse pacote, e expor uma ponte local (`rpyc`) pro Python nativo consumir. Passo a passo (o que foi feito e validado neste projeto):

```bash
# 1. Wine (com suporte a 32 bits — o instalador do MT5 e do Python precisam)
sudo dpkg --add-architecture i386 && sudo apt-get update
sudo apt-get install -y wine winetricks

# 2. Crie o prefixo já com suporte a 32+64 bits (nesta ordem, senão fica quebrado)
WINEARCH=win64 WINEPREFIX=~/.wine /usr/lib/wine/wine64 wineboot -i

# 3. Runtime C++ real da Microsoft (evita crash "unimplemented function ucrtbase.dll.*")
WINE=/usr/lib/wine/wine64 WINEPREFIX=~/.wine winetricks -q vcrun2022

# 4. Terminal MT5 (baixe de https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe)
/usr/lib/wine/wine64 mt5setup.exe
# faça login na sua conta manualmente na janela que abrir

# 5. Python embarcável 64-bit dentro do prefixo (baixe o "embeddable zip" de python.org,
#    NÃO o instalador normal — o instalador é um stub de 32 bits e trava sem WoW64 completo)
mkdir -p ~/.wine/drive_c/pyembed
unzip python-3.12.7-embed-amd64.zip -d ~/.wine/drive_c/pyembed
# edite ~/.wine/drive_c/pyembed/python312._pth: descomente "import site"
# e adicione a linha "Lib\site-packages"

# 6. pip + pacotes (baixe get-pip.py de https://bootstrap.pypa.io/get-pip.py)
/usr/lib/wine/wine64 "C:\\pyembed\\python.exe" get-pip.py
/usr/lib/wine/wine64 "C:\\pyembed\\python.exe" -m pip install "numpy==1.26.4" MetaTrader5 mt5linux
# numpy mais recente (2.x) também crasha no Wine — fixe em 1.26.4

# 7. Suba o servidor da ponte (deixe rodando; precisa do terminal MT5 aberto e logado)
/usr/lib/wine/wine64 "C:\\pyembed\\python.exe" -m mt5linux --host localhost --port 18812

# 8. No Python nativo (venv já tem mt5linux/rpyc via requirements.txt)
.venv/bin/python signal_demo.py --mt5
```

**Use sempre `/usr/lib/wine/wine64` diretamente**, não o comando `wine` genérico — em sistemas com `wine32` e `wine64` instalados juntos, o script `/usr/bin/wine` prioriza cegamente o loader de 32 bits, o que quebra qualquer coisa num prefixo 64-bit (erro `could not load kernel32.dll, status c0000135`).

A cesta padrão em [signals/instruments.py](signals/instruments.py) usa nomenclatura genérica (`USOIL`, `BTCUSD`, etc.) — cada corretora MT5 tem seus próprios nomes de símbolo. Ajuste a lista conforme o catálogo da sua corretora (`mt5.symbols_get()` pra descobrir os nomes certos).

## Cesta de ativos

Editável em [signals/instruments.py](signals/instruments.py) — FX, metais, energia, juros (proxy) e crypto por padrão. `get_instrument(symbol)` busca um ativo específico.

## Limites de custo/rate limit

O free tier do Vercel AI Gateway trava rápido (poucas chamadas antes de bloquear, com reset após um tempo). Pra uso contínuo/produção, adicione crédito em [vercel.com/ai-gateway](https://vercel.com/ai-gateway).
