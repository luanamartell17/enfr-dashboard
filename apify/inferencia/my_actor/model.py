"""Carga del modelo entrenado y predicción. El Actor NUNCA entrena: solo lee el artefacto guardado."""
import base64
import os
import pickle

import sklearn

RUTA_MODELO = os.environ.get("MODELO_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models", "modelo_hta_logreg.pkl"))
CLAVES_OBLIGATORIAS = {"modelo", "features", "umbral", "versiones"}


class ModeloInvalido(RuntimeError):
    pass


def _leer_bytes(ruta):
    """Lee el modelo como .pkl binario o, si no está, como texto base64 (<ruta>.b64): sirve para editores web que no aceptan binarios."""
    if os.path.exists(ruta):
        with open(ruta, "rb") as f:
            return f.read()
    if os.path.exists(ruta + ".b64"):
        with open(ruta + ".b64", "rb") as f:
            return base64.b64decode(f.read())
    raise ModeloInvalido(f"No se encontró el modelo en {os.path.abspath(ruta)} (ni su versión {os.path.basename(ruta)}.b64). "
                         "Copiá modelo_hta_logreg.pkl a la carpeta models/.")


def cargar_modelo(ruta=RUTA_MODELO):
    """Carga el modelo (propio, incluido en la imagen del Actor) y verifica que sea compatible."""
    art = pickle.loads(_leer_bytes(ruta))
    faltan = CLAVES_OBLIGATORIAS - set(art)
    if faltan:
        raise ModeloInvalido(f"El artefacto no tiene las claves esperadas: {sorted(faltan)}")
    v_entrenado, v_actual = art["versiones"].get("sklearn"), sklearn.__version__
    if v_entrenado != v_actual and os.environ.get("PERMITIR_VERSION_DISTINTA") != "1":
        raise ModeloInvalido(f"El modelo se entrenó con scikit-learn {v_entrenado} pero acá hay {v_actual}. "
                             f"Fijá scikit-learn=={v_entrenado} en requirements.txt y volvé a construir el Actor.")
    return art


def predecir_proba(art, X):
    """Probabilidad de la clase positiva (hipertensión) para cada fila de X."""
    return art["modelo"].predict_proba(X)[:, 1]