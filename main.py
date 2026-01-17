from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import os
import time
import random
import threading

PORT_NUMBER = 8888

# --- ESTRUCTURA DE DATOS ---
data_store = {
    "global": { # ESTE ES EL REAL (Calle del agua)
        "temperature": 0.0, 
        "count": 0.0,
        "timestamp": "--", 
        "history": [] 
    },
    "simulados": {} # ESTOS SON LOS FALSOS
}

NOMBRES_SIMULADOS = [
    "Ronda Palmeras", "Calle José Antonio Cutillas", "Calle Palmeras",
    "Avenida de Catral", "Calle la Huerta", "Calle Pedro Lopez",
    "Calle Paz", "Ronda del Amor"
]

def obtener_objetivo_san_isidro():
    hora = datetime.now().hour
    return 22.0 if 11 <= hora <= 19 else 13.0

# Inicialización: Empiezan entre 0 y 30
for nombre in NOMBRES_SIMULADOS:
    # Elegimos un valor inicial que sea múltiplo de 10 para que sea estético (0, 10, 20 o 30)
    peso_ini = random.choice([0.0, 10.0, 20.0, 30.0])
    data_store["simulados"][nombre] = {
        "current_weight": peso_ini,
        "current_temp": obtener_objetivo_san_isidro() + random.uniform(-1, 1),
        "history": [{"timestamp": datetime.now().strftime("%H:%M:%S"), "weight": peso_ini}]
    }

# --- HILO DE LLENADO PARA FALSOS (PASOS DE 10) ---
def bucle_llenado_automatico():
    while True:
        # Esperamos un tiempo largo (ej. 60 segundos) para simular que alguien tira basura
        time.sleep(60) 
        
        ts = datetime.now().strftime("%H:%M:%S")
        
        for nombre in data_store["simulados"]:
            contenedor = data_store["simulados"][nombre]
            
            # Probabilidad del 30% de que este contenedor se llene en este ciclo
            if random.random() < 0.3: 
                nuevo_volumen = contenedor["current_weight"] + 10.0
                
                if nuevo_volumen <= 100:
                    contenedor["current_weight"] = nuevo_volumen
                    contenedor["history"].append({"timestamp": ts, "weight": nuevo_volumen})
                    
                    if len(contenedor["history"]) > 15:
                        contenedor["history"].pop(0)

# --- SERVIDOR ---
class IoTHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): return 

    def _set_headers(self, status_code=200, content_type='application/json'):
        self.send_response(status_code)
        self.send_header('Content-type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/reset':
            content_length = int(self.headers['Content-Length'])
            params = json.loads(self.rfile.read(content_length))
            contenedores_a_vaciar = params.get('contenedores', [])

            for nombre in contenedores_a_vaciar:
                if nombre == "Calle del agua":
                    data_store["global"]["count"] = 0.0
                    data_store["global"]["history"] = []
                elif nombre in data_store["simulados"]:
                    data_store["simulados"][nombre]["current_weight"] = 0.0
                    data_store["simulados"][nombre]["history"] = [{"timestamp": datetime.now().strftime("%H:%M:%S"), "weight": 0.0}]
            
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "success"}).encode())

    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path in ['/', '/index.html']:
            try:
                with open('index.html', 'rb') as file:
                    self._set_headers(200, 'text/html')
                    self.wfile.write(file.read())
            except: self._set_headers(404)

        elif parsed_path.path == '/data-receiver':
            query = parse_qs(parsed_path.query)
            try:
                temp = float(query.get('temp', [20])[0])
                
                # --- LÓGICA EXCLUSIVA PARA EL REAL ---
                if 'click' in query:
                    # Incremento exacto de 10
                    data_store["global"]["count"] = min(100.0, data_store["global"]["count"] + 10.0)
                
                peso_actual = data_store["global"]["count"]
                ts = datetime.now().strftime("%H:%M:%S")
                
                data_store["global"].update({
                    "temperature": temp,
                    "timestamp": ts
                })
                
                hist = data_store["global"]["history"]
                if not hist or hist[-1]["weight"] != peso_actual:
                    hist.append({"timestamp": ts, "weight": peso_actual})
                if len(hist) > 15: hist.pop(0)

                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "success"}).encode())
            except: self._set_headers(400)

        elif parsed_path.path == '/latest-data':
            self._set_headers(200)
            self.wfile.write(json.dumps(data_store).encode())

if __name__ == '__main__':
    port = int(os.environ.get("PORT", PORT_NUMBER))
    # Iniciar hilo para los falsos
    threading.Thread(target=bucle_llenado_automatico, daemon=True).start()
    server = HTTPServer(('0.0.0.0', port), IoTHandler)
    server.serve_forever()

