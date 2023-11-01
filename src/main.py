from fastapi import FastAPI,WebSocket,WebSocketDisconnect,Depends
from fastapi.responses import HTMLResponse
from src.db.models import Message
from src.db.database import SessionLocal,engine,URL_DATABASE
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Union,Callable
from fastapi_sqlalchemy import DBSessionMiddleware


app = FastAPI()
app.add_middleware(DBSessionMiddleware,db_url=URL_DATABASE)

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency: Union[Session, Callable[[], Session]] = Depends(get_db)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}

    async def connect(self, websocket: WebSocket,client_id : int):
        await websocket.accept()
        self.active_connections[client_id] = websocket
    def disconnect(self,websocket: WebSocket,client_id : int):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_personal_message(self,message : dict, websocket:WebSocket):
        await websocket.send_text(message)

    async def broadcast(self,message:dict):
        for connection in self.active_connections.values():
            await connection.send_text(message)

    async def send_message_to_client(self,client_id : int,message : str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket : WebSocket,client_id : int,db:Session = Depends(get_db)):
    await manager.connect(websocket,client_id)
    try:
        while True:
            data = await websocket.receive_text()

            message = Message(client_id = client_id,content = data)
            db.add(message)
            db.commit()
            await manager.send_personal_message(f"you wrote :{data}",websocket)
            await manager.broadcast(f"Client #{client_id} says: {data}")
            await manager.send_message_to_client(f"client {client_id} says : {data}",websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket,client_id)
        await manager.broadcast(f"Client #{client_id} has left the chat")
    except Exception as error: 
        print("\nerror\n",error)
 