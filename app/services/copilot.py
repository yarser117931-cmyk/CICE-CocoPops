
from __future__ import annotations

import re
from typing import Any


def _normalize(text: str) -> str:
    return (
        text.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )


def _money(value: float) -> str:
    return f"${value:,.2f}"


def answer_question(
    question: str,
    inventory: dict[str, Any],
    production: dict[str, Any],
    sales: dict[str, Any],
    priorities: dict[str, Any],
) -> dict[str, Any]:
    q = _normalize(question.strip())
    products = inventory.get("products", [])
    categories = inventory.get("categories", [])
    global_summary = inventory.get("global", {})

    if not q:
        return {
            "answer": "Escribe una pregunta sobre inventario, producción o ventas.",
            "type": "HELP",
            "items": [],
        }

    # Critical products.
    if any(term in q for term in ("critico", "criticos", "urgente", "urgentes")):
        critical = [
            p for p in products
            if p.get("status") == "CRITICO"
        ][:10]
        return {
            "answer": (
                f"Hay {len([p for p in products if p.get('status') == 'CRITICO'])} "
                "productos críticos. Estos son los primeros que deben revisarse."
            ),
            "type": "PRODUCT_LIST",
            "items": [
                {
                    "name": p["name"],
                    "category": p["category"],
                    "available": p["available"],
                    "minimum": p["minimum"],
                    "missing": p["missing_to_minimum"],
                    "uom": p["uom"],
                    "status": p["status"],
                }
                for p in critical
            ],
        }

    # What to manufacture.
    if "fabricar" in q or "produccion" in q or "producir" in q:
        finished_words = ("PALETA", "NIEVE", "HELADO", "PASTEL")
        candidates = [
            p for p in products
            if p.get("status") in ("CRITICO", "BAJO_MINIMO")
            and any(word in p.get("category", "").upper() for word in finished_words)
        ][:10]
        return {
            "answer": (
                f"Se detectaron {len(candidates)} productos terminados prioritarios "
                "para fabricar, ordenados por criticidad."
            ),
            "type": "PRODUCT_LIST",
            "items": [
                {
                    "name": p["name"],
                    "category": p["category"],
                    "available": p["available"],
                    "minimum": p["minimum"],
                    "missing": p["missing_to_minimum"],
                    "uom": p["uom"],
                    "status": p["status"],
                }
                for p in candidates
            ],
        }

    # What to buy or replenish.
    if any(term in q for term in ("comprar", "compra", "reabastecer", "ingrediente")):
        finished_words = ("PALETA", "NIEVE", "HELADO", "PASTEL")
        candidates = [
            p for p in products
            if p.get("status") in ("CRITICO", "BAJO_MINIMO")
            and not any(word in p.get("category", "").upper() for word in finished_words)
        ][:10]
        return {
            "answer": (
                f"Se detectaron {len(candidates)} materiales o ingredientes "
                "prioritarios para reabastecer."
            ),
            "type": "PRODUCT_LIST",
            "items": [
                {
                    "name": p["name"],
                    "category": p["category"],
                    "available": p["available"],
                    "minimum": p["minimum"],
                    "missing": p["missing_to_minimum"],
                    "uom": p["uom"],
                    "status": p["status"],
                }
                for p in candidates
            ],
        }

    # Category needing most attention.
    if "categoria" in q and any(term in q for term in ("atencion", "peor", "riesgo")):
        ranked = sorted(
            categories,
            key=lambda c: (
                -(c.get("critical", 0) + c.get("below_minimum", 0)),
                c.get("coverage_pct") if c.get("coverage_pct") is not None else 999999,
            ),
        )
        if not ranked:
            return {
                "answer": "No hay categorías disponibles para analizar.",
                "type": "TEXT",
                "items": [],
            }
        top = ranked[0]
        return {
            "answer": (
                f"La categoría que requiere más atención es {top['name']}: "
                f"{top['critical']} productos críticos y "
                f"{top['below_minimum']} bajo mínimo."
            ),
            "type": "CATEGORY",
            "items": [top],
        }

    # Sales.
    if "venta" in q or "vendido" in q or "facturado" in q or "cliente" in q:
        details = sales.get("details", [])
        top_sales = sorted(
            details,
            key=lambda item: float(item.get("total") or 0),
            reverse=True,
        )[:10]
        return {
            "answer": (
                f"Las ventas confirmadas de hoy suman {_money(float(sales.get('total') or 0))} "
                f"en {sales.get('orders', 0)} pedidos y "
                f"{sales.get('customers', 0)} clientes. "
                f"Se han facturado {_money(float(sales.get('invoiced_today') or 0))}. "
                "Estas son las ventas de mayor importe."
            ),
            "type": "SALES_LIST",
            "items": top_sales,
        }

    # Production status.
    if (
        "avance" in q
        or "ordenes de fabricacion" in q
        or "orden de produccion" in q
        or "produccion" in q
    ):
        details = production.get("details", [])[:10]
        return {
            "answer": (
                f"La producción de hoy registra {production.get('orders', 0)} órdenes, "
                f"{production.get('open_orders', 0)} abiertas, "
                f"{production.get('finished_today', 0)} terminadas hoy y "
                f"{production.get('progress', 0)}% de avance."
            ),
            "type": "PRODUCTION_LIST",
            "items": details,
        }

    # Inventory summary.
    if "inventario" in q or "existencia" in q or "stock" in q:
        coverage = global_summary.get("coverage_pct")
        coverage_text = "sin cobertura calculable" if coverage is None else f"{coverage}% de cobertura"
        return {
            "answer": (
                f"El inventario tiene {global_summary.get('available', 0)} unidades disponibles, "
                f"{global_summary.get('critical', 0)} productos críticos, "
                f"{global_summary.get('below_minimum', 0)} bajo mínimo y "
                f"{coverage_text}."
            ),
            "type": "INVENTORY",
            "items": [],
        }

    # Search by product name.
    tokens = [token for token in re.split(r"\W+", q) if len(token) >= 4]
    matches = []
    for product in products:
        searchable = _normalize(
            f"{product.get('name', '')} {product.get('code', '')} "
            f"{product.get('category', '')} {product.get('original_category', '')}"
        )
        if tokens and all(token in searchable for token in tokens):
            matches.append(product)

    if matches:
        p = matches[0]
        return {
            "answer": (
                f"{p['name']} tiene {p['available']} {p['uom']} disponibles, "
                f"mínimo de {p['minimum']} y faltante de {p['missing_to_minimum']}. "
                f"Estado: {p['status']}."
            ),
            "type": "PRODUCT",
            "items": [{
                "name": p["name"],
                "category": p["category"],
                "available": p["available"],
                "minimum": p["minimum"],
                "missing": p["missing_to_minimum"],
                "uom": p["uom"],
                "status": p["status"],
            }],
        }

    return {
        "answer": (
            "Puedo responder preguntas como: qué fabricar, qué comprar, "
            "qué productos están críticos, qué categoría requiere atención, "
            "cómo van las ventas, producción o inventario."
        ),
        "type": "HELP",
        "items": [],
    }
