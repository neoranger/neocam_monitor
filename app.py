import os
import glob
import time
import threading
import numpy as np
import cv2
from flask import Flask, render_template, Response, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///neocam.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelo de Base de Datos
class Camera(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False) # 'usb', 'rtsp', 'http'
    source = db.Column(db.String(255), nullable=False) # '/dev/video0', rtsp://..., http://...
    is_enabled = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'source': self.source,
            'is_enabled': self.is_enabled
        }

# Stream individual de Cámara
class CameraStream:
    def __init__(self, camera_id, name, camera_type, source):
        self.camera_id = camera_id
        self.name = name
        self.camera_type = camera_type
        self.source = source
        self.running = False
        self.thread = None
        self.latest_frame = None
        self.lock = threading.Lock()
        self.error_msg = "Inicializando..."
        
    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._update, daemon=True)
            self.thread.start()
            
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            
    def _update(self):
        src = self.source
        if self.camera_type == 'usb':
            try:
                if src.isdigit():
                    src = int(src)
                elif src.startswith('/dev/video'):
                    src = int(src.replace('/dev/video', ''))
            except ValueError:
                pass
                
        cap = None
        consecutive_failures = 0
        
        while self.running:
            if cap is None or not cap.isOpened():
                self.error_msg = f"Conectando a {self.name}..."
                cap = cv2.VideoCapture(src)
                if self.camera_type == 'usb' and cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                
                if not cap.isOpened():
                    consecutive_failures += 1
                    self.error_msg = f"Error al abrir stream. Reintentando..."
                    # Dormir con backoff incremental
                    sleep_time = min(1.0 * consecutive_failures, 10.0)
                    time.sleep(sleep_time)
                    continue
                
            success, frame = cap.read()
            if not success:
                self.error_msg = "Error al leer fotograma. Reconectando..."
                cap.release()
                cap = None
                time.sleep(1.0)
                continue
                
            consecutive_failures = 0
            self.error_msg = None
            
            # Codificar fotograma a JPEG
            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                with self.lock:
                    self.latest_frame = jpeg.tobytes()
                    
            # Mantener ~25 FPS para reducir uso de CPU
            time.sleep(0.04)
            
        if cap is not None:
            cap.release()
            
    def get_frame(self):
        with self.lock:
            return self.latest_frame, self.error_msg

# Administrador Global de Cámaras
class CameraManager:
    def __init__(self):
        self.streams = {}
        self.lock = threading.Lock()
        
    def start_camera(self, camera):
        with self.lock:
            if camera.id not in self.streams and camera.is_enabled:
                stream = CameraStream(camera.id, camera.name, camera.type, camera.source)
                stream.start()
                self.streams[camera.id] = stream
                
    def stop_camera(self, camera_id):
        with self.lock:
            if camera_id in self.streams:
                self.streams[camera_id].stop()
                del self.streams[camera_id]
                
    def get_stream(self, camera_id):
        with self.lock:
            return self.streams.get(camera_id)
            
    def update_cameras(self, active_cameras):
        active_ids = {c.id for c in active_cameras if c.is_enabled}
        
        # Detener las que ya no están activas o deshabilitadas
        current_ids = list(self.streams.keys())
        for cid in current_ids:
            if cid not in active_ids:
                self.stop_camera(cid)
                
        # Iniciar las nuevas habilitadas
        for camera in active_cameras:
            if camera.is_enabled and camera.id not in self.streams:
                self.start_camera(camera)

camera_manager = CameraManager()

def generate_placeholder_frame(text):
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Fondo degradado azul oscuro / slate
    for i in range(480):
        img[i, :, 0] = int(15 + (i / 480) * 10)
        img[i, :, 1] = int(23 + (i / 480) * 15)
        img[i, :, 2] = int(42 + (i / 480) * 20)
        
    font = cv2.FONT_HERSHEY_SIMPLEX
    # Dibujar texto centrado
    text_size = cv2.getTextSize(text, font, 0.7, 2)[0]
    text_x = (640 - text_size[0]) // 2
    text_y = (480 + text_size[1]) // 2
    
    cv2.putText(img, text, (text_x, text_y), font, 0.7, (147, 197, 253), 2, cv2.LINE_AA)
    ret, jpeg = cv2.imencode('.jpg', img)
    return jpeg.tobytes()

