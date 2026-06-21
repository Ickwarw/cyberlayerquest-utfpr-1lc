# CyberLayerQuest — UTFPR-1ºLC

Plataforma 2D educacional sobre segurança de redes que ensina os modelos **OSI** (7 camadas) e **TCP/IP** (4 camadas).
Dois personagens se enfrentam: **WhiteHat** (defensor) e **BlackHat** (atacante), cada um com mecânicas únicas por nível.

---

## 1. Download e Instalação

### Requisitos

| Software | Versão |
|---|---|
| Python | 3.12.0 |
| pip | qualquer |

Baixe o Python 3.12 em https://www.python.org/downloads/ e marque a opção **"Add Python to PATH"** durante a instalação.

---

### Instalação do Jogo

```bash
# 1. Entre na pasta do jogo
cd game

# 2. Instale as dependências
pip install -r requirements.txt
```

`requirements.txt` contém:
```
pygame>=2.6.0
```

---

### Instalação do Backend (opcional)

O backend é um servidor FastAPI separado. O jogo funciona completamente sem ele — o multiplayer usa TCP/UDP direto via `netplay.py`.

```bash
cd backend
pip install fastapi uvicorn python-dotenv pydantic
```

---

## 2. Inicialização

### Rodar o Jogo

```bash
cd game
python main.py
```

O jogo abre uma janela 1200×680 pixels. Se aparecer a tela com título "CyberLayerQuest — UTFPR-1ºLC", a instalação está correta.

---

### Controles Padrão

| Ação | Jogador 1 (P1) | Jogador 2 (P2) |
|---|---|---|
| Mover esquerda | A | ← |
| Mover direita | D | → |
| Pular | W | ↑ |

Os controles são configuráveis no menu principal → **Controles**. As configurações são salvas em `game/controls.json`.

---

### Multiplayer Local (LAN / mesma máquina)

Para jogar em dois computadores na mesma rede, ou duas janelas no mesmo PC:

**Criando sala (host):**
1. Abra o jogo → **Multiplayer** → **Criar Sala**
2. Digite um código e senha → clique **Criar**
3. Escolha o nível no seletor de fases → clique **Iniciar Jogo**

**Entrando na sala (cliente):**
1. Abra o jogo em outro terminal ou máquina → **Multiplayer** → **Entrar em Sala**
2. Digite o mesmo código e senha → clique **Entrar**
3. O jogo começa automaticamente quando o host inicia

> O host sempre joga como **WhiteHat**, o cliente como **BlackHat**.
> O primeiro a completar o objetivo vence; o outro recebe Game Over com a mensagem do que o vencedor fez.

---

### Rodar o Backend (opcional)

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API disponível em `http://localhost:8000`. Documentação interativa em `http://localhost:8000/docs`.

---

### Sprites (opcional)

Por padrão, os personagens são desenhados geometricamente. Para usar um spritesheet customizado:

1. Salve o arquivo em `game/sprites/spritesheet.png`
2. Execute `python find_sprites.py` para inspecionar as coordenadas com grade visual
3. O auto-detector escolhe as duas primeiras linhas válidas do sheet automaticamente
4. Para fixar linhas manualmente, edite `SPRITE_CFG_ROWS` no topo de `main.py`

---

## 3. Documentação do Código

### Estrutura do Projeto

```
CyberLayerQuest/
├── game/
│   ├── main.py          # Jogo principal — motor, níveis, telas e multiplayer
│   ├── netplay.py       # Módulo de rede para multiplayer TCP/UDP
│   ├── find_sprites.py  # Utilitário para inspecionar spritesheets
│   ├── requirements.txt # Dependências Python do jogo
│   └── sprites/         # Pasta onde colocar spritesheet.png (opcional)
├── backend/
│   └── main.py          # Servidor FastAPI com WebSocket (opcional)
└── .gitignore
```

---

### `game/main.py`

Arquivo principal com aproximadamente 4 400 linhas. Contém todo o motor do jogo, dados dos níveis, telas e lógica de multiplayer.

---

#### Cabeçalho e Imports (linhas 1–18)

```python
import sys, math, os, json, platform, ctypes
import pygame
from netplay import NetworkManager  # importado com try/except
```

- `sys` — encerra o processo ao fechar a janela
- `math` — funções `sin` e `cos` para animações de braços, pernas e efeitos de glow pulsante
- `os` — caminhos de arquivo portáveis entre Windows, Linux e Mac
- `json` — leitura e escrita de `controls.json`
- `platform` — detecta se o sistema é Windows para usar `GetAsyncKeyState`
- `ctypes` — acessa a API nativa do Windows para leitura global de teclado
- `pygame` — motor gráfico, eventos, fontes e controle de FPS
- `NetworkManager` — importado com `try/except`; se `netplay.py` estiver ausente, a opção de multiplayer fica desabilitada sem travar o jogo

---

#### Constantes (linhas 23–57)

```python
W, H = 1200, 680      # Dimensões da janela em pixels
GRAV = 0.55           # Aceleração gravitacional adicionada a vy por frame
JUMP = -13            # Velocidade vertical inicial do salto (negativo = para cima)
SPEED = 4.8           # Velocidade horizontal do personagem em pixels por frame
FPS = 60              # Frames por segundo alvo
PW, PH = 24, 40       # Largura e altura do personagem (hitbox e desenho)
PANEL_W = 280         # Largura do painel lateral direito com tarefas e dicas
GAME_W = W - PANEL_W  # Largura da área jogável = 920 pixels
HEADER_H = 48         # Altura da barra de status superior
GROUND_H = 8          # Espessura da barra do chão
GROUND_Y = H - GROUND_H  # Coordenada Y do topo do chão
```

---

#### Paleta de Cores (linhas 37–57)

Tuplas RGB nomeadas usadas em todo o código para manter consistência visual:

