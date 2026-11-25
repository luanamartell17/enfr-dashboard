# Actor de Apify – Riesgo de hipertensión (inferencia)

Recibe datos de encuesta, arma las features, usa el modelo **previamente entrenado** y devuelve la probabilidad de hipertensión.

## Estructura

```
.actor/actor.json               configuración del Actor
.actor/input_schema.json        formulario / contrato de la entrada
.actor/dataset_schema.json, output_schema.json   formato de la salida
Dockerfile                      imagen (python de Apify)
my_actor/__main__.py            arranque (python -m my_actor)
my_actor/main.py                SOLO orquestación del Actor: leer entrada -> llamar módulos -> escribir salida
my_actor/preprocessing.py       validación de registros y construcción de las features
my_actor/model.py               carga del modelo y predicción (verifica versión de scikit-learn)
my_actor/tooling_business.py    reglas de negocio: umbral, niveles de riesgo, formato de salida, resumen
models/modelo_hta_logreg.pkl.b64   modelo entrenado (pickle en base64)
entrenamiento/entrenamiento.py  entrena el modelo y genera el .pkl y el .pkl.b64 (fuera del Actor)
```

Entrenar: `python entrenamiento/entrenamiento.py --entrada <carpeta con el dataset limpio> --salida <carpeta> [--comparar]`.
Con `--comparar` evalúa también Random Forest y Gradient Boosting.

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