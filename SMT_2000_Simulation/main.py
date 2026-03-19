import simpy
import random
import statistics
from datetime import datetime
from collections import defaultdict
from database import SessionLocal
from models import ToolGroup, LotRelease, ProcessStep, SetupInfo, BreakdownEvent

print("=== 🏭 SMT2020: Full Simulation Mode (KPI, Batch, Q-Time) ===")

# [전역 변수] 배치 대기열 관리 (Key: (Route, StepSeq) -> Value: [List of Events])
batch_queues = defaultdict(list)

# [검증용] 데이터 수집 저장소
kpi_data = {
    "lots": [],            # 완료된 Lot들의 성적표 객체 저장
    "breakdowns": [],      # 고장 이력
}

class LotStat:
    """Lot 별 성적표 (통계용)"""
    def __init__(self, name, product, start_time, due_date):
        self.name = name
        self.product = product
        self.start_time = start_time
        self.end_time = None
        self.due_date = due_date
        self.setup_time_sum = 0.0
        self.q_time_violations = 0
        self.history = {} # {step_seq: finish_time}

    def get_tat(self):
        if self.end_time: return self.end_time - self.start_time
        return 0.0

    def get_lateness(self):
        # 납기일(분) - 완료일(분)
        # 양수(+)면 여유 있게 도착 (Early)
        # 음수(-)면 지각 (Late)
        if self.due_date is not None and self.end_time is not None:
            # self.due_date는 이미 '분(minute)' 단위로 변환되어 들어옵니다.
            return self.due_date - self.end_time 
        return 0.0

# -----------------------------------------------------------
# [클래스] 가상 장비
# -----------------------------------------------------------
class SimMachine:
    def __init__(self, env, data: ToolGroup, setup_manager, breakdown_data=None):
        self.env = env
        self.name = data.toolgroup_name
        self.total_capacity = data.num_tools
        self.setup_manager = setup_manager
        self.current_setup = None 
        self.resource = simpy.PriorityResource(env, capacity=self.total_capacity)

        if breakdown_data:
            self.env.process(self.breakdown_loop(breakdown_data))

    def breakdown_loop(self, bd_data: BreakdownEvent):
        # ... (기존과 동일) ...
        mean_time = bd_data.foa_mean if bd_data.foa_mean else bd_data.mttf_mean
        if mean_time > 0:
            yield self.env.timeout(random.expovariate(1.0 / mean_time))
        
        while True:
            with self.resource.request(priority=0) as req:
                yield req 
                repair_time = random.expovariate(1.0 / bd_data.mttr_mean) if bd_data.mttr_mean > 0 else 0.0
                kpi_data["breakdowns"].append((self.name, repair_time))
                print(f"   [{self.env.now:8.2f}] 💥 {self.name} 고장 (수리: {repair_time:.2f}분)")
                yield self.env.timeout(repair_time)
                print(f"   [{self.env.now:8.2f}] 🔧 {self.name} 재가동")

            next_fail = random.expovariate(1.0 / bd_data.mttf_mean) if bd_data.mttf_mean > 0 else 1e6
            yield self.env.timeout(next_fail)

# -----------------------------------------------------------
# [헬퍼] 셋업 매니저
# -----------------------------------------------------------
class SetupManager:
    def __init__(self, setup_list):
        self.setup_map = {}
        for s in setup_list:
            g = str(s.setup_group) if s.setup_group else "None"
            f = str(s.from_setup) if s.from_setup else "None"
            t = str(s.to_setup) if s.to_setup else "None"
            self.setup_map[(g, f, t)] = s.setup_time

    def get_setup_time(self, group_name, current_setup, next_setup):
        if current_setup == next_setup: return 0.0
        return self.setup_map.get((str(group_name), str(current_setup), str(next_setup)), 0.0)

