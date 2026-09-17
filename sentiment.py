import os
from dataclasses import dataclass

from typesafe_sdk import Noul, Score, TypeSafeClient

RELEVANCE_THRESHOLD = 0.5
CONFIDENCE_FLOOR = 0.4

SENTIMENT_LEVELS = [
    "Muito negativo: risco relevante, guidance cortado, fraude, calote, investigação",
    "Negativo: resultado abaixo do esperado, corte de estimativa, perda de contrato",
    "Neutro: fato administrativo sem direção clara de preço",
    "Positivo: resultado acima do esperado, novo contrato, upgrade de rating",
    "Muito positivo: fusão/aquisição vantajosa, guidance elevado, ganho estrutural",
]


@dataclass
class HeadlineAnalysis:
    ticker: str
    headline: str
    relevant: bool
    relevance_prob: float
    sentiment_score: float
    sentiment_confidence: float


def analyze_headline(client: TypeSafeClient, ticker: str, headline: str) -> HeadlineAnalysis:
    response = client.system_one(
        state={"ticker": ticker, "headline": headline},
        questions={
            "relevance": Noul(
                instructions="A notícia em `headline` é diretamente relevante para o preço da ação em `ticker`?",
            ),
            "sentiment": Score(
                instructions="Qual o impacto da notícia em `headline` no sentimento de mercado sobre `ticker`?",
                criteria=SENTIMENT_LEVELS,
            ),
        },
    )
    relevance_prob = response.answers["relevance"].noul
    sentiment = response.answers["sentiment"]
    return HeadlineAnalysis(
        ticker=ticker,
        headline=headline,
        relevant=relevance_prob >= RELEVANCE_THRESHOLD,
        relevance_prob=relevance_prob,
        sentiment_score=sentiment.score,
        sentiment_confidence=sentiment.confidence,
    )


def sentiment_index(analyses: list[HeadlineAnalysis]) -> float | None:
    """Média normalizada em [-1, 1] das notícias relevantes e com confiança suficiente."""
    usable = [a for a in analyses if a.relevant and a.sentiment_confidence >= CONFIDENCE_FLOOR]
    if not usable:
        return None
    top_level = len(SENTIMENT_LEVELS) - 1
    normalized = [(a.sentiment_score / top_level) * 2 - 1 for a in usable]
    return sum(normalized) / len(normalized)


if __name__ == "__main__":
    feed = [
        ("PETR4", "Petrobras anuncia corte de 15% no guidance de produção para 2027"),
        ("PETR4", "Petrobras confirma pagamento de dividendos extraordinários acima do esperado"),
        ("PETR4", "Diretor de RH da Petrobras é substituído após reestruturação interna"),
    ]

    if not os.environ.get("TYPESAFE_API_KEY"):
        raise SystemExit("Defina a variável de ambiente TYPESAFE_API_KEY antes de rodar.")

    with TypeSafeClient() as client:
        results = [analyze_headline(client, ticker, headline) for ticker, headline in feed]

    for r in results:
        status = "relevante" if r.relevant else "ignorada"
        print(
            f"[{r.ticker}] {status} | sentimento={r.sentiment_score:.2f} "
            f"(conf={r.sentiment_confidence:.2f}, rel={r.relevance_prob:.2f}) | {r.headline}"
        )

    idx = sentiment_index(results)
    print(f"\nÍndice de sentimento agregado (-1 bearish .. +1 bullish): {idx}")
