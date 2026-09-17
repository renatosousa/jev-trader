import { experimental_evaluate as evaluate } from 'ai';

const RELEVANCE_THRESHOLD = 0.5;
const CONFIDENCE_FLOOR = 0.4;

const SENTIMENT_LEVELS = [
  'Muito negativo: risco relevante, guidance cortado, fraude, calote, investigação',
  'Negativo: resultado abaixo do esperado, corte de estimativa, perda de contrato',
  'Neutro: fato administrativo sem direção clara de preço',
  'Positivo: resultado acima do esperado, novo contrato, upgrade de rating',
  'Muito positivo: fusão/aquisição vantajosa, guidance elevado, ganho estrutural',
];

function maxProbability(probabilities) {
  if (!probabilities) return undefined;
  return Math.max(...Object.values(probabilities));
}

async function analyzeHeadline(ticker, headline) {
  const result = await evaluate({
    model: 'typesafe-ai/jev',
    state: { ticker, headline },
    questions: {
      relevance: {
        type: 'boolean',
        instructions:
          'A notícia em `headline` é diretamente relevante para o preço da ação em `ticker`?',
      },
      sentiment: {
        type: 'score',
        instructions:
          'Qual o impacto da notícia em `headline` no sentimento de mercado sobre `ticker`?',
        criteria: SENTIMENT_LEVELS,
      },
    },
  });

  const relevance = result.answers.relevance;
  const sentiment = result.answers.sentiment;

  const relevanceProb = relevance.probability ?? maxProbability(relevance.probabilities) ?? 0;
  const sentimentConfidence = sentiment.confidence ?? maxProbability(sentiment.probabilities) ?? 0;

  return {
    ticker,
    headline,
    relevant: relevanceProb >= RELEVANCE_THRESHOLD,
    relevanceProb,
    sentimentScore: sentiment.score,
    sentimentConfidence,
  };
}

function sentimentIndex(analyses) {
  const usable = analyses.filter(
    (a) => a.relevant && a.sentimentConfidence >= CONFIDENCE_FLOOR,
  );
  if (usable.length === 0) return null;
  const topLevel = SENTIMENT_LEVELS.length - 1;
  const normalized = usable.map((a) => (a.sentimentScore / topLevel) * 2 - 1);
  return normalized.reduce((sum, v) => sum + v, 0) / normalized.length;
}

async function main() {
  if (!process.env.AI_GATEWAY_API_KEY) {
    console.error('Defina a variável de ambiente AI_GATEWAY_API_KEY antes de rodar.');
    process.exit(1);
  }

  const feed = [
    ['PETR4', 'Petrobras anuncia corte de 15% no guidance de produção para 2027'],
    ['PETR4', 'Petrobras confirma pagamento de dividendos extraordinários acima do esperado'],
    ['PETR4', 'Diretor de RH da Petrobras é substituído após reestruturação interna'],
  ];

  const results = [];
  for (const [ticker, headline] of feed) {
    results.push(await analyzeHeadline(ticker, headline));
  }

  for (const r of results) {
    const status = r.relevant ? 'relevante' : 'ignorada';
    console.log(
      `[${r.ticker}] ${status} | sentimento=${r.sentimentScore.toFixed(2)} ` +
        `(conf=${r.sentimentConfidence.toFixed(2)}, rel=${r.relevanceProb.toFixed(2)}) | ${r.headline}`,
    );
  }

  const idx = sentimentIndex(results);
  console.log(`\nÍndice de sentimento agregado (-1 bearish .. +1 bullish): ${idx}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