# -----------------------------------------------------------
# [핵심] Lot 프로세스 (Batch & Q-Time 추가됨!)
# -----------------------------------------------------------
def process_lot(env, lot_name, route_name, machines, routes, due_date_val):
    my_steps = routes.get(route_name)
    if not my_steps: return

    # KPI 생성
    stat = LotStat(lot_name, route_name, env.now, due_date_val)
    
    # 1. 공장 투입 로그
    print(f"[{env.now:8.2f}] 📦 {lot_name} 투입 (Start)")

    for step in my_steps:
        # Q-Time 체크 로직 (생략 - 기존 유지)
        if step.cqt_start_step and step.cqt_limit:
            start_seq = step.cqt_start_step
            if start_seq in stat.history:
                elapsed = env.now - stat.history[start_seq]
                if elapsed > step.cqt_limit:
                    stat.q_time_violations += 1

        target_group = step.target_tool_group
        machine = machines.get(target_group)
        if not machine: continue

        # --- Batch Logic ---
        is_batch = (step.proc_unit == 'Batch')
        batch_id = (step.route_id, step.step_seq)
        my_work_done = env.event()
        
        if is_batch:
            batch_queues[batch_id].append(my_work_done)
            queue = batch_queues[batch_id]
            b_min = step.batch_min if step.batch_min else 1
            b_max = step.batch_max if step.batch_max else 1
            
            if len(queue) >= b_min:
                # [Leader] 내가 총대 메고 장비 잡음
                batch_group = queue[:b_max]
                batch_queues[batch_id] = queue[b_max:]
                
                with machine.resource.request(priority=10) as req:
                    yield req
                    
                    # 🔴 [추가된 로그 1] 배치 리더 작업 시작 (Step 번호 포함)
                    print(f"   [{env.now:8.2f}] 🚜 {lot_name} (Leader) -> {machine.name} [Step {step.step_seq}] 작업 시작")

                    # 셋업 (기존 유지)
                    setup_time = 0.0
                    if step.setup_id and machine.current_setup != step.setup_id:
                        if machine.setup_manager:
                            setup_time = machine.setup_manager.get_setup_time(step.setup_id, machine.current_setup, step.setup_id)
                        if setup_time > 0: yield env.timeout(setup_time)
                        machine.current_setup = step.setup_id
                    
                    # 작업
                    proc_time = get_proc_time(step)
                    yield env.timeout(proc_time)
                    
                    # 친구들 깨워주기
                    for evt in batch_group:
                        if not evt.triggered:
                            evt.succeed(value=setup_time)
            else:
                # [Follower] 리더가 깨워줄 때까지 대기
                setup_val = yield my_work_done
                stat.setup_time_sum += setup_val
                
                #  배치 멤버 작업 합류
                print(f"   [{env.now:8.2f}] 🚌 {lot_name} (Follower) -> {machine.name} [Step {step.step_seq}] 배치 합류 완료")

        # --- Normal Logic ---
        else:
            with machine.resource.request(priority=10) as req:
                yield req
                
                #  일반 랏 작업 시작
                print(f"   [{env.now:8.2f}] ⚙️ {lot_name} -> {machine.name} [Step {step.step_seq}] 작업 시작")
                
                # 셋업 (기존 유지)
                setup_time = 0.0
                if step.setup_id and machine.current_setup != step.setup_id:
                    if machine.setup_manager:
                        setup_time = machine.setup_manager.get_setup_time(step.setup_id, machine.current_setup, step.setup_id)
                    if setup_time > 0: yield env.timeout(setup_time)
                    machine.current_setup = step.setup_id
                
                stat.setup_time_sum += setup_time
                
                # 작업
                proc_time = get_proc_time(step)
                yield env.timeout(proc_time)

        # 공정 완료 기록
        stat.history[step.step_seq] = env.now

    # 전체 완료
    stat.end_time = env.now
    kpi_data["lots"].append(stat)
    print(f"[{env.now:8.2f}] 🎉 {lot_name} 완제품 생산 완료! (TAT: {stat.get_tat():.1f})")

def get_proc_time(step):
    """Uniform 분포 등 시간 계산"""
    mean = step.proc_time_mean if step.proc_time_mean else 0.0
    offset = step.proc_time_offset if step.proc_time_offset else 0.0
    dist = str(step.proc_time_dist).lower()
    
    val = mean
    if "uniform" in dist:
        val = random.uniform(max(0, mean - offset), mean + offset)
    elif "normal" in dist:
        val = random.normalvariate(mean, offset)
    return max(0.0, val)

