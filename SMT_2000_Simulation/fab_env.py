import gymnasium as gym
from gymnasium import spaces
import numpy as np
import simpy
import random
from collections import defaultdict
from datetime import datetime
import sys # 출력 강제 배출용

# DB Loading
from database import SessionLocal
from models import ToolGroup, LotRelease, ProcessStep, SetupInfo, BreakdownEvent, SimulationLog

# ==============================================================================
# 1. Helper Logic
# ==============================================================================

class LotStat:
    def __init__(self, name, product, start_time, due_date):
        self.name = name
        self.product = product
        self.start_time = start_time
        self.end_time = None
        self.due_date = due_date
        self.setup_time_sum = 0.0
        self.q_time_violations = 0
        self.history = {}
        
    def get_tat(self):
        if self.end_time: return self.end_time - self.start_time
        return 0.0

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

SIM_START = datetime(2018, 1, 1, 0, 0, 0)

def calc_minutes(date_str):
    s = str(date_str).strip()
    if not s or s.lower() in ['none', 'nan', 'nat', '']: return 0.0
    
    formats = [
        "%Y-%m-%d %H:%M:%S",    
        "%Y-%m-%d %H:%M:%S.%f", 
        "%m-%d-%y %H:%M:%S",    
        "%Y-%m-%d",             
        "%d-%m-%Y %H:%M:%S"     
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return max(0.0, (dt - SIM_START).total_seconds() / 60.0)
        except ValueError:
            continue
            
    print(f"⚠️ [Date Parse Error] 변환 실패: '{s}' -> 0.0", flush=True)
    return 0.0

def get_proc_time(step):
    mean = step.proc_time_mean if step.proc_time_mean else 0.0
    offset = step.proc_time_offset if step.proc_time_offset else 0.0
    dist = str(step.proc_time_dist).lower()
    val = mean
    if "uniform" in dist:
        val = random.uniform(max(0, mean - offset), mean + offset)
    elif "normal" in dist:
        val = random.normalvariate(mean, offset)
    return max(0.0, val)

# ==============================================================================
# 2. FabEnv Class
# ==============================================================================

class FabEnv(gym.Env):
    metadata = {'render_modes': ['human']}

    def __init__(self):
        super(FabEnv, self).__init__()
        
        self.candidate_limit = 10  
        self.feature_dim = 6       
        
        self.action_space = spaces.Discrete(self.candidate_limit)
        total_obs = 2 + (self.candidate_limit * self.feature_dim)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(total_obs,), dtype=np.float32)

        self.sim_env = None
        self.machines = {}
        self.batch_queues = defaultdict(list)
        self.kpi = {"lots": [], "breakdowns": []}
        
        self.decision_event = None 
        self.target_machine_name = None 
        self.active_lots_data = {}
        # 초기 구간에서 "정지처럼 보이는" 시간을 줄이기 위해
        # 부분 배치 강제 시작 대기시간을 짧게 둔다.
        self.batch_max_wait = 5.0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        print("🔄 [FabEnv] Resetting... Loading DB", flush=True)
        
        self.sim_env = simpy.Environment()
        self.batch_queues = defaultdict(list)
        self.kpi = {"lots": [], "breakdowns": []}
        self.machines = {}
        self.active_lots_data = {} 
        
        db = SessionLocal()
        try:
            self._build_simulation(db)
        finally:
            db.close()
        
        print("🔄 [FabEnv] Initialized. Proceeding...", flush=True)
        self._resume_simulation()
        print(f"✅ [FabEnv] Reset complete (Current time: {self.sim_env.now:.2f})", flush=True)
        
        return self._get_observation(), {}

    def step(self, action):
        m_name = self.target_machine_name
        
        # 👇 [디버그] Step 호출 확인 로그
        print(f"👣 [Step] Action 요청됨 (Target: {m_name})", flush=True)

        if m_name is not None and m_name in self.machines:
            m_data = self.machines[m_name]
            queue = m_data['queue']
            
            valid_idx = action if action < len(queue) else 0
            if len(queue) > 0:
                selected_lot_event = queue.pop(valid_idx)
                if not selected_lot_event.triggered:
                    selected_lot_event.succeed() 
        
        prev_completed_count = len(self.kpi['lots'])
        self._resume_simulation()
        
        curr_completed_count = len(self.kpi['lots'])
        new_finished_count = curr_completed_count - prev_completed_count
        
        truncated = False
        terminated = (self.sim_env.now >= 200000) 

        reward = self._calculate_reward(new_finished_count)
        observation = self._get_observation()
        
        return observation, reward, terminated, truncated, {}

    def _resume_simulation(self):
        self.decision_event = self.sim_env.event()
        try:
            # 👇 [핵심] 1분 단위 심장 박동 로그 (살아있는지 확인용)
            print(f"⏱️ [Tick] Time: {self.sim_env.now:.2f}", flush=True)
            
            timeout_event = self.sim_env.timeout(1.0)
            self.sim_env.run(until=self.decision_event | timeout_event)
        except simpy.Interrupt:
            pass

    def _get_observation(self):
        m_name = self.target_machine_name
        if not m_name: return np.zeros(self.observation_space.shape, dtype=np.float32)
        
        m_data = self.machines.get(m_name)
        if not m_data: return np.zeros(self.observation_space.shape, dtype=np.float32)

        queue = m_data['queue']
        raw_setup = str(m_data['current_setup']) if m_data['current_setup'] else "None"
        curr_setup_val = 0.0
        
        try:
            clean_setup = raw_setup.replace("Setup_", "").replace("setup_", "")
            if 'E' in clean_setup:
                num_part = clean_setup.replace('E', '')
                curr_setup_val = float(num_part) + 10000.0
            else:
                curr_setup_val = float(clean_setup)
        except ValueError:
            curr_setup_val = float(sum(ord(c) for c in raw_setup))
        
        obs = [curr_setup_val, float(len(queue))]
        
        for i in range(self.candidate_limit):
            if i < len(queue):
                lot_info = queue[i].payload 
                is_setup_match = 1.0 if lot_info['req_setup'] == m_data['current_setup'] else 0.0
                
                feat = [
                    lot_info['rem_steps'],
                    lot_info['due_date'] - self.sim_env.now,
                    is_setup_match,
                    lot_info['q_danger'],
                    lot_info['priority'],
                    1.0 if lot_info['is_batch'] else 0.0
                ]
                obs.extend(feat)
            else:
                obs.extend([0]*self.feature_dim)
                
        return np.array(obs, dtype=np.float32)
    
    def _calculate_reward(self, new_count):
        reward = -0.1 
        if new_count > 0:
            reward += (new_count * 500.0)
            recent_lots = self.kpi['lots'][-new_count:]
            for lot in recent_lots:
                if lot.q_time_violations > 0:
                    reward -= (lot.q_time_violations * 50.0)
        return reward

    def _save_log(self, log_data):
        try:
            db = SessionLocal()
            log_entry = SimulationLog(
                lot_id=log_data['lot_id'],
                product=log_data['product'],
                route_id=log_data['route_id'],
                step_seq=log_data['step_seq'],
                step_name=log_data['step_name'],
                tool_group=log_data['tool_group'],
                arrive_time=log_data['arrive_time'],
                start_time=log_data['start_time'],
                end_time=log_data['end_time'],
                queue_time=log_data['start_time'] - log_data['arrive_time'],
                process_time=log_data['end_time'] - log_data['start_time'],
                event_type='PROCESS'
            )
            db.add(log_entry)
            db.commit()
            db.close()
        except Exception as e:
            print(f"⚠️ [Log Error] DB 저장 실패: {e}", flush=True)

    def _build_simulation(self, db):
        setups = db.query(SetupInfo).all()
        setup_mgr = SetupManager(setups)
        bds = db.query(BreakdownEvent).all()
        
        tgs = db.query(ToolGroup).all()
        for tg in tgs:
            my_bd = next((b for b in bds if b.target_name in tg.toolgroup_name), None)
            res = simpy.PriorityResource(self.sim_env, capacity=tg.num_tools)
            print(f"🔧 장비 생성: {tg.toolgroup_name}", flush=True)

            self.machines[tg.toolgroup_name] = {
                'resource': res,
                'current_setup': None,
                'setup_mgr': setup_mgr,
                'queue': [], 
                'name': tg.toolgroup_name
            }
            
            if my_bd:
                self.sim_env.process(self._breakdown_process(tg.toolgroup_name, my_bd))
            
            for _ in range(tg.num_tools):
                self.sim_env.process(self._machine_monitor(tg.toolgroup_name))

        steps = db.query(ProcessStep).order_by(ProcessStep.route_id, ProcessStep.step_seq).all()
        self.routes = defaultdict(list)
        for s in steps: self.routes[s.route_id].append(s)
        
        releases = db.query(LotRelease).all()
        count = 0
        for r in releases:
            if r.wafers_per_lot and r.wafers_per_lot > 0:
                self.sim_env.process(self._source_process(r))
                count += 1
        print(f"📥 [FabEnv] Source {count} created", flush=True)

    def _source_process(self, r):
        start_delay = calc_minutes(r.start_date)
        due_date_val = calc_minutes(r.due_date)
        
        if due_date_val == 0.0:
            print(f"⚠️ [데이터 경고] 납기일 0! Lot: {r.lot_type}", flush=True)

        if start_delay > 0: yield self.sim_env.timeout(start_delay)
        
        if not r.release_interval or r.release_interval <= 0:
            lot_name = r.lot_type if r.lot_type else f"Eng_{r.product_name}_1"
            self.sim_env.process(self._lot_process(lot_name, r.product_name, r.route_name, due_date_val, r.priority))
        else:
            cnt = 1
            while True:
                lot_name = f"Lot_{r.product_name}_{cnt}"
                self.sim_env.process(self._lot_process(lot_name, r.product_name, r.route_name, due_date_val, r.priority))
                yield self.sim_env.timeout(r.release_interval)
                cnt += 1

    def _lot_process(self, lot_name, product_name, route_name, due_date, priority):
        my_steps = self.routes.get(route_name)
        if not my_steps: return

        stat = LotStat(lot_name, route_name, self.sim_env.now, due_date)
        print(f"[{self.sim_env.now:8.2f}] 📦 {lot_name} 투입됨", flush=True)

        lot_global_info = {
            'lot_name': lot_name,
            'product': route_name,
            'rem_steps': len(my_steps),
            'total_steps': len(my_steps),
            'due_date': due_date,
            'start_time': self.sim_env.now,
            'status': 'Waiting' 
        }
        self.active_lots_data[lot_name] = lot_global_info

        for i, step in enumerate(my_steps):
            self.active_lots_data[lot_name]['status'] = 'Queuing'
            self.active_lots_data[lot_name]['rem_steps'] = len(my_steps) - i

            arrive_time = self.sim_env.now

            if step.cqt_start_step and step.cqt_limit:
                start_seq = step.cqt_start_step
                if start_seq in stat.history:
                    if (self.sim_env.now - stat.history[start_seq]) > step.cqt_limit:
                        stat.q_time_violations += 1

            m_name = step.target_tool_group
            if m_name not in self.machines: continue
            
            is_batch = (step.proc_unit == 'Batch')
            batch_id = (step.route_id, step.step_seq)
            
            permission_event = self.sim_env.event()
            
            lot_info = {
                'name': lot_name, 'rem_steps': len(my_steps) - i, 
                'due_date': due_date, 'req_setup': step.setup_id,
                'q_danger': 0.0, 'priority': priority, 'is_batch': is_batch
            }
            permission_event.payload = lot_info

            run_now = False 

            if is_batch:
                self.batch_queues[batch_id].append(permission_event)
                permission_event.enqueue_time = self.sim_env.now
                queue = self.batch_queues[batch_id]
                b_min = step.batch_min if step.batch_min else 1
                
                if len(queue) >= b_min:
                    batch_group = queue[:step.batch_max if step.batch_max else 1]
                    self.batch_queues[batch_id] = queue[len(batch_group):]
                    leader_evt = batch_group[0] 
                    followers = batch_group[1:]
                    
                    self.machines[m_name]['queue'].append(leader_evt)
                    self._check_trigger(m_name)
                    
                    yield leader_evt 
                    run_now = True
                    for f in followers: f.succeed() 
                else:
                    # Batch minimum이 과도하게 크면 영구 대기가 발생할 수 있어
                    # 최대 대기시간 이후에는 부분 배치로 강제 시작한다.
                    timeout_evt = self.sim_env.timeout(self.batch_max_wait)
                    result = yield permission_event | timeout_evt
                    if permission_event in result:
                        pass
                    else:
                        queue = self.batch_queues[batch_id]
                        if permission_event in queue:
                            take_n = min(len(queue), step.batch_max if step.batch_max else 1)
                            batch_group = queue[:take_n]
                            self.batch_queues[batch_id] = queue[take_n:]
                            leader_evt = batch_group[0]
                            followers = batch_group[1:]
                            print(
                                f"🕒 [Batch Timeout] {m_name} batch released with {len(batch_group)} lots "
                                f"(wait={self.batch_max_wait}m, min={b_min})",
                                flush=True
                            )
                            self.machines[m_name]['queue'].append(leader_evt)
                            self._check_trigger(m_name)
                            yield leader_evt
                            run_now = True
                            for f in followers:
                                if not f.triggered:
                                    f.succeed()
            else:
                self.machines[m_name]['queue'].append(permission_event)
                self._check_trigger(m_name)
                # print(f"[{self.sim_env.now:8.2f}] ⏳ {lot_name} 대기열 진입 ({m_name})", flush=True)
                yield permission_event 
                run_now = True

            if run_now:
                # print(f"[{self.sim_env.now:8.2f}] ✋ {lot_name} -> {m_name} 장비 요청...", flush=True)
                
                machine_res = self.machines[m_name]['resource']
                with machine_res.request(priority=10) as req:
                    yield req
                    
                    print(f"[{self.sim_env.now:8.2f}] ⚙️ {lot_name} -> {m_name} 작업 시작", flush=True)
                    
                    start_time = self.sim_env.now
                    self.active_lots_data[lot_name]['status'] = 'Processing'

                    m_data = self.machines[m_name]
                    if step.setup_id and m_data['current_setup'] != step.setup_id:
                        setup_time = m_data['setup_mgr'].get_setup_time(m_name, m_data['current_setup'], step.setup_id)
                        if setup_time > 0: 
                            # print(f"   (Setup: {setup_time:.1f}분)", flush=True)
                            yield self.sim_env.timeout(setup_time)
                        m_data['current_setup'] = step.setup_id
                        stat.setup_time_sum += setup_time
                    
                    proc_time = get_proc_time(step)
                    yield self.sim_env.timeout(proc_time)
                    
                    end_time = self.sim_env.now
                    print(f"[{self.sim_env.now:8.2f}] ✅ {lot_name} -> {m_name} 완료", flush=True)
                    
                    self._save_log({
                        'lot_id': lot_name,
                        'product': product_name,
                        'route_id': route_name,
                        'step_seq': step.step_seq,
                        'step_name': step.step_name,
                        'tool_group': m_name,
                        'arrive_time': arrive_time,
                        'start_time': start_time,
                        'end_time': end_time
                    })
            
            stat.history[step.step_seq] = self.sim_env.now

        if lot_name in self.active_lots_data:
            del self.active_lots_data[lot_name]

        stat.end_time = self.sim_env.now
        self.kpi['lots'].append(stat)
        print(f"[{self.sim_env.now:8.2f}] 🎉 {lot_name} 최종 완료", flush=True)

    def _breakdown_process(self, m_name, bd_data):
        mean = bd_data.foa_mean if bd_data.foa_mean else bd_data.mttf_mean
        if mean > 0: yield self.sim_env.timeout(random.expovariate(1.0/mean))
        while True:
            res = self.machines[m_name]['resource']
            with res.request(priority=0) as req:
                yield req
                repair_time = random.expovariate(1.0/bd_data.mttr_mean) if bd_data.mttr_mean else 0
                self.kpi['breakdowns'].append((m_name, repair_time))
                print(f"   [{self.sim_env.now:8.2f}] 💥 {m_name} 고장", flush=True) 
                yield self.sim_env.timeout(repair_time)
                print(f"   [{self.sim_env.now:8.2f}] 🔧 {m_name} 수리 완료", flush=True)
            next_fail = random.expovariate(1.0/bd_data.mttf_mean) if bd_data.mttf_mean else 1e6
            yield self.sim_env.timeout(next_fail)

    def _machine_monitor(self, m_name):
        """
        장비 상태를 주기적으로 감시하다가, '대기열도 있고 장비도 비었으면' AI를 호출
        """
        while True:
            # 1초마다 검사
            yield self.sim_env.timeout(1.0)
            
            queue = self.machines[m_name]['queue']
            res = self.machines[m_name]['resource']
            
            # 👇 [디버그] 모니터링 로그 (너무 시끄러우면 주석 처리)
            # if len(queue) > 0:
            #    print(f"👀 [Monitor] {m_name}: Q={len(queue)}, Busy={res.count}/{res.capacity}", flush=True)

            if len(queue) > 0 and (res.capacity - res.count > 0):
                self.target_machine_name = m_name
                if not self.decision_event.triggered:
                    # print(f"🔔 [Trigger] {m_name}에서 AI 호출! (Monitor)", flush=True)
                    self.decision_event.succeed()

    def _check_trigger(self, m_name):
        """
        랏이 대기열에 들어올 때 즉시 호출되는 함수
        """
        res = self.machines[m_name]['resource']
        queue = self.machines[m_name]['queue']
        
        # print(f"CHECK TRIGGER: {m_name} (Q: {len(queue)}, Idle: {res.capacity - res.count})", flush=True)

        if len(queue) > 0 and (res.capacity - res.count > 0):
            self.target_machine_name = m_name
            if not self.decision_event.triggered:
                print(f"🔔 [Trigger] {m_name}에서 AI 호출! (Instant)", flush=True)
                self.decision_event.succeed()