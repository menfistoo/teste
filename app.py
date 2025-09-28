from __future__ import annotations

import io
import itertools
from datetime import datetime
from typing import List, Optional

from flask import Flask, redirect, render_template, request, url_for, flash
import pandas as pd

app = Flask(__name__)
app.secret_key = "halfboard-secret"

# In-memory store for uploaded records
_records: List[dict] = []
_record_id_counter = itertools.count(1)


REQUIRED_COLUMNS = {
    "room number": "habitacion",
    "number of persons": "personas",
    "day of check out": "salida",
    "half-board included?": "media_pension",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza los nombres de columnas para que coincidan con los esperados."""
    normalized = {col.lower().strip(): col for col in df.columns}
    missing = [col for col in REQUIRED_COLUMNS if col not in normalized]
    if missing:
        raise ValueError(
            "Faltan las siguientes columnas en el archivo: "
            + ", ".join(REQUIRED_COLUMNS[col] for col in missing)
        )

    rename_map = {normalized[key]: key for key in REQUIRED_COLUMNS}
    return df.rename(columns=rename_map)


def _format_checkout(value: pd.Timestamp | datetime | str | float) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, (int, float)):
        try:
            as_date = datetime.fromordinal(datetime(1899, 12, 30).toordinal() + int(value))
            return as_date.strftime("%d/%m/%Y")
        except Exception:  # pragma: no cover - manejo defensivo
            return str(value)
    return str(value)


def _parse_file(file_storage) -> List[dict]:
    content = file_storage.read()
    if not content:
        raise ValueError("El archivo está vacío.")
    try:
        df = pd.read_excel(io.BytesIO(content))
    except Exception as exc:  # pragma: no cover - pandas lanza distintos errores
        raise ValueError("No se pudo leer el archivo. Asegúrate de que sea un Excel válido.") from exc

    df = _normalize_columns(df)
    df = df[list(REQUIRED_COLUMNS.keys())]

    parsed: List[dict] = []
    for _, row in df.iterrows():
        record_id = next(_record_id_counter)
        parsed.append(
            {
                "id": record_id,
                "habitacion": str(row["room number"]).strip(),
                "personas": int(row["number of persons"]) if not pd.isna(row["number of persons"]) else "",
                "salida": _format_checkout(row["day of check out"]),
                "media_pension": str(row["half-board included?"]).strip(),
                "estado": "Pendiente",
            }
        )
    return parsed


@app.route("/")
def index():
    return render_template("index.html", registros=_records)


@app.post("/upload")
def upload():
    file = request.files.get("archivo")
    if file is None or file.filename == "":
        flash("Debes seleccionar un archivo de Excel antes de subirlo.", "error")
        return redirect(url_for("index"))

    try:
        parsed = _parse_file(file)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    global _records
    _records = parsed
    flash("Archivo cargado correctamente.", "success")
    return redirect(url_for("index"))


@app.post("/toggle/<int:record_id>")
def toggle(record_id: int):
    record: Optional[dict] = next((r for r in _records if r["id"] == record_id), None)
    if record is None:
        flash("No se encontró la habitación solicitada.", "error")
    else:
        record["estado"] = "Ingresó" if record["estado"] == "Pendiente" else "Pendiente"
        flash("Estado actualizado.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
