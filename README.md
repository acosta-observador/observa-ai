# Observa AI

Ferramenta **interna** do Observador para ajudar jornalistas a encontrar notícias. Duas modalidades:

1. **Radar** — ingestão diária de fontes oficiais, classificação de relevância por IA (score, categoria, resumo, "porque pode ser notícia", entidades, localização) e mapa de Portugal.
2. **Searcher ativo** — *missões* persistentes ("avisa-me se aparecer algo sobre habitação em despachos") que correm em background e geram alertas, mais uma caixa de pesquisa livre com fontes citadas.

Cada alerta tem **Útil / Ruído**; os votos recentes entram como exemplos (few-shot) no prompt de classificação.

```
backend/    FastAPI + SQLAlchemy + Alembic, conectores, pipeline, jobs (cron), testes
frontend/   React + Vite + TypeScript + MapLibre GL (compilado e servido pelo backend)
render.yaml Blueprint do Render (1 web, 1 Postgres, 2 cron jobs)
.env.example  variáveis de ambiente documentadas
```

---

## 1. Correr localmente (com dados de demonstração, sem chaves)

Requisitos: Python 3.11+ e Node 20+. Não precisas de Postgres: localmente usa SQLite.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
# variáveis: a app lê o ambiente (não carrega .env sozinha). Para a demo basta:
export APP_PASSWORD=demo SECRET_KEY=dev LLM_PROVIDER=fake
# (ou: cp ../.env.example ../.env e depois `set -a; source ../.env; set +a`)
alembic upgrade head
python -m app.seed              # 28 documentos FICTÍCIOS ("[Demo]"), 2 missões, feedback de exemplo
cd ../frontend && npm install && npm run build && cd ../backend
uvicorn app.main:app --port 8000
```

Abre http://localhost:8000 e entra com a password (`demo`). Se não definires `APP_PASSWORD` localmente, a app abre sem login (só em desenvolvimento; em produção recusa arrancar sem ela).

Desenvolvimento do frontend com hot reload: `cd frontend && npm run dev` (http://localhost:5173, faz proxy de `/api` para a porta 8000).

`LLM_PROVIDER=fake` é um classificador de **palavras-chave** sem rede (não é IA) — serve para ver o produto a funcionar. Para IA a sério: `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`.

Correr a ingestão real e as missões à mão (precisam de rede; a classificação precisa de IA configurada):

```bash
python -m app.jobs ingest       # ingere IPMA, fogos.pt, DRE (descoberta) e classifica pendentes
python -m app.jobs missions     # corre as missões ativas devidas
```

Testes (LLM sempre mockado, sem rede):

```bash
cd backend && python -m pytest -q
```

---

## 2. Criar o repositório no GitHub e fazer push

O projeto já tem um repositório git local com commits pequenos. Com a CLI do GitHub (`gh`):

```bash
cd "Observa AI"
gh auth login                                   # uma vez
gh repo create observa-ai --private --source=. --remote=origin --push
```

Sem `gh`: cria um repositório **privado** vazio em github.com/new e depois

```bash
git remote add origin git@github.com:<organizacao-ou-utilizador>/observa-ai.git
git branch -M main
git push -u origin main
```

Confirma antes do push que não há segredos: o `.gitignore` já exclui `.env`, bases de dados locais, `node_modules` e `frontend/dist`; só o `.env.example` (sem valores reais) vai para o repo.

---

## 3. Deploy no Render (Blueprint)

1. Em https://dashboard.render.com → **New → Blueprint** → liga a tua conta GitHub e escolhe o repositório `observa-ai`.
2. O Render lê o `render.yaml` e propõe: **observa-ai** (web), **observa-db** (Postgres), **observa-ingest** e **observa-missions** (cron jobs).
3. Preenche as variáveis marcadas como `sync: false` (aparecem no formulário; repetem-se nos serviços que as usam):

| Variável | Onde | O que pôr |
|---|---|---|
| `APP_PASSWORD` | web | password partilhada da equipa |
| `ANTHROPIC_API_KEY` | web + crons | chave da API Anthropic (console.anthropic.com) |
| `X_BEARER_TOKEN` | todos | deixa vazio (X está desligado) |
| `SECRET_KEY` | web | gerada automaticamente pelo Render |
| `DATABASE_URL` | todos | ligada automaticamente ao Postgres do Blueprint |

   As restantes (`LLM_PROVIDER=anthropic`, `MAX_LLM_CALLS_PER_DAY=200`, `RELEVANCE_THRESHOLD=40`, `ENABLE_X=false`, …) têm valores por omissão no `render.yaml`; ajusta-os depois no painel se quiseres.
4. **Apply**. O web service faz build (`pip install` + `npm ci && npm run build`), corre `alembic upgrade head` no arranque e responde em `/health`. Os crons também correm as migrações/`python -m app.jobs …` com o mesmo código.
5. Abre o URL `https://observa-ai-xxxx.onrender.com`, entra com `APP_PASSWORD`. A base começa **vazia** (o seed é só para uso local): dispara a primeira ingestão em **observa-ingest → Trigger Run** para não esperar pelas 06:00.

