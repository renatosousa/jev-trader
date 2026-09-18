import { createServer } from 'node:http';
import { experimental_evaluate as evaluate } from 'ai';

const PORT = process.env.JEV_BRIDGE_PORT ?? 8787;
const MODEL = process.env.JEV_MODEL ?? 'typesafe-ai/jev';

if (!process.env.AI_GATEWAY_API_KEY) {
  console.error('Defina AI_GATEWAY_API_KEY antes de subir o bridge.');
  process.exit(1);
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
    const result = await evaluate({ model: MODEL, state, questions });
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
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ ok: true, model: MODEL }));
    return;
  }
  res.writeHead(404, { 'content-type': 'application/json' });
  res.end(JSON.stringify({ error: 'not_found' }));
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`jev-bridge escutando em http://127.0.0.1:${PORT} (model=${MODEL})`);
});
