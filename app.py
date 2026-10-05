import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # SQLite fallback for local development
    psycopg = None

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-key")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_DB = Path(os.environ.get("SQLITE_DB", Path(__file__).with_name("mimp_cae.db")))

AULAS = [
    ("Aula 1", "aula"),
    ("Aula 2", "aula"),
    ("Aula 3", "aula"),
    ("Salón 1", "salon"),
    ("Salón 2", "salon"),
]

AFOROS = {
    "Aula 1": 30,
    "Aula 2": 30,
    "Aula 3": 30,
    "Salón 1": 10,
    "Salón 2": 6,
}

ESPACIOS = [x[0] for x in AULAS]


def using_postgres():
    return bool(DATABASE_URL) and psycopg is not None


def get_db():
    if using_postgres():
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    con = sqlite3.connect(SQLITE_DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = get_db()
    try:
        if using_postgres():
            con.execute("""
                CREATE TABLE IF NOT EXISTS reservas (
                    id BIGSERIAL PRIMARY KEY,
                   espacio TEXT NOT NULL,
                trabajador TEXT NOT NULL,
                contacto TEXT NOT NULL DEFAULT '',
                oficina TEXT NOT NULL DEFAULT '',
                fecha DATE NOT NULL,
                    hora_inicio TIME NOT NULL,
                    hora_fin TIME NOT NULL,
                    motivo TEXT,
                    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_reservas_fecha_espacio
                ON reservas (fecha, espacio, hora_inicio)
            """)
        else:
            con.execute("""
                CREATE TABLE IF NOT EXISTS reservas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                espacio TEXT NOT NULL,
                trabajador TEXT NOT NULL,
                contacto TEXT NOT NULL DEFAULT '',
                oficina TEXT NOT NULL DEFAULT '',
                fecha TEXT NOT NULL,
                    hora_inicio TEXT NOT NULL,
                    hora_fin TEXT NOT NULL,
                    motivo TEXT,
                    creado_en TEXT NOT NULL
                )
            """)
        con.commit()
    finally:
        con.close()


init_db()
def actualizar_db():
    con = get_db()
    try:
        if using_postgres():
            con.execute("""
                ALTER TABLE reservas
                ADD COLUMN IF NOT EXISTS contacto TEXT NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS oficina TEXT NOT NULL DEFAULT ''
            """)
        else:
            try:
                con.execute("ALTER TABLE reservas ADD COLUMN contacto TEXT NOT NULL DEFAULT ''")
            except Exception:
                pass

            try:
                con.execute("ALTER TABLE reservas ADD COLUMN oficina TEXT NOT NULL DEFAULT ''")
            except Exception:
                pass

        con.commit()
    finally:
        con.close()

actualizar_db()

def valid_time_range(inicio, fin):
    try:
        return datetime.strptime(inicio, "%H:%M") < datetime.strptime(fin, "%H:%M")
    except ValueError:
        return False


def get_reservas(fecha):
    con = get_db()
    try:
        if using_postgres():
            return con.execute(
                "SELECT * FROM reservas WHERE fecha=%s ORDER BY hora_inicio, espacio",
                (fecha,),
            ).fetchall()
        return con.execute(
            "SELECT * FROM reservas WHERE fecha=? ORDER BY hora_inicio, espacio",
            (fecha,),
        ).fetchall()
    finally:
        con.close()


@app.route("/")
def index():
    fecha = request.args.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    reservas = get_reservas(fecha)
    return render_template("index.html", reservas=reservas, fecha=fecha, espacios=ESPACIOS)


@app.get("/healthz")
def healthz():
    con = get_db()
    try:
        if using_postgres():
            con.execute("SELECT 1").fetchone()
        else:
            con.execute("SELECT 1").fetchone()
        return jsonify({"status": "ok", "database": "postgresql" if using_postgres() else "sqlite"})
    finally:
        con.close()


@app.post("/reservar")
def reservar():
    espacio = request.form.get("espacio", "").strip()
    trabajador = request.form.get("trabajador", "").strip()
    contacto = request.form.get("contacto", "").strip()
    oficina = request.form.get("oficina", "").strip()
    fecha = request.form.get("fecha", "").strip()
    inicio = request.form.get("hora_inicio", "").strip()
    fin = request.form.get("hora_fin", "").strip()
    motivo = request.form.get("motivo", "").strip()

    if not all([espacio, trabajador, contacto, oficina, fecha, inicio, fin]):
        flash("Completa todos los campos obligatorios.", "error")
        return redirect(url_for("index", fecha=fecha))
    if espacio not in ESPACIOS:
        flash("El espacio seleccionado no es válido.", "error")
        return redirect(url_for("index", fecha=fecha))
    if not valid_time_range(inicio, fin):
        flash("La hora de fin debe ser posterior a la hora de inicio y usar HH:MM.", "error")
        return redirect(url_for("index", fecha=fecha))

    con = get_db()
    try:
        if using_postgres():
            # Serializa reservas para el mismo espacio y fecha para evitar carreras.
            con.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"{espacio}|{fecha}",))
            conflicto = con.execute("""
                SELECT 1 FROM reservas
                WHERE espacio=%s AND fecha=%s
                  AND hora_inicio < %s::time AND hora_fin > %s::time
                LIMIT 1
            """, (espacio, fecha, fin, inicio)).fetchone()
        else:
            conflicto = con.execute("""
                SELECT 1 FROM reservas
                WHERE espacio=? AND fecha=? AND hora_inicio < ? AND hora_fin > ?
                LIMIT 1
            """, (espacio, fecha, fin, inicio)).fetchone()

        if conflicto:
            con.rollback()
            flash("Ese espacio ya está reservado en ese horario.", "error")
            return redirect(url_for("index", fecha=fecha))

        if using_postgres():
            con.execute("""
              INSERT INTO reservas
                (espacio, trabajador, contacto, oficina, fecha, hora_inicio, hora_fin, motivo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (espacio, trabajador, contacto, oficina, fecha, inicio, fin, motivo))
        if using_postgres():
                 con.execute("""
                INSERT INTO reservas
                (espacio, trabajador, contacto, oficina, fecha, hora_inicio, hora_fin, motivo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (espacio, trabajador, contacto, oficina, fecha, inicio, fin, motivo))
        else:
            con.execute("""
                INSERT INTO reservas
                (espacio, trabajador, contacto, oficina, fecha, hora_inicio, hora_fin, motivo, creado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                espacio,
                trabajador,
                contacto,
                oficina,
                fecha,
                inicio,
                fin,
                motivo,
                datetime.now().isoformat(timespec="seconds")
            ))

            con.commit()
        flash("Reserva confirmada automáticamente.", "success")
    except Exception:
        con.rollback()
        app.logger.exception("Error creando reserva")
        flash("No se pudo guardar la reserva. Inténtalo nuevamente.", "error")
    finally:
        con.close()

    return redirect(url_for("index", fecha=fecha))


@app.post("/eliminar/<int:reserva_id>")
def eliminar(reserva_id):
    con = get_db()
    try:
        if using_postgres():
            con.execute("DELETE FROM reservas WHERE id=%s", (reserva_id,))
        else:
            con.execute("DELETE FROM reservas WHERE id=?", (reserva_id,))
        con.commit()
        flash("Reserva cancelada.", "success")
    except Exception:
        con.rollback()
        app.logger.exception("Error cancelando reserva")
        flash("No se pudo cancelar la reserva.", "error")
    finally:
        con.close()
    return redirect(request.referrer or url_for("index"))


@app.get("/api/disponibilidad")
def disponibilidad():
    fecha = request.args.get("fecha")
    inicio = request.args.get("inicio")
    fin = request.args.get("fin")
    if not all([fecha, inicio, fin]) or not valid_time_range(inicio, fin):
        return jsonify({"error": "Parámetros de fecha/hora inválidos"}), 400

    con = get_db()
    try:
        if using_postgres():
            rows = con.execute("""
                SELECT espacio FROM reservas
                WHERE fecha=%s AND hora_inicio < %s::time AND hora_fin > %s::time
            """, (fecha, fin, inicio)).fetchall()
        else:
            rows = con.execute("""
                SELECT espacio FROM reservas
                WHERE fecha=? AND hora_inicio < ? AND hora_fin > ?
            """, (fecha, fin, inicio)).fetchall()
        ocupados = {r["espacio"] for r in rows}
        return jsonify({
            "disponibles": [x for x in ESPACIOS if x not in ocupados],
            "ocupados": sorted(ocupados),
        })
    finally:
        con.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