Horários: o cron do Render é em **UTC**. `0 6 * * *` (ingestão) e `0 7 * * *` (missões) correspondem às 06:00/07:00 de Lisboa no inverno e às 07:00/08:00 no verão. Se quiseres 06:00 exatas todo o ano, muda o `schedule` quando mudar a hora.

Custos: os planos usados no Blueprint (`starter`, Postgres `basic-256mb`) são pagos; consulta os preços atuais do Render. O Postgres *free* do Render expira ao fim de 30 dias, por isso não é adequado para isto. O gasto de IA é limitado por `MAX_LLM_CALLS_PER_DAY` (cada lote de 5 documentos, cada missão e cada pesquisa livre contam 1 chamada).

---

## 4. Como funciona

- **Ingestão** (`app/services/ingest.py`): cada conector (`app/connectors/*.py`, interface `SourceConnector`) devolve documentos brutos (fonte, URL original, data, texto). Deduplica por `(fonte, id externo)`.
- **Classificação** (`app/services/classify.py`): lotes de `CLASSIFY_BATCH_SIZE` documentos por chamada; nunca reclassifica; para quando o orçamento diário acaba. Prompt com few-shot dinâmico (últimos exemplos "útil"/"ruído").
- **Georreferenciação** (`app/geo.py` + `app/data/pt_places.json`): 308 concelhos, 18 distritos e 2 regiões autónomas com centroides, **tabela local, sem APIs externas em runtime**. Os concelhos e coordenadas vêm do Wikidata (gerados uma vez por `backend/scripts/build_places.py`) e devem ser vistos como centroides aproximados. Coordenadas exatas da fonte (fogos.pt) têm prioridade.
- **Limiar**: documentos com score abaixo do limiar ficam guardados mas escondidos (ajustável em Definições; `?include_hidden=true` na API).
- **Missões** (`app/services/missions.py`): pré-filtro por palavras-chave/categoria sobre os documentos já ingeridos + ranking e justificação por LLM sobre os candidatos (sem embeddings). Cada resultado vira alerta com motivo, resumo e link. Opção "incluir web aberta" usa a pesquisa web do provider, se existir.
- **Trocar/acrescentar LLM** (ex.: Grok/xAI): cria `backend/app/llm/xai_provider.py` com uma subclasse de `LLMProvider` (`complete_json`, opcionalmente `web_search`) e regista-a em `PROVIDERS` no `app/llm/factory.py`; depois `LLM_PROVIDER=xai`. O resto da app não muda.

---

## 5. Estado das fontes — o que é real, o que é stub, o que está por validar

Verificado a 2026-11-16 com pedidos reais:

