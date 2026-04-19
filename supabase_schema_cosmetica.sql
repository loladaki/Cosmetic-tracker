-- ============================================================
-- Correr uma vez no Supabase SQL Editor
-- ============================================================

CREATE TABLE IF NOT EXISTS cosmetica_precos (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data              DATE           NOT NULL,
    produto           TEXT           NOT NULL,
    preco             NUMERIC(10,2),
    pvpr              NUMERIC(10,2),
    desconto_percent  NUMERIC(5,2),
    desconto_euros    NUMERIC(10,2),
    created_at        TIMESTAMPTZ    DEFAULT NOW(),

    UNIQUE (data, produto)
);

-- Índices para o Power BI e queries históricas
CREATE INDEX IF NOT EXISTS idx_cosmetica_data    ON cosmetica_precos (data DESC);
CREATE INDEX IF NOT EXISTS idx_cosmetica_produto ON cosmetica_precos (produto);

-- ============================================================
-- VIEW útil para Power BI: histórico com médias por produto
-- ============================================================

CREATE OR REPLACE VIEW cosmetica_historico AS
SELECT
    data,
    produto,
    preco,
    pvpr,
    desconto_percent,
    desconto_euros,
    -- média histórica do desconto até esse dia (janela deslizante)
    ROUND(AVG(desconto_percent) OVER (
        PARTITION BY produto
        ORDER BY data
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    ), 2) AS media_desconto_historica,
    -- mínimo histórico do preço até esse dia
    MIN(preco) OVER (
        PARTITION BY produto
        ORDER BY data
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    ) AS preco_minimo_historico,
    -- flag se hoje é mínimo histórico
    CASE
        WHEN preco <= MIN(preco) OVER (
            PARTITION BY produto
            ORDER BY data
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) THEN TRUE ELSE FALSE
    END AS e_minimo_historico,
    -- flag se desconto de hoje está acima da média
    CASE
        WHEN desconto_percent > AVG(desconto_percent) OVER (
            PARTITION BY produto
            ORDER BY data
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) THEN TRUE ELSE FALSE
    END AS acima_da_media
FROM cosmetica_precos
ORDER BY produto, data;
