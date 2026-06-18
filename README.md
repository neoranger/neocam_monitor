# NeoCam Monitor

**NeoCam Monitor** es un centro de monitoreo de cámaras ligero y moderno diseñado para homeservers. Permite autodetectar cámaras web locales conectadas por USB y agregar fuentes de video externas (como streams RTSP de cámaras IP o endpoints HTTP/MJPEG) para visualizarlas en una sola grilla en tiempo real o analizarlas de manera individual en una pantalla dedicada.

El proyecto está completamente contenerizado usando Docker y mapea el bus de dispositivos USB para una fácil integración plug-and-play.

---

## Características Principales

1. **Diseño Oscuro Premium**: Interfaz glassmorphic moderna con acentos verde esmeralda y cian, optimizada para pantallas grandes y móviles (totalmente responsiva).
2. **Detección Automática de USB**: Escaneo en caliente de dispositivos `/dev/video*` para agregarlos con un solo clic.
3. **Mapeo de Dispositivos Dinámico**: Soporte para fuentes USB locales, cámaras IP RTSP y feeds HTTP/MJPEG.
4. **Streaming Asíncrono Eficiente**: Hilos dedicados independientes en backend usando OpenCV para leer frames de forma continua, evitando cuellos de botella en la renderización y optimizando el consumo de CPU.
5. **Persistencia Completa**: Base de datos SQLite persistida a través de volúmenes Docker.

---

## Requisitos Previos

- **Docker** y **Docker Compose** instalados en el sistema host.
- Dispositivos de cámara web conectados (opcional, para usar la función de captura USB local).

---

## Instalación y Despliegue con Docker

1. Clona o copia este repositorio en tu servidor.
2. Inicia el contenedor usando Docker Compose:

   ```bash
   docker compose up -d --build
   ```

3. Accede al panel web ingresando a la dirección IP de tu servidor en el puerto `5000`:
   
   ```
   http://localhost:5000
   ```

---

## Acceso a Dispositivos de Cámara USB (Linux)

Para que el contenedor tenga acceso a las cámaras físicas conectadas a los puertos USB de tu servidor, el archivo `docker-compose.yml` mapea el directorio `/dev` del host al contenedor y ejecuta el servicio en modo privilegiado (`privileged: true`). 

Si deseas limitar el acceso a cámaras específicas, puedes modificar `docker-compose.yml` mapeando únicamente los dispositivos necesarios (por ejemplo: `devices: - "/dev/video0:/dev/video0"`).

---

## Uso

### Monitoreo General
La pantalla de inicio presenta una grilla interactiva que muestra todas las cámaras habilitadas de forma simultánea. Desde allí puedes:
- Entrar al modo de pantalla completa enfocada.
- Apagar o encender el feed de cualquier cámara individualmente con el botón de ocultar.

### Panel de Administración
Accede mediante el menú de navegación para:
1. **Auto-Detectar**: Hacer clic en "Buscar Cámaras USB" para listar las cámaras activas y agregarlas inmediatamente.
2. **Agregar Manualmente**: Registrar cámaras IP remotas especificando su URL (ej. `rtsp://usuario:clave@192.168.1.50/live`) o streams HTTP.
3. **Gestión Completa**: Modificar nombres, cambiar orígenes de feed, apagar temporalmente o eliminar cámaras del sistema.
