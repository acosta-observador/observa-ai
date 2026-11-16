"""Dados de demonstração (FICTÍCIOS) para ver o mapa e os alertas sem chaves reais.

  python -m app.seed            # só insere se a base estiver vazia
  python -m app.seed --reset    # apaga tudo e volta a inserir
"""
from __future__ import annotations

import datetime as dt
import sys

from sqlalchemy import select

from . import geo
from .db import Base, SessionLocal, engine
from .models import Document, Feedback, Mission, MissionAlert, utcnow

# (fonte, tipo, título, resumo, porquê, categoria, score, concelho, distrito, horas atrás)
DEMO = [
    ("dre", "despacho", "Despacho autoriza expropriação de terrenos para nova ligação rodoviária", "O despacho declara utilidade pública de 14 parcelas. O valor estimado das indemnizações ronda os 3,2 milhões.", "Dinheiro público e proprietários afetados; possível contestação local.", "autarquias", 78, "Santarém", "Santarém", 3),
    ("dre", "aviso", "Aviso de revisão do PDM prevê 1.200 novos fogos em zona de risco de cheia", "A revisão do plano diretor municipal altera o perímetro urbano junto ao rio. Há parecer desfavorável da agência do ambiente.", "Conflito entre habitação e risco de cheia.", "habitação", 84, "Loures", "Lisboa", 5),
    ("dre", "despacho", "Nomeação do novo presidente do conselho de administração de unidade local de saúde", "É nomeado um antigo secretário de Estado para presidir à unidade. A nomeação tem efeitos imediatos.", "Nomeação política numa unidade com listas de espera críticas.", "saúde", 71, "Braga", "Braga", 8),
    ("dre", "portaria", "Portaria fixa novos limites de renda para arrendamento acessível", "Os tetos sobem 4% face ao ano anterior. A medida aplica-se aos contratos novos a partir de janeiro.", "Afeta milhares de inquilinos; tema recorrente.", "habitação", 88, None, None, 10),
    ("dre", "despacho", "Despacho retifica designação de vogal de comissão administrativa", "Retifica uma data numa designação anterior.", "Rotina administrativa.", "outros", 8, "Évora", "Évora", 12),
    ("ipma", "aviso meteorológico", "Aviso laranja — Agitação Marítima — Porto", "Ondas de noroeste entre 5 e 6 metros, com máximas até 10 metros, a partir do fim da tarde.", "Risco para a orla costeira e atividade portuária.", "ambiente", 66, "Porto", "Porto", 2),
    ("ipma", "aviso meteorológico", "Aviso laranja — Precipitação — Faro", "Precipitação persistente e forte, com possibilidade de inundações em zonas baixas.", "Risco de inundações no Algarve.", "ambiente", 69, "Faro", "Faro", 4),
    ("ipma", "aviso meteorológico", "Aviso vermelho — Vento — Madeira", "Rajadas até 130 km/h nas zonas altas e costa norte.", "Aviso vermelho raro; possíveis cortes de estradas e voos.", "ambiente", 90, "Funchal", "Madeira", 1),
    ("fogos", "ocorrência", "Incêndio rural — Odemira (Beja)", "Incêndio com 62 operacionais e 3 meios aéreos. A frente ativa aproxima-se de uma zona de habitações dispersas.", "Risco para pessoas e habitações no Alentejo.", "ambiente", 82, "Odemira", "Beja", 1),
    ("fogos", "ocorrência", "Acidente grave na A1 — Santarém", "Colisão múltipla com seis veículos. Há vítimas e a autoestrada está cortada em ambos os sentidos.", "Acidente com vítimas e trânsito cortado numa via principal.", "outros", 74, "Santarém", "Santarém", 6),
    ("dre", "contrato público", "Contrato de 18 milhões para requalificação de hospital adjudicado por ajuste direto", "A adjudicação foi feita por ajuste direto com fundamento em urgência imperiosa. O adjudicatário já tinha ganho três contratos este ano.", "Ajuste direto de valor elevado a empresa recorrente.", "economia", 92, "Coimbra", "Coimbra", 14),
    ("dre", "despacho", "Despacho cria grupo de trabalho para reforma das custas judiciais", "O grupo tem 90 dias para apresentar propostas. Inclui magistrados, advogados e académicos.", "Reforma com impacto no acesso à justiça.", "justiça", 58, None, None, 20),
    ("dre", "aviso", "Aviso abre concurso para habitação a custos controlados em Ponta Delgada", "O concurso abrange 96 fogos. O preço médio por metro quadrado fica abaixo do mercado local.", "Resposta à crise de habitação nos Açores.", "habitação", 76, "Ponta Delgada", "Açores", 9),
    ("dre", "despacho", "Despacho atribui verba extraordinária a municípios afetados por intempéries", "Dez municípios recebem 12 milhões para reparação de estradas e pontes.", "Dinheiro público a municípios afetados por mau tempo.", "autarquias", 64, "Viseu", "Viseu", 26),
    ("dre", "portaria", "Portaria altera regras de acesso a consultas no SNS", "Muda os critérios de prioridade para primeiras consultas hospitalares.", "Mexe nos tempos de espera do SNS.", "saúde", 73, None, None, 30),
    ("ipma", "aviso meteorológico", "Aviso laranja — Tempo Frio — Bragança", "Descida acentuada da temperatura mínima, com geada e queda de neve acima dos 800 metros.", "Neve e frio nas serras do Nordeste.", "ambiente", 55, "Bragança", "Bragança", 40),
    ("fogos", "ocorrência", "Deslizamento de terras corta estrada — Arouca", "Deslizamento na EN326 devido à chuva intensa. Estrada cortada, sem vítimas.", "Estrada cortada no interior norte.", "ambiente", 47, "Arouca", "Aveiro", 52),
    ("dre", "despacho", "Despacho designa júri de concurso para direção de agrupamento de escolas", "Designa três vogais para o júri.", "Rotina administrativa.", "outros", 12, "Guarda", "Guarda", 60),
    ("dre", "aviso", "Aviso de abertura de consulta pública sobre loteamento junto à praia", "Loteamento de 38 lotes em zona de duna é submetido a consulta pública durante 20 dias.", "Construção em zona costeira sensível.", "ambiente", 81, "Vila do Bispo", "Faro", 72),
    ("dre", "despacho", "Despacho aprova aumento de capital em empresa municipal de transportes", "Aumento de 5 milhões para cobrir prejuízos acumulados da empresa de autocarros.", "Dinheiro público a cobrir prejuízos.", "economia", 68, "Setúbal", "Setúbal", 90),
    ("dre", "acórdão", "Acórdão do Tribunal Constitucional sobre lei das rendas", "O tribunal declara inconstitucional uma norma sobre atualização de rendas antigas.", "Decisão com efeitos no mercado de arrendamento.", "justiça", 86, None, None, 120),
    ("fogos", "ocorrência", "Incêndio urbano — Viana do Castelo", "Incêndio num edifício de habitação com evacuação de 20 pessoas.", "Evacuação de habitação.", "outros", 52, "Viana do Castelo", "Viana do Castelo", 150),
    ("dre", "despacho", "Despacho de subsídio a associação cultural em Castelo Branco", "Subsídio de 8 mil euros a uma associação local.", "Montante reduzido.", "autarquias", 24, "Castelo Branco", "Castelo Branco", 200),
    ("dre", "portaria", "Portaria regula alojamento local em áreas de contenção", "Municípios podem suspender novos registos de alojamento local em zonas saturadas.", "Impacto direto no mercado de habitação e turismo.", "habitação", 83, "Lisboa", "Lisboa", 240),
    ("dre", "despacho", "Despacho nomeia chefe de gabinete do ministro", "Nomeação de chefe de gabinete com remuneração equiparada a dirigente superior.", "Nomeações políticas costumam ter interesse.", "política", 62, None, None, 300),
    ("fogos", "ocorrência", "Incêndio florestal — Pampilhosa da Serra", "Fogo em zona de mato com 40 operacionais e 2 meios aéreos.", "Fogo no interior centro.", "ambiente", 59, "Pampilhosa da Serra", "Coimbra", 400),
    ("dre", "aviso", "Aviso de concurso para obra de dessalinização no Algarve", "Concurso público de 45 milhões para uma central de dessalinização.", "Grande investimento público contra a seca.", "ambiente", 85, "Faro", "Faro", 500),
    ("dre", "despacho", "Despacho exonera presidente de instituto público", "Exoneração a pedido do interessado, com efeitos a partir de dia 1.", "Saída de dirigente de topo.", "política", 57, None, None, 600),
]


