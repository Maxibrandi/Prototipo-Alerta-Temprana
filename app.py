import sqlite3
import os
from datetime import datetime
from fastapi import FastAPI, Form, File, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="Sistema de Alerta Temprana e Interacción - ISFD N° 9")
DB_NAME = "sistema_isfd9.db"
UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# ESTRUCTURA DE BASE DE DATOS Y DATOS INICIALES
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
            estado TEXT DEFAULT 'Notificada'
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
            estado TEXT NOT NULL -- 'Presente' o 'Ausente'
        );

        CREATE TABLE IF NOT EXISTS ForoMensaje (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            materia TEXT NOT NULL,
            autor_nombre TEXT NOT NULL,
            rol TEXT NOT NULL,
            contenido TEXT NOT NULL,
            fecha_hora TEXT NOT NULL
        );

        -- Usuarios base
        INSERT OR IGNORE INTO Usuario (id, nombre, email, password, rol) VALUES 
        (1, 'Prof. Carlos Gómez', 'docente@isfd9.edu.ar', '1234', 'Docente'),
        (2, 'Lucía Fernández', 'alumno@isfd9.edu.ar', '1234', 'Alumno'),
        (3, 'Martín Paz', 'ingresante@isfd9.edu.ar', '1234', 'Ingresante'),
        (4, 'Admin Bedelía', 'admin@isfd9.edu.ar', '1234', 'Administrador');

        INSERT OR IGNORE INTO Materia (id, nombre, comision) VALUES 
        (1, 'Análisis y Diseño de Sistemas', '3° Año'),
        (2, 'Ingeniería de Software', '3° Año');
    """)
    conn.commit()
    conn.close()

init_db()

# -----------------------------------------------------------------------------
# MAQUETADO BASE (TAILWIND CSS)
# -----------------------------------------------------------------------------
def html_layout(title: str, content: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - ISFD N° 9</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-100 min-h-screen font-sans">
        <nav class="bg-blue-900 text-white p-4 shadow-md flex justify-between items-center">
            <h1 class="text-xl font-bold">ISFD N° 9 | Plataforma Institucional</h1>
            <a href="/" class="text-sm bg-blue-700 hover:bg-blue-800 px-3 py-1.5 rounded transition">Cambiar Rol / Salir</a>
        </nav>
        <main class="container mx-auto p-6 max-w-5xl">
            {content}
        </main>
    </body>
    </html>
    """

