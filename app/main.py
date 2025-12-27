from fastapi import FastAPI
import uvicorn
from threading import Thread
from app.doh_handler import router as doh_router
from app.dns_server import start_udp_server
from app.data_base import init_db

app = FastAPI(title="DNS + DoH Server")
init_db()

app.include_router(doh_router)

udp_thread = Thread(target=start_udp_server)
udp_thread.start()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=False)
