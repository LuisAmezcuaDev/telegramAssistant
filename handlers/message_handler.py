from telegram import Update
from telegram.ext import ContextTypes
from services.gemini_service import generar_respuesta_asistente

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los mensajes de texto y delega la autonomía operativa al motor de Gemini."""
    texto_usuario = update.message.text
    
    # 1. Obtenemos el ID único del chat actual de Telegram
    chat_id = update.effective_chat.id

    # 2. Pasamos tanto el texto como el chat_id para mantener la sesión de chat independiente por usuario
    respuesta_ia = generar_respuesta_asistente(texto_usuario, chat_id)

    await update.message.reply_text(respuesta_ia, parse_mode="Markdown")