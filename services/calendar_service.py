import os.path
import unicodedata
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks'
]
TIMEZONE = 'America/Mexico_City'
TZ = ZoneInfo(TIMEZONE)

def get_calendar_service():
    """Autentica y devuelve el servicio oficial de Google Calendar."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

def _norm(s: str) -> str:
    s = unicodedata.normalize('NFD', s.lower())
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')

def _to_rfc3339(s: str) -> str:
    dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.isoformat()

def _limites_del_dia(fecha: str):
    ini = datetime.fromisoformat(fecha).replace(tzinfo=TZ, hour=0, minute=0, second=0)
    return ini.isoformat(), (ini + timedelta(days=1)).isoformat()

def _hhmm(ev: dict) -> str:
    s = ev['start'].get('dateTime')
    return datetime.fromisoformat(s).astimezone(TZ).strftime('%H:%M') if s else ''

def _buscar_traslapes(service, start_dt: datetime, end_dt: datetime, exclude_event_id: str = None) -> list:
    t_min, t_max = _limites_del_dia(start_dt.strftime('%Y-%m-%d'))
    events = service.events().list(
        calendarId='primary', timeMin=t_min, timeMax=t_max,
        singleEvents=True, orderBy='startTime'
    ).execute().get('items', [])
    
    conflictos = []
    for ev in events:
        if exclude_event_id and ev['id'] == exclude_event_id:
            continue
        if 'dateTime' not in ev['start'] or 'dateTime' not in ev['end']:
            continue
            
        ev_start = datetime.fromisoformat(ev['start']['dateTime'].replace('Z', '+00:00'))
        ev_end = datetime.fromisoformat(ev['end']['dateTime'].replace('Z', '+00:00'))
        
        if ev_start < end_dt and ev_end > start_dt:
            conflictos.append(ev)
            
    return conflictos

def consultar_agenda_rango(start_time: str, end_time: str) -> str:
    """
    Consulta los eventos de Google Calendar en un rango de fecha y hora.

    Args:
        start_time: Inicio del rango en ISO local, ej. '2026-11-03T00:00:00'.
        end_time: Fin del rango en ISO local, ej. '2026-11-03T23:59:59'.
    """
    print(f"\n🛠️ [TOOL CALLED] Consultando Google Calendar del {start_time} al {end_time}...")
    try:
        service = get_calendar_service()
        events_result = service.events().list(
            calendarId='primary',
            timeMin=_to_rfc3339(start_time),
            timeMax=_to_rfc3339(end_time),
            singleEvents=True,
            orderBy='startTime',
            maxResults=50
        ).execute()
        events = events_result.get('items', [])
        
        if not events:
            return "No hay eventos programados en este rango de tiempo. El espacio está completamente libre."
        
        resultado = []
        for event in events:
            summary = event.get('summary', 'Sin título')
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            resultado.append(f"- Ocupado: {summary} (De {start} a {end})")
        return "\n".join(resultado)
    except Exception as e:
        print(f"❌ [ERROR en Consulta]: {str(e)}")
        return f"Error al consultar el calendario: {str(e)}"

def crear_evento_calendario(summary: str, start_time: str, end_time: str, recurrence_rule: str = None) -> str:
    """
    Crea y agenda un nuevo evento o bloque de tiempo en Google Calendar, validando traslapes y soportando recurrencia.
    
    Args:
        summary: Título descriptivo del evento o bloque.
        start_time: Fecha y hora de inicio local en formato ISO (ej. '2026-11-03T18:00:00').
        end_time: Fecha y hora de fin local en formato ISO (ej. '2026-11-03T20:00:00').
        recurrence_rule: (Opcional) Regla de recurrencia RRULE (ej. 'RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR').
    """
    print(f"\n🛠️ [TOOL CALLED] Creando evento en Google Calendar: '{summary}' ({start_time} a {end_time}) [Recurrencia: {recurrence_rule}]")
    try:
        service = get_calendar_service()
        dt_inicio = datetime.fromisoformat(start_time.replace('Z', ''))
        if dt_inicio.tzinfo is None:
            dt_inicio = dt_inicio.replace(tzinfo=TZ)
        dt_fin = datetime.fromisoformat(end_time.replace('Z', ''))
        if dt_fin.tzinfo is None:
            dt_fin = dt_fin.replace(tzinfo=TZ)
            
        conflictos = _buscar_traslapes(service, dt_inicio, dt_fin)
        if conflictos:
            nombres_conflictos = ", ".join([f"'{c.get('summary')}' ({_hhmm(c)})" for c in conflictos])
            return f"⚠️ Conflicto de horario: No se puede crear '{summary}' porque se encima con: {nombres_conflictos}. Elige otro horario."

        event = {
            'summary': summary,
            'description': 'Bloque de agenda gestionado de forma autónoma por el asistente personal.',
            'start': {'dateTime': start_time, 'timeZone': TIMEZONE},
            'end': {'dateTime': end_time, 'timeZone': TIMEZONE},
        }

        if recurrence_rule:
            if isinstance(recurrence_rule, str):
                event['recurrence'] = [recurrence_rule if recurrence_rule.startswith("RRULE:") else f"RRULE:{recurrence_rule}"]
            elif isinstance(recurrence_rule, list):
                event['recurrence'] = recurrence_rule

        service.events().insert(calendarId='primary', body=event).execute()
        print(f"✅ [ÉXITO] Evento creado físicamente con éxito.")
        return f"Éxito: El evento '{summary}' ha sido agendado correctamente en Google Calendar de {start_time} a {end_time}."
    except Exception as e:
        print(f"❌ [ERROR en Creación]: {str(e)}")
        return f"Error al crear el evento en el calendario: {str(e)}"

def reagendar_evento_por_criterio(fecha: str, criterio: str, nueva_hora_inicio: str, hora_original: str = "") -> str:
    """
    Busca un evento del día por palabras clave y lo mueve a una nueva hora manteniendo su duración,
    validando que no exista un traslape con otros eventos.

    Args:
        fecha: Fecha del evento en ISO, ej. '2026-11-03'.
        criterio: Palabras clave del nombre, ej. 'película'.
        nueva_hora_inicio: Nueva hora de inicio en ISO local, ej. '2026-11-03T19:00:00'.
        hora_original: (Opcional) Hora actual del evento en 'HH:MM' 24h, ej. '18:00'.
    """
    print(f"\n🛠️ [TOOL CALLED] Reagendar | fecha={fecha} criterio='{criterio}' hora_original='{hora_original}' nuevo={nueva_hora_inicio}")
    try:
        service = get_calendar_service()
        t_min, t_max = _limites_del_dia(fecha)
        events = service.events().list(
            calendarId='primary', timeMin=t_min, timeMax=t_max,
            singleEvents=True, orderBy='startTime'
        ).execute().get('items', [])

        if not events:
            return f"No hay eventos en {fecha}."

        agenda_del_dia = "\n".join(f"- {e.get('summary','Sin título')} ({_hhmm(e)})" for e in events)

        tokens = [t for t in _norm(criterio).split() if len(t) > 2]
        candidatos = [e for e in events if any(t in _norm(e.get('summary', '')) for t in tokens)]

        if hora_original:
            por_hora = [e for e in (candidatos or events) if _hhmm(e) == hora_original]
            if por_hora:
                candidatos = por_hora

        if not candidatos:
            return (f"No encontré coincidencia con '{criterio}'. Eventos de {fecha}:\n"
                    f"{agenda_del_dia}\nElige el correcto y vuelve a llamar la herramienta.")
        if len(candidatos) > 1:
            return (f"Hay varias coincidencias:\n" +
                    "\n".join(f"- {e.get('summary')} ({_hhmm(e)})" for e in candidatos) +
                    "\nVuelve a llamar la herramienta con hora_original para desambiguar.")

        ev = candidatos[0]
        if 'dateTime' not in ev['start']:
            return "Ese evento es de día completo; no se puede mover a una hora."

        ini = datetime.fromisoformat(ev['start']['dateTime'])
        fin = datetime.fromisoformat(ev['end']['dateTime'])
        nuevo_ini = datetime.fromisoformat(nueva_hora_inicio.replace('Z', ''))
        if nuevo_ini.tzinfo is None:
            nuevo_ini = nuevo_ini.replace(tzinfo=TZ)
        nuevo_fin = nuevo_ini + (fin - ini)

        conflictos = _buscar_traslapes(service, nuevo_ini, nuevo_fin, exclude_event_id=ev['id'])
        if conflictos:
            nombres_conflictos = ", ".join([f"'{c.get('summary')}' ({_hhmm(c)})" for c in conflictos])
            return f"⚠️ Conflicto de horario: No se puede mover '{ev.get('summary')}' a ese horario porque se encima con: {nombres_conflictos}. Elige otra hora."

        service.events().patch(
            calendarId='primary', eventId=ev['id'],
            body={'start': {'dateTime': nuevo_ini.isoformat(), 'timeZone': TIMEZONE},
                  'end':   {'dateTime': nuevo_fin.isoformat(), 'timeZone': TIMEZONE}}
        ).execute()

        return (f"Éxito: '{ev.get('summary')}' movido de {_hhmm(ev)} a "
                f"{nuevo_ini.strftime('%H:%M')}–{nuevo_fin.strftime('%H:%M')}.")
    except Exception as e:
        print(f"❌ [ERROR en Reagendamiento]: {str(e)}")
        return f"Error al reagendar: {e}"

def eliminar_evento_por_criterio(fecha: str, criterio: str, hora_original: str = "") -> str:
    """
    Busca un evento del día por palabras clave (y opcionalmente su hora original)
    y lo elimina permanentemente del calendario de Google.
    Úsala SIEMPRE que el usuario pida cancelar o borrar un evento existente.

    Args:
        fecha: Fecha del evento en ISO, ej. '2026-11-03'.
        criterio: Palabras clave del nombre del evento a eliminar, ej. 'película'.
        hora_original: (Opcional) Hora actual del evento en 'HH:MM' 24h, ej. '23:15'.
    """
    print(f"\n🛠️ [TOOL CALLED] Eliminar Evento | fecha={fecha} criterio='{criterio}' hora_original='{hora_original}'")
    try:
        service = get_calendar_service()
        t_min, t_max = _limites_del_dia(fecha)
        events = service.events().list(
            calendarId='primary', timeMin=t_min, timeMax=t_max,
            singleEvents=True, orderBy='startTime'
        ).execute().get('items', [])

        if not events:
            return f"No hay eventos en {fecha} para eliminar."

        agenda_del_dia = "\n".join(f"- {e.get('summary','Sin título')} ({_hhmm(e)})" for e in events)

        tokens = [t for t in _norm(criterio).split() if len(t) > 2]
        candidatos = [e for e in events if any(t in _norm(e.get('summary', '')) for t in tokens)]

        if hora_original:
            por_hora = [e for e in (candidatos or events) if _hhmm(e) == hora_original]
            if por_hora:
                candidatos = por_hora

        if not candidatos:
            return (f"No encontré ningún evento que coincida con '{criterio}' para eliminar. Eventos de {fecha}:\n"
                    f"{agenda_del_dia}")
        if len(candidatos) > 1:
            return (f"Encontré varias coincidencias para eliminar:\n" +
                    "\n".join(f"- {e.get('summary')} ({_hhmm(e)})" for e in candidatos) +
                    "\nEspecifica la hora_original para saber cuál borrar exactamente.")

        ev = candidatos[0]
        titulo = ev.get('summary', 'Sin título')
        hora_ev = _hhmm(ev)

        service.events().delete(calendarId='primary', eventId=ev['id']).execute()
        print(f"✅ [ÉXITO] Evento '{titulo}' eliminado.")
        return f"Éxito: El evento '{titulo}' ({hora_ev}) ha sido cancelado y eliminado de Google Calendar."
    except Exception as e:
        print(f"❌ [ERROR al Eliminar]: {str(e)}")
        return f"Error al eliminar el evento: {e}"

from datetime import datetime, timedelta

def rellenar_tiempos_libres(fecha: str) -> str:
    """
    Analiza el calendario para una fecha específica (formato 'YYYY-MM-DD'), 
    detecta los huecos vacíos entre las 08:00 AM y las 11:00 PM (hora de dormir), 
    y crea automáticamente bloques físicos de 'Tiempo Libre' en esos espacios.
    
    Args:
        fecha: Fecha en formato ISO, ej. '2026-11-05'.
    """
    print(f"\n🛠️ [TOOL CALLED] Rellenando tiempos libres para el día: {fecha}")
    try:
        service = get_calendar_service()
        
        # Definir los límites del día activo (ej. de 08:00 a 23:00)
        t_min = f"{fecha}T08:00:00"
        t_max = f"{fecha}T23:00:00"
        
        dt_inicio_dia = datetime.fromisoformat(t_min).replace(tzinfo=TZ)
        dt_fin_dia = datetime.fromisoformat(t_max).replace(tzinfo=TZ)
        
        # Listar eventos del día ordenados por hora de inicio
        events_result = service.events().list(
            calendarId='primary', 
            timeMin=dt_inicio_dia.isoformat(), 
            timeMax=dt_fin_dia.isoformat(),
            singleEvents=True, 
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Filtrar solo eventos con dateTime válido
        eventos_validos = []
        for e in events:
            if 'dateTime' in e['start'] and 'dateTime' in e['end']:
                start_dt = datetime.fromisoformat(e['start']['dateTime'])
                end_dt = datetime.fromisoformat(e['end']['dateTime'])
                eventos_validos.append({'summary': e.get('summary', ''), 'start': start_dt, 'end': end_dt})
        
        # Ordenar por hora de inicio
        eventos_validos.sort(key=lambda x: x['start'])
        
        huecos_creados = 0
        tiempo_actual = dt_inicio_dia
        
        for ev in eventos_validos:
            # Evitar solapamientos si el evento empieza antes del puntero actual
            if ev['start'] > tiempo_actual:
                duracion_hueco = (ev['start'] - tiempo_actual).total_seconds() / 60
                # Solo crear bloque si el hueco libre es de al menos 10 minutos
                if duracion_hueco >= 10:
                    _crear_bloque_libre(service, tiempo_actual, ev['start'])
                    huecos_creados += 1
            if ev['end'] > tiempo_actual:
                tiempo_actual = ev['end']
        
        # Verificar si queda espacio entre el último evento y el fin del día (23:00)
        if tiempo_actual < dt_fin_dia:
            duracion_hueco = (dt_fin_dia - tiempo_actual).total_seconds() / 60
            if duracion_hueco >= 10:
                _crear_bloque_libre(service, tiempo_actual, dt_fin_dia)
                huecos_creados += 1
                
        return f"Éxito: Se han rellenado y creado {huecos_creados} bloques de 'Tiempo Libre' en los huecos del día {fecha}."
    except Exception as e:
        print(f"❌ [ERROR al rellenar tiempos libres]: {str(e)}")
        return f"Error al rellenar los tiempos libres: {str(e)}"

def _crear_bloque_libre(service, start_dt, end_dt):
    event = {
        'summary': 'Tiempo Libre',
        'description': 'Bloque de tiempo libre gestionado automáticamente por el backend.',
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': TIMEZONE},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': TIMEZONE},
    }
    service.events().insert(calendarId='primary', body=event).execute()
    print(f"➕ [BACKEND] Creado bloque 'Tiempo Libre' de {start_dt.strftime('%H:%M')} a {end_dt.strftime('%H:%M')}")