- `DARK_BG` — fundo azul escuro quase preto
- `EMERALD` — verde esmeralda (WhiteHat, elementos de defesa)
- `RED_HAT` — vermelho (BlackHat, ataques)
- `CYAN` — ciano (elementos de rede, pacotes TCP)
- `YELLOW` — amarelo (chaves, itens dourados)
- `ORANGE` — laranja (avisos, toasts de alerta)
- `PURPLE` — roxo (adulteração, tampering)
- `CABLE_BLUE` — azul para cabos RJ45
- `LED_GREEN / LED_RED` — LEDs piscantes nos servidores
- `SCREEN_BLUE` — cor da tela do monitor CRT
- `NEON_GREEN` — verde neon para efeitos de hacker
- `STEEL` — cinza metálico para estruturas de rack

---

#### Sistema de Sprites (linhas 63–160)

```python
_SPRITE_CANDIDATES = [
    "sprites/spritesheet.png",
    "sprites/sprite.png",
    "sprites/characters.png",
    "spritesheet.png",
]
SPRITE_SHEET_PATH = next((p for p in _SPRITE_CANDIDATES if os.path.exists(p)), None)
SPRITE_CFG_ROWS = None  # None = auto-detectar; [(y_white, y_black)] para fixar manualmente
SPRITES = {}
```

`load_sprites()` — carrega e fatia automaticamente o spritesheet:
1. Testa todas as combinações de `fw` (frame width: 24, 16, 32, 48px) × `fh` (frame height: 32, 24, 48, 16, 40px)
2. Para cada combinação, percorre linhas e conta frames não-transparentes (pixel alpha > 10)
3. Linhas com pelo menos 2 frames válidos são candidatas
4. Escolhe a primeira combinação que encontra 2 ou mais linhas válidas
5. Linha 0 → WhiteHat, linha 1 → BlackHat (ou conforme `SPRITE_CFG_ROWS`)
6. Armazena em `SPRITES[char] = {"right": [...], "left": [...], "size": (w, h)}`
7. Se nenhum spritesheet for encontrado ou nenhuma linha válida detectada, `SPRITES` fica vazio e os personagens são desenhados geometricamente como fallback

---

#### Inicialização do pygame (linhas 162–166)

```python
pygame.init()
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("CyberLayerQuest — UTFPR-1ºLC")
clock = pygame.time.Clock()
load_sprites()
```

- `pygame.init()` — inicializa todos os subsistemas: gráfico, evento, fonte e som
- `screen` — superfície principal onde tudo é desenhado a cada frame
- `clock` — objeto que limita o loop ao FPS configurado
- `load_sprites()` — chamado aqui pois pygame precisa estar ativo para carregar imagens

---

#### Teclado Global — GetAsyncKeyState (linhas 168–220)

Problema: `pygame.key.get_pressed()` só lê teclas quando a janela do pygame tem foco. Em multiplayer com duas janelas abertas no mesmo PC, o jogador P1 não conseguia mover quando a janela do P2 estava em foco.

Solução: `GetAsyncKeyState` — função da API Win32 que lê o estado do teclado independente de qual janela tem foco.

```python
_IS_WINDOWS = platform.system() == "Windows"
if _IS_WINDOWS:
    _u32 = ctypes.windll.user32
    def _vk_down(vk: int) -> bool:
        return bool(_u32.GetAsyncKeyState(vk) & 0x8000)
```

- O bit 0x8000 (mais significativo) indica que a tecla está pressionada no momento
- `_PG_TO_VK` — dicionário que converte constante pygame (ex: `K_a = 97`) para Virtual-Key code Windows (ex: `0x41`)
- `_build_vk_map()` — preenche o mapa para letras a–z, dígitos 0–9, F1–F12 e teclas especiais como setas, Espaço, Enter e Backspace
- `is_key_down(pg_key)` — retorna True se a tecla está pressionada; usa `GetAsyncKeyState` no Windows e `pygame.key.get_pressed()` como fallback no Linux/Mac

---

#### Configuração de Controles (linhas 222–272)

```python
_DEFAULT_CONTROLS = {
    "P1": {"left": K_a,    "right": K_d,     "jump": K_w},
    "P2": {"left": K_LEFT, "right": K_RIGHT, "jump": K_UP},
}
CONTROLS = {"P1": dict(...), "P2": dict(...)}
```

- `CONTROLS` — dicionário global com os keycodes atuais de cada jogador
- `_CONTROLS_FILE` — caminho para `game/controls.json`
- `_save_controls()` — converte keycodes para nomes legíveis via `pygame.key.name()` e salva JSON (ex: `{"P1": {"left": "a", "right": "d", "jump": "w"}}`)
- `_load_controls()` — lê o JSON e converte nomes para keycodes via `pygame.key.key_code()`; chamado na inicialização do jogo
- `get_actions(slot)` — recebe `"P1"` ou `"P2"` e retorna `{"left": bool, "right": bool, "jump": bool}` usando `is_key_down`

---

#### Fontes (linhas 274–290)

```python
FONT_BIG   = SysFont("Segoe UI", 52, bold=True)  # título de fase, overlays de vitória
FONT_MED   = SysFont("Segoe UI", 28, bold=True)  # headers e botões
FONT_LG    = SysFont("Segoe UI", 26, bold=True)  # diálogos de minigame
FONT_SM    = SysFont("Segoe UI", 18)              # texto normal do painel
FONT_XS    = SysFont("Segoe UI", 14)              # subtítulos e labels
FONT_EMOJI = SysFont("Segoe UI Emoji", 20)        # ícones emoji nos pickups
FONT_TINY  = SysFont("Segoe UI", 12)              # labels de dispositivos de rede
```

O bloco `try/except` usa `pygame.font.Font(None, tamanho)` como fallback se Segoe UI não estiver instalado no sistema.

---

#### Funções Auxiliares Gerais (linhas 296–328)

