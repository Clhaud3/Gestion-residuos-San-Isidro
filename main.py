from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import os
import time
import random
import threading

PORT_NUMBER = 8888

# --- CONFIGURACIÓN GLOBAL ---
data_store = {
    "global": {
        "temperature": 0.0, 
        "count": 0.0,
        "timestamp": "--", 
        "status": "Iniciando...",
        "history": [] 
    },
    "simulados": {} 
}

NOMBRES_SIMULADOS = [
    "Ronda Palmeras", "Calle José Antonio Cutillas", "Calle Palmeras",
    "Avenida de Catral", "Calle la Huerta", "Calle Pedro Lopez",
    "Calle Paz", "Ronda del Amor"
]

def obtener_objetivo_san_isidro():
    hora = datetime.now().hour
    return 22.0 if 11 <= hora <= 19 else 13.0

# Inicialización de contenedores simulados con valores aleatorios iniciales
for nombre in NOMBRES_SIMULADOS:
    peso_ini = random.uniform(5, 30)
    data_store["simulados"][nombre] = {
        "current_weight": peso_ini,
        "current_temp": obtener_objetivo_san_isidro() + random.uniform(-1, 1),
        "history": [{"timestamp": datetime.now().strftime("%H:%M:%S"), "weight": peso_ini}]
    }

# --- HILO DE SIMULACIÓN AUTÓNOMA ---
def bucle_llenado_automatico():
    """Esta función corre para siempre en segundo plano"""
    while True:
        ts = datetime.now().strftime("%H:%M:%S")
        temp_ambiente = obtener_objetivo_san_isidro()

        for nombre in data_store["simulados"]:
            contenedor = data_store["simulados"][nombre]
            
            # Subida orgánica (entre 0.1 y 0.5 litros cada ciclo)
            incremento = random.uniform(0.1, 0.5)
            nuevo_volumen = round(min(100, contenedor["current_weight"] + incremento), 1)
            contenedor["current_weight"] = nuevo_volumen
            
            # Ajuste de temperatura suave hacia la ambiente
            t_act = contenedor["current_temp"]
            paso = 0.1 if t_act < temp_ambiente else -0.1
            contenedor["current_temp"] = round(t_act + paso, 1)
            
            # Actualizar historial
            contenedor["history"].append({"timestamp": ts, "weight": nuevo_volumen})
            if len(contenedor["history"]) > 15:
                contenedor["history"].pop(0)

        # Esperar 30 segundos para la siguiente actualización
        time.sleep(30)

# --- CONTROLADOR DEL SERVIDOR ---
class IoTHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): return 

    def _set_headers(self, status_code=200, content_type='application/json'):
        self.send_response(status_code)
        self.send_header('Content-type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/reset':
            content_length = int(self.headers['Content-Length'])
            params = json.loads(self.rfile.read(content_length))
            contenedores_a_vaciar = params.get('contenedores', [])

            for nombre in contenedores_a_vaciar:
                if nombre == "Calle del agua":
                    data_store["global"]["count"] = 0
                    data_store["global"]["history"] = []
                elif nombre in data_store["simulados"]:
                    data_store["simulados"][nombre]["current_weight"] = 0
                    data_store["simulados"][nombre]["history"] = [{"timestamp": datetime.now().strftime("%H:%M:%S"), "weight": 0}]
            
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "success"}).encode())

    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        # Servir el HTML
        if parsed_path.path in ['/', '/index.html']:
            try:
                with open('index.html', 'rb') as file:
                    self._set_headers(200, 'text/html')
                    self.wfile.write(file.read())
            except:
                self._set_headers(404)

        # Receptor de datos del Arduino
        elif parsed_path.path == '/data-receiver':
            query = parse_qs(parsed_path.query)
            try:
                temp = float(query.get('temp', [20])[0])
                # Solo sumamos 10 si viene el parámetro 'click'
                if 'click' in query:
                    data_store["global"]["count"] = min(100, data_store["global"]["count"] + 10)
                
                peso_actual = data_store["global"]["count"]
                ts = datetime.now().strftime("%H:%M:%S")
                
                data_store["global"].update({
                    "temperature": temp,
                    "timestamp": ts,
                    "status": "LLENO" if peso_actual >= 90 else "OK"
                })
                
                # Actualizar historial del real
                hist = data_store["global"]["history"]
                if not hist or hist[-1]["weight"] != peso_actual:
                    hist.append({"timestamp": ts, "weight": peso_actual})
                if len(hist) > 15: hist.pop(0)

                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "success"}).encode())
            except:
                self._set_headers(400)

        # Envío de datos a la web
        elif parsed_path.path == '/latest-data':
            self._set_headers(200)
            self.wfile.write(json.dumps(data_store).encode())

if __name__ == '__main__':
    port = int(os.environ.get("PORT", PORT_NUMBER))
    
    # Iniciar el hilo de simulación para que los falsos suban solos
    sim_thread = threading.Thread(target=bucle_llenado_automatico, daemon=True)
    sim_thread.start()
    
    server = HTTPServer(('0.0.0.0', port), IoTHandler)
    print(f"🚀 SERVIDOR SMART CITY ACTIVO EN PUERTO {port}")
    server.serve_forever()
