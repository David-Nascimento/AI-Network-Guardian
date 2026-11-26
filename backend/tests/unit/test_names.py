from __future__ import annotations

import struct

from app.collectors import names_collector as nc


def _name(labels: str) -> bytes:
    return b"".join(bytes([len(p)]) + p.encode() for p in labels.split(".")) + b"\x00"


def test_mdns_query_tem_ptr_reverso_e_bit_unicast() -> None:
    query = nc.build_mdns_ptr_query("192.168.100.20")
    assert _name("20.100.168.192.in-addr.arpa") in query
    assert query.endswith(struct.pack(">HH", 12, 0x8001))


def test_mdns_resposta_com_compressao_de_ponteiro() -> None:
    header = struct.pack(">HHHHHH", 0, 0x8400, 0, 1, 0, 0)
    owner = _name("20.100.168.192.in-addr.arpa")
    target = _name("iPhone-do-David.local")
    answer = owner + struct.pack(">HHIH", 12, 1, 120, len(target)) + target
    assert nc.parse_mdns_ptr(header + answer) == "iPhone-do-David"


def test_mdns_ignora_lixo_e_perguntas() -> None:
    assert nc.parse_mdns_ptr(b"") is None
    assert nc.parse_mdns_ptr(b"\x00" * 5) is None
    question = struct.pack(">HHHHHH", 0, 0, 1, 0, 0, 0)  # não é resposta
    assert nc.parse_mdns_ptr(question) is None


def _nbns_response(entries: list[tuple[str, int, int]]) -> bytes:
    header = struct.pack(">HHHHHH", 0, 0x8400, 0, 1, 0, 0)
    body = b"\x20" + b"CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" + b"\x00"
    body += struct.pack(">HHIH", 0x0021, 1, 0, 1 + 18 * len(entries)) + bytes([len(entries)])
    for name, suffix, flags in entries:
        body += name.ljust(15).encode() + bytes([suffix]) + struct.pack(">H", flags)
    return header + body


def test_nbns_pega_nome_de_estacao_e_ignora_grupo() -> None:
    data = _nbns_response([("WORKGROUP", 0x00, 0x8400), ("NOTEBOOK-DAVID", 0x00, 0x0400)])
    assert nc.parse_nbns(data) == "NOTEBOOK-DAVID"
    assert nc.parse_nbns(_nbns_response([("WORKGROUP", 0x00, 0x8400)])) is None
    assert nc.parse_nbns(b"curto") is None


def test_clean_name() -> None:
    assert nc.clean_name("Galaxy-S23.local.") == "Galaxy-S23"
    assert nc.clean_name("  ") is None
    assert nc.clean_name("a\x00b") == "ab"
    assert len(nc.clean_name("x" * 200) or "") == 80


def test_mdns_ponteiro_circular_nao_trava() -> None:
    header = struct.pack(">HHHHHH", 0, 0x8400, 0, 1, 0, 0)
    loop = b"\xc0" + bytes([12])  # aponta para si mesmo
    assert nc.parse_mdns_ptr(header + loop) is None
