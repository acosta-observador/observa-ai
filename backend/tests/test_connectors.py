import datetime as dt
import json

from app.connectors.dre import DREConnector, _doc_from_url
from app.connectors.fogos import FogosConnector
from app.connectors.ipma import IPMAConnector
from app.connectors.x_twitter import XConnector


class FakeClient:
    def __init__(self, payloads):
        self.payloads = payloads

    def get_json(self, url, **kw):
        return self.payloads[url]

    def get_text(self, url, **kw):
        return self.payloads[url]


SINCE = dt.datetime(2026, 11, 15)


def test_ipma_filters_by_level_and_maps_area():
    from app.connectors.ipma import URL
    data = [
        {"awarenessTypeName": "Vento", "idAreaAviso": "MCS", "startTime": "2026-11-16T10:00:00", "endTime": "2026-11-17T10:00:00", "awarenessLevelID": "red", "text": "Rajadas"},
        {"awarenessTypeName": "Nevoeiro", "idAreaAviso": "BGC", "startTime": "2026-11-16T10:00:00", "endTime": "2026-11-17T10:00:00", "awarenessLevelID": "yellow", "text": ""},
        {"awarenessTypeName": "Vento", "idAreaAviso": "FAR", "startTime": "2026-11-16T10:00:00", "endTime": "2026-11-17T10:00:00", "awarenessLevelID": "green", "text": ""},
    ]
    docs = IPMAConnector(FakeClient({URL: data})).fetch(SINCE)
    assert len(docs) == 1  # por defeito só laranja/vermelho
    d = docs[0]
    assert d.hint_distrito == "Madeira" and d.hint_concelho == "Funchal" and "vermelho" in d.title


def test_fogos_uses_coordinates_and_threshold():
    from app.connectors.fogos import URL
    data = {"data": [
        {"id": "1", "man": 40, "terrain": 10, "aerial": 2, "lat": 38.5, "lng": -8.8, "district": "Setúbal", "concelho": "Palmela",
         "location": "Setúbal, Palmela", "natureza": "Incêndio rural", "status": "Em curso", "dateTime": {"sec": 1794847860}},
        {"id": "2", "man": 2, "lat": 38.5, "lng": -8.8, "district": "Setúbal", "concelho": "Palmela", "location": "x", "natureza": "Queima"},
    ]}
    docs = FogosConnector(FakeClient({URL: data})).fetch(SINCE)
    assert [d.external_id for d in docs] == ["1"]
    assert docs[0].hint_lat == 38.5 and docs[0].url.endswith("/1")


def test_dre_discovers_from_sitemap_without_text():
    from app.connectors.dre import INDEX
    sub = "https://files.diariodarepublica.pt/sitemap/despacho-sitemap-16.xml"
    index = (f"<sitemapindex><sitemap><loc>{sub}</loc><lastmod>2026-11-16</lastmod></sitemap>"
             "<sitemap><loc>https://files.diariodarepublica.pt/sitemap/despacho-sitemap-15.xml</loc><lastmod>2026-11-16</lastmod></sitemap>"
             "<sitemap><loc>https://files.diariodarepublica.pt/sitemap/ato-societario-sitemap-1.xml</loc><lastmod>2026-11-16</lastmod></sitemap></sitemapindex>")
    sm = ("<urlset><url><loc>https://diariodarepublica.pt/dr/detalhe/despacho/13717-2026-1192709949</loc><lastmod>2026-11-16</lastmod></url>"
          "<url><loc>https://diariodarepublica.pt/dr/detalhe/despacho/1149-2007-74862787</loc><lastmod>2025-08-18</lastmod></url></urlset>")
    docs = DREConnector(FakeClient({INDEX: index, sub: sm})).fetch(SINCE)
    assert len(docs) == 1 and docs[0].title == "Despacho n.º 13717/2026" and docs[0].text == ""
    assert DREConnector.has_text is False


def test_dre_url_parsing():
    d = _doc_from_url("https://diariodarepublica.pt/dr/detalhe/portaria/456-2026-1195477288", "2026-11-16")
    assert d.title == "Portaria n.º 456/2026" and d.external_id == "456-2026-1195477288"


def test_x_disabled_by_default_and_stub_base():
    from app.connectors.base_gov import BaseGovConnector
    assert XConnector().availability()[0] is False
    assert XConnector().fetch(SINCE) == []
    assert BaseGovConnector().availability()[0] is False