- `hex_to_rgb(h)` — converte string `"#rrggbb"` para tupla `(r, g, b)`; usado para as cores do gradiente de céu de cada nível
- `lerp_color(c1, c2, t)` — interpolação linear entre duas cores RGB; `t=0.0` retorna c1, `t=1.0` retorna c2; usado no gradiente de fundo
- `draw_text_centered(surf, text, font, color, cx, cy)` — renderiza texto centralizado no ponto (cx, cy)
- `draw_text(surf, text, font, color, x, y)` — renderiza texto com canto superior esquerdo em (x, y)
- `draw_rect_alpha(surf, color, rect, alpha)` — retângulo semi-transparente usando `Surface` com flag `SRCALPHA`
- `clamp(v, lo, hi)` — limita o valor v ao intervalo fechado [lo, hi]; usado na física e posicionamento de câmera
- `wrap_text(text, font, max_w)` — quebra texto em lista de linhas que cabem dentro de `max_w` pixels; usado no painel de tarefas

---

#### Funções de Efeitos Visuais (linhas 321–507)

- `draw_glow(surf, color, cx, cy, radius, alpha)` — brilho radial desenhando círculos concêntricos com alpha decrescente do centro para fora; usado em pickups, olhos do BlackHat e zonas de entrega
- `draw_neon_rect(surf, color, rect, width, glow, radius)` — retângulo com borda neon e camada de glow externa semi-transparente
- `draw_server_rack_detailed(surf, x, y, w, h, label)` — rack de servidor estilo pixel art com 8 unidades de disco, LEDs RGB piscando em padrão assíncrono por unidade e label no topo em ciano
- `draw_monitor_detailed(surf, x, y, w, h, label)` — monitor CRT com tela azul escura pulsante (brilho varia com seno do tempo), texto "SYS:XX>_" rolando na tela e brilho de borda ciano
- `draw_cable_bundle(surf, x1, y1, x2, y2, color, thickness)` — linha de cabo com reflexo claro no topo e conectores metálicos retangulares a cada 40px ao longo do trajeto
- `draw_datacenter_bg(surf, x, y, w, h)` — data center com 3 colunas de servidores, 5 unidades por coluna, LEDs de 4 cores em padrão assíncrono e painel de gerenciamento de cabos na base com conectores azuis
- `draw_router_detailed(surf, x, y, w, h, label)` — roteador com antena, círculos de sinal ciano expandindo (animados por tempo), e 3 LEDs piscando
- `draw_binary_rain(surf, sky_top)` — chuva de "0" e "1" estilo Matrix no fundo; apenas aparece quando o brilho do céu é menor que 150 (fundos escuros); cada coluna tem velocidade e alpha diferentes para variar o visual

---

#### Dados dos Níveis (linhas 534–1210)

São quatro coleções de dicionários, cada uma com todos os parâmetros de um nível.

**Campos de cada nível:**

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | int | Identificador interno da fase |
| `name` | str | Nome exibido na HUD durante o jogo |
| `spawn` | tuple | Posição inicial (x, y) do jogador |
| `sky` | tuple de 2 hex | Cores do gradiente de céu (topo, base) |
| `ground_color` | hex | Cor da barra do chão |
| `centerpiece` | dict | Elemento central decorativo (kind, x, y, w, h) |
| `platforms` | list | Lista de plataformas e dispositivos do nível |
| `pickups` | list | Itens coletáveis pelo WhiteHat |
| `pickups_black` | list | Itens coletáveis pelo BlackHat |
| `enemies` | list | Inimigos que perseguem ou patrulham contra o WhiteHat |
| `enemies_black` | list | Inimigos contra o BlackHat |
| `goal` | dict | Zona de entrega do WhiteHat (x, y, w, h, kind) |
| `goal_black` | dict | Zona de entrega do BlackHat |
| `need` | str | Tipo de item que o WhiteHat precisa entregar para vencer |
| `need_black` | str | Tipo de item que o BlackHat precisa entregar para vencer |
| `lesson` | str | Texto educativo sobre a camada mostrado no painel |
| `tasks_white` | list | Passos da missão exibidos ao WhiteHat |
| `tasks_black` | list | Passos da missão exibidos ao BlackHat |
| `thoughts_text` | list | Dicas rotativas exibidas no canto inferior da tela |

**Tipos de plataforma (`kind`):**

| kind | Descrição |
|---|---|
| `bridge` | Plataforma navegável cor madeira com ripas verticais decorativas |
| `server` | Servidor visual grande não navegável |
| `rack` | Rack de servidor com LEDs e unidades de disco detalhados |
| `monitor` | Monitor CRT com tela animada |
| `scanner` | Dispositivo scanner ou roteador cor roxa |
| `laptop / pc / phone / tablet` | Dispositivos cliente decorativos nas extremidades |

**Tipos de pickup:**

| type | Usuário | Camada | Descrição |
|---|---|---|---|
| `cable` | WhiteHat | Física / Acesso | Cabo RJ45 para conectar servidores |
| `mac_cert` | WhiteHat | Enlace | Certificado MAC para autenticação no switch |
| `firewall_key` | WhiteHat | Rede / Internet | Regra de firewall para proteger o roteador |
| `terminal` | WhiteHat | Transporte | Abre diálogo para escrever mensagem que se fragmenta em 3 partes |
| `tls_cert` | WhiteHat | Sessão | Certificado TLS para autenticar sessão SSH |
| `hash` | WhiteHat | Apresentação / Aplicação | Hash de integridade dos dados |
| `dos_amp` | BlackHat | Física | Amplificador de ataque DDoS |
| `arp_spoofer` | BlackHat | Enlace | Ferramenta de ARP Spoofing para envenenar switch |
| `ip_bomb` | BlackHat | Rede | Bomba IP para derrubar roteadores |
| `syn_packet` | BlackHat | Transporte | Pacote SYN Flood — 3 necessários para o ataque |
| `cookie_grab` | BlackHat | Sessão | Cookie Stealer para roubo de sessão |

**Flags especiais de nível:**

