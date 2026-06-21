"""
Backend UTFPR - CyberLayerQuest
================================
Servidor de salas multiplayer via WebSocket (FastAPI + uvicorn).
Pygame é importado para lógica de física/colisão server-side;
a interface gráfica permanece no frontend React.

Executar:
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional

import pygame
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

# ---------------------------------------------------------------------------
# Inicializa pygame (somente motor, sem janela)
# ---------------------------------------------------------------------------
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")   # sem janela no servidor
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")   # sem áudio no servidor
pygame.init()

app = FastAPI(
    title="CyberLayerQuest API — UTFPR",
    description="Backend multiplayer do jogo CyberLayerQuest (UTFPR-1ºLC).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # em produção, restringir à origem do frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Modelos de dados
# ---------------------------------------------------------------------------

class CriarSalaRequest(BaseModel):
    codigo: str
    senha: str
    personagem: str  # "whitehat" | "blackhat"


class EntrarSalaRequest(BaseModel):
    codigo: str
    senha: str
    personagem: str


@dataclass
class Jogador:
    ws: WebSocket
    personagem: str
    pronto: bool = False

    def dict_info(self) -> dict:
        return {"personagem": self.personagem, "pronto": self.pronto}


@dataclass
class Sala:
    codigo: str
    senha: str
    jogadores: Dict[str, Jogador] = field(default_factory=dict)  # id -> Jogador
    fase_atual: int = 0

    @property
    def cheia(self) -> bool:
        return len(self.jogadores) >= 2

    def jogadores_info(self) -> list:
        return [j.dict_info() for j in self.jogadores.values()]


# Registro global de salas  {codigo: Sala}
salas: Dict[str, Sala] = {}

# ---------------------------------------------------------------------------
# Utilitários de física via pygame (lógica server-side)
# ---------------------------------------------------------------------------

W, H = 1200, 680
GRAV = 0.6
JUMP = -12
SPEED = 3.2


def verificar_colisao(px: float, py: float, plataformas: list[dict]) -> dict:
    """Verifica colisões do jogador com a lista de plataformas (server-side)."""
    pw, ph = 26, 36
    player_rect = pygame.Rect(int(px), int(py), pw, ph)
    resultado = {"no_chao": False, "py_corrigido": py, "vy_corrigido": 0.0}

    for pl in plataformas:
        if pl.get("kind") not in ("bridge", "brick"):
            continue
        plat_rect = pygame.Rect(int(pl["x"]), int(pl["y"]), int(pl["w"]), int(pl["h"]))
        if player_rect.colliderect(plat_rect):
            resultado["no_chao"] = True
            resultado["py_corrigido"] = pl["y"] - ph
            resultado["vy_corrigido"] = 0.0
            break

    return resultado


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["saúde"])
def raiz():
    return {"projeto": "CyberLayerQuest", "instituicao": "UTFPR-1ºLC", "status": "online"}


@app.post("/salas/criar", tags=["salas"])
def criar_sala(req: CriarSalaRequest):
    codigo = req.codigo.upper()[:8]
    if codigo in salas:
        raise HTTPException(status_code=409, detail="Sala já existe.")
    salas[codigo] = Sala(codigo=codigo, senha=req.senha)
    return {"codigo": codigo, "mensagem": "Sala criada. Aguardando segundo jogador."}


@app.get("/salas/{codigo}", tags=["salas"])
def estado_sala(codigo: str):
    sala = salas.get(codigo.upper())
    if not sala:
        raise HTTPException(status_code=404, detail="Sala não encontrada.")
    return {
        "codigo": sala.codigo,
        "cheia": sala.cheia,
        "fase_atual": sala.fase_atual,
        "jogadores": sala.jogadores_info(),
    }


@app.delete("/salas/{codigo}", tags=["salas"])
def fechar_sala(codigo: str):
    sala = salas.pop(codigo.upper(), None)
    if not sala:
        raise HTTPException(status_code=404, detail="Sala não encontrada.")
    return {"mensagem": f"Sala {codigo} encerrada."}


# ---------------------------------------------------------------------------
# WebSocket — sala multiplayer
# ---------------------------------------------------------------------------

@app.websocket("/ws/{codigo}/{senha}/{personagem}")
async def websocket_sala(
    ws: WebSocket,
    codigo: str,
    senha: str,
    personagem: str,
):
    codigo = codigo.upper()

    # Validar sala
    sala = salas.get(codigo)
    if not sala:
        await ws.close(code=4040, reason="Sala não encontrada")
        return
    if sala.senha != senha:
        await ws.close(code=4031, reason="Senha incorreta")
        return
    if sala.cheia:
        await ws.close(code=4090, reason="Sala cheia")
        return

    await ws.accept()
    jogador_id = str(uuid.uuid4())
    sala.jogadores[jogador_id] = Jogador(ws=ws, personagem=personagem)

    # Notificar todos na sala
    await _broadcast(sala, {
        "tipo": "jogador_entrou",
        "id": jogador_id,
        "personagem": personagem,
        "total": len(sala.jogadores),
    })

    if sala.cheia:
        await _broadcast(sala, {"tipo": "sala_cheia", "iniciar": True})

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg: dict = json.loads(raw)
            except json.JSONDecodeError:
                continue

            tipo = msg.get("tipo", "")

            if tipo == "posicao":
                # Repassar posição do jogador para os demais
                msg["id"] = jogador_id
                await _broadcast(sala, msg, excluir=jogador_id)

            elif tipo == "colisao":
                # Verificar colisão server-side via pygame
                resultado = verificar_colisao(
                    msg.get("px", 0),
                    msg.get("py", 0),
                    msg.get("plataformas", []),
                )
                await ws.send_text(json.dumps({"tipo": "resultado_colisao", **resultado}))

            elif tipo == "evento":
                # Eventos de jogo: coletou item, chegou ao goal, etc.
                msg["id"] = jogador_id
                await _broadcast(sala, msg)

            elif tipo == "proxima_fase":
                sala.fase_atual = msg.get("fase", sala.fase_atual + 1)
                await _broadcast(sala, {"tipo": "mudar_fase", "fase": sala.fase_atual})

            elif tipo == "ping":
                await ws.send_text(json.dumps({"tipo": "pong"}))

    except WebSocketDisconnect:
        sala.jogadores.pop(jogador_id, None)
        await _broadcast(sala, {"tipo": "jogador_saiu", "id": jogador_id})
        if not sala.jogadores:
            salas.pop(codigo, None)


async def _broadcast(sala: Sala, msg: dict, excluir: Optional[str] = None):
    payload = json.dumps(msg)
    mortos: list[str] = []
    for jid, jogador in sala.jogadores.items():
        if jid == excluir:
            continue
        try:
            await jogador.ws.send_text(payload)
        except Exception:
            mortos.append(jid)
    for jid in mortos:
        sala.jogadores.pop(jid, None)


# ---------------------------------------------------------------------------
# Ponto de entrada direto
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
