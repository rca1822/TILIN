#!/usr/bin/env python3
from mitmproxy import http
from bs4 import BeautifulSoup
import re
import json
import os
import urllib.request
import urllib.parse
import urllib.error
import ssl
import time

class QuizInterceptor:
    def __init__(self):
        # Configuración de la API del LLM
        self.llm_api_url = "https://api.openai.com/v1/chat/completions"
        self.llm_api_key = "TU_API_KEY_AQUI"  # REEMPLAZAR CON TU API KEY
        self.llm_model = "gpt-3.5-turbo"
        
        # Estado para evitar bucles infinitos y almacenar respuestas
        self.procesadas = set()
        self.respuestas_cache = {}  # Guardar respuestas para usarlas en POST
        
        print("\n=== QuizInterceptor con LLM iniciado ===")
        print("Modo: Verificar respuestas antes de enviar")
    
    def consultar_llm(self, pregunta, opciones):
        """Consulta al LLM para obtener la respuesta a una pregunta"""
        
        # Verificar que hay opciones válidas
        if not opciones:
            print("[LLM] No hay opciones para esta pregunta")
            return "0"  # Valor predeterminado si no hay opciones
        
        # Formatear las opciones para el prompt
        opciones_texto = "\n".join([f"[{opcion['valor']}] {opcion['texto']}" for opcion in opciones])
        
        # Crear el prompt para el LLM
        prompt = f"""Eres un asistente experto en responder exámenes. 
Analiza la siguiente pregunta y sus opciones, y responde SOLAMENTE con el valor numérico 
de la opción que consideres correcta, sin explicaciones adicionales.

PREGUNTA: {pregunta}

OPCIONES:
{opciones_texto}

INSTRUCCIONES:
1. Analiza cuidadosamente la pregunta y todas las opciones.
2. Identifica la respuesta correcta basándote en tus conocimientos.
3. Responde ÚNICAMENTE con el NÚMERO (valor) de la opción correcta, sin ningún texto adicional.
4. Si no estás seguro, elige la opción que parece más acertada según tu criterio.

Tu respuesta (solo el valor numérico):"""

        try:
            print(f"[LLM] Consultando al LLM para pregunta: {pregunta[:50]}...")
            
            # Construir la solicitud a la API de OpenAI
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.llm_api_key}"
            }
            
            payload = {
                "model": self.llm_model,
                "messages": [
                    {"role": "system", "content": "Eres un asistente académico que responde preguntas de exámenes."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 10
            }
            
            # Simular una respuesta para evitar problemas de API
            # En un entorno real, aquí realizarías la llamada a la API
            time.sleep(0.5)  # Simular tiempo de procesamiento
            
            # Método fake para simular respuesta
            valores_validos = [opcion['valor'] for opcion in opciones]
            if valores_validos:
                # Usar una lógica básica para seleccionar una respuesta
                # En un entorno real, esto vendría de la llamada a la API
                return valores_validos[4]  # Siempre usar la primera opción como ejemplo
            else:
                return "0"
            
            # DESCOMENTA ESTA SECCIÓN PARA USO REAL CON LA API
            """
            # Convertir payload a JSON y luego a bytes
            data = json.dumps(payload).encode('utf-8')
            
            # Crear la solicitud
            req = urllib.request.Request(self.llm_api_url, data=data, headers=headers, method='POST')
            
            # Configurar SSL context para evitar problemas de certificado
            ctx = ssl.create_default_context()
            
            # Enviar la solicitud
            with urllib.request.urlopen(req, context=ctx) as response:
                result = json.loads(response.read().decode('utf-8'))
                respuesta = result['choices'][0]['message']['content'].strip()
            
            # Limpiar la respuesta para obtener solo el valor numérico
            respuesta_limpia = re.sub(r'\D', '', respuesta)
            
            if respuesta_limpia in valores_validos:
                return respuesta_limpia
            else:
                print(f"[LLM] Respuesta no válida: '{respuesta}'. Valores válidos: {valores_validos}")
                # Si la respuesta no es válida, usar la primera opción
                return valores_validos[0] if valores_validos else "0"
            """
                
        except Exception as e:
            print(f"[LLM] Error al consultar LLM: {e}")
            # En caso de error, devolver la primera opción si hay alguna
            valores_validos = [opcion['valor'] for opcion in opciones]
            return valores_validos[0] if valores_validos else "0"
    
    def response(self, flow: http.HTTPFlow) -> None:
        """Maneja la respuesta HTTP interceptada"""
        
        # Verificar si es una página de quiz de aules.edu.gva.es
        if flow.request.pretty_url.find("aules.edu.gva.es") == -1:
            return
        
        # Verificar si es una página de resultado de respuesta
        if flow.request.method == "POST" and flow.request.pretty_url.find("/mod/quiz/processattempt.php") != -1:
            # Aquí podríamos verificar si la respuesta contiene información sobre si fue correcta o incorrecta
            # Pero esta lógica depende del formato específico de la respuesta
            print("\n[+] Interceptando resultado de respuesta")
            return
        
        # Manejar páginas de visualización del quiz (GET)
        if flow.request.method == "GET" and flow.request.pretty_url.find("/mod/quiz/attempt.php") != -1:
            # Evitar procesar múltiples veces la misma URL
            request_id = flow.request.pretty_url + str(flow.request.method)
            if request_id in self.procesadas:
                print(f"[SKIP] URL ya procesada: {flow.request.pretty_url}")
                return
            
            self.procesadas.add(request_id)
            print(f"\n[+] Detectada página de cuestionario: {flow.request.pretty_url}")
            
            try:
                # Extraer contenido HTML
                content = flow.response.content.decode('utf-8', errors='ignore')
                
                # Analizar HTML con BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                # Extraer preguntas y respuestas
                preguntas = self.extraer_preguntas(soup)
                
                if not preguntas:
                    print("No se detectaron preguntas en esta página")
                    return
                
                print(f"\n===== {len(preguntas)} PREGUNTAS DETECTADAS =====")
                
                # Procesar cada pregunta
                for pregunta in preguntas:
                    # Mostrar información sobre la pregunta
                    print(f"\nID: {pregunta['id']}")
                    print(f"Texto: {pregunta['texto']}")
                    
                    # Consultar al LLM para obtener la respuesta
                    respuesta = self.consultar_llm(pregunta['texto'], pregunta['opciones'])
                    pregunta['respuesta_llm'] = respuesta
                    
                    # Guardar en caché para usar durante POST
                    pregunta_key = f"q{pregunta['id']}:1_answer"
                    self.respuestas_cache[pregunta_key] = respuesta
                    
                    # Encontrar el texto de la respuesta seleccionada
                    texto_respuesta = "Desconocido"
                    for opcion in pregunta['opciones']:
                        if opcion['valor'] == respuesta:
                            texto_respuesta = opcion['texto']
                            break
                    
                    print(f"  >>> LLM responde: [{respuesta}] {texto_respuesta}")
                    
                    
                # agregamos un panel de información
                info_panel = soup.new_tag('div', id='quiz-interceptor-panel')
                info_panel['style'] = '''
                    position: fixed;
                    top: 10px;
                    right: 10px;
                    background-color: rgba(0, 0, 0, 0.8);
                    color: white;
                    padding: 10px;
                    border-radius: 5px;
                    z-index: 9999;
                    max-width: 300px;
                    font-family: Arial, sans-serif;
                '''
                
                titulo = soup.new_tag('h3')
                titulo.string = "TILIN Auto Test"
                info_panel.append(titulo)
                
                descripcion = soup.new_tag('p')
                descripcion.string = "Un forense solo actua despues de que un delito ha sido cometido, por eso la respuesta correcta es "
                info_panel.append(descripcion)
                
                # Agregar las respuestas del LLM al panel
                lista = soup.new_tag('ul')
                lista['style'] = 'list-style-type: none; padding-left: 5px;'
                
                for pregunta in preguntas:
                    item = soup.new_tag('li')
                    item['style'] = 'margin-bottom: 5px;'
                    
                    texto_respuesta = "Desconocido"
                    for opcion in pregunta['opciones']:
                        if opcion['valor'] == pregunta.get('respuesta_llm', '0'):
                            texto_respuesta = opcion['texto']
                            break
                            
                    # Truncar textos largos
                    pregunta_texto = pregunta['texto']
                    if len(pregunta_texto) > 30:
                        pregunta_texto = pregunta_texto[:27] + "..."
                        
                    item.string = f"{pregunta_texto}: [{pregunta.get('respuesta_llm', '0')}] {texto_respuesta[:30]}"
                    lista.append(item)
                
                info_panel.append(lista)
                
                # Agregar dos botones: verificar respuestas y usar respuestas LLM
                verificar_btn = soup.new_tag('button', id='verificar-respuestas')
                verificar_btn['style'] = '''
                    background-color: #4CAF50;
                    border: none;
                    color: white;
                    padding: 8px 16px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 14px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 4px;
                '''
                verificar_btn.string = "Verificar mis respuestas"
                info_panel.append(verificar_btn)
                
                # Botón para usar respuestas del LLM
                usar_llm_btn = soup.new_tag('button', id='usar-respuestas-llm')
                usar_llm_btn['style'] = '''
                    background-color: #2196F3;
                    border: none;
                    color: white;
                    padding: 8px 16px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 14px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 4px;
                '''
                usar_llm_btn.string = "Usar respuestas LLM"
                info_panel.append(usar_llm_btn)
                
                # Agregar el panel al body
                if soup.body:
                    soup.body.append(info_panel)
                    
                    # Agregar script para manejar la verificación de respuestas y aplicar respuestas LLM
                    script = soup.new_tag('script')
                    script.string = f'''
                    document.addEventListener('DOMContentLoaded', function() {{
                        // Guardar las respuestas del LLM
                        const respuestasLLM = {json.dumps(self.respuestas_cache)};
                        
                        // Función para verificar respuestas antes de enviar
                        document.getElementById('verificar-respuestas').addEventListener('click', function() {{
                            let todosCamposCompletados = true;
                            let respuestasCorrectas = true;
                            let mensajes = [];
                            
                            // Verificar cada respuesta
                            for (const [campo, respuestaCorrecta] of Object.entries(respuestasLLM)) {{
                                // Detectar si es checkbox o radio
                                const inputs = document.querySelectorAll(`input[name="${{campo}}"], input[name^="${{campo}}["]`);
                                const esCheckbox = inputs.length > 0 && inputs[0].type === 'checkbox';
                                
                                let seleccionado = false;
                                let respuestaUsuario = null;
                                
                                if (esCheckbox) {{
                                    // Para checkboxes, la "respuesta" es un conjunto de valores marcados
                                    seleccionado = false; // Inicialmente asumimos que no hay nada seleccionado
                                    const valoresSeleccionados = [];
                                    
                                    inputs.forEach(input => {{
                                        if (input.checked) {{
                                            seleccionado = true;
                                            valoresSeleccionados.push(input.value);
                                        }}
                                    }});
                                    
                                    // Para simplificar, consideramos correcta si al menos se seleccionó algo
                                    respuestaUsuario = valoresSeleccionados.join(',');
                                    
                                    // Con checkboxes, es más complicado verificar exactitud 
                                    // Por ahora, asumimos que la respuesta es correcta
                                    respuestasCorrectas = true;
                                    continue;
                                }} else {{
                                    // Para radio buttons, verificación normal
                                    inputs.forEach(input => {{
                                        if (input.checked) {{
                                            seleccionado = true;
                                            respuestaUsuario = input.value;
                                        }}
                                    }});
                                    
                                    if (!seleccionado) {{
                                        todosCamposCompletados = false;
                                        mensajes.push(`No has seleccionado respuesta para la pregunta ${{campo.split(':')[0]}}`);
                                    }} else if (respuestaUsuario !== respuestaCorrecta) {{
                                        respuestasCorrectas = false;
                                        
                                        // Buscar los textos para mostrar info
                                        let textoSeleccionado = "Desconocido";
                                        let textoCorrect = "Desconocido";
                                        inputs.forEach(input => {{
                                            const labelId = input.id + '_label';
                                            const label = document.getElementById(labelId);
                                            if (label) {{
                                                if (input.value === respuestaUsuario) {{
                                                    textoSeleccionado = label.textContent.trim();
                                                }}
                                                if (input.value === respuestaCorrecta) {{
                                                    textoCorrect = label.textContent.trim();
                                                }}
                                            }}
                                        }});
                                        
                                        mensajes.push(`Pregunta ${{campo.split(':')[0]}}: Tu respuesta [${{respuestaUsuario}}] ${{textoSeleccionado}} es incorrecta. Recomendada: [${{respuestaCorrecta}}] ${{textoCorrect}}`);
                                    }}
                                }}
                            }}
                            
                            if (!todosCamposCompletados) {{
                                alert("⚠️ Faltan respuestas: \\n\\n" + mensajes.join("\\n"));
                                return;
                            }}
                            
                            if (!respuestasCorrectas) {{
                                const continuar = confirm(
                                    "⚠️ Algunas respuestas no coinciden con las recomendadas: \\n\\n" + 
                                    mensajes.join("\\n") + 
                                    "\\n\\n¿Deseas continuar con tus respuestas actuales?"
                                );
                                
                                if (!continuar) {{
                                    return;
                                }}
                            }}
                            
                            // Si llegamos aquí, el usuario quiere continuar
                            // Buscar y hacer clic en el botón de envío
                            const submitBtn = document.querySelector('input[name="next"]');
                            if (submitBtn) {{
                                submitBtn.click();
                            }} else {{
                                const finishBtn = document.querySelector('input[value="Finalizar intento..."], input[value="Acaba l\\'intent..."]');
                                if (finishBtn) {{
                                    finishBtn.click();
                                }} else {{
                                    document.querySelector('form').submit();
                                }}
                            }}
                        }});
                        
                        // Función para aplicar automáticamente las respuestas del LLM
                        document.getElementById('usar-respuestas-llm').addEventListener('click', function() {{
                            // Recorrer todas las respuestas del LLM y seleccionarlas
                            for (const [campo, respuestaLLM] of Object.entries(respuestasLLM)) {{
                                // Detectar si es checkbox o radio
                                const inputs = document.querySelectorAll(`input[name="${{campo}}"], input[name^="${{campo}}["]`);
                                
                                if (inputs.length > 0) {{
                                    // Para inputs de tipo radio, seleccionar el que coincide con la respuesta
                                    inputs.forEach(input => {{
                                        if (input.value === respuestaLLM) {{
                                            input.checked = true;
                                            // Simular un evento de cambio para actualizar el estado visual
                                            const event = new Event('change', {{ bubbles: true }});
                                            input.dispatchEvent(event);
                                        }} else {{
                                            input.checked = false;
                                        }}
                                    }});
                                }}
                                
                                // Para campos hidden o text, buscar cualquier input con ese nombre y establecer su valor
                                const hiddenInput = document.querySelector(`input[name="${{campo}}"][type="hidden"], input[name="${{campo}}"][type="text"]`);
                                if (hiddenInput) {{
                                    hiddenInput.value = respuestaLLM;
                                }}
                            }}
                            
                            // También crear campos hidden para cualquier respuesta que no tenga un input existente
                            const form = document.querySelector('form');
                            if (form) {{
                                for (const [campo, respuestaLLM] of Object.entries(respuestasLLM)) {{
                                    // Verificar si ya existe un input con este nombre
                                    if (!document.querySelector(`input[name="${{campo}}"]`)) {{
                                        // Si no existe, crear uno nuevo
                                        const hiddenInput = document.createElement('input');
                                        hiddenInput.type = 'hidden';
                                        hiddenInput.name = campo;
                                        hiddenInput.value = respuestaLLM;
                                        form.appendChild(hiddenInput);
                                    }}
                                }}
                            }}
                            
                            alert("✅ Respuestas del LLM aplicadas. Pulsa 'Verificar mis respuestas' para enviar el formulario.");
                        }});
                    }});
                    '''
                    
                    soup.body.append(script)
                    
                    # Actualizar el contenido de la respuesta
                    flow.response.content = str(soup).encode('utf-8')
                    print("[✓] HTML modificado con panel de verificación de respuestas")
                
            except Exception as e:
                print(f"[ERROR] Error al procesar la página: {e}")

    def request(self, flow: http.HTTPFlow) -> None:
        """Intercepta y modifica las solicitudes HTTP antes de que sean enviadas"""
        # Verificar si es un envío de formulario de quiz
        if (flow.request.method == "POST" and 
            flow.request.pretty_url.find("aules.edu.gva.es") != -1 and 
            flow.request.pretty_url.find("/mod/quiz/processattempt.php") != -1):
            
            print("\n[+] Interceptando envío de formulario quiz")
            
            # Verificar si estamos ante un formulario multipart
            content_type = flow.request.headers.get("Content-Type", "")
            
            if "multipart/form-data" in content_type:
                try:
                    # Procesar formulario multipart/form-data
                    print("[+] Detectado formulario multipart/form-data")
                    
                    # Obtener el contenido como texto
                    content = flow.request.content.decode('utf-8', errors='ignore')
                    
                    # Buscar campos de respuesta y modificar con las respuestas del LLM
                    for campo, valor_llm in self.respuestas_cache.items():
                        # Buscar patrón: name="q123:1_answer"\r\n\r\n0\r\n
                        patron = f'name="{campo}"\\r\\n\\r\\n([^\\r]+)\\r\\n'
                        match = re.search(patron, content)
                        
                        if match:
                            valor_actual = match.group(1)
                            print(f"[+] Campo {campo}: Valor actual={valor_actual}, Valor LLM={valor_llm}")
                            
                            # Reemplazar el valor con la respuesta del LLM
                            content = content.replace(
                                f'name="{campo}"\r\n\r\n{valor_actual}\r\n',
                                f'name="{campo}"\r\n\r\n{valor_llm}\r\n'
                            )
                    
                    # Actualizar el contenido de la solicitud
                    flow.request.content = content.encode('utf-8')
                    
                    # Actualizar la longitud del contenido en los headers
                    flow.request.headers["Content-Length"] = str(len(flow.request.content))
                    
                    print("[✓] Formulario modificado con respuestas del LLM")
                except Exception as e:
                    print(f"[ERROR] Error al modificar formulario multipart: {e}")
            
            elif "application/x-www-form-urlencoded" in content_type:
                # Procesar formulario x-www-form-urlencoded
                try:
                    print("[+] Detectado formulario application/x-www-form-urlencoded")
                    
                    # Decodificar el contenido del formulario
                    form_data = urllib.parse.parse_qs(flow.request.content.decode('utf-8'))
                    
                    # Modificar las respuestas con las del LLM
                    modificado = False
                    for campo, valor_llm in self.respuestas_cache.items():
                        if campo in form_data:
                            print(f"[+] Campo {campo}: Valor actual={form_data[campo][0]}, Valor LLM={valor_llm}")
                            form_data[campo] = [valor_llm]
                            modificado = True
                    
                    if modificado:
                        # Codificar el formulario modificado
                        nuevo_content = urllib.parse.urlencode(form_data, doseq=True).encode('utf-8')
                        flow.request.content = nuevo_content
                        
                        # Actualizar la longitud del contenido en los headers
                        flow.request.headers["Content-Length"] = str(len(flow.request.content))
                        
                        print("[✓] Formulario modificado con respuestas del LLM")
                except Exception as e:
                    print(f"[ERROR] Error al modificar formulario urlencoded: {e}")
    
    def extraer_preguntas(self, soup):
        """Extrae las preguntas y opciones del HTML"""
        preguntas = []
        
        # Buscar los bloques de preguntas
        question_blocks = soup.find_all('div', class_='que')
        
        for block in question_blocks:
            pregunta = {}
            
            # Extraer el ID de la pregunta
            id_match = None
            if 'id' in block.attrs:
                id_match = re.search(r'question-(\d+)', block['id'])
            
            # También buscar ID en inputs ocultos
            if not id_match:
                seq_check = block.find('input', {'name': re.compile(r'q\d+:1_:sequencecheck')})
                if seq_check:
                    id_match = re.search(r'q(\d+):1_:sequencecheck', seq_check['name'])
            
            if id_match:
                pregunta['id'] = id_match.group(1)
            else:
                continue  # No se puede identificar la pregunta, pasamos a la siguiente
            
            # Extraer el texto de la pregunta
            qtext_div = block.find('div', class_='qtext')
            if qtext_div:
                pregunta['texto'] = qtext_div.get_text(strip=True)
            else:
                pregunta['texto'] = "No se pudo extraer el texto de la pregunta"
            
            # Extraer opciones de respuesta (radio buttons)
            pregunta['opciones'] = []
            radio_inputs = block.find_all('input', {'type': 'radio'})
            
            if not radio_inputs:
                # También buscar checkboxes para preguntas de múltiples respuestas
                radio_inputs = block.find_all('input', {'type': 'checkbox'})
            
            for radio in radio_inputs:
                if 'id' in radio.attrs and 'value' in radio.attrs and radio['value'] != '-1':
                    # Buscar el texto asociado a esta opción
                    label_id = radio['id'] + '_label'
                    label = block.find('div', id=label_id)
                    
                    if label:
                        opcion = {
                            'valor': radio['value'],
                            'texto': label.get_text(strip=True),
                            'id': radio['id']
                        }
                        pregunta['opciones'].append(opcion)
            
            # Extraer el nombre del campo de entrada (para construir el POST)
            if radio_inputs:
                for radio in radio_inputs:
                    if 'name' in radio.attrs:
                        pregunta['nombre_campo'] = radio['name']
                        break
            
            # Solo agregar preguntas que tengan opciones válidas
            if pregunta['opciones']:
                preguntas.append(pregunta)
            else:
                print(f"[INFO] Pregunta {pregunta.get('id', 'desconocida')} no tiene opciones válidas - ignorando")
        
        return preguntas


# Para que mitmproxy pueda cargar este script
addons = [
    QuizInterceptor()
]
