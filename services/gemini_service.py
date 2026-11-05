import time
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL, SYSTEM_PROMPT
from services.calendar_service import (
    consultar_agenda_rango, 
    crear_evento_calendario, 
    reagendar_evento_por_criterio, 
    eliminar_evento_por_criterio,
    rellenar_tiempos_libres
)
from services.tasks_service import (
    obtener_tareas_pendientes,
    crear_tarea_pendiente,
    completar_tarea_por_criterio
)

client = genai.Client(api_key=GEMINI_API_KEY)

TZ = ZoneInfo("America/Mexico_City")
_sesiones = {}

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

def _get_chat(chat_id: int):
    if chat_id not in _sesiones:
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT + """

REGLAS DE HERRAMIENTAS Y DISTINCIÓN (CALENDAR vs TASKS):
- **Google Calendar:** Úsalo exclusivamente para bloques de tiempo estrictos, eventos con horario fijo, comidas, tareas express con ocupación horaria o imprevistos de la agenda.
- **Google Tasks:** Úsalo exclusivamente para pendientes sueltos, recados o tareas rápidas **que no tienen una hora asignada** en el calendario. 
  - Para listar pendientes sin hora, usa `obtener_tareas_pendientes`.
  - Para crear un recado rápido sin horario, usa `crear_tarea_pendiente`.
  - Para marcar un pendiente como hecho, usa `completar_tarea_por_criterio`.
- Para mover/cambiar de hora un evento existente, llama a `reagendar_evento_por_criterio`.
- Para cancelar o borrar un evento del calendario, llama obligatoriamente a `eliminar_evento_por_criterio`. NUNCA dejes parámetros vacíos.
- Nunca te quedes en bucles de llamadas repetidas: si una herramienta falla, informa al usuario con claridad.
""",
            temperature=0.1,
            tools=[
                consultar_agenda_rango, 
                crear_evento_calendario, 
                reagendar_evento_por_criterio, 
                eliminar_evento_por_criterio,
                obtener_tareas_pendientes,
                crear_tarea_pendiente,
                completar_tarea_por_criterio,
                rellenar_tiempos_libres
            ],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=False, maximum_remote_calls=5
            ),
        )
        _sesiones[chat_id] = client.chats.create(model=GEMINI_MODEL, config=config)
    return _sesiones[chat_id]

def generar_respuesta_asistente(prompt_usuario: str, chat_id: int = 12345) -> str:
    max_intentos = 3
    espera_inicial = 2

    ahora = datetime.now(TZ)
    mensaje = (f"[Ahora: {DIAS[ahora.weekday()]} {ahora:%Y-%m-%d %H:%M}, zona America/Mexico_City]\n"
               f"{prompt_usuario}")
    
    chat = _get_chat(chat_id)

    for intento in range(1, max_intentos + 1):
        try:
            response = chat.send_message(mensaje)
            if not response.text or not response.text.strip():
                return "He procesado tu solicitud, pero no he podido generar un texto de respuesta. Revisa tus herramientas para confirmar los cambios."
            return response.text
        except Exception as e:
            logging.warning(f"Error en sesión de chat de Gemini (Intento {intento}/{max_intentos}): {e}")
            if "503" in str(e) or "Service Unavailable" in str(e):
                if intento < max_intentos:
                    time.sleep(espera_inicial)
                    espera_inicial *= 2
                    continue
            return "Lo siento, mis circuitos cognitivos han experimentado una sobrecarga temporal. Por favor, intenta de nuevo."
    
    return "Error crítico de conexión con el núcleo de procesamiento de IA."