| Flag | Descrição |
|---|---|
| `minigame_layer=True` | Ativa o minigame de Cifra de César nesta fase |
| `ssh_layer=True` | WhiteHat deve definir senha SSH antes de pegar o hash |
| `tamper_on_pickup=True` | BlackHat abre diálogo de adulteração ao coletar o hash |
| `confirm_phrase` | Frase que BlackHat deve interceptar e redigitar no servidor |
| `fragment_positions` | Lista de coordenadas onde os 3 fragmentos aparecem após escrever no terminal |

**`LEVELS`** — 4 fases do modelo TCP/IP (versão original do projeto, ainda disponível no código)

**`LEVELS_OSI`** — 7 fases seguindo o modelo OSI completo:
- L1 Física: WhiteHat pega cabo RJ45 × BlackHat usa DDoS Amplifier
- L2 Enlace: WhiteHat pega Certificado MAC × BlackHat usa ARP Spoofing
- L3 Rede: WhiteHat pega Regra de Firewall × BlackHat usa IP Bomb
- L4 Transporte: WhiteHat fragmenta mensagem em 3 pacotes TCP × BlackHat faz SYN Flood
- L5 Sessão: WhiteHat pega Certificado TLS × BlackHat rouba Cookie
- L6 Apresentação: WhiteHat cifra com César × BlackHat decifra (minigame)
- L7 Aplicação: WhiteHat protege hash com SSH × BlackHat adultera a mensagem

**`LEVELS_TCPIP`** — 4 fases seguindo o modelo TCP/IP:
- L1 Acesso à Rede: cabo RJ45 × DDoS Amplifier
- L2 Internet: Regra de Firewall × IP Bomb
- L3 Transporte: mensagem fragmentada × SYN Flood com confirmação por digitação
- L4 Aplicação: hash protegido por SSH × interceptar e confirmar frase digitando

**`CESAR_STATE`** — dicionário global persistente entre fases para o minigame de Cifra de César:
- `original` — mensagem digitada pelo WhiteHat no terminal
- `encrypted` — versão cifrada com o deslocamento `shift`
- `shift` — número de posições deslocadas escolhido (1 a 9)
- `ssh_locked` — True se WhiteHat ativou proteção SSH
- `ssh_password` — senha SSH definida pelo WhiteHat

**`DEVICE_COLORS`** — lookup de cor RGB por tipo de dispositivo (rack, server, monitor, etc.)

**`ENEMY_COLORS`** — lookup de cor por tipo de inimigo (sniff=vermelho, dos=laranja, tamper=roxo, defender=azul)

**`ENEMY_ICONS`** — lookup de emoji por tipo de inimigo exibido sobre eles (👀 💥 ⚠️ 🛡)

---

#### Funções de Desenho do Jogo (linhas ~1246–1600)

- `draw_player(surf, x, y, char, facing, anim_frame)` — desenha o personagem:
  - Se spritesheet disponível: blit do frame correspondente ajustando tamanho para PW×PH
  - Sem spritesheet — desenho geométrico detalhado:
    - **WhiteHat**: terno branco, gravata preta, chapéu branco alto com banda preta, sapatos pretos, pele clara
    - **BlackHat**: roupa toda preta, capa vermelha nas laterais, chapéu preto alto com banda vermelha, olhos vermelhos com glow pulsante, aura maligna
  - Animação: pernas alternam posição com `abs(sin(anim_frame))`, braços balançam com `sin(anim_frame * 1.2)`
  - `facing` determina para qual lado o personagem olha: 1 = direita, -1 = esquerda

- `draw_device(surf, plat)` — despacha para a função de desenho correta baseado em `plat["kind"]`:
  - `bridge` → retângulo marrom com ripas de madeira verticais decorativas
  - `rack / server` → chama `draw_server_rack_detailed`
  - `monitor` → chama `draw_monitor_detailed`
  - `router` → chama `draw_router_detailed`
  - outros → caixa colorida genérica com label centralizado

- `draw_pickup(surf, p)` — desenha item coletável com animação de "bob" (sobe e desce suavemente com `sin(tempo / 400)`):
  - `cable` — conector RJ45 azul com 4 pinos verdes; fica como socket vazio após coletado
  - `hash` — círculo verde esmeralda com emoji ✅ e glow pulsante
  - `packet` (fragmento TCP) — caixa ciano com número "N/3" e linha de scan animada varrendo de cima a baixo
  - `terminal` — tela verde escura com cursor piscante e símbolo >_
  - `firewall_key` — escudo com chama laranja
  - `mac_cert` — crachá dourado com símbolo MAC
  - `tls_cert` — cadeado ciano com label TLS
  - `dos_amp` — antena vermelha pulsante com símbolo DDoS
  - `arp_spoofer` — placa de rede violeta com seta de redirecionamento
  - `ip_bomb` — bomba com rastro de explosão vermelho
  - `syn_packet` — envelope vermelho com numeração sequencial
  - `cookie_grab` — cookie marrom com glow laranja

---

#### Classes de Interface (linhas ~1600–2100)

**`Toast`** — notificação temporária que aparece na tela:
- Construtor recebe texto, cor e duração em milissegundos
- `update()` — decrementa tempo; retorna False quando expirado para remoção da lista
- `draw(surf)` — retângulo arredondado com sombra e texto centralizado, posição empilhada automaticamente
- Várias toasts coexistem e empilham verticalmente no topo da tela

**`Button`** — botão clicável:
- Construtor: `(x, y, w, h, text, bg_color, text_color)`
- `handle_event(ev)` — retorna True quando o botão é clicado com mouse
- `draw(surf)` — retângulo com hover (clareia 20% ao passar o mouse) e borda neon

**`InputBox`** — campo de texto editável:
- Ativado por clique; mostra cursor piscante quando ativo
- `handle_event(ev)` — captura `KEYDOWN`: Backspace apaga último caractere, outros caracteres imprimíveis são adicionados
- `draw(surf)` — caixa com borda que muda de cor quando ativa; texto placeholder em cinza quando vazio

---