def run(reset: bool = False) -> None:
    Base.metadata.create_all(engine)  # só para uso local; em produção é o Alembic
    with SessionLocal() as db:
        if reset:
            for m in (Feedback, MissionAlert, Mission, Document):
                db.query(m).delete()
            db.commit()
        if db.scalar(select(Document.id).limit(1)):
            print("Base já tem dados; usa --reset para recomeçar.")
            return
        now = utcnow()
        docs = []
        for i, (src, typ, title, summ, why, cat, score, conc, dist, hours) in enumerate(DEMO):
            place = geo.locate(conc, dist)
            d = Document(source=src, external_id=f"demo-{i}", url=f"https://exemplo.invalid/demo/{src}/{i}", title=f"[Demo] {title}",
                         text=summ, doc_type=typ, published_at=now - dt.timedelta(hours=hours), fetched_at=now - dt.timedelta(hours=hours),
                         status="classified", score=score, category=cat, summary=summ, why=why,
                         entities={"people": [], "orgs": []}, concelho=place.concelho if place else None,
                         distrito=place.distrito if place else None, lat=place.lat if place else None,
                         lon=place.lon if place else None, classified_at=now)
            docs.append(d)
        db.add_all(docs)
        db.flush()
        for d, v, ago in ((docs[3], "useful", 40), (docs[9], "useful", 30), (docs[1], "useful", 20), (docs[4], "noise", 38),
                          (docs[16], "noise", 28), (docs[21], "noise", 18), (docs[7], "useful", 10), (docs[24], "useful", 5)):
            db.add(Feedback(document_id=d.id, value=v, created_at=now - dt.timedelta(hours=ago * 8)))
        m1 = Mission(name="Habitação em despachos e avisos", instruction="Avisa-me se aparecer algo sobre habitação, arrendamento ou alojamento local em despachos, portarias e avisos.", sources=["dre"])
        m2 = Mission(name="Alertas de risco no Algarve", instruction="Qualquer aviso ou ocorrência relevante no Algarve (Faro): chuva, incêndios, seca.", sources=[])
        db.add_all([m1, m2])
        db.flush()
        for m, idxs in ((m1, (1, 3, 12, 18, 22)), (m2, (6, 18, 25))):
            for i in idxs:
                d = docs[i]
                db.add(MissionAlert(mission_id=m.id, document_id=d.id, dedupe_key=f"doc:{d.id}", title=d.title, reason="Corresponde à instrução da missão (demo).",
                                    summary=d.summary or "", url=d.url, source=d.source))
        db.commit()
        print(f"Seed ok: {len(docs)} documentos, 2 missões.")


if __name__ == "__main__":
    run("--reset" in sys.argv)