| Fonte | Estado |
|---|---|
| **IPMA** — avisos meteorológicos | **Funciona** (API aberta, testada). Por omissão só ingere laranja/vermelho (`IPMA_MIN_LEVEL`). |
| **Ocorrências / Proteção Civil** via **fogos.pt** | **Funciona** (API aberta, testada), mas é um projeto de **terceiros**, não a ANEPC, e tem *rate limit* (durante os testes devolveu `429` quando abusei; o conector faz 1 pedido por execução e uma falha não afeta as outras fontes). Só ingere ocorrências com ≥ `FOGOS_MIN_MEN` operacionais. Convém confirmar com o fogos.pt se o uso institucional exige chave. A ANEPC não tem API aberta equivalente que tenha encontrado. |
| **Diário da República** | **Só descoberta; sem texto.** Não há RSS nem API oficial acessível (`dre.pt/rss` devolve a SPA; não encontrei dataset da INCM em dados.gov.pt). O `robots.txt` permite acesso e publica um sitemap (`files.dre.pt/sitemap/sitemap.xml`) com `lastmod` por URL — o conector usa-o (rate limit 1 pedido/s, User-Agent identificado, cache) para listar despachos, portarias, avisos, decretos, etc. novos (tipo, número/ano, link). **Mas as páginas de detalhe são uma SPA OutSystems sem texto nem metadados sem JavaScript**, por isso os documentos DRE ficam com estado `no_text`: são guardados e linkados, **não são classificados nem aparecem em Hoje/Mapa** (não vale gastar IA em títulos como "Despacho n.º 13717/2026"). Para o DRE ser útil falta uma fonte de texto legítima: contactar a INCM por acesso a dados abertos/API, ou renderizar as páginas com browser headless (a decidir por vocês — não contornei nada). Além disso, o `lastmod` do sitemap pode refletir reindexações e não só a data de publicação. |
| **Portal BASE** (contratação pública) | **Stub.** Só encontrei exportações *completas* (zip/xlsx/json 2012–2026) e um dataset OCDS em dados.gov.pt; não encontrei API incremental estável. O site tem proteções, não faço scraping. Ver `app/connectors/base_gov.py`. Fica desligado e marcado como indisponível nas Definições. |
| **X/Twitter** | **Opcional, desligado** (`ENABLE_X=false`). Implementação mínima com a API v2 de pesquisa recente; **não testada** (precisa de token e de plano de API pago). Nada na app depende dele. |

Outras coisas **não validadas** (não consegui testar neste ambiente):

- **Anthropic em produção**: o `AnthropicProvider` nunca correu com uma chave real aqui (só foi testado com LLM mockado/`fake`). O modelo por omissão `claude-haiku-5-5` está em `ANTHROPIC_MODEL`; confirma que o ID existe na tua conta e muda-o se necessário. A pesquisa web (`web_search_20250305`) das missões com "web aberta" está por validar; se falhar, a missão regista aviso e continua só com os documentos ingeridos.
- **Postgres**: localmente só testei com SQLite. A migração Alembic foi autogerada e só usa tipos portáveis (`JSON`, `String`, …), e o `DATABASE_URL` do Render (`postgres://`) é convertido para o driver `psycopg`; mesmo assim, o primeiro deploy é o primeiro teste real em Postgres. As pesquisas usam `ILIKE`, que funciona em ambos.
- **Build no Render**: o `render.yaml` assume que o runtime Python do Render tem Node disponível para `npm ci && npm run build` (definido `NODE_VERSION`). Se o build falhar por falta de Node, a alternativa é um `Dockerfile` multi-stage (peço-te que me digas e acrescento). O Blueprint também não foi validado com a CLI do Render (não instalada aqui); o YAML foi apenas verificado sintaticamente.
- **Mapa**: usa os tiles públicos do OpenStreetMap (sem chave) — adequado a uso interno de baixo tráfego, mas a política de uso do OSM não permite uso intensivo; para mais, troca por um provider de tiles. Os rótulos dos clusters usam *glyphs* alojados em `demotiles.maplibre.org`; se isso falhar, os números dos clusters deixam de aparecer (os marcadores continuam).
- **Qualidade da classificação/few-shot**: o desenho está implementado e testado com mocks, mas a qualidade real depende do modelo e dos prompts; calibra o limiar nas primeiras semanas com o feedback.
- **Missões — pré-filtro por palavras-chave**: pode falhar sinónimos (p. ex. "renda" vs "arrendamento"). Há um atalho por categoria (se a instrução mencionar "habitação", entram os documentos dessa categoria). Se for pouco, o passo seguinte natural é acrescentar embeddings.
- **Segurança**: password partilhada + cookie assinado (14 dias, `HttpOnly`, `Secure` em produção) e limite simples de tentativas de login em memória (por instância). Adequado a ferramenta interna; não há contas individuais.
- **Fusos horários**: datas guardadas em UTC; o filtro "Hoje" usa "últimas 24 h" ou um dia UTC específico.

---

## 6. Variáveis de ambiente

Ver `.env.example` (todas documentadas). Nunca coloques chaves no código nem no repositório; no Render preenche-as no painel.