#### Minigames (linhas ~2100–2400)

**`CesarMiniGame`** — Cifra de César (OSI L6 e TCP/IP L4):
- Modo `"encrypt"` (WhiteHat): digita a mensagem, escolhe deslocamento 1–9 com botões, vê prévia criptografada em tempo real. Ao confirmar, salva em `CESAR_STATE` e posiciona fragmentos no mapa.
- Modo `"decrypt"` (BlackHat): vê o texto cifrado interceptado, navega entre deslocamentos 1–9 com setas ← →, prévia do texto decifrado atualiza ao vivo. Precisa confirmar quando achar a mensagem original.
- Estado compartilhado em `CESAR_STATE` para que ambos trabalhem com a mesma cifra.

**`MessageWriteDialog`** — Fragmentação TCP (OSI L4 / TCP/IP L3):
- WhiteHat digita uma mensagem no terminal do PC
- Ao confirmar, a mensagem é dividida em 3 fragmentos numerados: `[msg[:N]] 1/3`, `[msg[N:2N]] 2/3`, `[msg[2N:]] 3/3`
- Os fragmentos aparecem fisicamente no mapa nas posições `fragment_positions`
- WhiteHat deve coletá-los em ordem numérica; coleta fora de ordem é ignorada

**`TypeConfirmDialog`** — Confirmação de Interceptação (TCP/IP L4 BlackHat):
- Aparece quando BlackHat chega ao servidor com a frase interceptada
- Mostra a frase que foi interceptada no topo do diálogo
- BlackHat deve redigitar a frase exatamente (comparação case-insensitive com `.upper()`)
- Tentativas erradas mostram mensagem de erro e limpam o campo
- Acerto define `state = "win"` imediatamente

**`AlterMessageDialog`** — Adulteração de Mensagem (OSI L7 BlackHat):
- Aparece quando BlackHat coleta o hash num nível com `tamper_on_pickup=True`
- Mostra a mensagem original interceptada
- BlackHat digita uma versão adulterada — a validação rejeita texto idêntico ao original
- Ao confirmar, o item é marcado como coletado e a mensagem adulterada é guardada para exibição no toast de entrega

---

#### `compute_win_msg(level_data, char)` (linhas ~2400–2460)

Gera uma frase contextual de vitória ou derrota baseada exatamente no que o jogador executou nesta fase:

```python
def compute_win_msg(level_data: dict, char: str) -> str
```

- Lê `need` (WhiteHat) ou `need_black` (BlackHat) do dicionário do nível ativo
- Consulta tabelas internas `_W` e `_B` com frases específicas por tipo de item
- Refinamentos para o tipo `"hash"` que aparece em múltiplos níveis:
  - WhiteHat + `ssh_layer=True` → frase menciona proteção SSH
  - WhiteHat + `"L6"` no nome → frase menciona Cifra de César
  - BlackHat + `tamper_on_pickup=True` → frase menciona adulteração de payload
  - BlackHat + `"L6"` no nome → frase menciona quebra da cifra César
- Usado na tela de vitória do vencedor e na mensagem de derrota do perdedor em multiplayer

---

#### Classe `Player` (linhas ~2460–2600)

Representa o personagem controlável pelo jogador:

```python
class Player:
    def __init__(self, x, y, char)
```

**Atributos principais:**
- `x, y` — posição atual em pixels
- `vx, vy` — velocidade horizontal e vertical em pixels por frame
- `on_ground` — True quando o personagem está apoiado em plataforma ou chão
- `char` — `"white"` ou `"black"`, define aparência e itens disponíveis
- `facing` — 1 para direita, -1 para esquerda; atualizado com base em `vx`
- `anim_frame` — contador incrementado a cada frame para animar membros
- `has_cable / has_hash / has_mac_cert / has_firewall_key / has_tls_cert` — flags de itens coletados
- `fragments` — lista de IDs de fragmentos TCP coletados (deve ser [1, 2, 3] em ordem)
- `syn_count` — número de pacotes SYN coletados pelo BlackHat (vitória ao chegar em 3)

**`update(actions, platforms)`** — aplica física a cada frame:
1. `vx` definido por `actions["left"]` e `actions["right"]`
2. `vy += GRAV` — gravidade acumulada
3. Move `x += vx`, testa colisão horizontal com cada plataforma
4. Move `y += vy`, testa colisão vertical — se colidir pelo topo da plataforma: `vy = 0`, `on_ground = True`, `y = plataforma.top - PH`
5. Limita `x` ao intervalo `[0, GAME_W - PW]` e `y` ao chão

---

#### Classe `GameLevel` (linhas ~2600–3600)

Motor de uma fase individual — contém estado completo do jogo durante o gameplay:

```python
class GameLevel:
    def __init__(self, level_data, char, control_slot="P1")
```

**Atributos principais:**
- `data` — dicionário do nível com todas as configurações
- `char` — personagem do jogador local (`"white"` ou `"black"`)
- `control_slot` — `"P1"` ou `"P2"` para buscar os bindings corretos de teclado
- `state` — estado atual: `"playing"` | `"win"` | `"fail"`
- `player` — instância de `Player`
- `minigame` — instância de minigame ativa (None quando não há)
- `minigame_stage` — controla progresso multi-etapa do minigame César (0=inicial, 1=aberto)
- `intercept_phrase` — frase que BlackHat interceptou (para `TypeConfirmDialog`)
- `_pending_pickup` — referência ao pickup aguardando conclusão de minigame
- `remote_x / remote_y / remote_facing / remote_frame / remote_char` — estado do oponente recebido via rede
- `toasts` — lista de instâncias `Toast` atualmente visíveis na tela
- `fail_reason` — texto exibido quando `state = "fail"`

**Métodos principais:**

