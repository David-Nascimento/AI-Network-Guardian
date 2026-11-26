from __future__ import annotations

from app.services.router_import import parse_router_table

TABLE_TABS = """Nome do host\tEndereço IP\tEndereço MAC\tTempo de concessão
iPhone-do-David\t192.168.100.20\t50:F2:65:F3:02:C9\t23:59:10
Galaxy S23\t192.168.100.26\t86-52-0D-47-3F-79\t1d
"""

TABLE_COLUMNS = """  1   192.168.100.34   4C:EB:42:D1:51:6E   NOTEBOOK-DAVID   Wireless   dynamic
  2   192.168.100.27   90:39:5f:16:7c:39   Echo Dot Sala   LAN
"""


def test_parse_tabela_separada_por_tabs() -> None:
    entries = parse_router_table(TABLE_TABS)
    assert [(e.mac, e.ip, e.name) for e in entries] == [
        ("50:f2:65:f3:02:c9", "192.168.100.20", "iPhone-do-David"),
        ("86:52:0d:47:3f:79", "192.168.100.26", "Galaxy S23"),
    ]


def test_parse_tabela_em_colunas_ignora_estado_e_tipo() -> None:
    entries = parse_router_table(TABLE_COLUMNS)
    assert [e.name for e in entries] == ["NOTEBOOK-DAVID", "Echo Dot Sala"]


def test_parse_ignora_linhas_sem_mac_ou_ip_e_sem_nome() -> None:
    text = "Dispositivos conectados\n192.168.100.40  aa:bb:cc:dd:ee:ff  dynamic\n"
    assert parse_router_table(text) == []