# Rutas del Servidor Web
@app.route('/')
def index():
    cameras = Camera.query.all()
    camera_manager.update_cameras(cameras)
    return render_template('index.html', cameras=cameras)

@app.route('/camera/<int:camera_id>')
def camera_detail(camera_id):
    camera = db.get_or_404(Camera, camera_id)
    return render_template('camara.html', camera=camera)

@app.route('/admin')
def admin():
    cameras = Camera.query.all()
    return render_template('admin.html', cameras=cameras)

@app.route('/admin/add', methods=['POST'])
def add_camera():
    name = request.form.get('name')
    camera_type = request.form.get('type')
    source = request.form.get('source')
    
    if name and camera_type and source:
        new_cam = Camera(name=name, type=camera_type, source=source, is_enabled=True)
        db.session.add(new_cam)
        db.session.commit()
        camera_manager.start_camera(new_cam)
        
    return redirect(url_for('admin'))

@app.route('/admin/edit/<int:camera_id>', methods=['POST'])
def edit_camera(camera_id):
    camera = db.get_or_404(Camera, camera_id)
    camera.name = request.form.get('name')
    camera.type = request.form.get('type')
    camera.source = request.form.get('source')
    
    db.session.commit()
    
    # Reiniciar stream con nueva configuración
    camera_manager.stop_camera(camera_id)
    if camera.is_enabled:
        camera_manager.start_camera(camera)
        
    return redirect(url_for('admin'))

@app.route('/admin/toggle/<int:camera_id>', methods=['POST'])
def toggle_camera(camera_id):
    camera = db.get_or_404(Camera, camera_id)
    camera.is_enabled = not camera.is_enabled
    db.session.commit()
    
    if camera.is_enabled:
        camera_manager.start_camera(camera)
    else:
        camera_manager.stop_camera(camera_id)
        
    return jsonify({'success': True, 'is_enabled': camera.is_enabled})

@app.route('/admin/delete/<int:camera_id>', methods=['POST'])
def delete_camera(camera_id):
    camera = db.get_or_404(Camera, camera_id)
    camera_manager.stop_camera(camera_id)
    db.session.delete(camera)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/api/scan_usb')
def scan_usb():
    devices = []
    # Escanear rutas comunes en Linux (/dev/video*)
    video_paths = sorted(glob.glob('/dev/video*'))
    for path in video_paths:
        try:
            device_idx = int(path.replace('/dev/video', ''))
            # Solo probar índices pares para evitar los sub-canales de metadatos (común en Linux)
            if device_idx % 2 != 0:
                continue
            
            cap = cv2.VideoCapture(device_idx)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    devices.append({
                        'path': path,
                        'name': f"Cámara USB ({path.split('/')[-1]})",
                        'source': str(device_idx)
                    })
                cap.release()
        except Exception:
            pass
            
    return jsonify(devices)

@app.route('/video_feed/<int:camera_id>')
def video_feed(camera_id):
    def gen():
        while True:
            stream = camera_manager.get_stream(camera_id)
            if stream is None:
                # Comprobar si la cámara está deshabilitada o cargando
                camera = db.session.get(Camera, camera_id)
                if camera and not camera.is_enabled:
                    frame = generate_placeholder_frame("Cámara Desactivada")
                else:
                    frame = generate_placeholder_frame("Conectando cámara...")
            else:
                frame_data, error_msg = stream.get_frame()
                if error_msg:
                    frame = generate_placeholder_frame(error_msg)
                elif frame_data is not None:
                    frame = frame_data
                else:
                    frame = generate_placeholder_frame("Recibiendo señal...")
                    
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.04)
            
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Inicializar cámaras al iniciar
        cameras = Camera.query.all()
        camera_manager.update_cameras(cameras)
        
    app.run(host='0.0.0.0', port=5000)
