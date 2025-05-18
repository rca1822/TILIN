from mitmproxy import http
from bs4 import BeautifulSoup
import time

# Credenciales - REEMPLAZA CON TUS DATOS REALES
USERNAME = "NIA"
PASSWORD = "CONTRASEÑA"

# Variables de estado
login_pending = True
login_token = None
last_login_attempt = 0
cookies_storage = {}

def request(flow: http.HTTPFlow):
    global login_pending, login_token, last_login_attempt, cookies_storage
    
    # Guardar cookies de cada petición para mantener la sesión
    if flow.request.cookies:
        for cookie_name, cookie_value in flow.request.cookies.items():
            cookies_storage[cookie_name] = cookie_value
    
    # Si estamos solicitando la página de login y hay un login pendiente
    if "aules.edu.gva.es/fp/login/index.php" in flow.request.pretty_url and login_pending:
        # Evitar múltiples intentos de login en poco tiempo
        current_time = time.time()
        if current_time - last_login_attempt < 5:  # 5 segundos entre intentos
            return
        
        last_login_attempt = current_time
        print(f"[+] Interceptando petición a página de login: {flow.request.pretty_url}")

def response(flow: http.HTTPFlow):
    global login_pending, login_token, last_login_attempt, cookies_storage
    
    # Si es la respuesta de la página de login y hay un login pendiente
    if "aules.edu.gva.es/fp/login/index.php" in flow.request.pretty_url and login_pending and flow.response:
        # Verificar que hay un formulario de login en la página
        if "logintoken" in flow.response.text and "<form" in flow.response.text:
            print("[+] Página de login detectada con formulario")
            
            # Extraer el token del formulario
            soup = BeautifulSoup(flow.response.content, "html.parser")
            token_input = soup.find("input", {"name": "logintoken"})
            
            if token_input and token_input.has_attr("value"):
                login_token = token_input["value"]
                print(f"[+] Token de login extraído: {login_token}")
                
                # Guardar cookies de la respuesta
                if flow.response.cookies:
                    for cookie_name, cookie_value in flow.response.cookies.items():
                        cookies_storage[cookie_name] = cookie_value
                        # Asegurarnos de que estas cookies se envían de vuelta al cliente
                        if cookie_name not in flow.response.headers.get("Set-Cookie", ""):
                            flow.response.headers.add("Set-Cookie", f"{cookie_name}={cookie_value}; Path=/; Domain=aules.edu.gva.es")
                
                # Construir HTML con el formulario de autoenvío
                html_response = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Iniciando sesión en Aules...</title>
                    <meta charset="UTF-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                        .loader {{ 
                            border: 16px solid #f3f3f3; 
                            border-top: 16px solid #3498db; 
                            border-radius: 50%;
                            width: 80px;
                            height: 80px;
                            animation: spin 2s linear infinite;
                            margin: 20px auto;
                        }}
                        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
                    </style>
                </head>
                <body>
                    <h2>Iniciando sesión automáticamente en Aules...</h2>
                    <div class="loader"></div>
                    <p>Por favor espera, serás redirigido en breve.</p>
                    
                    <form id="loginForm" method="POST" action="https://aules.edu.gva.es/fp/login/index.php" style="display:none;">
                        <input type="hidden" name="username" value="{USERNAME}">
                        <input type="hidden" name="password" value="{PASSWORD}">
                        <input type="hidden" name="logintoken" value="{login_token}">
                        <input type="hidden" name="anchor" value="">
                    </form>
                    
                    <script>
                        // Enviar el formulario automáticamente
                        document.addEventListener('DOMContentLoaded', function() {{
                            console.log("Enviando formulario de login...");
                            setTimeout(function() {{
                                document.getElementById('loginForm').submit();
                            }}, 500); // Pequeño retraso para asegurar que las cookies se han procesado
                        }});
                    </script>
                </body>
                </html>
                """
                
                # Establecer la respuesta modificada
                flow.response.content = html_response.encode('utf-8')
                flow.response.headers["Content-Type"] = "text/html"
                
                print("[+] Página de login modificada para autoenviar credenciales")
    
    # Capturar la respuesta al envío del formulario de login
    elif "aules.edu.gva.es/fp/login/index.php" in flow.request.pretty_url and flow.request.method == "POST":
        print("[+] Interceptando respuesta del formulario de login")
        
        # Preservar todas las cookies que el servidor envía como respuesta al login
        if flow.response and flow.response.cookies:
            print("[+] Cookies de sesión detectadas en la respuesta de login:")
            for cookie_name, cookie_value in flow.response.cookies.items():
                cookies_storage[cookie_name] = cookie_value
                print(f"    - {cookie_name}: {cookie_value}")
                
                # Nos aseguramos de que estas cookies se envían al cliente
                if cookie_name not in flow.response.headers.get("Set-Cookie", ""):
                    flow.response.headers.add("Set-Cookie", f"{cookie_name}={cookie_value}; Path=/; Domain=aules.edu.gva.es")
        
        # Si hay una redirección después del login, la dejamos pasar
        if flow.response and flow.response.status_code in [301, 302, 303, 307, 308]:
            login_pending = False
            print(f"[+] Redirección detectada después del login hacia: {flow.response.headers.get('Location', 'desconocido')}")
    
    # Si detectamos que ya se ha iniciado sesión correctamente
    elif "aules.edu.gva.es/fp/my/" in flow.request.pretty_url and flow.response and flow.response.status_code == 200:
        print("[+] ¡Login exitoso! Detectada página de cursos.")
        login_pending = False  # Ya no necesitamos hacer login
        
        # Seguir propagando las cookies de sesión por si acaso
        if flow.response.cookies:
            for cookie_name, cookie_value in flow.response.cookies.items():
                cookies_storage[cookie_name] = cookie_value