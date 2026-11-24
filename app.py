import sqlite3
import os
from datetime import datetime
from fastapi import FastAPI, Request, Form, File, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="Sistema de Alerta Temprana e Interacción - ISFD N° 9")
DB_NAME = "sistema_isfd9.db"
UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# ESTRUCTURA DE BASE DE DATOS Y MIGRACIÓN AUTOMÁTICA
# -----------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS Usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS Materia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            comision TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS Ausencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            docente_nombre TEXT NOT NULL,
            materia TEXT NOT NULL,
            fecha TEXT NOT NULL,
            motivo TEXT,
            motivo_generico TEXT DEFAULT 'Ausencia justificada',
            reemplazo TEXT DEFAULT '',
            tarea_actividad TEXT DEFAULT '',
            fecha_emision TEXT DEFAULT '',
            estado TEXT DEFAULT 'Activa',
            lecturas_confirmadas INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS Documento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingresante_nombre TEXT NOT NULL,
            nombre_archivo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            fecha_carga TEXT NOT NULL,
            estado TEXT DEFAULT 'Pendiente'
        );

        CREATE TABLE IF NOT EXISTS AsistenciaAlumno (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_nombre TEXT NOT NULL,
            materia TEXT NOT NULL,
            fecha TEXT NOT NULL,
            estado TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ForoMensaje (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            materia TEXT NOT NULL,
            autor_nombre TEXT NOT NULL,
            rol TEXT NOT NULL,
            contenido TEXT NOT NULL,
            fecha_hora TEXT NOT NULL
        );
    """)

    # Migración segura si ya existía sistema_isfd9.db de la versión previa
    columnas_existentes = [col[1] for col in cursor.execute("PRAGMA table_info(Ausencia)").fetchall()]
    nuevas_columnas = {
        "motivo_generico": "TEXT DEFAULT 'Ausencia justificada'",
        "reemplazo": "TEXT DEFAULT ''",
        "tarea_actividad": "TEXT DEFAULT ''",
        "fecha_emision": "TEXT DEFAULT ''",
        "lecturas_confirmadas": "INTEGER DEFAULT 0"
    }
    for col_name, col_def in nuevas_columnas.items():
        if col_name not in columnas_existentes:
            cursor.execute(f"ALTER TABLE Ausencia ADD COLUMN {col_name} {col_def}")

    # Actualizar estados antiguos 'Notificada' a 'Activa' para consistencia
    cursor.execute("UPDATE Ausencia SET estado = 'Activa' WHERE estado = 'Notificada'")

    # Usuarios representativos del ISFD N° 9
    cursor.executescript("""
        INSERT OR IGNORE INTO Usuario (id, nombre, email, password, rol) VALUES 
        (1, 'Prof. Danilo Brega', 'docente@isfd9.edu.ar', '1234', 'Docente'),
        (2, 'Lucía Fernández', 'alumno@isfd9.edu.ar', '1234', 'Alumno'),
        (3, 'Martín Paz', 'ingresante@isfd9.edu.ar', '1234', 'Ingresante'),
        (4, 'Admin Bedelía', 'admin@isfd9.edu.ar', '1234', 'Administrador'),
        (5, 'Alejandro Ferreyra', 'preceptor@isfd9.edu.ar', '1234', 'Preceptor');

        INSERT OR IGNORE INTO Materia (id, nombre, comision) VALUES 
        (1, 'Prácticas Docentes (Prueba Piloto)', '3° Año'),
        (2, 'Análisis y Diseño de Sistemas', '3° Año'),
        (3, 'Ingeniería de Software', '3° Año');
    """)
    conn.commit()
    conn.close()

init_db()

# -----------------------------------------------------------------------------
# MAQUETADO BASE (TAILWIND CSS)
# -----------------------------------------------------------------------------
def html_layout(title: str, content: str, auto_refresh: bool = False) -> str:
    refresh_tag = '<meta http-equiv="refresh" content="30">' if auto_refresh else ''
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        {refresh_tag}
        <title>{title} - ISFD N° 9</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-100 min-h-screen font-sans">
        <nav class="bg-blue-900 text-white p-4 shadow-md flex flex-wrap justify-between items-center gap-2">
            <div class="flex items-center gap-3">
                <h1 class="text-xl font-bold">ISFD N° 9 | Alerta Temprana</h1>
                <span class="hidden sm:inline-block text-xs bg-blue-800 text-blue-200 px-2.5 py-0.5 rounded-full">Piloto Prácticas</span>
            </div>
            <div class="flex items-center gap-2">
                <a href="/cartelera" class="text-sm bg-amber-500 hover:bg-amber-600 text-slate-900 font-semibold px-3 py-1.5 rounded transition">
                    Cartelera Hall (Sin Login)
                </a>
                <a href="/" class="text-sm bg-blue-700 hover:bg-blue-800 px-3 py-1.5 rounded transition">
                    Cambiar Rol / Salir
                </a>
            </div>
        </nav>
        <main class="container mx-auto p-6 max-w-5xl">
            {content}
        </main>
    </body>
    </html>
    """

# -----------------------------------------------------------------------------
# AUTENTICACIÓN Y VISTA PÚBLICA (MODO HALL)
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def vista_login():
    content = """
    <div class="bg-white p-8 rounded-xl shadow-lg max-w-md mx-auto mt-10 border border-slate-200">
        <h2 class="text-2xl font-bold text-center text-slate-800 mb-1">Plataforma ISFD N° 9</h2>
        <p class="text-sm text-center text-slate-500 mb-6">Canal único formal de comunicación institucional</p>
        <form action="/login" method="post" class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-slate-700">Seleccionar Perfil de Prueba</label>
                <select name="email" class="w-full mt-1 p-2.5 border rounded-lg bg-slate-50 focus:ring-2 focus:ring-blue-500 outline-none">
                    <option value="docente@isfd9.edu.ar">Prof. Danilo Brega (Docente)</option>
                    <option value="alumno@isfd9.edu.ar">Lucía Fernández (Alumno)</option>
                    <option value="preceptor@isfd9.edu.ar">Alejandro Ferreyra (Preceptor)</option>
                    <option value="ingresante@isfd9.edu.ar">Martín Paz (Ingresante)</option>
                    <option value="admin@isfd9.edu.ar">Admin Bedelía (Administrador)</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700">Contraseña</label>
                <input type="password" name="password" value="1234" class="w-full mt-1 p-2.5 border rounded-lg bg-slate-50" required>
            </div>
            <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg transition">
                Ingresar al Sistema
            </button>
        </form>
        <div class="mt-6 pt-5 border-t border-slate-200 text-center">
            <p class="text-xs text-slate-500 mb-2">¿Sin celular o sin datos móviles en el instituto?</p>
            <a href="/cartelera" class="inline-block w-full bg-slate-800 hover:bg-slate-900 text-white text-sm font-medium py-2 px-4 rounded-lg transition">
                Abrir Pantalla Pública del Hall (Sin Login)
            </a>
        </div>
    </div>
    """
    return html_layout("Inicio de Sesión", content)

@app.post("/login")
def procesar_login(email: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM Usuario WHERE email = ? AND password = ?", (email, password)).fetchone()
    conn.close()

    if not user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    rol = user["rol"]
    if rol == "Docente":
        return RedirectResponse(url=f"/docente?nombre={user['nombre']}", status_code=status.HTTP_302_FOUND)
    elif rol == "Alumno":
        return RedirectResponse(url=f"/alumno?nombre={user['nombre']}", status_code=status.HTTP_302_FOUND)
    elif rol == "Preceptor":
        return RedirectResponse(url=f"/preceptor?nombre={user['nombre']}", status_code=status.HTTP_302_FOUND)
    elif rol == "Ingresante":
        return RedirectResponse(url=f"/ingresante?nombre={user['nombre']}", status_code=status.HTTP_302_FOUND)
    elif rol == "Administrador":
        return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.get("/cartelera", response_class=HTMLResponse)
def cartelera_hall():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    avisos = cursor.execute("SELECT * FROM Ausencia ORDER BY id DESC").fetchall()
    conn.close()

    tarjetas = ""
    for a in avisos:
        es_activa = (a["estado"] == "Activa")
        borde = "border-l-8 border-red-600 bg-white" if es_activa else "border-l-8 border-emerald-600 bg-emerald-50/60"
        badge = '<span class="bg-red-600 text-white px-3 py-1 rounded-full text-xs font-bold uppercase">Ausencia Activa</span>' if es_activa else '<span class="bg-emerald-600 text-white px-3 py-1 rounded-full text-xs font-bold uppercase">Aviso Retirado - Hay Clase Normal</span>'
        reemplazo_txt = a["reemplazo"] if a["reemplazo"] else "Sin reemplazo asignado"
        tarea_txt = a["tarea_actividad"] if a["tarea_actividad"] else "Sin actividad cargada"
        emision_txt = a["fecha_emision"] if a["fecha_emision"] else "Registrado en sistema"

        tarjetas += f"""
        <div class="{borde} p-5 rounded-xl shadow-md border border-slate-200 flex flex-col md:flex-row justify-between gap-4">
            <div class="space-y-1.5">
                <div class="flex flex-wrap items-center gap-2">
                    <span class="text-lg font-extrabold text-slate-900">{a['materia']}</span>
                    {badge}
                </div>
                <p class="text-sm text-slate-700"><strong>Docente:</strong> {a['docente_nombre']} | <strong>Fecha de Clase:</strong> {a['fecha']}</p>
                <p class="text-sm text-slate-600"><strong>Motivo:</strong> {a['motivo_generico']} | <strong>Reemplazo:</strong> {reemplazo_txt}</p>
                <p class="text-sm text-blue-900 bg-blue-50 px-3 py-1.5 rounded-lg inline-block"><strong>Tarea / Actividad:</strong> {tarea_txt}</p>
            </div>
            <div class="text-left md:text-right text-xs text-slate-500 flex flex-col justify-between shrink-0">
                <span>Emitido: {emision_txt}</span>
                <span class="font-semibold text-slate-700 mt-2">Confirmaciones (Vistos): {a['lecturas_confirmadas']}</span>
            </div>
        </div>
        """

    hora_actual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    content = f"""
    <div class="space-y-6">
        <div class="bg-slate-900 text-white p-6 rounded-xl shadow-lg flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
                <h2 class="text-2xl font-bold">Cartelera Digital de Cursadas — Hall ISFD N° 9</h2>
                <p class="text-sm text-slate-300">Acceso público sin necesidad de cuenta ni datos móviles (actualización automática cada 30s)</p>
            </div>
            <div class="bg-slate-800 px-4 py-2 rounded-lg text-right">
                <p class="text-xs text-slate-400">Última sincronización</p>
                <p class="text-sm font-mono font-bold text-amber-400">{hora_actual}</p>
            </div>
        </div>
        <div class="space-y-4">
            {tarjetas or '<div class="bg-white p-8 rounded-xl text-center text-slate-500 shadow">No se registran avisos de ausencia docente para la jornada.</div>'}
        </div>
    </div>
    """
    return html_layout("Cartelera Hall", content, auto_refresh=True)

# -----------------------------------------------------------------------------
# MÓDULO DOCENTE (Alertas Estructuradas, Anulación, Asistencia y Foro)
# -----------------------------------------------------------------------------
@app.get("/docente", response_class=HTMLResponse)
def panel_docente(nombre: str = "Prof. Danilo Brega", materia: str = "Prácticas Docentes (Prueba Piloto)"):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    mis_avisos = cursor.execute("SELECT * FROM Ausencia WHERE docente_nombre = ? ORDER BY id DESC", (nombre,)).fetchall()
    alumnos = cursor.execute("SELECT nombre FROM Usuario WHERE rol = 'Alumno'").fetchall()
    mensajes = cursor.execute("SELECT * FROM ForoMensaje WHERE materia = ? ORDER BY id DESC", (materia,)).fetchall()
    conn.close()

    filas_avisos = ""
    for av in mis_avisos:
        if av["estado"] == "Activa":
            estado_badge = '<span class="bg-red-100 text-red-700 px-2.5 py-0.5 rounded-full text-xs font-bold">Activa</span>'
            accion_btn = f"""
            <form action="/ausencia/anular/{av['id']}" method="post" class="inline">
                <input type="hidden" name="docente_nombre" value="{nombre}">
                <button type="submit" class="bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold px-3 py-1 rounded transition">
                    Retirar / Anular Aviso
                </button>
            </form>
            """
        else:
            estado_badge = '<span class="bg-emerald-100 text-emerald-800 px-2.5 py-0.5 rounded-full text-xs font-bold">Anulada (Clase Normal)</span>'
            accion_btn = '<span class="text-xs text-slate-400">Aviso retirado</span>'

        filas_avisos += f"""
        <tr class="border-b hover:bg-slate-50">
            <td class="p-2.5 text-sm font-semibold">{av['fecha']}</td>
            <td class="p-2.5 text-sm">{av['materia']}</td>
            <td class="p-2.5 text-xs text-slate-600">{av['motivo_generico']}</td>
            <td class="p-2.5 text-xs font-bold text-slate-700">{av['lecturas_confirmadas']} vistos</td>
            <td class="p-2.5">{estado_badge}</td>
            <td class="p-2.5">{accion_btn}</td>
        </tr>
        """

    filas_alumnos = ""
    for al in alumnos:
        filas_alumnos += f"""
        <tr class="border-b">
            <td class="p-2 text-sm text-slate-700">{al['nombre']}</td>
            <td class="p-2 space-x-4">
                <label class="inline-flex items-center text-xs font-semibold text-green-700">
                    <input type="radio" name="asistencia_{al['nombre']}" value="Presente" checked class="mr-1"> Presente
                </label>
                <label class="inline-flex items-center text-xs font-semibold text-red-700">
                    <input type="radio" name="asistencia_{al['nombre']}" value="Ausente" class="mr-1"> Ausente
                </label>
            </td>
        </tr>
        """

    foro_html = ""
    for m in mensajes:
        badge_color = "bg-blue-100 text-blue-800" if m['rol'] == 'Docente' else "bg-emerald-100 text-emerald-800"
        foro_html += f"""
        <div class="p-3 bg-slate-50 border rounded-lg space-y-1">
            <div class="flex justify-between items-center text-xs">
                <span class="font-bold text-slate-700">{m['autor_nombre']} <span class="{badge_color} px-2 py-0.5 rounded-full">{m['rol']}</span></span>
                <span class="text-slate-400">{m['fecha_hora']}</span>
            </div>
            <p class="text-sm text-slate-800">{m['contenido']}</p>
        </div>
        """

    content = f"""
    <div class="space-y-6">
        <!-- SECCIÓN 1: AVISO ESTRUCTURADO DE AUSENCIA DOCENTE -->
        <div class="bg-white p-6 rounded-xl shadow-md border border-slate-200">
            <div class="flex justify-between items-center mb-3">
                <h2 class="text-xl font-bold text-slate-800">Emitir Aviso de Ausencia Docente</h2>
                <span class="text-xs bg-blue-50 text-blue-800 font-semibold px-3 py-1 rounded-full">Docente: {nombre}</span>
            </div>
            <form action="/ausencia/guardar" method="post" class="space-y-4">
                <input type="hidden" name="docente_nombre" value="{nombre}">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-700">Materia / Curso</label>
                        <select name="materia" class="w-full mt-1 p-2 border rounded-lg bg-slate-50">
                            <option value="Prácticas Docentes (Prueba Piloto)">Prácticas Docentes (Prueba Piloto)</option>
                            <option value="Análisis y Diseño de Sistemas">Análisis y Diseño de Sistemas (3° Año)</option>
                            <option value="Ingeniería de Software">Ingeniería de Software (3° Año)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700">Fecha de Clase</label>
                        <input type="date" name="fecha" value="{datetime.now().strftime('%Y-%m-%d')}" class="w-full mt-1 p-2 border rounded-lg bg-slate-50" required>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700">Motivo Genérico (Privacidad)</label>
                        <select name="motivo_generico" class="w-full mt-1 p-2 border rounded-lg bg-slate-50">
                            <option value="Ausencia justificada">Ausencia justificada</option>
                            <option value="Razones de salud">Razones de salud</option>
                            <option value="Comisión / Actividad institucional">Comisión / Actividad institucional</option>
                            <option value="Licencia reglamentaria">Licencia reglamentaria</option>
                        </select>
                    </div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-700">Docente Reemplazante (Opcional)</label>
                        <input type="text" name="reemplazo" class="w-full mt-1 p-2 border rounded-lg bg-slate-50" placeholder="Ej: Prof. María López o dejar vacío">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700">Actividad / Tarea para Alumnos (Opcional)</label>
                        <input type="text" name="tarea_actividad" class="w-full mt-1 p-2 border rounded-lg bg-slate-50" placeholder="Ej: Lectura Unidad 3 y debate en el foro">
                    </div>
                </div>
                <button type="submit" class="bg-amber-600 hover:bg-amber-700 text-white font-semibold px-5 py-2.5 rounded-lg transition text-sm">
                    Notificar Simultáneamente (Alumnos, Preceptoría y Cartelera)
                </button>
            </form>

            <!-- MIS AVISOS EMITIDOS (OPCIÓN RETIRAR / ANULAR) -->
            <div class="mt-6 pt-5 border-t border-slate-200">
                <h3 class="text-sm font-bold uppercase text-slate-600 mb-3">Mis Avisos Emitidos (Gestión y Anulación)</h3>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-slate-100 border-b text-xs uppercase text-slate-600 font-bold">
                                <th class="p-2.5">Fecha</th>
                                <th class="p-2.5">Materia</th>
                                <th class="p-2.5">Motivo</th>
                                <th class="p-2.5">Trazabilidad</th>
                                <th class="p-2.5">Estado</th>
                                <th class="p-2.5">Acción</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filas_avisos or '<tr><td colspan="6" class="p-3 text-center text-xs text-slate-400">No emitiste avisos de ausencia aún.</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- SECCIÓN 2: TOMAR ASISTENCIA DE ALUMNOS -->
        <div class="bg-white p-6 rounded-xl shadow-md border border-slate-200">
            <h2 class="text-xl font-bold text-slate-800 mb-3">Tomar Asistencia de Alumnos</h2>
            <form action="/asistencia/guardar" method="post" class="space-y-4">
                <input type="hidden" name="docente_nombre" value="{nombre}">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-700">Materia</label>
                        <select name="materia" class="w-full mt-1 p-2 border rounded-lg bg-slate-50">
                            <option value="Prácticas Docentes (Prueba Piloto)">Prácticas Docentes (Prueba Piloto)</option>
                            <option value="Análisis y Diseño de Sistemas">Análisis y Diseño de Sistemas</option>
                            <option value="Ingeniería de Software">Ingeniería de Software</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700">Fecha de Clase</label>
                        <input type="date" name="fecha" value="{datetime.now().strftime('%Y-%m-%d')}" class="w-full mt-1 p-2 border rounded-lg bg-slate-50" required>
                    </div>
                </div>
                <table class="w-full text-left border-collapse mt-2">
                    <thead>
                        <tr class="bg-slate-100 border-b text-xs uppercase text-slate-600 font-bold">
                            <th class="p-2">Alumno</th>
                            <th class="p-2">Estado</th>
                        </tr>
                    </thead>
                    <tbody>{filas_alumnos}</tbody>
                </table>
                <button type="submit" class="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-4 py-2 rounded-lg transition text-sm">
                    Guardar Planilla de Asistencia
                </button>
            </form>
        </div>

        <!-- SECCIÓN 3: FORO DE COMUNICACIÓN -->
        <div class="bg-white p-6 rounded-xl shadow-md border border-slate-200 space-y-4">
            <h2 class="text-xl font-bold text-slate-800">Foro de Interacción Académica ({materia})</h2>
            <form action="/foro/publicar" method="post" class="flex gap-2">
                <input type="hidden" name="autor_nombre" value="{nombre}">
                <input type="hidden" name="rol" value="Docente">
                <input type="hidden" name="materia" value="{materia}">
                <input type="text" name="contenido" placeholder="Publicar consigna o responder consultas de alumnos..." class="flex-grow p-2 border rounded-lg bg-slate-50" required>
                <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-semibold text-sm transition">
                    Publicar
                </button>
            </form>
            <div class="space-y-2 mt-4 max-h-60 overflow-y-auto">
                {foro_html or '<p class="text-xs text-slate-400">No hay publicaciones aún en el foro.</p>'}
            </div>
        </div>
    </div>
    """
    return html_layout("Panel Docente", content)

@app.post("/ausencia/guardar")
def guardar_ausencia(
    docente_nombre: str = Form(...),
    materia: str = Form(...),
    fecha: str = Form(...),
    motivo_generico: str = Form("Ausencia justificada"),
    reemplazo: str = Form(""),
    tarea_actividad: str = Form("")
):
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Ausencia (docente_nombre, materia, fecha, motivo, motivo_generico, reemplazo, tarea_actividad, fecha_emision, estado, lecturas_confirmadas)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Activa', 0)
    """, (docente_nombre, materia, fecha, motivo_generico, motivo_generico, reemplazo, tarea_actividad, fecha_emision))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/docente?nombre={docente_nombre}", status_code=status.HTTP_302_FOUND)

@app.post("/ausencia/anular/{ausencia_id}")
def anular_ausencia(ausencia_id: int, docente_nombre: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE Ausencia SET estado = 'Anulada' WHERE id = ?", (ausencia_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/docente?nombre={docente_nombre}", status_code=status.HTTP_302_FOUND)

@app.post("/ausencia/visto/{ausencia_id}")
def confirmar_lectura(ausencia_id: int, origen: str = Form("alumno"), nombre: str = Form("Lucía Fernández")):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE Ausencia SET lecturas_confirmadas = lecturas_confirmadas + 1 WHERE id = ?", (ausencia_id,))
    conn.commit()
    conn.close()
    destino = f"/preceptor?nombre={nombre}" if origen == "preceptor" else f"/alumno?nombre={nombre}"
    return RedirectResponse(url=destino, status_code=status.HTTP_302_FOUND)

@app.post("/asistencia/guardar")
async def guardar_asistencia(request: Request):
    form_data = await request.form()
    docente_nombre = form_data.get("docente_nombre", "Prof. Danilo Brega")
    materia = form_data.get("materia", "Prácticas Docentes (Prueba Piloto)")
    fecha = form_data.get("fecha", datetime.now().strftime("%Y-%m-%d"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    alumnos = cursor.execute("SELECT nombre FROM Usuario WHERE rol = 'Alumno'").fetchall()

    for al in alumnos:
        nombre_al = al[0]
        estado_seleccionado = form_data.get(f"asistencia_{nombre_al}", "Presente")
        cursor.execute(
            "INSERT INTO AsistenciaAlumno (alumno_nombre, materia, fecha, estado) VALUES (?, ?, ?, ?)",
            (nombre_al, materia, fecha, estado_seleccionado)
        )

    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/docente?nombre={docente_nombre}", status_code=status.HTTP_302_FOUND)

# -----------------------------------------------------------------------------
# MÓDULO ALUMNO (Alertas con Confirmación de Lectura, Asistencias y Foro)
# -----------------------------------------------------------------------------
@app.get("/alumno", response_class=HTMLResponse)
def panel_alumno(nombre: str = "Lucía Fernández", materia: str = "Prácticas Docentes (Prueba Piloto)"):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    ausencias_docentes = cursor.execute("SELECT * FROM Ausencia ORDER BY id DESC").fetchall()
    mis_asistencias = cursor.execute("SELECT * FROM AsistenciaAlumno WHERE alumno_nombre = ? ORDER BY id DESC", (nombre,)).fetchall()
    mensajes_foro = cursor.execute("SELECT * FROM ForoMensaje WHERE materia = ? ORDER BY id DESC", (materia,)).fetchall()
    conn.close()

    filas_ausencias = ""
    for a in ausencias_docentes:
        es_activa = (a["estado"] == "Activa")
        estado_badge = '<span class="bg-red-100 text-red-700 px-2 py-0.5 rounded-full text-xs font-bold">Activa</span>' if es_activa else '<span class="bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full text-xs font-bold">Anulada (Hay Clase)</span>'
        detalle_extra = f"Motivo: {a['motivo_generico']}"
        if a["reemplazo"]:
            detalle_extra += f" | Reemplazo: {a['reemplazo']}"
        if a["tarea_actividad"]:
            detalle_extra += f"<br><span class='text-blue-700 font-medium'>Tarea: {a['tarea_actividad']}</span>"

        filas_ausencias += f"""
        <tr class="border-b hover:bg-slate-50">
            <td class="p-2.5 text-sm font-semibold text-slate-700">
                {a['fecha']}
                <div class="text-[11px] font-normal text-slate-400">Emitido: {a['fecha_emision']}</div>
            </td>
            <td class="p-2.5 text-sm text-slate-800">
                <div class="font-semibold">{a['materia']}</div>
                <div class="text-xs text-slate-500">{a['docente_nombre']}</div>
            </td>
            <td class="p-2.5 text-xs text-slate-600">{detalle_extra}</td>
            <td class="p-2.5">{estado_badge}</td>
            <td class="p-2.5">
                <form action="/ausencia/visto/{a['id']}" method="post" class="flex items-center gap-2">
                    <input type="hidden" name="origen" value="alumno">
                    <input type="hidden" name="nombre" value="{nombre}">
                    <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-2.5 py-1 rounded transition">
                        Confirmar Lectura
                    </button>
                    <span class="text-xs text-slate-500 font-semibold">({a['lecturas_confirmadas']})</span>
                </form>
            </td>
        </tr>
        """

    filas_asistencias = ""
    for asis in mis_asistencias:
        badge = "bg-green-100 text-green-800" if asis['estado'] == 'Presente' else "bg-red-100 text-red-800"
        filas_asistencias += f"""
        <tr class="border-b">
            <td class="p-2.5 text-sm text-slate-700">{asis['fecha']}</td>
            <td class="p-2.5 text-sm text-slate-800">{asis['materia']}</td>
            <td class="p-2.5"><span class="{badge} px-2 py-0.5 rounded-full text-xs font-bold">{asis['estado']}</span></td>
        </tr>
        """

    foro_html = ""
    for m in mensajes_foro:
        badge_color = "bg-blue-100 text-blue-800" if m['rol'] == 'Docente' else "bg-emerald-100 text-emerald-800"
        foro_html += f"""
        <div class="p-3 bg-slate-50 border rounded-lg space-y-1">
            <div class="flex justify-between items-center text-xs">
                <span class="font-bold text-slate-700">{m['autor_nombre']} <span class="{badge_color} px-2 py-0.5 rounded-full">{m['rol']}</span></span>
                <span class="text-slate-400">{m['fecha_hora']}</span>
            </div>
            <p class="text-sm text-slate-800">{m['contenido']}</p>
        </div>
        """

    content = f"""
    <div class="space-y-6">
        <!-- ALERTAS DE AUSENCIA DOCENTE -->
        <div class="bg-white p-6 rounded-xl shadow-md border border-slate-200">
            <div class="flex justify-between items-center mb-3">
                <h2 class="text-xl font-bold text-slate-800">Alertas Tempranas de Ausencia Docente</h2>
                <span class="text-xs bg-emerald-50 text-emerald-800 font-semibold px-3 py-1 rounded-full">Alumna: {nombre}</span>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-slate-100 border-b text-xs uppercase text-slate-600 font-bold">
                            <th class="p-2.5">Fecha Clase</th>
                            <th class="p-2.5">Materia / Docente</th>
                            <th class="p-2.5">Detalle y Tarea</th>
                            <th class="p-2.5">Estado</th>
                            <th class="p-2.5">Trazabilidad</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_ausencias or '<tr><td colspan="5" class="p-4 text-center text-slate-400">No hay avisos de inasistencia docente.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- ASISTENCIA INDIVIDUAL DEL ALUMNO -->
        <div class="bg-white p-6 rounded-xl shadow-md border border-slate-200">
            <h2 class="text-xl font-bold text-slate-800 mb-3">Mi Registro de Asistencias</h2>
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="bg-slate-100 border-b text-xs uppercase text-slate-600 font-bold">
                        <th class="p-2.5">Fecha</th>
                        <th class="p-2.5">Materia</th>
                        <th class="p-2.5">Mi Estado</th>
                    </tr>
                </thead>
                <tbody>
                    {filas_asistencias or '<tr><td colspan="3" class="p-3 text-center text-slate-400">Aún no se registraron asistencias.</td></tr>'}
                </tbody>
            </table>
        </div>

        <!-- FORO DE INTERACCIÓN -->
        <div class="bg-white p-6 rounded-xl shadow-md border border-slate-200 space-y-4">
            <h2 class="text-xl font-bold text-slate-800">Foro de la Materia ({materia})</h2>
            <form action="/foro/publicar" method="post" class="flex gap-2">
                <input type="hidden" name="autor_nombre" value="{nombre}">
                <input type="hidden" name="rol" value="Alumno">
                <input type="hidden" name="materia" value="{materia}">
                <input type="text" name="contenido" placeholder="Hacer una pregunta o responder en el foro..." class="flex-grow p-2 border rounded-lg bg-slate-50" required>
                <button type="submit" class="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg font-semibold text-sm transition">
                    Comentar
                </button>
            </form>
            <div class="space-y-2 mt-4 max-h-60 overflow-y-auto">
                {foro_html or '<p class="text-xs text-slate-400">No hay publicaciones aún en el foro.</p>'}
            </div>
        </div>
    </div>
    """
    return html_layout("Tablero Alumnos", content)

# -----------------------------------------------------------------------------
# MÓDULO PRECEPTOR (Monitoreo Simultáneo sin Cuello de Botella)
# -----------------------------------------------------------------------------
@app.get("/preceptor", response_class=HTMLResponse)
def panel_preceptor(nombre: str = "Alejandro Ferreyra"):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    avisos = cursor.execute("SELECT * FROM Ausencia ORDER BY id DESC").fetchall()
    conn.close()

    filas = ""
    for a in avisos:
        es_activa = (a["estado"] == "Activa")
        estado_badge = '<span class="bg-red-100 text-red-700 px-2 py-0.5 rounded-full text-xs font-bold">Activa</span>' if es_activa else '<span class="bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full text-xs font-bold">Anulada</span>'
        filas += f"""
        <tr class="border-b hover:bg-slate-50">
            <td class="p-2.5 text-sm font-semibold">{a['fecha']}<div class="text-[11px] text-slate-400">Emitido: {a['fecha_emision']}</div></td>
            <td class="p-2.5 text-sm">{a['materia']}</td>
            <td class="p-2.5 text-sm">{a['docente_nombre']}</td>
            <td class="p-2.5 text-xs">{a['motivo_generico']} | Reemplazo: {a['reemplazo'] or 'No'}</td>
            <td class="p-2.5">{estado_badge}</td>
            <td class="p-2.5">
                <form action="/ausencia/visto/{a['id']}" method="post" class="flex items-center gap-2">
                    <input type="hidden" name="origen" value="preceptor">
                    <input type="hidden" name="nombre" value="{nombre}">
                    <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-2.5 py-1 rounded">
                        Confirmar Recepción
                    </button>
                    <span class="text-xs font-bold text-slate-600">({a['lecturas_confirmadas']} vistos)</span>
                </form>
            </td>
        </tr>
        """

    content = f"""
    <div class="bg-white p-6 rounded-xl shadow-md border border-slate-200">
        <div class="flex justify-between items-center mb-4">
            <div>
                <h2 class="text-xl font-bold text-slate-800">Panel de Preceptoría y Regencia</h2>
                <p class="text-xs text-slate-500">Recepción simultánea automatizada (elimina retransmisión manual por correo)</p>
            </div>
            <span class="text-xs bg-blue-100 text-blue-900 font-bold px-3 py-1 rounded-full">Preceptor: {nombre}</span>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="bg-slate-100 border-b text-xs uppercase text-slate-600 font-bold">
                        <th class="p-2.5">Fecha</th>
                        <th class="p-2.5">Materia</th>
                        <th class="p-2.5">Docente</th>
                        <th class="p-2.5">Detalle</th>
                        <th class="p-2.5">Estado</th>
                        <th class="p-2.5">Auditoría</th>
                    </tr>
                </thead>
                <tbody>
                    {filas or '<tr><td colspan="6" class="p-4 text-center text-slate-400">Sin novedades docentes registradas.</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    """
    return html_layout("Panel Preceptoría", content)

@app.post("/foro/publicar")
def publicar_foro(autor_nombre: str = Form(...), rol: str = Form(...), materia: str = Form(...), contenido: str = Form(...)):
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ForoMensaje (materia, autor_nombre, rol, contenido, fecha_hora) VALUES (?, ?, ?, ?, ?)",
                   (materia, autor_nombre, rol, contenido, fecha_hora))
    conn.commit()
    conn.close()

    redireccion = f"/docente?nombre={autor_nombre}" if rol == "Docente" else f"/alumno?nombre={autor_nombre}"
    return RedirectResponse(url=redireccion, status_code=status.HTTP_302_FOUND)

# -----------------------------------------------------------------------------
# MÓDULO INGRESANTE Y BEDELÍA (Gestión Documental)
# -----------------------------------------------------------------------------
@app.get("/ingresante", response_class=HTMLResponse)
def panel_ingresante(nombre: str = "Martín Paz"):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    docs = cursor.execute("SELECT * FROM Documento WHERE ingresante_nombre = ?", (nombre,)).fetchall()
    conn.close()

    filas = ""
    for d in docs:
        color = "bg-yellow-100 text-yellow-800" if d['estado'] == 'Pendiente' else ("bg-green-100 text-green-800" if d['estado'] == 'Aprobado' else "bg-red-100 text-red-800")
        filas += f"""
        <tr class="border-b">
            <td class="p-3 font-medium">{d['nombre_archivo']}</td>
            <td class="p-3">{d['fecha_carga']}</td>
            <td class="p-3"><span class="{color} px-2.5 py-1 rounded-full text-xs font-bold">{d['estado']}</span></td>
        </tr>
        """

    content = f"""
    <div class="space-y-6">
        <div class="bg-white p-6 rounded-xl shadow-md border border-slate-200">
            <h2 class="text-xl font-bold text-slate-800 mb-2">Carga de Documentación de Inscripción</h2>
            <p class="text-sm text-slate-600 mb-4">Ingresante: <strong>{nombre}</strong></p>
            <form action="/documento/subir" method="post" enctype="multipart/form-data" class="space-y-4">
                <input type="hidden" name="ingresante_nombre" value="{nombre}">
                <div>
                    <label class="block text-sm font-medium text-slate-700">Seleccionar Archivo (PDF, JPG, PNG)</label>
                    <input type="file" name="file" accept=".pdf,.png,.jpg,.jpeg" class="w-full mt-1 p-2 border rounded-lg bg-slate-50" required>
                </div>
                <button type="submit" class="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-4 py-2 rounded-lg transition">
                    Subir Documento
                </button>
            </form>
        </div>
        <div class="bg-white p-6 rounded-xl shadow-md border border-slate-200">
            <h3 class="text-lg font-bold text-slate-800 mb-3">Mis Documentos Presentados</h3>
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="bg-slate-100 border-b text-xs uppercase text-slate-600 font-bold">
                        <th class="p-3">Archivo</th>
                        <th class="p-3">Fecha de Carga</th>
                        <th class="p-3">Estado de Revisión</th>
                    </tr>
                </thead>
                <tbody>{filas or '<tr><td colspan="3" class="p-3 text-slate-400">No ha subido archivos aún.</td></tr>'}</tbody>
            </table>
        </div>
    </div>
    """
    return html_layout("Panel Ingresante", content)

@app.post("/documento/subir")
def subir_documento(ingresante_nombre: str = Form(...), file: UploadFile = File(...)):
    ext = file.filename.split(".")[-1].lower()
    if ext not in ["pdf", "jpg", "jpeg", "png"]:
        return HTMLResponse("<script>alert('Formato no permitido. Solo PDF, JPG o PNG.'); window.history.back();</script>")

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(file.file.read())

    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Documento (ingresante_nombre, nombre_archivo, tipo, fecha_carga) VALUES (?, ?, ?, ?)",
                   (ingresante_nombre, file.filename, ext, fecha_actual))
    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/ingresante?nombre={ingresante_nombre}", status_code=status.HTTP_302_FOUND)

@app.get("/admin", response_class=HTMLResponse)
def panel_admin():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    docs = cursor.execute("SELECT * FROM Documento ORDER BY id DESC").fetchall()
    conn.close()

    filas = ""
    for d in docs:
        filas += f"""
        <tr class="border-b">
            <td class="p-3 font-medium">{d['ingresante_nombre']}</td>
            <td class="p-3">{d['nombre_archivo']}</td>
            <td class="p-3">{d['fecha_carga']}</td>
            <td class="p-3"><span class="font-bold text-xs uppercase">{d['estado']}</span></td>
            <td class="p-3 space-x-2">
                <a href="/documento/estado/{d['id']}?nuevo_estado=Aprobado" class="bg-green-600 text-white px-2 py-1 rounded text-xs">Aprobar</a>
                <a href="/documento/estado/{d['id']}?nuevo_estado=Rechazado" class="bg-red-600 text-white px-2 py-1 rounded text-xs">Rechazar</a>
            </td>
        </tr>
        """

    content = f"""
    <div class="bg-white p-6 rounded-xl shadow-md border border-slate-200">
        <h2 class="text-xl font-bold text-slate-800 mb-4">Administración / Bedelía — Revisión de Documentación</h2>
        <table class="w-full text-left border-collapse">
            <thead>
                <tr class="bg-slate-100 border-b text-xs uppercase text-slate-600 font-bold">
                    <th class="p-3">Ingresante</th>
                    <th class="p-3">Archivo</th>
                    <th class="p-3">Fecha Carga</th>
                    <th class="p-3">Estado</th>
                    <th class="p-3">Acción</th>
                </tr>
            </thead>
            <tbody>{filas or '<tr><td colspan="5" class="p-3 text-slate-400">Sin documentos pendientes.</td></tr>'}</tbody>
        </table>
    </div>
    """
    return html_layout("Panel Administración", content)

@app.get("/documento/estado/{doc_id}")
def cambiar_estado_documento(doc_id: int, nuevo_estado: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE Documento SET estado = ? WHERE id = ?", (nuevo_estado, doc_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)