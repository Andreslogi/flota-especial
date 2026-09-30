# Control de Flota — backend real (FastAPI + PostgreSQL)

App para administrar una flota de buses de servicios especiales (rutas
escolares + viajes de turismo): vehículos, contratos, pagos de contratos,
viajes, ingresos, gastos, mantenimiento y un dashboard financiero con
sugerencias automáticas.

A diferencia de la versión inicial (que corría dentro de Claude), esta es
una aplicación web independiente: un backend en **Python (FastAPI)** con
base de datos **PostgreSQL**, y un frontend en HTML/CSS/JS que le habla por
API REST. Se puede desplegar en **Render** y quedar con un link propio,
usable desde cualquier navegador, por varios usuarios.

## Estructura del proyecto

```
flota-app/
  app/
    main.py           # arma la app FastAPI y monta el frontend
    database.py        # conexión a Postgres (o SQLite en local)
    models.py           # tablas (SQLAlchemy)
    schemas.py           # formas de los datos que entran por la API
    security.py           # hash de contraseñas y JWT
    deps.py                 # autenticación de cada request
    seed.py                   # crea el primer usuario admin
    routers/
      auth.py, users.py, vehicles.py, contracts.py, trips.py,
      income.py, expenses.py, maintenance.py
  static/
    index.html          # todo el frontend (un solo archivo)
  requirements.txt
  render.yaml            # despliegue con un clic en Render
  .env.example
```

## Gastos, comisión del conductor, programación y permisos (última actualización)

**Gastos estandarizados:** la categoría de cada gasto ahora es una lista
desplegable fija, para que todos capturen igual: `ACPM`, `Requintada de
muelles`, `Lavada`, `Engrasada`, `Peajes`, `Administración`,
`Quincena conductor`. Se define en `static/index.html` (constante
`EXPENSE_CATEGORIES`) — si necesitas agregar o renombrar una categoría, es
el único lugar que hay que tocar.

**Comisión del conductor (7%):** cada vehículo ahora tiene un
**propietario** y un **conductor asignado** (módulo Vehículos). Cada
**viaje de turismo** calcula automáticamente el 7% de su valor cobrado
como comisión del conductor (columna "Comisión conductor" en Viajes, y
campo `driver_commission` guardado en la base de datos — así el histórico
no cambia aunque el porcentaje cambie a futuro). La tasa está en
`app/routers/trips.py` (`DRIVER_COMMISSION_RATE = 0.07`) y en
`static/index.html` (`DRIVER_COMMISSION_RATE`) — cambia ambos si el
porcentaje cambia.

La nueva vista **Comisiones** muestra, por vehículo/conductor, cuánto se
debe liquidar: puedes filtrar por Quincena 1 (día 1–15), Quincena 2 (día
16–fin) o el mes completo. Es informativa — cuando efectivamente le pagues
al conductor, regístralo en **Gastos** con la categoría "Quincena
conductor" para que quede en el balance del mes.

**Programación de viajes:** la vista **Programación** lista todos los
viajes (pasados y futuros, sin importar el mes seleccionado arriba),
ordenados por fecha, con un filtro por vehículo y una insignia de "en
cuántos días es" — así ves qué tan llena está la agenda de cada carro,
incluso con viajes programados con meses de anticipación.

**Permisos (Administrador vs. Usuario):** cada persona que entra a la app
tiene un rol:
- **Administrador**: puede crear, editar y eliminar cualquier registro
  (vehículos, contratos, viajes, ingresos, gastos, mantenimiento, y
  gestionar otros usuarios).
- **Usuario**: solo puede **ver** la información — el backend rechaza
  (403) cualquier intento de crear/editar/borrar desde ese rol, y el
  frontend directamente oculta esos botones para no confundir.

Esto es clave porque no todos los vehículos son tuyos: puedes crear una
cuenta de solo lectura para otro propietario o para un conductor, sin que
puedan alterar los datos de nadie más, y reservar el rol de administrador
para quien lleva las cuentas.

## Cómo funciona la lógica de contratos y pagos

- Cada **contrato** tiene un valor mensual.
- En el módulo de Contratos, para el mes seleccionado, cada fila tiene un
  botón **"Marcar pagado"**.
- Al confirmarlo (fecha, monto, método), el backend crea automáticamente
  un registro en **Ingresos** vinculado a ese contrato y guarda el estado
  "pagado" para ese mes exacto (tabla `contract_payments`, con la
  restricción de que solo puede haber un pago por contrato y mes).
