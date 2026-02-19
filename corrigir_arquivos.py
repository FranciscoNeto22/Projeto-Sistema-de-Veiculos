import os

# --- Conteúdo do monitor.html ---
monitor_html = """<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
    <title>Server Monitor</title>
    <link rel="manifest" href="/static/manifest.json">
    <meta name="theme-color" content="#000000">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: 'Courier New', monospace; }
        .card { background-color: #1e1e1e; border: 1px solid #333; margin-bottom: 15px; }
        .stat-value { font-size: 1.5rem; font-weight: bold; color: #00ff00; }
        .stat-label { font-size: 0.8rem; color: #888; text-transform: uppercase; }
        .status-dot { height: 12px; width: 12px; background-color: #bbb; border-radius: 50%; display: inline-block; }
        .online { background-color: #00ff00; box-shadow: 0 0 10px #00ff00; }
        .offline { background-color: #ff0000; box-shadow: 0 0 10px #ff0000; }
        .slow { background-color: #ffcc00; }
        
        /* Animação de pulso para rede */
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .ping-indicator { animation: pulse 2s infinite; }
    </style>
</head>
<body class="p-3">

    <div class="d-flex justify-content-between align-items-center mb-4">
        <h5 class="m-0">📟 SERVER MONITOR</h5>
        <a href="/app" class="btn btn-sm btn-outline-secondary">Voltar</a>
    </div>

    <!-- Status Geral -->
    <div class="card">
        <div class="card-body text-center">
            <div class="stat-label">Status do Servidor</div>
            <div class="mt-2">
                <span id="server-dot" class="status-dot offline"></span>
                <span id="server-text" class="fw-bold ms-2">Desconectado</span>
            </div>
            <div class="mt-2 small text-muted">Ping: <span id="ping-val">--</span>ms</div>
        </div>
    </div>

    <div class="row">
        <!-- Uptime -->
        <div class="col-6">
            <div class="card h-100">
                <div class="card-body text-center">
                    <div class="stat-label">Tempo Ativo</div>
                    <div id="uptime-val" class="stat-value text-info" style="font-size: 1.1rem;">--:--:--</div>
                </div>
            </div>
        </div>
        <!-- DB Size -->
        <div class="col-6">
            <div class="card h-100">
                <div class="card-body text-center">
                    <div class="stat-label">Banco de Dados</div>
                    <div id="db-size-val" class="stat-value text-warning">-- MB</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Rede / Conexão -->
    <div class="card">
        <div class="card-body">
            <div class="d-flex justify-content-between align-items-center">
                <span class="stat-label">Rede (Cliente)</span>
                <span id="net-type" class="badge bg-secondary">--</span>
            </div>
            <div class="progress mt-2" style="height: 5px;">
                <div id="net-bar" class="progress-bar bg-success" style="width: 0%"></div>
            </div>
        </div>
    </div>

    <!-- Log Console -->
    <div class="card mt-3">
        <div class="card-header py-1 small bg-dark border-bottom border-secondary">System Log</div>
        <div class="card-body p-2 bg-black" style="height: 150px; overflow-y: auto; font-size: 0.75rem; color: #0f0;">
            <div id="console-log">
                > Inicializando monitor...<br>
                > Aguardando conexão...
            </div>
        </div>
    </div>

    <div class="text-center mt-4">
        <button onclick="window.location.reload()" class="btn btn-dark w-100 py-3">🔄 Atualizar Dados</button>
    </div>

    <script>
        const logDiv = document.getElementById('console-log');
        
        function log(msg) {
            const time = new Date().toLocaleTimeString();
            logDiv.innerHTML += `> [${time}] ${msg}<br>`;
            logDiv.scrollTop = logDiv.scrollHeight;
        }

        async function checkServer() {
            const start = Date.now();
            try {
                const res = await fetch('/api/server-status');
                const latency = Date.now() - start;
                
                if (!res.ok) throw new Error("Erro API");
                
                const data = await res.json();
                
                // Atualiza UI
                document.getElementById('server-dot').className = 'status-dot online';
                document.getElementById('server-text').textContent = 'ONLINE';
                document.getElementById('server-text').style.color = '#00ff00';
                document.getElementById('ping-val').textContent = latency;
                
                document.getElementById('uptime-val').textContent = data.uptime;
                document.getElementById('db-size-val').textContent = data.db_size;

                // Indicador de qualidade da rede baseado no ping
                const netBar = document.getElementById('net-bar');
                if (latency < 100) { netBar.style.width = '100%'; netBar.className = 'progress-bar bg-success'; }
                else if (latency < 500) { netBar.style.width = '70%'; netBar.className = 'progress-bar bg-warning'; }
                else { netBar.style.width = '30%'; netBar.className = 'progress-bar bg-danger'; }

            } catch (e) {
                document.getElementById('server-dot').className = 'status-dot offline';
                document.getElementById('server-text').textContent = 'OFFLINE';
                document.getElementById('server-text').style.color = '#ff0000';
                log("Falha na conexão com servidor!");
            }
        }

        // Info de Rede do Navegador
        if (navigator.connection) {
            document.getElementById('net-type').textContent = navigator.connection.effectiveType.toUpperCase();
            navigator.connection.addEventListener('change', () => {
                document.getElementById('net-type').textContent = navigator.connection.effectiveType.toUpperCase();
                log("Mudança de rede detectada: " + navigator.connection.effectiveType);
            });
        }

        // Loop de verificação (a cada 2 segundos)
        setInterval(checkServer, 2000);
        checkServer();
        log("Monitor iniciado.");
    </script>
</body>
</html>"""

# --- Conteúdo do manifest.json ---
manifest_json = """{
  "name": "AutoGate Monitor",
  "short_name": "Monitor",
  "start_url": "/monitor",
  "display": "standalone",
  "background_color": "#000000",
  "theme_color": "#000000",
  "icons": [
    {
      "src": "https://cdn-icons-png.flaticon.com/512/2942/2942544.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "https://cdn-icons-png.flaticon.com/512/2942/2942544.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}"""

# --- Lógica de Correção ---
base_dir = os.path.dirname(os.path.abspath(__file__))
monitor_path = os.path.join(base_dir, "monitor.html")
static_dir = os.path.join(base_dir, "static")
manifest_path = os.path.join(static_dir, "manifest.json")

# Criar pasta static se não existir
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

# Escrever arquivos corretos
print("Criando arquivos corretos...")
with open(monitor_path, "w", encoding="utf-8") as f:
    f.write(monitor_html)
print(f"✅ Arquivo criado: {monitor_path}")

with open(manifest_path, "w", encoding="utf-8") as f:
    f.write(manifest_json)
print(f"✅ Arquivo criado: {manifest_path}")

# Remover arquivos errados (.txt)
print("Verificando arquivos duplicados/errados...")
arquivos_para_remover = [
    "monitor.html.txt",
    "monitor.txt",
    "static/manifest.json.txt",
    "static/manifest.txt"
]

for arq in arquivos_para_remover:
    caminho_errado = os.path.join(base_dir, arq)
    if os.path.exists(caminho_errado):
        try:
            os.remove(caminho_errado)
            print(f"🗑️ Arquivo incorreto removido: {arq}")
        except Exception as e:
            print(f"⚠️ Não foi possível remover {arq}: {e}")

print("\n🎉 Tudo pronto! Reinicie o servidor e acesse /monitor.")
input("Pressione Enter para sair...")
