"""Validação de formulários da ELiXX (Fase 08) — pura, sem renderer.

Regras por campo: obrigatorio, validar (nenhum/texto/email/numero),
min_caracteres, max_caracteres, min_valor, max_valor. Mensagens em
português. Usada pela ação validar()/enviar().
"""
from __future__ import annotations

import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validar_campo(valor: object, regras: dict) -> tuple[bool, str]:
    """Retorna (ok, mensagem). Mensagem vazia quando ok."""
    texto = "" if valor is None else str(valor)
    if regras.get("obrigatorio") and not texto.strip():
        return False, "preenchimento obrigatório"
    if not texto.strip():
        return True, ""
    tipo = str(regras.get("validar", "texto")).lower()
    if tipo == "email" and not EMAIL_RE.match(texto.strip()):
        return False, "email inválido"
    numero = None
    if tipo == "numero":
        try:
            numero = float(texto.replace(",", "."))
        except ValueError:
            return False, "precisa ser número"
    if "min_caracteres" in regras and len(texto) < regras["min_caracteres"]:
        return False, f"mínimo de {regras['min_caracteres']} caracteres"
    if "max_caracteres" in regras and len(texto) > regras["max_caracteres"]:
        return False, f"máximo de {regras['max_caracteres']} caracteres"
    base = numero if numero is not None else None
    if base is None and tipo != "numero":
        try:
            base = float(texto.replace(",", "."))
        except ValueError:
            base = None
    if "min_valor" in regras and base is not None \
            and base < regras["min_valor"]:
        return False, f"mínimo {regras['min_valor']:g}"
    if "max_valor" in regras and base is not None \
            and base > regras["max_valor"]:
        return False, f"máximo {regras['max_valor']:g}"
    return True, ""


def validar_formulario(campos: dict) -> tuple[bool, list[str]]:
    """campos: nome → (valor, regras). Retorna (ok, erros)."""
    erros = []
    for nome, (valor, regras) in campos.items():
        ok, mensagem = validar_campo(valor, regras)
        if not ok:
            erros.append(f"{nome}: {mensagem}")
    return (not erros), erros