- Si te equivocas, "deshacer pago" borra ambos registros.
- El dashboard (ingresos vs. gastos, gráfico de categorías, sugerencias)
  se calcula en el navegador a partir de los datos que trae la API — no
  hay que tocar nada ahí cuando agregas contratos o pagos nuevos.

## Correr el proyecto en tu computador

Requisitos: Python 3.11+ (funciona igual con 3.10/3.12).

```bash
cd flota-app
python3 -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# abre .env y cambia al menos ADMIN_PASSWORD y SECRET_KEY

# si no tienes Postgres a mano, puedes dejar DATABASE_URL sin definir:
# la app usará un archivo SQLite local (flota.db) para que pruebes ya mismo.

uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000` — ahí verás la pantalla de login. Entra con
el correo y contraseña que pusiste en `ADMIN_EMAIL` / `ADMIN_PASSWORD`
(por defecto `admin@tuempresa.com` / `cambia-esta-clave`, definidos en
`seed.py`; ese usuario se crea automáticamente la primera vez que arranca
la app, si la tabla de usuarios está vacía).

### Si quieres usar PostgreSQL en local

Crea una base y apunta `DATABASE_URL` a ella, por ejemplo:

```
DATABASE_URL=postgresql://postgres:tu_clave@localhost:5432/flota
```

## Desplegar en Render (con link público)

**Opción rápida — Blueprint (usa `render.yaml`):**

1. Sube esta carpeta a un repositorio de GitHub.
2. En Render: **New → Blueprint**, conecta el repositorio.
3. Render lee `render.yaml` y crea automáticamente:
   - una base de datos Postgres (`flota-db`),
   - el servicio web (`flota-backend`), con `DATABASE_URL` ya conectada
     y `SECRET_KEY` / `ADMIN_PASSWORD` generados de forma segura.
4. Antes de darle "Apply", revisa las variables de entorno del servicio y
   cambia `ADMIN_EMAIL` por el correo con el que vas a entrar.
5. Cuando termine el despliegue, Render te da un link tipo
   `https://flota-backend.onrender.com` — ese es el link de tu app.
6. Entra a **Environment** del servicio y copia el valor generado de
   `ADMIN_PASSWORD` para tu primer login (o ponle uno tú mismo antes del
   primer arranque).

**Opción manual (sin Blueprint):**

1. Crea una base de datos Postgres en Render (New → PostgreSQL) y copia su
   "Internal Database URL".
2. Crea un Web Service (New → Web Service) apuntando a tu repo:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. En Environment del servicio, agrega:
   - `DATABASE_URL` = la URL de la base que creaste
   - `SECRET_KEY` = un texto largo y aleatorio
   - `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME`
4. Deploy. El link que te da Render (`https://tu-servicio.onrender.com`)
   ya sirve la app completa (frontend + API) — ese es el link que
   compartes con tus usuarios.

> El plan gratuito de Render "duerme" el servicio tras un rato sin uso: la
> primera carga después de estar dormido puede tardar unos 30-50 segundos
> en responder. Para uso real de la empresa, conviene pasar al plan
> pagado más económico para que no duerma.

## Usuarios

- El primer usuario (administrador) se crea solo, desde las variables de
  entorno `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
- Desde la app, con ese usuario admin, entra a **Usuarios** (aparece solo
  para administradores) y crea accesos para tu equipo (conductor
  encargado, contador, etc.), con rol *Staff* o *Admin*.
- Cada usuario inicia sesión con su propio correo y contraseña; la sesión
  dura 24 horas (configurable con `ACCESS_TOKEN_EXPIRE_MINUTES`).

## Notas técnicas / próximos pasos razonables

- Las tablas se crean automáticamente al arrancar (`Base.metadata.create_all`).
  Para un proyecto que va a evolucionar con el tiempo, lo recomendable es
  migrar a **Alembic** para versionar cambios de esquema sin perder datos.
- Las contraseñas se guardan con hash `bcrypt` (nunca en texto plano).
- La autenticación usa JWT (token en el header `Authorization: Bearer`).
- CORS está abierto (`*`) para simplificar; si more adelante separas el
  frontend en otro dominio, conviene restringirlo al dominio real.
- No hay backups automáticos configurados: en Render, activa los backups
  de la base de datos Postgres desde su panel (el plan free no los
  incluye — considera el plan pagado si estos datos son el sistema de
  contabilidad real del negocio).
