from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import json
import time
from starlette.requests import Request

# 우리가 만든 매니저 클래스 임포트
from backend_manager import SimulationManager

# 1. FastAPI 앱 생성
app = FastAPI(title="SMT2020 Fab Simulation API")

# 2. CORS 설정 (Vue.js에서 접속할 수 있도록 허용)
# 보안상 실제 배포 시에는 allow_origins에 Vue 주소만 적어야 하지만,
# 개발 단계에서는 ["*"]로 모든 접속을 허용합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def debug_request_logger(request: Request, call_next):
    # region agent log
    try:
        with open("/Users/skala/Desktop/SKALA_backup/Semi_Fab_Sim/.cursor/debug-99a118.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "99a118",
                "runId": "ui-repro",
                "hypothesisId": "H6",
                "location": "main_api.py:middleware:before",
                "message": "api request received",
                "data": {
                    "method": request.method,
                    "path": request.url.path
                },
                "timestamp": int(time.time() * 1000)
            }, ensure_ascii=True) + "\n")
    except Exception:
        pass
    # endregion
    response = await call_next(request)
    # region agent log
    try:
        with open("/Users/skala/Desktop/SKALA_backup/Semi_Fab_Sim/.cursor/debug-99a118.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "99a118",
                "runId": "ui-repro",
                "hypothesisId": "H6",
                "location": "main_api.py:middleware:after",
                "message": "api response sent",
                "data": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code
                },
                "timestamp": int(time.time() * 1000)
            }, ensure_ascii=True) + "\n")
    except Exception:
        pass
    # endregion
    return response

# 3. 시뮬레이션 매니저 인스턴스 생성 (서버가 켜지면 딱 1개 생성됨)
# 전역 변수로 관리하여 상태를 유지합니다.
sim_manager = SimulationManager(model_path="ppo_smt_final")

# --- 데이터 모델 (Request Body 정의) ---
class DispatchRequest(BaseModel):
    action_idx: int

class UiEventRequest(BaseModel):
    event: str
    details: dict = {}

# --- API 엔드포인트 정의 ---

@app.get("/")
def read_root():
    """서버 상태 확인용"""
    return {"status": "Server is running", "simulation_time": sim_manager.env.sim_env.now}

@app.get("/api/status")
def get_status():
    """현재 시뮬레이션 상태(시간, KPI, 대기열 등) 조회"""
    # Frontend loop가 비정상인 환경에서도 status polling만으로 진행되도록 보강.
    # 초기 paused 상태(리셋 직후)에서는 자동 재개를 1회 수행한다.
    if sim_manager.is_paused and not sim_manager.done and sim_manager.env.sim_env.now <= 1.0:
        # region agent log
        try:
            with open("/Users/skala/Desktop/SKALA_backup/Semi_Fab_Sim/.cursor/debug-99a118.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "99a118",
                    "runId": "ui-repro",
                    "hypothesisId": "H17",
                    "location": "main_api.py:get_status",
                    "message": "auto resume on initial status poll",
                    "data": {"time": float(sim_manager.env.sim_env.now)},
                    "timestamp": int(time.time() * 1000)
                }, ensure_ascii=True) + "\n")
        except Exception:
            pass
        # endregion
        sim_manager.toggle_pause(False)

    if not sim_manager.is_paused and not sim_manager.done:
        # region agent log
        try:
            with open("/Users/skala/Desktop/SKALA_backup/Semi_Fab_Sim/.cursor/debug-99a118.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "99a118",
                    "runId": "ui-repro",
                    "hypothesisId": "H17",
                    "location": "main_api.py:get_status",
                    "message": "auto step on status poll",
                    "data": {"time_before": float(sim_manager.env.sim_env.now)},
                    "timestamp": int(time.time() * 1000)
                }, ensure_ascii=True) + "\n")
        except Exception:
            pass
        # endregion
        return sim_manager.proceed_step()

    return sim_manager.get_current_status()

@app.post("/api/control/reset")
def reset_simulation():
    """시뮬레이션 초기화"""
    return sim_manager.reset_simulation()

@app.post("/api/control/pause")
def pause_simulation():
    """일시정지"""
    return sim_manager.toggle_pause(True)

@app.post("/api/control/resume")
def resume_simulation():
    """재개"""
    return sim_manager.toggle_pause(False)

@app.post("/api/step")
def proceed_step():
    """
    1 스텝 진행 (Vue.js에서 1초마다 이 API를 호출하면 시뮬레이션이 흘러감)
    만약 일시정지 상태라면 상태값만 반환함.
    """
    if sim_manager.is_paused:
        return sim_manager.get_current_status()
    
    result = sim_manager.proceed_step()
    return result

@app.post("/api/dispatch")
def manual_dispatch(req: DispatchRequest):
    """
    [Human-in-the-loop] 사용자가 특정 랏을 강제로 할당
    """
    return sim_manager.apply_manual_dispatch(req.action_idx)

@app.post("/api/debug/ui-event")
def debug_ui_event(req: UiEventRequest):
    # region agent log
    try:
        with open("/Users/skala/Desktop/SKALA_backup/Semi_Fab_Sim/.cursor/debug-99a118.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "99a118",
                "runId": "ui-repro",
                "hypothesisId": "H7",
                "location": "main_api.py:/api/debug/ui-event",
                "message": "ui event received",
                "data": {
                    "event": req.event,
                    "details": req.details
                },
                "timestamp": int(time.time() * 1000)
            }, ensure_ascii=True) + "\n")
    except Exception:
        pass
    # endregion
    return {"ok": True}

@app.get("/api/debug/file-write-check")
def debug_file_write_check():
    try:
        with open("/Users/skala/Desktop/SKALA_backup/Semi_Fab_Sim/.cursor/debug-99a118.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "99a118",
                "runId": "ui-repro",
                "hypothesisId": "H8",
                "location": "main_api.py:/api/debug/file-write-check",
                "message": "file write check",
                "data": {"ok": True},
                "timestamp": int(time.time() * 1000)
            }, ensure_ascii=True) + "\n")
        return {"ok": True, "path": "/Users/skala/Desktop/SKALA_backup/Semi_Fab_Sim/.cursor/debug-99a118.log"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# main_api.py 에 추가
@app.get("/api/layout")
def get_fab_map():
    """공장 장비 배치도 정보 반환"""
    return sim_manager.get_fab_layout_info()

# --- 서버 실행 코드 (직접 실행 시) ---
if __name__ == "__main__":
    print("🚀 시뮬레이션 API 서버를 시작합니다...")
    print("👉 Swagger UI(테스트 페이지): http://localhost:8000/docs")
    # 0.0.0.0으로 열면 외부에서도 접속 가능, 로컬 개발은 127.0.0.1
    uvicorn.run("main_api:app", host="127.0.0.1", port=8000, reload=True)