from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import os
import time
import random
import threading

# TRUCO 1: Render asigna el puerto dinámicamente. Usamos la variable de entorno.
PORT_NUMBER = int(os.environ.get("PORT", 8888))

NOMBRES_SIMULADOS = [
    "Ronda Palmeras", "Calle José Antonio Cutillas", "Calle Palmeras",
    "Avenida de Catral", "Calle la Huerta", "Calle Pedro Lopez",
    "Calle Paz", "Ronda del Amor"
]

data_store = {
    "global": { 
        "temperature": 0.0, 
        "count": 0,
        "timestamp": "--", 
        "status": "Iniciando...",
        "history": [] 
    },
    "simulados": {} 
}

def obtener_objetivo_san_isidro():
    hora = datetime.now().hour
    return 22.0 if 11 <= hora <= 19 else 13.0

for nombre in NOMBRES_SIMULADOS:
    valor_aleatorio = round(random.uniform(0, 30), 1)
    data_store["simulados"][nombre] = {
        "current_weight": valor_aleatorio,
        "current_temp": obtener_objetivo_san_isidro() + random.uniform(-1, 1),
        "history": [{"timestamp": datetime.now().strftime("%H:%M:%S"), "weight": valor_aleatorio}]
    }

def bucle_llenado_estricto():
    while True:
        time.sleep(30) 
        ts = datetime.now().strftime("%H:%M:%S")
        for nombre in data_store["simulados"]:
            contenedor = data_store["simulados"][nombre]
            nuevo_peso = contenedor["current_weight"] + 10.0
            if nuevo_peso <= 100:
                contenedor["current_weight"] = round(nuevo_peso, 1)
                contenedor["history"].append({"timestamp": ts, "weight": round(nuevo_peso, 1)})
                if len(contenedor["history"]) > 15:
                    contenedor["history"].pop(0)

class IoTHandler(BaseHTTPRequestHandler):
    # TRUCO 2: Forzamos la versión HTTP 1.0 para evitar problemas de Keep-Alive con Arduino
    protocol_version = 'HTTP/1.0'

    def _set_headers(self, status_code=200, content_type='application/json'):
        self.send_response(status_code)
        self.send_header('Content-type', content_type)
        # TRUCO 3: Intentamos desactivar la redirección forzada en el header (si Render lo lee)
        self.send_header('Strict-Transport-Security', 'max-age=0') 
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        # LOG AGRESIVO: Esto saldrá en Render SIEMPRE que algo toque el servidor
        print(f"--- PETICIÓN RECIBIDA: {self.path} ---")

        if parsed_path.path == '/' or parsed_path.path == '/index.html':
            try:
                with open('index.html', 'rb') as file:
                    self._set_headers(200, 'text/html')
                    self.wfile.write(file.read())
            except: self._set_headers(404)

        elif parsed_path.path == '/data-receiver':
            query = parse_qs(parsed_path.query)
            try:
                temp = float(query.get('temp', [0])[0])
                click = 'click' in query
                
                # LOG DE DATOS: Si ves esto en Render, ¡LO HEMOS LOGRADO!
                print(f"!!! EXITO !!! Datos: Temp={temp}, Click={click}")

                if click:
                    data_store["global"]["count"] = min(100, data_store["global"]["count"] + 10)
                
                ts = datetime.now().strftime("%H:%M:%S")
                data_store["global"].update({
                    "temperature": temp,
                    "timestamp": ts,
                    "status": "LLENO" if data_store["global"]["count"] >= 80 else "OK"
                })
                
                hist = data_store["global"]["history"]
                if not hist or hist[-1]["weight"] != data_store["global"]["count"]:
                    hist.append({"timestamp": ts, "weight": float(data_store["global"]["count"])})
                
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "success"}).encode())
            except Exception as e:
                print(f"Error procesando datos: {e}")
                self._set_headers(400)

        elif parsed_path.path == '/latest-data':
            self._set_headers(200)
            self.wfile.write(json.dumps(data_store).encode())

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/reset':
            content_length = int(self.headers['Content-Length'])
            params = json.loads(self.rfile.read(content_length))
            for nombre in params.get('contenedores', []):
                if nombre == "Calle del agua":
                    data_store["global"]["count"] = 0
                    data_store["global"]["history"] = []
                elif nombre in data_store["simulados"]:
                    data_store["simulados"][nombre]["current_weight"] = 0.0
                    data_store["simulados"][nombre]["history"] = []
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "success"}).encode())

if __name__ == '__main__':
    threading.Thread(target=bucle_llenado_estricto, daemon=True).start()
    print(f"Iniciando servidor en puerto {PORT_NUMBER}...")
    server = HTTPServer(('0.0.0.0', PORT_NUMBER), IoTHandler)
    server.serve_forever()
