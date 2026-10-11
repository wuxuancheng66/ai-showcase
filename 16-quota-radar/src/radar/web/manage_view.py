"""AI 运行管理页（已部署 AI 列表：充值类/免费类 + 额度/预测/诊断/修复）。"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from radar.config import get_settings
from radar.core.fleet import fleet_inventory
from radar.web.deps import get_db

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def _rows(conn):
    return fleet_inventory(conn, get_settings())


@router.get("/manage", response_class=HTMLResponse)
def manage_page(request: Request, conn=Depends(get_db)):
    from radar.monitoring import refresh_local, summary
    refresh_local(conn)
    inv = _rows(conn)
    return templates.TemplateResponse(request, "manage.html", {
        "paid": inv["paid"], "free": inv["free"], "updated": inv["updated_at"],
        "monitor": summary(conn),
    })


def _status_color(status: str) -> str:
    return {"ok": "#1d9e63", "limited": "#b97f16"}.get(status, "#d64545" if status == "error" else "#8b96ad")