- `update(keys=None)` — loop principal da fase a cada frame:
  1. Se minigame ativo, retorna imediatamente (pausa física durante diálogos)
  2. Verifica `state != "playing"` e retorna
  3. Chama `get_actions(self.control_slot)` para ler teclado global
  4. Atualiza `player.update(actions, platforms)`
  5. Move inimigos (patrulha entre `minX/maxX` ou perseguição se `chase=True`)
  6. Verifica colisão com inimigos (`state = "fail"`)
  7. Chama `_check_pickups()` — detecta proximidade e coleta de itens
  8. Chama `_check_minigame_triggers()` — abre minigames por proximidade
  9. Chama `check_goal()` — verifica condição de vitória
  10. Atualiza toasts (remove os expirados)

- `_handle_pickup(p)` — lógica de coleta de item por tipo:
  - `cable` → `player.has_cable = True`; toast verde confirmando coleta
  - `mac_cert / tls_cert / firewall_key` → ativa flag correspondente; toast informativo
  - `terminal` → abre `MessageWriteDialog`; fragmentos aparecem no mapa ao fechar
  - `hash` (BlackHat + `tamper_on_pickup`) → abre `AlterMessageDialog`; item fica pendente
  - `hash` (BlackHat + `confirm_phrase`) → salva frase em `intercept_phrase`; toast com a frase
  - `hash` (WhiteHat ou BlackHat normal) → `player.has_hash = True`
  - `syn_packet` → incrementa `player.syn_count`; ao chegar em 3: `state = "win"`

- `check_goal()` — verifica se jogador está na zona de entrega com o item correto:
  - `need = "cable"` → verifica `player.has_cable`
  - `need = "fragments3"` → verifica `player.fragments == [1, 2, 3]`
  - `need = "syn_flood3"` → verifica `player.syn_count >= 3`
  - `need = "intercepted_phrase"` → abre `TypeConfirmDialog` com a frase interceptada
  - outros → verifica flag correspondente em `player`
  - Sucesso: `state = "win"`; falha: toast de aviso

- `_check_minigame_triggers()` — detecta proximidade de zonas especiais:
  - WhiteHat perto do terminal numa fase com `minigame_layer` → abre `CesarMiniGame("encrypt")`
  - BlackHat perto do centro numa fase com `minigame_layer` → auto-gera cifra César se não existir, abre `CesarMiniGame("decrypt")`

- `_finish_minigame(mg)` — processa resultado do minigame ao fechar:
  - `CesarMiniGame encrypt` → armazena em `CESAR_STATE`, cria pickups de fragmento no mapa
  - `CesarMiniGame decrypt` → `state = "win"` para BlackHat
  - `MessageWriteDialog` → cria os 3 fragmentos nos `fragment_positions` do nível
  - `TypeConfirmDialog` success → `state = "win"` para BlackHat
  - `AlterMessageDialog` altered → marca `_pending_pickup` como coletado, toast com mensagem adulterada

- `add_toast(text, color)` — cria e adiciona instância `Toast` à lista ativa

- `draw(surf)` — renderiza toda a fase na superfície passada (chamado a cada frame):
  1. Gradiente de céu com `lerp_color` entre as duas cores do nível
  2. Binary rain animado nos fundos escuros
  3. Todas as plataformas e dispositivos via `draw_device`
  4. Centerpiece central (data center / globo / disco / cloud hub)
  5. Pickups com animação de bob
  6. Inimigos com cor por tipo, ícone emoji e sombra
  7. Oponente remoto em `remote_x, remote_y` com char e facing recebidos pela rede
  8. Personagem local com `draw_player`
  9. Linha de cabo sendo carregado (do jogador até o servidor de origem)
  10. Zona de entrega com borda pulsante verde ou vermelha
  11. Painel lateral direito: tarefas da missão, dica rotativa, status de itens coletados
  12. Header superior: barra de HP, nome da fase, personagem e modelo de rede
  13. Toasts empilhados no topo
  14. Overlay de vitória (fundo escuro + mensagem verde + `compute_win_msg`) ou derrota (vermelho + `fail_reason`)
  15. Minigame ativo desenhado por cima de tudo

---

#### Classe `ControlsScreen` (linhas ~3600–3750)

Tela de configuração de controles acessada pelo menu principal → **Controles**:

- Tabela com colunas P1 e P2, linhas Esquerda, Direita e Pular
- Cada célula exibe o nome da tecla atual (via `pygame.key.name()`) e um botão "Alterar"
- Ao clicar "Alterar", entra em modo de escuta: a próxima tecla pressionada substitui o binding atual
- Botão "Padrão" restaura WASD para P1 e setas para P2
- Toda mudança salva imediatamente em `controls.json` via `_save_controls()`

---

#### Classe `MenuScreen` (linhas ~3750–3850)

Tela inicial do jogo com fundo animado de binary rain e título pulsante:

- Botão **OSI Model** → `result = "osi"` para selecionar as 7 fases OSI
- Botão **TCP/IP Model** → `result = "tcpip"` para selecionar as 4 fases TCP/IP
- Botão **Multiplayer** → `result = "multiplayer"` para abrir a tela de sala
- Botão **Controles** → `result = "controles"` para abrir a tela de configuração
- Botão **Sair** → encerra o processo

---

#### Classe `CharacterSelect` (linhas ~3850–3950)

Tela de escolha de personagem após selecionar o modelo de rede:

- Exibe WhiteHat (esquerda) e BlackHat (direita) com preview animado do personagem
- Cada lado mostra descrição do papel: defender a rede vs. atacar a rede
- Clique em um personagem define `self.char` e `self.result = "selected"` para avançar

---

#### Classe `RoomScreen` (linhas ~3950–4150)

Tela de multiplayer que gerencia criação e entrada em salas:

**Modo host (`mode="criar"`):**
- Campos de texto: Código da sala e Senha
- Botão "Criar" → instancia `NetworkManager` e chama `net.host(code, password)`
- Enquanto aguarda o cliente conectar, exibe o status e o **seletor de nível**
- Seletor de nível: grade de botões gerada dinamicamente, um por fase disponível
- `_level_btn_w(n)` — calcula largura de cada botão para preencher a tela sem transbordar
- `_level_btn_pos(i, n)` — calcula posição x, y centralizada do botão de índice `i`
- `level_choice` — índice da fase selecionada (0 a N-1)
- Botão "Iniciar Jogo" → `_send_start()` envia `{"type": "start", "model": ..., "level": level_choice}`

