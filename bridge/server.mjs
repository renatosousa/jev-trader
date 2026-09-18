import { createServer } from 'node:http';
import { experimental_evaluate as evaluate } from 'ai';

const PORT = process.env.JEV_BRIDGE_PORT ?? 8787;
const MODEL = process.env.JEV_MODEL ?? 'typesafe-ai/jev';

if (!process.env.AI_GATEWAY_API_KEY) {
  console.error('Defina AI_GATEWAY_API_KEY antes de subir o bridge.');
  process.exit(1);
}

// Espaçamento mínimo entre chamadas reais ao Jev, para não estourar rate limit
// (ex: "muitas chamadas por segundo" do free tier do AI Gateway). Ajustável em
// tempo real via POST /config, sem precisar reiniciar o servidor.
let minIntervalMs = Number(process.env.JEV_MIN_INTERVAL_MS ?? 10_000);
let lastCallAt = 0;
let queueLength = 0;
let callQueue = Promise.resolve();

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function throttledEvaluate(args) {
  queueLength += 1;
  const runAfterPrevious = callQueue.catch(() => {});
  const thisCall = runAfterPrevious.then(async () => {
    const wait = Math.max(0, lastCallAt + minIntervalMs - Date.now());
    if (wait > 0) await sleep(wait);
    lastCallAt = Date.now();
    return evaluate(args);
  });
  callQueue = thisCall.catch(() => {});
  try {
    return await thisCall;
  } finally {
    queueLength -= 1;
  }
}

async function handleConfig(req, res) {
  if (req.method === 'GET') {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ minIntervalMs, queueLength }));
    return;
  }

  let body = '';
  for await (const chunk of req) body += chunk;
  let payload;
  try {
    payload = JSON.parse(body);
  } catch {
    res.writeHead(400, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ error: 'invalid_json' }));
    return;
  }

  const next = Number(payload.minIntervalMs);
  if (!Number.isFinite(next) || next < 0) {
    res.writeHead(400, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ error: 'invalid_min_interval_ms' }));
    return;
  }

  minIntervalMs = next;
  res.writeHead(200, { 'content-type': 'application/json' });
  res.end(JSON.stringify({ minIntervalMs, queueLength }));
}

async function handleEvaluate(req, res) {
  let body = '';
  for await (const chunk of req) body += chunk;

  let payload;
  try {
    payload = JSON.parse(body);
  } catch {
    res.writeHead(400, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ error: 'invalid_json' }));
    return;
  }

  const { state, questions } = payload;
  if (!state || !questions) {
    res.writeHead(400, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ error: 'missing_state_or_questions' }));
    return;
  }

  try {
    const result = await throttledEvaluate({ model: MODEL, state, questions });
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ answers: result.answers, usage: result.usage }));
  } catch (err) {
    res.writeHead(502, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ error: 'evaluate_failed', message: String(err?.message ?? err) }));
  }
}

const server = createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/evaluate') {
    handleEvaluate(req, res);
    return;
  }
  if (req.url === '/config' && (req.method === 'GET' || req.method === 'POST')) {
    handleConfig(req, res);
    return;
  }
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ ok: true, model: MODEL, minIntervalMs, queueLength }));
    return;
  }
  res.writeHead(404, { 'content-type': 'application/json' });
  res.end(JSON.stringify({ error: 'not_found' }));
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(
    `jev-bridge escutando em http://127.0.0.1:${PORT} (model=${MODEL}, intervalo mínimo entre chamadas=${minIntervalMs}ms)`,
  );
});
