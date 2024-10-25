from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import logging

from ConnectionManager import ConnectionManager
from data.DatabaseFb import DatabaseFb, Prevenda
from RetornoWebSocket import RetornoWebSocket

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s -> %(message)s', filename='log\\ws.log', encoding='utf-8', level=logging.DEBUG)

# constantes
TAG_COMANDO = 'comando'
CMD_GET_ATENDENTE_ATIVO = 'get_atendente_ativo'
CMD_GET_LISTA_VEZ = 'get_lista_vez'
CMD_ADD_LISTA_VEZ = 'add_lista_vez'
CMD_ALTERAR_STATUS_LISTA_VEZ = 'alt_status_lista_vez'
# ---------------------------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origins=["*"],
)


manager = ConnectionManager()
db = DatabaseFb()
db.connect()

retorno_web_socket = RetornoWebSocket()

class ItemListaVez:
    def __init__(self, id_lista_vez: int, cod_atendente: int, nome_atendente: str):
        self.id_lista_vez = id_lista_vez
        self.cod_atendente = cod_atendente
        self.nome_atendente = nome_atendente


# app.mount("/site", StaticFiles(directory="site"), name="site")


@app.get('/')
def get_app_angular():

    with open('site/index.html', 'r') as file_index:
        html_content = file_index.read()
    return HTMLResponse(html_content, status_code=200)

@app.get("/lista_status")
async def get_lista_status():
    return db.get_lista_status()


@app.get("/lista_atendentes_ativos")
async def get_atendentes_ativos():
    return db.get_atendente_ativo()


@app.get("/lista_vez")
async def get_lista_vez():
    return db.get_lista_vez()


@app.post("/lancar_prevenda")
async def lancar_prevenda(prevenda: Prevenda):
    logger.info('POST:/lancar_prevenda')
    db.lancar_prevenda(prevenda)

    retorno_web_socket.set_lista_vez( db.get_lista_vez() )

    retorno_web_socket.set_warning_message('')
    retorno_web_socket.set_error_message('')
    await manager.broadcast(retorno_web_socket.get_resp_padrao())

    return prevenda


#@app.websocket("/ws/{client_id}")
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
#async def websocket_endpoint(websocket: WebSocket, client_id: int):
    # retorno_web_socket = RetornoWebSocket()

    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            #await manager.send_personal_message(f"You wrote: {data}", websocket)
            #await manager.broadcast(f"Client #{client_id} says: {data}")

            #await manager.send_personal_message(json.dumps('{"nome": "Eneias", "msg": "' + data + '"}'), websocket)
            #await manager.broadcast(json.dumps('{"nome": "Eneias", "msg": "'+data+'"}') )
            #logging.info('WS receive :', data)
            #print(' *********of type :', type(data))
            #print('data', data)

            #data_ret = {}
            retorno_web_socket.clear()
            sendBroadcast = False

            if data[TAG_COMANDO] == CMD_ADD_LISTA_VEZ:
                cod_atendente = data["cod_atendente"]

                if not db.atendente_em_atividade(cod_atendente):
                    data_ret = db.add_lista_vez(cod_atendente)
                    retorno_web_socket.set_warning_message(data_ret['warning'])
                    retorno_web_socket.set_error_message(data_ret['error'])
                    sendBroadcast = True
                else:
                    retorno_web_socket.set_warning_message('atendente ja estava em atividade')

                #await manager.broadcast(db.get_lista_vez())
                retorno_web_socket.set_lista_vez(db.get_lista_vez())
            elif data[TAG_COMANDO] == CMD_GET_ATENDENTE_ATIVO:
                retorno_web_socket.set_atendentes_ativos(db.get_atendente_ativo())
                #data_ret = db.get_atendente_ativo()

            elif data[TAG_COMANDO] == CMD_GET_LISTA_VEZ:
                retorno_web_socket.set_lista_vez(db.get_lista_vez() )

            elif data[TAG_COMANDO] == CMD_ALTERAR_STATUS_LISTA_VEZ:
                id_lista_vez = data["id_lista_vez"]
                id_novo_status = data["id_novo_status"]
                id_motivo = data["id_motivo"]
                id_prevenda = data["id_prevenda"]
                obs = data["obs"]
                venda_efetuada = data["venda_efetuada"]

                data_ret = db.alt_status_lista_vez(id_lista_vez = id_lista_vez, id_novo_status = id_novo_status, id_motivo = id_motivo, id_prevenda = id_prevenda, obs = obs, venda_efetuada = venda_efetuada)

                retorno_web_socket.set_warning_message(data_ret['warning'])
                retorno_web_socket.set_error_message(data_ret['error'])
                retorno_web_socket.set_lista_vez(db.get_lista_vez())
                sendBroadcast = True
                # await manager.broadcast(db.get_lista_vez())


            await manager.send_personal_message( retorno_web_socket.get_resp_padrao(), websocket)

            if sendBroadcast:
                # as mensagens sao apenas para o direct
                retorno_web_socket.set_warning_message('')
                retorno_web_socket.set_error_message('')
                await manager.broadcast(retorno_web_socket.get_resp_padrao())

            #await manager.broadcast(json.dumps('{"nome": "Eneias", "msg": "'+data+'"}') )

    except WebSocketDisconnect:
        logger.info('A Conexão foi fechada:' + str(WebSocketDisconnect))
        #db.disconnect()
        manager.disconnect(websocket)
        #await manager.broadcast(f"Client #{client_id} left the chat")
        retorno_web_socket.set_warning_message('WebSocket desconectado.')
        #await manager.broadcast(retorno_web_socket.get_resp_padrao() )


