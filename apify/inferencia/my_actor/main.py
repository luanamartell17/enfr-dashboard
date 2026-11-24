"""Punto de entrada del Actor (solo inferencia).

Este archivo solo contiene lo necesario para construir el Actor: leer la entrada, llamar a los módulos
y escribir la salida. Toda la lógica vive en:
  - preprocessing.py     -> validación y construcción de features
  - model.py             -> carga del modelo y predicción
  - tooling_business.py  -> reglas de negocio (umbral, niveles de riesgo, formato de salida, resumen)
No hay entrenamiento, ETL ni EDA dentro de este Actor.
"""
from apify import Actor

from .model import cargar_modelo, predecir_proba
from .preprocessing import armar_features, validar_registro
from .tooling_business import (clasificar_resultados, resultado_error, resumen_lote,
                               umbral_efectivo, validar_entrada)


async def main() -> None:
    async with Actor:
        entrada = await Actor.get_input() or {}
        registros, umbral_pedido, incluir_entrada = validar_entrada(entrada)   # lanza EntradaInvalida si está mal
        Actor.log.info("Registros recibidos: %d", len(registros))

        artefacto = cargar_modelo()
        umbral = umbral_efectivo(umbral_pedido, artefacto)

        # 1) validar cada registro: los inválidos no frenan el lote, devuelven su error
        validos, errores = [], {}
        for i, r in enumerate(registros):
            errs = validar_registro(r)
            if errs: errores[i] = errs
            else: validos.append((i, r))

        # 2) features -> probabilidades
        resultados = {i: resultado_error(i, e, registros[i], incluir_entrada) for i, e in errores.items()}
        if validos:
            X, advertencias = armar_features([r for _, r in validos], artefacto["features"])
            probs = predecir_proba(artefacto, X)
            resultados.update(clasificar_resultados(validos, probs, umbral, X.isna().sum(axis=1).tolist(),
                                                    advertencias, incluir_entrada))

        # 3) salida: un item del dataset por registro (en el mismo orden de entrada) + resumen
        salida = [resultados[i] for i in sorted(resultados)]
        await Actor.push_data(salida)
        resumen = resumen_lote(salida, umbral, artefacto)
        await Actor.set_value("RESUMEN", resumen)
        await Actor.set_status_message(f"{resumen['ok']} predicciones, {resumen['alertas']} alertas, {resumen['errores']} con error")