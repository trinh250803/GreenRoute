"""AI assistant (Claude) that answers staff questions about the plan in focus.

Privacy (mục 5.3): the context sent to the model holds order ids, districts, weights, times
and aggregates only — never customer names, phone numbers or street addresses.
Requires ANTHROPIC_API_KEY on the server; without it the endpoint reports "not configured".
"""
import json
import logging
import os

import anthropic

from .analytics import analytics, district_of, focus_run
from .auth import AuthError

log = logging.getLogger("greenroute")
MODEL = os.environ.get("ASSISTANT_MODEL", "claude-opus-5-5")
MAX_HISTORY = 12

SYSTEM = """Bạn là trợ lý vận hành của GreenRoute AI — nền tảng tối ưu giao hàng chặng cuối đa phương tiện.
Người hỏi là nhân viên (điều phối viên, quản lý đội xe, quản lý vận hành, quản trị). Trả lời bằng ngôn ngữ của câu hỏi (mặc định tiếng Việt), ngắn gọn, có số liệu cụ thể, dùng gạch đầu dòng khi liệt kê.

Chỉ dựa trên DỮ LIỆU KẾ HOẠCH bên dưới. Nếu dữ liệu không đủ để trả lời, nói rõ là không có trong dữ liệu — không suy đoán số liệu.
Phân biệt rõ: số liệu đo thực tế (kết quả giao do tài xế báo), số liệu kế hoạch (tuyến OR-Tools tính), và ước tính (giờ cao điểm, hệ số phát thải minh họa).
Phạm vi phát thải: CO2 chính là CO2 hóa thạch (co2_fossil_kg); CO2 sinh học từ ethanol và CO2 điện lưới của xe điện báo cáo riêng; co2_operational_kg = hóa thạch + điện lưới.
Khi đề xuất hành động (đổi xe, nới khung giờ, thêm xe…), nêu lý do từ dữ liệu và lưu ý rằng cần chạy lại tối ưu để xác nhận.
Bạn không thể tự thay đổi dữ liệu hay chạy tối ưu; hãy hướng dẫn người dùng thao tác trên giao diện (Lập tuyến, Kịch bản nhiên liệu, Đội xe, Quản trị)."""


def plan_context(db: dict) -> str:
    run = focus_run(db)
    if not run:
        return "Chưa có lần tối ưu nào."
    a = analytics(db)
    orders = {o["order_id"]: o for o in run["input"]["orders"]}
    routes = []
    for r in run["optimized"]["routes"]:
        routes.append({
            "vehicle_id": r["vehicle_id"], "type": r["vehicle_type"], "fuel": r["fuel_blend_code"],
            "start": r["start"], "end": r["end"], "km": r["distance_km"], "load_kg": r["load_weight_kg"], "capacity_kg": r["capacity_weight_kg"],
            "stops": [{"order_id": s["order_id"], "district": district_of(orders[s["order_id"]]["address"]), "arrival": s["arrival"],
                       "window": s["window"], "peak": s.get("peak"), "late_risk": s.get("late_risk"),
                       "status": run.get("deliveries", {}).get(s["order_id"], {}).get("status", "pending")} for s in r["stops"]],
        })
    ctx = {
        "plan": a["run"], "assumptions": {k: run["assumptions"].get(k) for k in ("emission_scope", "fuel_config_version", "routing_source", "solver")},
        "totals": a["totals"], "efficiency": a["efficiency"], "baseline_comparison": a["comparison"],
        "by_vehicle": a["by_vehicle"], "by_fuel": a["by_fuel"], "by_district": a["by_district"], "by_window": a["by_window"],
        "traffic_peak_estimate": a["traffic"], "deliveries": a["deliveries"], "unassigned": a["unassigned"],
        "fleet": [{k: v.get(k) for k in ("vehicle_id", "vehicle_type", "capacity_weight_kg", "capacity_volume_m3", "cost_per_km", "fuel_blend_code",
                                          "consumption_rate", "available", "start_time", "end_time")} for v in run["input"]["vehicles"]],
        "routes": routes,
    }
    # sort_keys keeps the cached prefix byte-stable for the same plan.
    return json.dumps(ctx, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def ask(db: dict, question: str, history: list[dict]) -> dict:
    if not configured():
        raise AuthError(503, "Trợ lý AI chưa được cấu hình: quản trị viên cần đặt biến môi trường ANTHROPIC_API_KEY trên server.")
    question = (question or "").strip()
    if not question:
        raise AuthError(400, "Hãy nhập câu hỏi")
    msgs = [{"role": m["role"], "content": str(m["content"])[:4000]} for m in (history or [])[-MAX_HISTORY:]
            if m.get("role") in ("user", "assistant") and m.get("content")]
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    msgs.append({"role": "user", "content": question[:2000]})

    client = anthropic.Anthropic()
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium"},
            system=[
                {"type": "text", "text": SYSTEM},
                # Plan data is stable between questions about the same plan → cache it.
                {"type": "text", "text": "DỮ LIỆU KẾ HOẠCH (JSON):\n" + plan_context(db), "cache_control": {"type": "ephemeral"}},
            ],
            messages=msgs,
        )
    except anthropic.AuthenticationError:
        raise AuthError(503, "API key của trợ lý AI không hợp lệ — kiểm tra ANTHROPIC_API_KEY")
    except anthropic.RateLimitError:
        raise AuthError(429, "Trợ lý AI đang quá tải, thử lại sau ít phút")
    except anthropic.APIStatusError as e:
        log.error("assistant API error %s %s", e.status_code, getattr(e, "request_id", None))
        raise AuthError(502, "Trợ lý AI tạm thời lỗi, thử lại sau")
    except anthropic.APIConnectionError:
        raise AuthError(502, "Không kết nối được tới dịch vụ AI")

    if resp.stop_reason == "refusal":
        return {"answer": "Trợ lý không thể trả lời câu hỏi này.", "refused": True, "model": resp.model}
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if resp.stop_reason == "max_tokens":
        text += "\n\n_(Câu trả lời bị cắt do quá dài — hãy hỏi cụ thể hơn.)_"
    return {"answer": text or "(Không có nội dung)", "model": resp.model,
            "usage": {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens,
                      "cache_read": getattr(resp.usage, "cache_read_input_tokens", 0) or 0}}