# -----------------------------------------------------------
# [헬퍼] 날짜 계산
# -----------------------------------------------------------
SIM_START = datetime(2018, 1, 1, 0, 0, 0)

def calc_minutes(date_str):
    if not date_str or str(date_str).strip() in ['None', '']: return 0.0
    try:
        clean = str(date_str).strip()
        for fmt in ("%m-%d-%y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(clean, fmt)
                return max(0.0, (dt - SIM_START).total_seconds() / 60.0)
            except: continue
    except: pass
    return 0.0

# -----------------------------------------------------------
# [프로세스] 투입기
# -----------------------------------------------------------
def run_source(env, r, machines, routes):
    start_delay = calc_minutes(r.start_date)
    due_date_val = calc_minutes(r.due_date) # 납기일(분) 계산
    
    if start_delay > 0: yield env.timeout(start_delay)
    
    interval = r.release_interval
    p_name = r.product_name
    r_name = r.route_name
    
    # 1회성 (Engineering)
    if not interval or interval <= 0:
        lot_name = r.lot_type if r.lot_type else f"Eng_{p_name}_1"
        env.process(process_lot(env, lot_name, r_name, machines, routes, due_date_val))
    
    # 반복 (Mass Production)
    else:
        cnt = 1
        while True:
            lot_name = f"Lot_{p_name}_{cnt}"
            env.process(process_lot(env, lot_name, r_name, machines, routes, due_date_val))
            yield env.timeout(interval)
            cnt += 1

# -----------------------------------------------------------
# [초기화 & 메인]
# -----------------------------------------------------------
def initialize_data(env, db):
    print("📥 데이터 로딩...")
    setups = db.query(SetupInfo).all()
    setup_mgr = SetupManager(setups)
    
    bds = db.query(BreakdownEvent).all()
    tgs = db.query(ToolGroup).all()
    machines = {}
    for tg in tgs:
        my_bd = next((b for b in bds if b.target_name in tg.toolgroup_name), None)
        machines[tg.toolgroup_name] = SimMachine(env, tg, setup_mgr, my_bd)
        
    steps = db.query(ProcessStep).order_by(ProcessStep.route_id, ProcessStep.step_seq).all()
    routes = defaultdict(list)
    for s in steps: routes[s.route_id].append(s)
    
    return machines, routes

def print_kpi():
    print("\n" + "="*60)
    print("📊 시뮬레이션 성적표 (KPI Report)")
    print("="*60)
    
    total_lots = len(kpi_data["lots"])
    if total_lots > 0:
        avg_tat = statistics.mean([l.get_tat() for l in kpi_data["lots"]])
        avg_setup = statistics.mean([l.setup_time_sum for l in kpi_data["lots"]])
        q_viol = sum([l.q_time_violations for l in kpi_data["lots"]])
        
        print(f"1. 생산량 (Throughput): {total_lots} 개")
        print(f"2. 평균 TAT (Lead Time): {avg_tat:.2f} 분")
        print(f"3. 평균 셋업 시간 (Setup): {avg_setup:.2f} 분")
        print(f"4. Q-Time 위반 총 횟수 : {q_viol} 회")
        
        # 납기 준수율 (간략)
        # lateness = [l.get_lateness() for l in kpi_data["lots"]]
        # print(f"5. 납기 지연 평균: {statistics.mean(lateness):.2f} 분")
    else:
        print("⚠️ 완료된 Lot이 없습니다.")
    print("="*60)

def run_simulation():
    env = simpy.Environment()
    db = SessionLocal()
    try:
        machines, routes = initialize_data(env, db)
        releases = db.query(LotRelease).all()
        
        count = 0
        for r in releases:
            if r.wafers_per_lot is None or r.wafers_per_lot == 0: continue
            env.process(run_source(env, r, machines, routes))
            count += 1
            
        print(f"🚀 시뮬레이션 시작 (Source: {count})")
        env.run(until=20000) # 충분히 길게
        print("⏹️ 종료")
        print_kpi()
        
    except Exception as e:
        print(f"❌ 에러: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    run_simulation()