from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import sys
import os
import time
import random

PORT_NUMBER = 8888

# --- CONFIGURACIÓN DE INICIO ---
START_TIME = time.time() 

VALORES_INICIALES = {
    "Ronda Palmeras": random.uniform(5, 50),
    "Calle José Antonio Cutillas": random.uniform(5, 50),
    "Calle Palmeras": random.uniform(5, 50),
    "Avenida de Catral": random.uniform(5, 50),
    "Calle la Huerta": random.uniform(5, 50),
    "Calle Pedro Lopez": random.uniform(5, 50),
    "Calle Paz": random.uniform(5, 50),
    "Ronda del Amor": random.uniform(5, 50)
}

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
    if 11 <= hora <= 19:
        return 22.0
    else:
        return 13.0

for nombre in VALORES_INICIALES:
    data_store["simulados"][nombre] = {
        "current_weight": VALORES_INICIALES[nombre],
        "current_temp": obtener_objetivo_san_isidro() + random.uniform(-1, 1),
        "history": []
    }

class IoTHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): return 

    def _set_headers(self, status_code=200, content_type='application/json'):
        self.send_response(status_code)
        self.send_header('Content-type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'ngrok-skip-browser-warning, Content-Type')
        self.send_header('Connection', 'close')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_POST(self):
        # 1. DECLARACIÓN GLOBAL AL PRINCIPIO DE LA FUNCIÓN
        global START_TIME
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/reset':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            params = json.loads(post_data)
            contenedores_a_vaciar = params.get('contenedores', [])

            segundos_transcurridos = time.time() - START_TIME
            bloques_30s = int(segundos_transcurridos // 30)
            aumento_actual = bloques_30s * 10

            for nombre in contenedores_a_vaciar:
                if nombre == "Calle del agua":
                    data_store["global"]["count"] = 0
                    data_store["global"]["history"] = []
                elif nombre in data_store["simulados"]:
                    VALORES_INICIALES[nombre] = -aumento_actual 
                    data_store["simulados"][nombre].update({
                        "current_weight": 0,
                        "current_temp": obtener_objetivo_san_isidro(),
                        "history": []
                    })
            
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "success"}).encode())

        elif parsed_path.path == '/reset-containers':
            START_TIME = time.time()
            data_store["global"]["count"] = 0
            data_store["global"]["history"] = []
            for nombre in VALORES_INICIALES:
                VALORES_INICIALES[nombre] = 0 
                data_store["simulados"][nombre].update({
                    "current_weight": 0,
                    "history": []
                })
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "success"}).encode())

    def actualizar_falsos(self):
        # 2. DECLARACIÓN GLOBAL TAMBIÉN AQUÍ AL PRINCIPIO
        global START_TIME
        segundos_transcurridos = time.time() - START_TIME
        bloques_30s = int(segundos_transcurridos // 30)
        aumento_golpe = bloques_30s * 10
        ts = datetime.now().strftime("%H:%M:%S")
        temp_ambiente = obtener_objetivo_san_isidro()

        for nombre, valor_base in VALORES_INICIALES.items():
            nuevo_volumen = round(min(100, max(0, valor_base + aumento_golpe)), 1)
            contenedor = data_store["simulados"][nombre]
            
            if not contenedor["history"] or contenedor["history"][-1]["weight"] != nuevo_volumen:
                contenedor["current_weight"] = nuevo_volumen
                temp_actual = contenedor["current_temp"]
                paso = 0.5 if temp_actual < temp_ambiente else -0.5
                contenedor["current_temp"] = round(temp_actual + paso, 1)
                contenedor["history"].append({"timestamp": ts, "weight": nuevo_volumen})
            
            if len(contenedor["history"]) > 15:
                contenedor["history"].pop(0)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/' or parsed_path.path == '/index.html':
            try:
                with open('index.html', 'rb') as file:
                    self._set_headers(200, 'text/html')
                    self.wfile.write(file.read())
            except FileNotFoundError:
                self._set_headers(404, 'text/plain')
                self.wfile.write(b"Error: index.html no encontrado")

        elif parsed_path.path == '/data-receiver':
            try:
                query = parse_qs(parsed_path.query)
                temp_raw = query.get('temp', [0])[0]
                current_temp = float(temp_raw)
                if 'click' in query:
                    data_store["global"]["count"] += 10
                current_weight = data_store["global"]["count"]
                ts = datetime.now().strftime("%H:%M:%S")
                data_store["global"].update({
                    "temperature": current_temp,
                    "timestamp": ts,
                    "status": "LLENO" if current_weight >= 80 else "OK"
                })
                if not data_store["global"]["history"] or data_store["global"]["history"][-1]["weight"] != current_weight:
                    data_store["global"]["history"].append({"timestamp": ts, "weight": current_weight})
                if len(data_store["global"]["history"]) > 15:
                    data_store["global"]["history"].pop(0)
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "success"}).encode())
            except Exception as e:
                self._set_headers(500)

        elif parsed_path.path == '/latest-data':
            self.actualizar_falsos()
            self._set_headers(200)
            self.wfile.write(json.dumps(data_store).encode())

if __name__ == '__main__':
    # CAMBIO PARA RENDER: Obtener puerto de la variable de entorno o usar 8888 por defecto
    port = int(os.environ.get("PORT", PORT_NUMBER))
    server = HTTPServer(('0.0.0.0', port), IoTHandler)
    print("="*50)
    print(f"🚀 SERVIDOR SMART CITY LISTO EN PUERTO {port}")
    print("="*50)
    server.serve_forever()