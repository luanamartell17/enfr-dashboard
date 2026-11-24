# Actor de Apify – Riesgo de hipertensión (inferencia)

Recibe datos de encuesta, arma las features, usa el modelo **previamente entrenado** y devuelve la probabilidad de hipertensión.

## Estructura

```
.actor/actor.json          configuración del Actor
.actor/input_schema.json   formulario / contrato de la entrada
.actor/Dockerfile          imagen (python 3.12 de Apify)
src/__main__.py            arranque (python -m src)
src/main.py                SOLO orquestación del Actor: leer entrada -> llamar módulos -> escribir salida
src/preprocessing.py       validación de registros y construcción de las 25 features
src/model.py               carga del .pkl y predicción (verifica versión de scikit-learn)
src/tooling_business.py    reglas de negocio: umbral, niveles de riesgo, formato de salida, resumen
models/                    acá va modelo_hta_logreg.pkl  (copiarlo; no se versiona acá)
ejemplos/input_ejemplo.json   entrada de ejemplo
tests/test_inferencia.py   pruebas de los módulos (sin Apify)
```

## Entrada

```json
{ "registros": [ {"id": "p1", "edad": 58, "mujer": 0, "peso_kg": 98, "talla_cm": 172, "tabaco": 1} ],
  "umbral": 0.4, "incluirEntrada": false }
```
- Obligatorios por persona: `edad` (18-110) y `mujer` (1 mujer, 0 varón). El resto es opcional (imc, obesidad, etc. se calculan solos).
- Los nombres y códigos de campos son los del modelo: `provincia, region, mujer, edad, nivel_instruccion, tiene_cobertura, condicion_actividad,
  quintil_ingreso, cant_componentes, salud_autopercibida, tabaco, actividad_fisica, alcohol_regular_riesgo, alcohol_episodico,
  fv_promedio_diario, cumple_5_fyv, peso_kg, talla_cm, colesterol_medido, colesterol_alto, diabetes`.
- `id` (opcional) se devuelve tal cual para poder cruzar resultados.

## Salida

- **Dataset** (un item por registro, mismo orden): `indice, estado ("ok"/"error"), probabilidad_hta, alerta (0/1), nivel_riesgo (bajo/medio/alto), n_campos_faltantes, advertencias, id`.
  Un registro inválido devuelve `estado: "error"` con la lista de `errores`, sin frenar al resto del lote.
- **Key-value store, clave `RESUMEN`**: totales, alertas, umbral usado y datos del modelo.