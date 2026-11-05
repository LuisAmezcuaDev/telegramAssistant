import os.path
import unicodedata
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks'
]

def get_tasks_service():
    """Autentica y devuelve el servicio oficial de Google Tasks."""
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

    return build('tasks', 'v1', credentials=creds)

def _norm(s: str) -> str:
    s = unicodedata.normalize('NFD', s.lower())
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')

def obtener_tareas_pendientes() -> str:
    """
    Consulta la lista principal de pendientes (Google Tasks) que no tienen horario asignado.
    """
    print(f"\n🛠️ [TOOL CALLED] Consultando Google Tasks (Pendientes sin hora)...")
    try:
        service = get_tasks_service()
        # '@default' representa la lista de tareas principal del usuario
        results = service.tasks().list(tasklist='@default', showCompleted=False).execute()
        items = results.get('items', [])

        if not items:
            return "No tienes pendientes sueltos en tu lista de Google Tasks. ¡Estás al día!"

        resultado = ["Tus pendientes actuales en Google Tasks:"]
        for task in items:
            titulo = task.get('title', 'Sin título')
            task_id = task.get('id')
            resultado.append(f"- [ID: {task_id}] {titulo}")
        return "\n".join(resultado)
    except Exception as e:
        print(f"❌ [ERROR en Google Tasks]: {str(e)}")
        return f"Error al consultar las tareas pendientes: {str(e)}"

def crear_tarea_pendiente(titulo: str, notas: str = "") -> str:
    """
    Crea un nuevo pendiente rápido en Google Tasks (sin hora fija ni impacto en el calendario).

    Args:
        titulo: Descripción corta de la tarea o pendiente.
        notas: (Opcional) Detalles adicionales o contexto de la tarea.
    """
    print(f"\n🛠️ [TOOL CALLED] Creando tarea en Google Tasks: '{titulo}'")
    try:
        service = get_tasks_service()
        task = {
            'title': titulo,
            'notes': notas
        }
        result = service.tasks().insert(tasklist='@default', body=task).execute()
        print(f"✅ [ÉXITO] Tarea creada en Google Tasks.")
        return f"Éxito: El pendiente '{titulo}' ha sido agregado correctamente a tu lista de Google Tasks."
    except Exception as e:
        print(f"❌ [ERROR al crear Tarea]: {str(e)}")
        return f"Error al crear el pendiente en Google Tasks: {str(e)}"

def completar_tarea_por_criterio(criterio: str) -> str:
    """
    Busca un pendiente en Google Tasks por palabras clave, lo marca como completado
    y lo oculta de la lista activa.

    Args:
        criterio: Palabras clave del título de la tarea a completar, ej. 'comprar café'.
    """
    print(f"\n🛠️ [TOOL CALLED] Completar Tarea | criterio='{criterio}'")
    try:
        service = get_tasks_service()
        results = service.tasks().list(tasklist='@default', showCompleted=False).execute()
        items = results.get('items', [])

        if not items:
            return "No hay tareas pendientes en la lista para completar."

        tokens = [t for t in _norm(criterio).split() if len(t) > 2]
        candidatos = [t for t in items if any(token in _norm(t.get('title', '')) for token in tokens)]

        if not candidatos:
            lista_actual = "\n".join(f"- {t.get('title')}" for t in items)
            return f"No encontré ningún pendiente que coincida con '{criterio}'. Tus pendientes actuales:\n{lista_actual}"
        
        if len(candidatos) > 1:
            nombres = "\n".join(f"- {t.get('title')}" for t in candidatos)
            return f"Encontré varias coincidencias para completar:\n{nombres}\nSé más específico con el nombre."

        task = candidatos[0]
        task_id = task['id']
        titulo = task.get('title', 'Sin título')

        # CORRECCIÓN: Usamos task=task_id en lugar de taskId
        service.tasks().patch(
            tasklist='@default', 
            task=task_id, 
            body={'status': 'completed'}
        ).execute()

        print(f"✅ [ÉXITO] Tarea '{titulo}' completada.")
        return f"Éxito: El pendiente '{titulo}' ha sido marcado como completado en Google Tasks."
    except Exception as e:
        print(f"❌ [ERROR al completar Tarea]: {str(e)}")
        return f"Error al completar la tarea: {e}"