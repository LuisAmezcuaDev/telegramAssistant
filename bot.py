import logging
import os
import json
import threading
from flask import Flask
from telegram.ext import ApplicationBuilder, MessageHandler, filters
from config import TELEGRAM_TOKEN
from handlers.message_handler import handle_message

# Recrear credentials.json si no existe y la variable de entorno está presente
if not os.path.exists('credentials.json') and os.getenv('CREDENTIALS_JSON'):
    with open('credentials.json', 'w') as f:
        f.write(os.getenv('CREDENTIALS_JSON'))

# Recrear token.json si no existe y la variable de entorno está presente
if not os.path.exists('token.json') and os.getenv('TOKEN_JSON'):
    with open('token.json', 'w') as f:
        f.write(os.getenv('TOKEN_JSON'))

# Configurar logs limpios en consola (corregido el formato)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Servidor web minúsculo para evitar que Railway duerma el contenedor por inactividad
app_flask = Flask(__name__)

@app_flask.route('/')
def health_check():
    return "Bot de Telegram activo y en línea", 200

def run_web_server():
    port = 8080
    app_flask.run(host="0.0.0.0", port=port)

def main():
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "tu_token_de_telegram_aqui":
        print("Error: Debes configurar tu TELEGRAM_TOKEN en el archivo .env")
        return

    # Inicializamos la app de Telegram
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Registramos el manejador de mensajes de texto
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    logging.info("Asistente iniciado y escuchando en Telegram...")
    
    # Arranca el bot de forma continua
    app.run_polling()

if __name__ == "__main__":
    # Iniciar Flask en un hilo independiente (daemon) para que corra junto al bot sin bloquearlo
    t = threading.Thread(target=run_web_server, daemon=True)
    t.start()
    
    main()