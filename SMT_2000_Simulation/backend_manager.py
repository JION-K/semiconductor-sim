import numpy as np
import traceback  # 👈 에러 추적을 위해 필수
from stable_baselines3 import PPO
from fab_env import FabEnv
import json
import time

class SimulationManager:
    def __init__(self, model_path="ppo_smt_final"):
        print("⚙️ [Manager] 시뮬레이션 매니저 초기화 중...")
        
        # 1. 환경 및 모델 로드
        self.env = FabEnv()
        self.model = None
        try:
            self.model = PPO.load(model_path)
            print(f"✅ [Manager] 학습된 모델 '{model_path}' 로드 성공")
        except:
            print(f"⚠️ [Manager] 모델 파일이 없습니다. 랜덤 에이전트로 동작합니다.")

        # 2. 상태 변수
        self.obs = None
        self.done = False
        self.is_paused = True  # 시작하면 일시정지 상태
        self.manual_action = None # 사용자가 강제로 지정한 액션 (없으면 None)
        self.status_seq = 0
        
        # 3. 초기화 수행
        self.reset_simulation()

    def reset_simulation(self):
        """시뮬레이션을 처음부터 다시 시작"""
        print("🔄 [Manager] 시뮬레이션 리셋")
        self.obs, _ = self.env.reset()
        self.done = False
        self.is_paused = True
        self.manual_action = None
        self.status_seq = 0
        return self.get_current_status()

    def proceed_step(self):
        """
        웹 프론트엔드에서 1초마다(또는 요청 시마다) 호출하는 함수.
        1 스텝(의사결정 1회)을 진행함.
        """
        try:
            if self.done:
                return {"status": "DONE", "message": "시뮬레이션 완료"}
            
            if self.is_paused:
                # region agent log
                try:
                    with open("/Users/skala/Desktop/SKALA_backup/Semi_Fab_Sim/.cursor/debug-99a118.log", "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "99a118",
                            "runId": "ui-repro",
                            "hypothesisId": "H5",
                            "location": "backend_manager.py:proceed_step",
                            "message": "step short-circuited because paused",
                            "data": {
                                "is_paused": True,
                                "status_seq": self.status_seq
                            },
                            "timestamp": int(time.time() * 1000)
                        }, ensure_ascii=True) + "\n")
                except Exception:
                    pass
                # endregion
                return self.get_current_status()

            # -------------------------------------------------
            # 1. Action 결정 (사람 vs AI)
            # -------------------------------------------------
            action = 0
            
            if self.manual_action is not None:
                # A. 사람이 개입함 (Dispatch 버튼 클릭)
                print(f"✋ [Human] 사용자 개입! Action: {self.manual_action}")
                action = self.manual_action
                self.manual_action = None # 초기화
            else:
                # B. AI가 결정함
                if self.model:
                    action, _ = self.model.predict(self.obs, deterministic=True)
                    # numpy int64 타입을 파이썬 int로 변환 (JSON 직렬화 위해)
                    action = int(action)
                else:
                    # 모델 없으면 랜덤
                    action = self.env.action_space.sample()

            # -------------------------------------------------
            # 2. 환경 진행 (Step)
            # -------------------------------------------------
            self.obs, reward, terminated, truncated, info = self.env.step(action)
            # region agent log
            try:
                with open("/Users/skala/Desktop/SKALA_backup/Semi_Fab_Sim/.cursor/debug-99a118.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "99a118",
                        "runId": "ui-repro",
                        "hypothesisId": "H3",
                        "location": "backend_manager.py:proceed_step",
                        "message": "step result snapshot",
                        "data": {
                            "sim_time": float(self.env.sim_env.now),
                            "target_machine": self.env.target_machine_name,
                            "active_lots_len": len(self.env.active_lots_data) if hasattr(self.env, "active_lots_data") and self.env.active_lots_data else 0
                        },
                        "timestamp": int(time.time() * 1000)
                    }, ensure_ascii=True) + "\n")
            except Exception:
                pass
            # endregion
            
            if terminated or truncated:
                self.done = True
                self.is_paused = True # 끝나면 정지

            return self.get_current_status()

        except Exception as e:
            # 🚨 에러가 나면 터미널에 상세 내용을 출력하고, 죽지 않게 처리
            print("\n" + "="*60)
            print("🔥 [CRITICAL ERROR] 시뮬레이션 진행 중 오류 발생!")
            print(f"👉 에러 내용: {e}")
            print("-" * 60)
            traceback.print_exc() 
            print("="*60 + "\n")
            
            # 웹에는 에러 상태 알림 (죽지는 않음)
            return {"status": "ERROR", "message": str(e)}

    def apply_manual_dispatch(self, action_idx):
        """
        웹에서 사용자가 특정 랏을 선택했을 때 호출
        """
        print(f"🖱️ [Web] 사용자 요청: 대기열 {action_idx}번 랏 우선 할당")
        self.manual_action = int(action_idx)
        self.is_paused = False # 개입했으므로 일시정지 해제하고 1스텝 진행
        return self.proceed_step()

    def toggle_pause(self, pause_state: bool):
        """일시정지 / 재개"""
        self.is_paused = pause_state
        status = "일시정지 ⏸️" if self.is_paused else "가동 중 ▶️"
        print(f"⏯️ [Manager] 시뮬레이션 상태 변경: {status}")
        # region agent log
        try:
            with open("/Users/skala/Desktop/SKALA_backup/Semi_Fab_Sim/.cursor/debug-99a118.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "99a118",
                    "runId": "ui-repro",
                    "hypothesisId": "H4",
                    "location": "backend_manager.py:toggle_pause",
                    "message": "pause state toggled",
                    "data": {
                        "is_paused": self.is_paused,
                        "status_seq": self.status_seq
                    },
                    "timestamp": int(time.time() * 1000)
                }, ensure_ascii=True) + "\n")
        except Exception:
            pass
        # endregion
        return self.get_current_status()

    def get_current_status(self):
        """
        [수정됨] 에러 방지용 안전 장치가 추가된 버전
        """
        try:
            target_machine = self.env.target_machine_name
            
            # 1. 대기열 정보
            queue_data = []
            if target_machine and target_machine in self.env.machines:
                raw_queue = self.env.machines[target_machine]['queue']
                for idx, event in enumerate(raw_queue):
                    info = event.payload
                    queue_data.append({
                        "index": idx,
                        "lot_name": info['name'],
                        "product": info['name'].split('_')[2] if '_' in info['name'] else 'Unknown',
                        "priority": info['priority'],
                        "rem_steps": info['rem_steps'],
                        "due_date": f"{info['due_date']:.1f}",
                        "q_danger": f"{info['q_danger']:.2f}"
                    })
            # UI 일관성 보장:
            # target_machine이 잡혀 있어도 실제 선택 대기열이 비어 있으면
            # 프론트에는 의사결정 대상 장비가 없는 것으로 표시한다.
            if len(queue_data) == 0:
                target_machine = None

            # 2. 전체 활성 랏 정보 (안전하게 가져오기)
            all_active_lots = []
            # active_lots_data가 아예 없거나 에러가 나도 죽지 않게 처리
            if hasattr(self.env, 'active_lots_data') and self.env.active_lots_data:
                for name, info in self.env.active_lots_data.items():
                    all_active_lots.append({
                        "lot_name": info['lot_name'],
                        "product": info['product'],
                        "rem_steps": info['rem_steps'],
                        "total_steps": info['total_steps'],
                        "due_date": f"{info['due_date']:.1f}",
                        "status": info.get('status', 'Unknown')
                    })

            # 3. KPI 정보
            finished_count = len(self.env.kpi['lots'])
            avg_tat = 0.0
            if finished_count > 0:
                avg_tat = sum([l.get_tat() for l in self.env.kpi['lots']]) / finished_count
            processing_count = sum(1 for lot in all_active_lots if lot.get("status") == "Processing")
            progress_signature = "|".join(
                f"{lot.get('lot_name')}:{lot.get('rem_steps')}:{lot.get('status')}"
                for lot in all_active_lots[:6]
            )

            status_payload = {
                "status_seq": self.status_seq + 1,
                "time": float(f"{self.env.sim_env.now:.2f}"),
                "is_paused": self.is_paused,
                "is_done": self.done,
                "target_machine": target_machine,
                "queue": queue_data,
                "active_lots": all_active_lots,
                "progress_signature": progress_signature,
                "kpi": {
                    "finished_lots": finished_count,
                    "avg_tat": float(f"{avg_tat:.2f}"),
                    "q_viol": sum([l.q_time_violations for l in self.env.kpi['lots']]),
                    "processing_lots": processing_count
                }
            }
            # region agent log
            try:
                with open("/Users/skala/Desktop/SKALA_backup/Semi_Fab_Sim/.cursor/debug-99a118.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "99a118",
                        "runId": "ui-repro",
                        "hypothesisId": "H1",
                        "location": "backend_manager.py:get_current_status",
                        "message": "status payload snapshot",
                        "data": {
                            "time": float(f"{self.env.sim_env.now:.2f}"),
                            "target_machine": target_machine,
                            "queue_len": len(queue_data),
                            "active_lots_len": len(all_active_lots),
                            "progress_signature": progress_signature
                        },
                        "timestamp": int(time.time() * 1000)
                    }, ensure_ascii=True) + "\n")
            except Exception:
                pass
            # endregion
            self.status_seq += 1
            return status_payload
        
        except Exception as e:
            # 상태 조회 중 에러가 나도 서버가 터지지 않게 방어
            print(f"⚠️ [Backend Error] 상태 조회 중 오류 발생: {e}")
            # traceback.print_exc() # 필요하면 주석 해제하여 상세 로그 확인
            return {
                "status_seq": self.status_seq + 1,
                "time": 0.0,
                "is_paused": True,
                "is_done": False,
                "target_machine": None,
                "queue": [],
                "active_lots": [],
                "kpi": {"finished_lots": 0, "avg_tat": 0, "q_viol": 0, "processing_lots": 0}
            }

    def get_fab_layout_info(self):
        """
        공장 장비 배치도 데이터 생성
        """
        layout = {}
        try:
            # 1. 모든 장비 루프
            for m_name, m_data in self.env.machines.items():
                res = m_data['resource']
                
                # 2. 그룹 이름 추출 (예: Litho_FE_1 -> "Litho")
                group_type = m_name.split('_')[0] 
                
                # 3. 상태 계산
                total_cap = res.capacity
                busy_cnt = res.count
                
                machine_info = {
                    "name": m_name,
                    "total": total_cap,
                    "busy": busy_cnt,
                    "utilization": (busy_cnt / total_cap) * 100 if total_cap > 0 else 0
                }
                
                if group_type not in layout:
                    layout[group_type] = []
                layout[group_type].append(machine_info)
        except Exception as e:
            print(f"⚠️ [Layout Error] 레이아웃 생성 중 오류: {e}")
            
        return layout

# 테스트 코드
if __name__ == "__main__":
    manager = SimulationManager()
    
    # 1. 초기 상태 확인
    print("\n--- 초기 상태 ---")
    print(manager.get_current_status())
    
    # 2. 시뮬레이션 시작 (일시정지 해제)
    print("\n--- 시작 (Paused -> Running) ---")
    manager.toggle_pause(False)
    
    # 3. 몇 스텝 진행해보기
    for i in range(5):
        print(f"\n--- Step {i+1} ---")
        status = manager.proceed_step()
        print(f"Time: {status.get('time', 'Error')}, Target: {status.get('target_machine', 'Error')}")