**Modo cliente (`mode="entrar"`):**
- Campos: Código e Senha
- Botão "Entrar" → instancia `NetworkManager` e chama `net.join(code, password)`
- Aguarda mensagem `welcome` (definida no handshake TCP) e depois `start` do host

**Status exibido em tempo real:**
- `hosting` → "Aguardando jogador..."
- `searching` → "Procurando sala na rede..."
- `connected` (host) → seletor de nível ativo + botão Iniciar
- `connected` (cliente) → "Conectado! Aguardando host iniciar..."
- `error` → mensagem de erro específica (ex: "Código ou senha incorretos")
- `disconnected` → "Conexão perdida"

---

#### Classe `Game` (linhas ~4150–4415)

Controlador principal que gerencia todas as telas e o loop de jogo:

```python
class Game:
    def __init__(self)
    def run(self)
```

**Atributos:**
- `screen_state` — tela atual: `"menu"` | `"char_select"` | `"room"` | `"game"`
- `menu / room / char_select` — instâncias das telas auxiliares
- `gl` — instância ativa de `GameLevel`
- `net` — instância de `NetworkManager` (None em jogo solo)
- `char` — personagem escolhido (`"white"` ou `"black"`)
- `active_levels` — lista de níveis ativa (LEVELS_OSI ou LEVELS_TCPIP)
- `current_level` — índice do nível atual na lista `active_levels`
- `_net_timer` — acumulador de tempo para enviar posição a 20Hz (a cada 50ms)

**`run()`** — loop principal do jogo:
1. `clock.tick(FPS)` — limita para 60 FPS e retorna delta time
2. Processa eventos pygame (QUIT fecha, ESC volta ao menu)
3. Despacha para o estado atual: menu, room ou game
4. Verifica transições (botões clicados → muda `screen_state`)
5. `pygame.display.flip()` — exibe o frame renderizado

**`start_level(idx)`** — inicializa uma fase específica:
- Cria `GameLevel(active_levels[idx], char, control_slot)`
- `control_slot = "P1"` em jogo solo ou host; `"P2"` quando é o cliente do multiplayer
- Reseta `CESAR_STATE` para que a cifra comece limpa
- Define `screen_state = "game"`

**`_update_game()`** — atualiza e renderiza o jogo a cada frame:
1. Se multiplayer e 50ms se passaram, chama `_net_update(gl)`
2. Chama `gl.update()` para atualizar física e lógica
3. Chama `gl.draw(screen)` para renderizar o frame
4. Se `gl.state == "win"` → envia `{"type": "win"}` pela rede, exibe overlay, aguarda tecla, avança para o próximo nível (`current_level + 1`) ou volta ao menu
5. Se `gl.state == "fail"` → exibe overlay de derrota com `fail_reason`, aguarda tecla

**`_net_update(gl)`** — sincronização multiplayer (executada a cada ~50ms):
- Envia posição local: `{"type": "pos", "x": ..., "y": ..., "facing": ..., "frame": ...}`
- Processa todas as mensagens recebidas de `net.poll()`:
  - `"pos"` → atualiza `gl.remote_x`, `gl.remote_y`, `gl.remote_facing`, `gl.remote_frame` para renderizar o oponente
  - `"win"` → oponente completou o objetivo; chama `compute_win_msg` para o oponente e define `gl.state = "fail"` com a mensagem contextual
  - `"peer_disconnect"` → adiciona toast de aviso e limpa a conexão

---

### `game/netplay.py`

Módulo de rede para multiplayer local sem servidor externo. Usa TCP para comunicação confiável e UDP para descoberta automática de sala na rede.

---

#### Constantes

```python
PORT_TCP = 12345        # porta da conexão peer-to-peer entre host e cliente
PORT_UDP = 12346        # porta do anúncio de sala via broadcast UDP
BCAST_INTERVAL = 1.5    # segundos entre cada anúncio UDP pelo host
```

---

#### Funções auxiliares

- `_get_local_ip()` — descobre o IP local conectando brevemente (sem enviar dados) ao `8.8.8.8:80`; fallback para `127.0.0.1` se não houver rede
- `_subnet_broadcast(local_ip)` — converte `192.168.1.42` em `192.168.1.255` para broadcast de sub-rede
- `_hash_pass(p)` — primeiros 10 caracteres do MD5 da senha; evita trafegar senha em texto claro na rede
- `_recv_line(sock, timeout)` — lê bytes do socket byte a byte até encontrar `\n`; usado no handshake inicial com timeout de 15 segundos

---

#### Classe `NetworkManager`

```python
class NetworkManager:
    mode: str    # "host" | "client"
    status: str  # idle | hosting | searching | connected | error | disconnected
    my_ip: str   # IP local do computador
    peer_ip: str # IP do computador remoto
```

**`host(code, password)`** — inicia o servidor TCP e aguarda um cliente:
1. Abre servidor TCP em `0.0.0.0:12345` com `SO_REUSEADDR` para reusar a porta imediatamente
2. Inicia `_broadcast_loop` em thread separada que anuncia a sala via UDP
3. `_broadcast_loop` envia pacote JSON para `255.255.255.255`, sub-rede e `127.0.0.1` a cada 1.5s
4. `srv.accept()` com timeout de 90 segundos aguarda conexão de cliente
5. Ao receber conexão, lê handshake JSON: `{"type": "join", "code": ..., "ph": hash_da_senha}`
6. Valida código e hash; se errado, responde com erro e fecha
7. Se correto, responde `{"type": "welcome", "char": "black"}` e inicia I/O threads
8. Define `status = "connected"` e `peer_ip` com o IP do cliente

