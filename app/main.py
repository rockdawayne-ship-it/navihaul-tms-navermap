"""FastAPI 앱: REST API + 정적 프론트."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, db, naver, orders, seed, simulator

@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    with db.get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        if n == 0:
            seed.reset(conn)
    yield


app = FastAPI(title="NaviHaul TMS", version="0.1.0", lifespan=lifespan)


class OrderIn(BaseModel):
    shipper_id: Optional[int] = None
    origin_name: str
    origin_addr: str = ""
    origin_lat: float
    origin_lng: float
    dest_name: str
    dest_addr: str = ""
    dest_lat: float
    dest_lng: float
    pickup_at: Optional[str] = None
    due_at: Optional[str] = None
    vehicle_type: str = Field(pattern="^(CARGO|WING|BOX|REEFER)$")
    weight_ton: float = Field(gt=0)
    cargo_desc: str = ""


class AssignIn(BaseModel):
    vehicle_id: int
    note: str = ""


class StatusIn(BaseModel):
    to: str
    note: str = ""


class TickIn(BaseModel):
    minutes: float = 10
    auto_deliver: bool = True


@app.get("/api/config")
def get_config():
    return {"map_key_id": config.NCP_MAP_KEY_ID, "features": config.features(),
            "statuses": orders.STATUS_KO, "allowed": {k: sorted(v) for k, v in orders.ALLOWED.items()}}


@app.get("/api/places")
def places(q: str = Query(min_length=1)):
    return {"items": naver.search_places(q)}


@app.get("/api/shippers")
def shippers():
    with db.get_conn() as conn:
        return db.rows(conn.execute("SELECT * FROM shippers ORDER BY name"))


@app.get("/api/vehicles")
def vehicles():
    with db.get_conn() as conn:
        return db.rows(conn.execute(
            """SELECT v.*, o.id AS order_id, o.order_no FROM vehicles v
               LEFT JOIN orders o ON o.vehicle_id=v.id AND o.status IN ('ASSIGNED','LOADED','IN_TRANSIT')
               ORDER BY v.plate"""))


@app.get("/api/orders")
def list_orders(status: Optional[str] = None):
    with db.get_conn() as conn:
        return orders.list_orders(conn, status)


@app.get("/api/orders/{oid}")
def get_order(oid: int):
    with db.get_conn() as conn:
        o = orders.get_order(conn, oid)
    if not o:
        raise HTTPException(404, "order not found")
    return o


@app.post("/api/orders", status_code=201)
def create_order(body: OrderIn):
    with db.get_conn() as conn:
        return orders.create_order(conn, body.model_dump())


@app.get("/api/orders/{oid}/recommend")
def recommend(oid: int):
    with db.get_conn() as conn:
        try:
            return orders.recommend(conn, oid)
        except KeyError as e:
            raise HTTPException(404, str(e))


@app.post("/api/orders/{oid}/assign")
def assign(oid: int, body: AssignIn):
    with db.get_conn() as conn:
        try:
            return orders.assign(conn, oid, body.vehicle_id, body.note)
        except KeyError as e:
            raise HTTPException(404, str(e))
        except orders.TransitionError as e:
            raise HTTPException(409, str(e))


@app.post("/api/orders/{oid}/status")
def change_status(oid: int, body: StatusIn):
    if body.to not in orders.ALLOWED:
        raise HTTPException(422, f"unknown status {body.to}")
    with db.get_conn() as conn:
        try:
            return orders.change_status(conn, oid, body.to, body.note)
        except KeyError as e:
            raise HTTPException(404, str(e))
        except orders.TransitionError as e:
            raise HTTPException(409, str(e))


@app.post("/api/sim/tick")
def sim_tick(body: TickIn):
    with db.get_conn() as conn:
        return simulator.tick(conn, body.minutes, body.auto_deliver)


@app.get("/api/kpi")
def kpi():
    with db.get_conn() as conn:
        return orders.kpi(conn)


@app.post("/api/reset")
def reset():
    with db.get_conn() as conn:
        return seed.reset(conn)


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