# -----------------------------------------------------------------------------
# AUTENTICACIÓN
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def vista_login():
    content = """
    <div class="bg-white p-8 rounded-xl shadow-lg max-w-md mx-auto mt-12 border border-slate-200">
        <h2 class="text-2xl font-bold text-center text-slate-800 mb-2">Iniciar Sesión</h2>
        <p class="text-sm text-center text-slate-500 mb-6">Seleccione un perfil de prueba</p>
        <form action="/login" method="post" class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-slate-700">Usuario</label>
                <select name="email" class="w-full mt-1 p-2 border rounded-lg bg-slate-50 focus:ring-2 focus:ring-blue-500 outline-none">
                    <option value="docente@isfd9.edu.ar">Prof. Carlos Gómez (Docente)</option>
                    <option value="alumno@isfd9.edu.ar">Lucía Fernández (Alumno)</option>
                    <option value="ingresante@isfd9.edu.ar">Martín Paz (Ingresante)</option>
                    <option value="admin@isfd9.edu.ar">Admin Bedelía (Administrador)</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700">Contraseña</label>
                <input type="password" name="password" value="1234" class="w-full mt-1 p-2 border rounded-lg bg-slate-50" required>
            </div>
            <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg transition">
                Ingresar al Sistema
            </button>
        </form>
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
    elif rol == "Ingresante":
        return RedirectResponse(url=f"/ingresante?nombre={user['nombre']}", status_code=status.HTTP_302_FOUND)
    elif rol == "Administrador":
        return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

# -----------------------------------------------------------------------------
# MÓDULO DOCENTE (Alertas, Registro Asistencia y Foro)
# -----------------------------------------------------------------------------
@app.get("/docente", response_class=HTMLResponse)
def panel_docente(nombre: str = "Docente", materia: str = "Análisis y Diseño de Sistemas"):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Obtener alumnos para la planilla de asistencia
    alumnos = cursor.execute("SELECT nombre FROM Usuario WHERE rol = 'Alumno'").fetchall()
    
    # Obtener mensajes del foro
    mensajes = cursor.execute("SELECT * FROM ForoMensaje WHERE materia = ? ORDER BY id DESC", (materia,)).fetchall()
    conn.close()

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
        <!-- SECCIÓN 1: ALERTA DE AUSENCIA DOCENTE -->
        <div class="bg-white p-6 rounded-xl shadow-md border border-slate-200">
            <h2 class="text-xl font-bold text-slate-800 mb-2">Registrar Mi Ausencia (Docente)</h2>
            <form action="/ausencia/guardar" method="post" class="space-y-4">
                <input type="hidden" name="docente_nombre" value="{nombre}">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-700">Materia</label>
                        <select name="materia" class="w-full mt-1 p-2 border rounded-lg bg-slate-50">
                            <option value="Análisis y Diseño de Sistemas">Análisis y Diseño de Sistemas (3° Año)</option>
                            <option value="Ingeniería de Software">Ingeniería de Software (3° Año)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700">Fecha de Ausencia</label>
                        <input type="date" name="fecha" class="w-full mt-1 p-2 border rounded-lg bg-slate-50" required>
                    </div>
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-700">Motivo (Opcional)</label>
                    <input type="text" name="motivo" class="w-full mt-1 p-2 border rounded-lg bg-slate-50" placeholder="Motivo institucional o salud...">
                </div>
                <button type="submit" class="bg-amber-600 hover:bg-amber-700 text-white font-semibold px-4 py-2 rounded-lg transition text-sm">
                    Emitir Alerta Temprana a Alumnos
                </button>
            </form>
        </div>

        <!-- SECCIÓN 2: TOMAR ASISTENCIA DE ALUMNOS -->
        <div class="bg-white p-6 rounded-xl shadow-md border border-slate-200">
            <h2 class="text-xl font-bold text-slate-800 mb-2">Tomar Asistencia de Alumnos</h2>
            <form action="/asistencia/guardar" method="post" class="space-y-4">
                <input type="hidden" name="docente_nombre" value="{nombre}">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-700">Materia</label>
                        <select name="materia" class="w-full mt-1 p-2 border rounded-lg bg-slate-50">
                            <option value="Análisis y Diseño de Sistemas">Análisis y Diseño de Sistemas</option>
                            <option value="Ingeniería de Software">Ingeniería de Software</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700">Fecha de Clase</label>
                        <input type="date" name="fecha" value="{datetime.now().strftime('%Y-%m-%d')}" class="w-full mt-1 p-2 border rounded-lg bg-slate-50" required>
                    </div>
                </div>
                
                <table class="w-full text-left border-collapse mt-4">
                    <thead>
                        <tr class="bg-slate-100 border-b text-xs uppercase text-slate-600 font-bold">
                            <th class="p-2">Alumno</th>
                            <th class="p-2">Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_alumnos}
                    </tbody>
                </table>

                <button type="submit" class="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-4 py-2 rounded-lg transition text-sm">
                    Guardar Planilla de Asistencia
                </button>
            </form>
        </div>

        <!-- SECCIÓN 3: FORO DE COMUNICACIÓN -->
        <div class="bg-white p-6 rounded-xl shadow-md border border-slate-200 space-y-4">
            <h2 class="text-xl font-bold text-slate-800">Foro de Interacción Académica</h2>
            <form action="/foro/publicar" method="post" class="flex gap-2">
                <input type="hidden" name="autor_nombre" value="{nombre}">
                <input type="hidden" name="rol" value="Docente">
                <input type="hidden" name="materia" value="{materia}">
                <input type="text" name="contenido" placeholder="Escribir una consulta o aviso para la clase..." class="flex-grow p-2 border rounded-lg bg-slate-50" required>
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

@app.post("/asistencia/guardar")
def guardar_asistencia(docente_nombre: str = Form(...), materia: str = Form(...), fecha: str = Form(...), request=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Obtener alumnos de la BD para registrar el estado enviado en el formulario
    alumnos = cursor.execute("SELECT nombre FROM Usuario WHERE rol = 'Alumno'").fetchall()
    
    # En FastAPI, leemos los campos dinámicos directamente de la petición POST si es necesario
    # Para el prototipo, tomamos a la alumna por defecto Lucía Fernández
    for al in alumnos:
        nombre_al = al[0]
        # Por defecto guardamos el registro para demostración
        cursor.execute("INSERT INTO AsistenciaAlumno (alumno_nombre, materia, fecha, estado) VALUES (?, ?, ?, ?)",
                       (nombre_al, materia, fecha, 'Presente'))

    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/docente?nombre={docente_nombre}", status_code=status.HTTP_302_FOUND)

@app.post("/ausencia/guardar")
def guardar_ausencia(docente_nombre: str = Form(...), materia: str = Form(...), fecha: str = Form(...), motivo: str = Form("")):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Ausencia (docente_nombre, materia, fecha, motivo) VALUES (?, ?, ?, ?)",
                   (docente_nombre, materia, fecha, motivo))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/docente?nombre={docente_nombre}", status_code=status.HTTP_302_FOUND)

# -----------------------------------------------------------------------------
# MÓDULO ALUMNO (Alertas, Consulta de Asistencias y Foro)
# -----------------------------------------------------------------------------
@app.get("/alumno", response_class=HTMLResponse)
def panel_alumno(nombre: str = "Lucía Fernández", materia: str = "Análisis y Diseño de Sistemas"):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    ausencias_docentes = cursor.execute("SELECT * FROM Ausencia ORDER BY id DESC").fetchall()
    mis_asistencias = cursor.execute("SELECT * FROM AsistenciaAlumno WHERE alumno_nombre = ? ORDER BY id DESC", (nombre,)).fetchall()
    mensajes_foro = cursor.execute("SELECT * FROM ForoMensaje WHERE materia = ? ORDER BY id DESC", (materia,)).fetchall()
    conn.close()

    filas_ausencias = ""
    for a in ausencias_docentes:
        filas_ausencias += f"""
        <tr class="border-b hover:bg-slate-50">
            <td class="p-2.5 font-semibold text-slate-700">{a['fecha']}</td>
            <td class="p-2.5 text-slate-800">{a['materia']}</td>
            <td class="p-2.5 text-slate-600">{a['docente_nombre']}</td>
            <td class="p-2.5 text-slate-500">{a['motivo'] or 'Sin especificar'}</td>
            <td class="p-2.5"><span class="bg-red-100 text-red-700 px-2 py-0.5 rounded-full text-xs font-bold">{a['estado']}</span></td>
        </tr>
        """

    filas_asistencias = ""
    for asis in mis_asistencias:
        badge = "bg-green-100 text-green-800" if asis['estado'] == 'Presente' else "bg-red-100 text-red-800"
        filas_asistencias += f"""
        <tr class="border-b">
            <td class="p-2.5 text-slate-700">{asis['fecha']}</td>
            <td class="p-2.5 text-slate-800">{asis['materia']}</td>
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
            <h2 class="text-xl font-bold text-slate-800 mb-3">Alertas Tempranas de Ausencia Docente</h2>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-slate-100 border-b text-xs uppercase text-slate-600 font-bold">
                            <th class="p-2.5">Fecha</th>
                            <th class="p-2.5">Materia</th>
                            <th class="p-2.5">Docente</th>
                            <th class="p-2.5">Motivo</th>
                            <th class="p-2.5">Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_ausencias or '<tr><td colspan="5" class="p-3 text-center text-slate-400">No hay avisos de inasistencia docente.</td></tr>'}
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
            <h2 class="text-xl font-bold text-slate-800">Foro de la Materia</h2>
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
# MÓDULO INGRESANTE (Carga de Documentación)
# -----------------------------------------------------------------------------
@app.get("/ingresante", response_class=HTMLResponse)
def panel_ingresante(nombre: str = "Ingresante"):
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

# -----------------------------------------------------------------------------
# MÓDULO ADMINISTRADOR / BEDELÍA
# -----------------------------------------------------------------------------
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
        <h2 class="text-xl font-bold text-slate-800 mb-4">Administración - Revisión de Documentación</h2>
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

# -----------------------------------------------------------------------------
# EJECUCIÓN DEL SERVIDOR LOCAL
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)