**`join(code, password)`** — procura e conecta a uma sala:
1. `_discover_host()` — abre socket UDP em `0.0.0.0:12346` e ouve por até 15 segundos
2. Ao receber `room_announce` com código e hash correspondentes, extrai o IP do host do pacote
3. Conecta TCP ao host descoberto em `port 12345` com timeout de 10 segundos
4. Envia handshake: `{"type": "join", "code": ..., "ph": hash_da_senha}`
5. Aguarda resposta `{"type": "welcome"}`; se recusar, define status de erro
6. Inicia I/O threads e define `status = "connected"`

**`send(msg: dict)`** — envia mensagem de forma thread-safe:
- Coloca o dicionário na `_send_q` (queue.Queue) que a thread de envio processa

**`poll() → list[dict]`** — retorna todas as mensagens recebidas desde a última chamada:
- Drena `_recv_q` de forma não-bloqueante e retorna lista

**`close()`** — encerra a conexão:
- Sinaliza stop para broadcast UDP
- Coloca `None` na fila de envio para parar a thread de send
- Fecha sockets TCP server e peer connection

**`_start_io(conn)`** — inicia as duas threads de I/O após handshake completo:
- `_recv_loop` — lê chunks de até 4096 bytes, acumula em buffer, divide por `\n`, faz parse JSON e coloca em `_recv_q`. Ao detectar socket fechado (bytes vazios), coloca `{"type": "peer_disconnect"}` na fila.
- `_send_loop` — espera mensagens em `_send_q` com timeout de 0.5s, serializa para `json + "\n"` e envia. Para quando recebe `None` na fila.

---

### `game/find_sprites.py`

Utilitário gráfico para inspecionar um spritesheet antes de configurar o jogo:

- Abre `sprites/spritesheet.png` em janela pygame escalada automaticamente para caber na tela
- Sobrepõe grade com célula ajustável: tecla `→` aumenta, `←` diminui o tamanho da célula
- Clique em qualquer ponto mostra no terminal: coordenadas do pixel, coordenadas da célula e tamanho
- Útil para identificar `y_white` e `y_black` para configurar `SPRITE_CFG_ROWS` manualmente
- Encerra com ESC ou fechar a janela

---

### `backend/main.py`

Servidor FastAPI opcional com comunicação por WebSocket. Não é necessário para o jogo funcionar — o multiplayer do jogo usa `netplay.py` direto.

---

#### Inicialização (linhas 1–48)

```python
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # pygame sem janela gráfica
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")  # pygame sem saída de áudio
pygame.init()
app = FastAPI(title="CyberLayerQuest API — UTFPR")
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
```

- pygame é inicializado com drivers "dummy" para usar apenas as funções de física (`pygame.Rect.colliderect`) sem abrir janela
- CORS liberado para todas as origens durante desenvolvimento (restringir em produção)

---

#### Modelos de Dados (linhas 54–92)

- `CriarSalaRequest(BaseModel)` — schema Pydantic para criação de sala: `{codigo, senha, personagem}`
- `EntrarSalaRequest(BaseModel)` — schema para entrada em sala: `{codigo, senha, personagem}`
- `Jogador` — dataclass com websocket ativo, nome do personagem e flag de pronto
  - `dict_info()` — retorna dicionário serializável com personagem e status de pronto
- `Sala` — dataclass com código, senha, dicionário de jogadores e fase atual
  - `cheia` — property que retorna True quando há 2 jogadores conectados
  - `jogadores_info()` — lista serializável de todos os jogadores
- `salas` — dicionário global `{codigo: Sala}` mantido em memória enquanto o servidor roda

---

#### Física Server-Side (linhas 97–120)

```python
def verificar_colisao(px, py, plataformas) -> dict
```

Recebe posição do jogador e lista de plataformas, usa `pygame.Rect.colliderect` para detectar colisões e retorna se está no chão, a posição Y corrigida e a velocidade vertical corrigida. Usa a mesma lógica do cliente para garantir consistência entre os dois.

---

#### Endpoints HTTP (linhas 127–159)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Health check — retorna nome do projeto, instituição e status online |
| POST | `/salas/criar` | Cria nova sala; retorna 409 se código já existe |
| GET | `/salas/{codigo}` | Retorna estado completo da sala — jogadores, fase atual, se está cheia |
| DELETE | `/salas/{codigo}` | Remove a sala permanentemente; retorna 404 se não existe |

---

#### WebSocket (linhas 166–256)

`/ws/{codigo}/{senha}/{personagem}` — conexão persistente mantida durante toda a partida:

- Valida sala (retorna código 4040 se não existe), senha (4031 se incorreta) e capacidade (4090 se cheia)
- Ao aceitar, gera UUID único para o jogador e o adiciona ao dicionário da sala
- Faz broadcast de `jogador_entrou` para todos na sala
- Quando sala completa (2 jogadores), broadcast `sala_cheia` com `"iniciar": True`

**Mensagens processadas em loop:**

| `tipo` | Comportamento |
|---|---|
| `posicao` | Adiciona o ID do remetente e repassa para todos os outros jogadores |
| `colisao` | Verifica colisão server-side e responde apenas ao remetente com posição corrigida |
| `evento` | Broadcast de eventos de jogo (coletou item, chegou ao goal, etc.) para todos |
| `proxima_fase` | Atualiza `sala.fase_atual` e faz broadcast de `mudar_fase` |
| `ping` | Responde `pong` para manter a conexão ativa |

- `_broadcast(sala, msg, excluir)` — envia para todos os jogadores da sala, registra conexões mortas e as remove automaticamente
- `WebSocketDisconnect` → remove o jogador, avisa os demais; se sala ficar vazia, remove a sala

---

### `game/requirements.txt`

```
pygame>=2.6.0
```

Única dependência do jogo. pygame 2.6 introduziu melhorias no subsistema de fontes, alpha blending em superfícies e performance de `Surface.blit` que são usadas nas animações de glow e gradientes do jogo.
