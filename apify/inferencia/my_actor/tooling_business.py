"""Reglas de negocio: validación de la entrada del Actor, umbral, niveles de riesgo y formato de salida."""
NIVEL_BAJO_HASTA = 0.25
AVISO = "Estimación estadística basada en autorreportes de la ENFR; no es un diagnóstico médico."


class EntradaInvalida(ValueError):
    pass


def validar_entrada(entrada):
    """Devuelve (registros, umbral_pedido|None, incluir_entrada). Lanza EntradaInvalida si la entrada no sirve."""
    registros = entrada.get("registros")
    if not isinstance(registros, list) or not registros:
        raise EntradaInvalida("La entrada debe incluir 'registros': una lista no vacía de objetos (uno por persona).")
    umbral = entrada.get("umbral")
    if umbral is not None:
        try:
            umbral = float(umbral)
        except (TypeError, ValueError):
            raise EntradaInvalida("'umbral' debe ser un número entre 0 y 1.")
        if not 0 <= umbral <= 1:
            raise EntradaInvalida("'umbral' debe estar entre 0 y 1.")
    return registros, umbral, bool(entrada.get("incluirEntrada", False))


def umbral_efectivo(umbral_pedido, artefacto):
    return float(artefacto["umbral"]) if umbral_pedido is None else float(umbral_pedido)


def clasificar(prob, umbral):
    """(alerta 0/1, nivel 'bajo'|'medio'|'alto'). Alto = alerta."""
    if prob >= umbral:
        return 1, "alto"
    return 0, ("bajo" if prob < min(NIVEL_BAJO_HASTA, umbral) else "medio")


def clasificar_resultados(validos, probs, umbral, n_faltantes, advertencias, incluir_entrada):
    """validos = [(indice_original, registro)] alineado con probs -> {indice: item de salida}."""
    out = {}
    for (i, r), p, nf, adv in zip(validos, probs, n_faltantes, advertencias):
        alerta, nivel = clasificar(float(p), umbral)
        item = {"indice": i, "estado": "ok", "probabilidad_hta": round(float(p), 4), "alerta": alerta,
                "nivel_riesgo": nivel, "n_campos_faltantes": int(nf), "advertencias": adv}
        if "id" in r: item["id"] = r["id"]
        if incluir_entrada: item["entrada"] = r
        out[i] = item
    return out


def resultado_error(indice, errores, registro, incluir_entrada):
    item = {"indice": indice, "estado": "error", "errores": errores}
    if isinstance(registro, dict) and "id" in registro: item["id"] = registro["id"]
    if incluir_entrada: item["entrada"] = registro
    return item


def resumen_lote(salida, umbral, artefacto):
    ok = [s for s in salida if s["estado"] == "ok"]
    return {"total": len(salida), "ok": len(ok), "errores": len(salida) - len(ok), "alertas": sum(s["alerta"] for s in ok),
            "umbral_usado": umbral, "modelo_entrenado_con": artefacto.get("anios_entrenamiento"),
            "modelo_creado": artefacto.get("creado"), "aviso": AVISO}