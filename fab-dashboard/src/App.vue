<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import axios from 'axios';
import FabMap from './components/FabMap.vue';     // 맵 컴포넌트
import GanttChart from './components/GanttChart.vue'; // 간트 차트 컴포넌트

// --- 상태 변수들 ---
const status = ref({
  status_seq: 0,
  time: 0.0,
  is_paused: true,
  is_done: false,
  target_machine: null,
  queue: [],
  active_lots: [], // 👈 초기값 설정 (에러 방지용)
  progress_signature: '',
  kpi: { finished_lots: 0, avg_tat: 0, q_viol: 0, processing_lots: 0 }
});
const lastStatusAt = ref(0);
const startClickCount = ref(0);

const layoutData = ref({});
const isAutoRunning = ref(false);
let statusPollTimer = null;
const didAutoFreshStart = ref(false);
const didAutoResumeFromInitialPause = ref(false);

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const UI_REV = "ui-rev-2026-03-19-02";
const DEBUG_RUN_ID = `run-${Date.now()}`;
const heartbeat = computed(() => {
  const lots = status.value.active_lots || [];
  return {
    seq: status.value.status_seq || 0,
    active: lots.length,
    processing: status.value.kpi?.processing_lots || 0,
    firstLots: lots.slice(0, 2).map((l) => l.lot_name).join(", "),
    at: lastStatusAt.value ? new Date(lastStatusAt.value).toLocaleTimeString() : "-"
  };
});
const liveLotBadges = computed(() => {
  const lots = status.value.active_lots || [];
  return lots.slice(0, 6).map((l) => `${l.lot_name} (${l.status})`);
});
const duplicateLotNameCount = computed(() => {
  const lots = status.value.active_lots || [];
  const counts = new Map();
  for (const l of lots) counts.set(l.lot_name, (counts.get(l.lot_name) || 0) + 1);
  let dup = 0;
  for (const v of counts.values()) if (v > 1) dup += (v - 1);
  return dup;
});

// --- API 통신 함수들 ---
const fetchStatus = async () => {
  try {
    const res = await axios.get(`${API_URL}/api/status`);
    status.value = res.data;
    lastStatusAt.value = Date.now();
    if (!didAutoFreshStart.value && (status.value.time || 0) > 0) {
      didAutoFreshStart.value = true;
      // #region agent log
      fetch('http://127.0.0.1:7762/ingest/9df8c455-7c67-4da7-b636-1936eb121846',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'99a118'},body:JSON.stringify({sessionId:'99a118',runId:DEBUG_RUN_ID,hypothesisId:'H14',location:'App.vue:fetchStatus',message:'auto fresh start on mount',data:{timeBefore:status.value.time||0},timestamp:Date.now()})}).catch(()=>{});
      // #endregion
      const resetRes = await axios.post(`${API_URL}/api/control/reset`);
      status.value = resetRes.data;
      lastStatusAt.value = Date.now();
      await axios.post(`${API_URL}/api/control/resume`);
      isAutoRunning.value = true;
      runLoop();
      await fetchLayout();
      return;
    }
    if (
      !didAutoResumeFromInitialPause.value &&
      (status.value.time || 0) <= 1.0 &&
      !!status.value.is_paused &&
      !status.value.is_done &&
      (status.value.active_lots || []).length > 0
    ) {
      didAutoResumeFromInitialPause.value = true;
      // #region agent log
      fetch('http://127.0.0.1:7762/ingest/9df8c455-7c67-4da7-b636-1936eb121846',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'99a118'},body:JSON.stringify({sessionId:'99a118',runId:DEBUG_RUN_ID,hypothesisId:'H16',location:'App.vue:fetchStatus',message:'auto resume from initial paused state',data:{time:status.value.time||0,active:(status.value.active_lots||[]).length},timestamp:Date.now()})}).catch(()=>{});
      // #endregion
      await axios.post(`${API_URL}/api/control/resume`);
      isAutoRunning.value = true;
      runLoop();
      return;
    }
    if (!status.value.is_paused && !isAutoRunning.value && !status.value.is_done) {
      isAutoRunning.value = true;
      // #region agent log
      fetch('http://127.0.0.1:7762/ingest/9df8c455-7c67-4da7-b636-1936eb121846',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'99a118'},body:JSON.stringify({sessionId:'99a118',runId:DEBUG_RUN_ID,hypothesisId:'H13',location:'App.vue:fetchStatus',message:'auto-attach runLoop on running backend',data:{seq:status.value.status_seq||0,time:status.value.time||0,is_paused:!!status.value.is_paused},timestamp:Date.now()})}).catch(()=>{});
      // #endregion
      runLoop();
    }
    // #region agent log
    fetch('http://127.0.0.1:7762/ingest/9df8c455-7c67-4da7-b636-1936eb121846',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'99a118'},body:JSON.stringify({sessionId:'99a118',runId:DEBUG_RUN_ID,hypothesisId:'H11',location:'App.vue:fetchStatus',message:'initial status fetched',data:{seq:status.value.status_seq||0,time:status.value.time||0,active:(status.value.active_lots||[]).length,processing:status.value.kpi?.processing_lots||0,firstLotHasIndex:Object.prototype.hasOwnProperty.call((status.value.active_lots||[])[0]||{},'index'),duplicateNameCount:duplicateLotNameCount.value,uiRev:UI_REV},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
  } catch (error) { 
    console.error("API 연결 실패 (Status):", error); 
    // #region agent log
    fetch('http://127.0.0.1:7762/ingest/9df8c455-7c67-4da7-b636-1936eb121846',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'99a118'},body:JSON.stringify({sessionId:'99a118',runId:DEBUG_RUN_ID,hypothesisId:'H3',location:'App.vue:fetchStatus',message:'initial status fetch failed',data:{error:String(error)},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
  }
};

const fetchLayout = async () => {
  try {
    const res = await axios.get(`${API_URL}/api/layout`);
    layoutData.value = res.data;
  } catch (e) { 
    console.error("API 연결 실패 (Layout):", e); 
  }
};

const proceedStep = async () => {
  try {
    const res = await axios.post(`${API_URL}/api/step`);
    status.value = res.data;
    lastStatusAt.value = Date.now();
    // #region agent log
    fetch('http://127.0.0.1:7762/ingest/9df8c455-7c67-4da7-b636-1936eb121846',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'99a118'},body:JSON.stringify({sessionId:'99a118',runId:DEBUG_RUN_ID,hypothesisId:'H11',location:'App.vue:proceedStep',message:'step response applied',data:{seq:status.value.status_seq||0,time:status.value.time||0,paused:!!status.value.is_paused,target:status.value.target_machine||null,queueLen:(status.value.queue||[]).length,active:(status.value.active_lots||[]).length,processing:status.value.kpi?.processing_lots||0,firstLotHasIndex:Object.prototype.hasOwnProperty.call((status.value.active_lots||[])[0]||{},'index'),duplicateNameCount:duplicateLotNameCount.value},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    fetchLayout(); // 맵 업데이트
    
    if (status.value.is_done) {
      stopAutoRun();
      alert("🎉 시뮬레이션이 종료되었습니다! (90일 완주)");
    }
  } catch (error) { 
    console.error("Step 진행 실패:", error); 
    // #region agent log
    fetch('http://127.0.0.1:7762/ingest/9df8c455-7c67-4da7-b636-1936eb121846',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'99a118'},body:JSON.stringify({sessionId:'99a118',runId:DEBUG_RUN_ID,hypothesisId:'H3',location:'App.vue:proceedStep',message:'step request failed',data:{error:String(error)},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    // 에러 발생 시 루프가 끊기지 않도록 잠시 멈췄다 가기 위해 false 리턴 고려 가능
  }
};

// 👇 [핵심 수정] 안전한 재귀 루프 함수
const runLoop = async () => {
  // 1. 멈춤 상태거나 종료되었으면 중단
  if (!isAutoRunning.value || status.value.is_done) {
    console.log("🛑 루프 중단됨");
    return;
  }

  // 2. Step 실행 (응답이 올 때까지 기다림)
  await proceedStep();

  // 3. 응답이 오면, 0.1초 쉬었다가 다시 자기 자신을 호출 (재귀)
  if (isAutoRunning.value && !status.value.is_done) {
    setTimeout(runLoop, 100);
  }
};

// 👇 [핵심 수정] Resume이 확실히 성공한 뒤에 루프 시작
const startAutoRun = async () => {
  if (isAutoRunning.value) return;
  
  try {
    // 1. 상태 먼저 변경
    isAutoRunning.value = true;
    try {
      await axios.post(`${API_URL}/api/debug/ui-event`, {
        event: "start_auto_run_clicked",
        details: {
          uiRev: UI_REV,
          is_done: !!status.value?.is_done,
          is_paused: !!status.value?.is_paused,
          status_seq: status.value?.status_seq || 0
        }
      });
    } catch (_) {}
    
    // 2. 진행 중 세션 재진입 혼선을 막기 위해, START는 항상 fresh run으로 시작
    if ((status.value.time || 0) > 0) {
      const timeBeforeReset = status.value.time || 0;
      const resetRes = await axios.post(`${API_URL}/api/control/reset`);
      status.value = resetRes.data;
      lastStatusAt.value = Date.now();
      await fetchLayout();
      // #region agent log
      fetch('http://127.0.0.1:7762/ingest/9df8c455-7c67-4da7-b636-1936eb121846',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'99a118'},body:JSON.stringify({sessionId:'99a118',runId:DEBUG_RUN_ID,hypothesisId:'H12',location:'App.vue:startAutoRun',message:'auto reset before resume',data:{timeBefore:timeBeforeReset},timestamp:Date.now()})}).catch(()=>{});
      // #endregion
    }

    // 3. 백엔드에 Resume 요청 보내고 기다림 (await)
    console.log("📡 Resume 요청 전송...");
    await axios.post(`${API_URL}/api/control/resume`);
    console.log("✅ Resume 완료, 루프 시작");
    // #region agent log
    fetch('http://127.0.0.1:7762/ingest/9df8c455-7c67-4da7-b636-1936eb121846',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'99a118'},body:JSON.stringify({sessionId:'99a118',runId:DEBUG_RUN_ID,hypothesisId:'H4',location:'App.vue:startAutoRun',message:'resume acknowledged by backend',data:{autoRunning:isAutoRunning.value,uiRev:UI_REV},timestamp:Date.now()})}).catch(()=>{});
    // #endregion

    // 4. 루프 시작
    runLoop();
    
  } catch (error) {
    console.error("시작 실패:", error);
    // #region agent log
    fetch('http://127.0.0.1:7762/ingest/9df8c455-7c67-4da7-b636-1936eb121846',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'99a118'},body:JSON.stringify({sessionId:'99a118',runId:DEBUG_RUN_ID,hypothesisId:'H3',location:'App.vue:startAutoRun',message:'resume request failed',data:{error:String(error)},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    alert("서버와 통신할 수 없습니다.");
    isAutoRunning.value = false;
  }
};

const onStartClicked = () => {
  startClickCount.value += 1;
  // #region agent log
  axios.post(`${API_URL}/api/debug/ui-event`, {
    event: "start_button_handler_entered",
    details: { clicks: startClickCount.value, uiRev: UI_REV }
  }).catch(() => {});
  // #endregion
  startAutoRun();
};

const stopAutoRun = async () => {
  isAutoRunning.value = false;
  try {
    await axios.post(`${API_URL}/api/control/pause`);
  } catch (error) {
    console.error("일시정지 실패:", error);
  }
};

const resetSim = async () => {
  if(!confirm("정말 초기화 하시겠습니까?")) return;
  
  // 먼저 멈춤
  stopAutoRun();
  
  try {
    const res = await axios.post(`${API_URL}/api/control/reset`);
    status.value = res.data;
    lastStatusAt.value = Date.now();
    fetchLayout();
    console.log("🔄 리셋 완료");
  } catch (error) {
    console.error("리셋 실패:", error);
  }
};

const manualDispatch = async (idx) => {
  // 사용자가 개입하면 잠깐 멈췄다가 다시 시작하는 로직
  const wasRunning = isAutoRunning.value;
  if (wasRunning) isAutoRunning.value = false; // 일단 플래그만 내림 (서버 Pause 요청은 생략 가능)

  try {
    const res = await axios.post(`${API_URL}/api/dispatch`, { action_idx: idx });
    status.value = res.data;
    fetchLayout();
    alert(`✅ ${idx}번 랏을 우선 할당했습니다!`);
    
    // 원래 돌고 있었다면 다시 시작
    if (wasRunning) {
      isAutoRunning.value = true;
      runLoop();
    }
  } catch (error) { 
    alert("Dispatch 실패"); 
  }
};

const props = defineProps({
  queue: Array,
  currentTime: Number
});

// 상위 5개 보여주기
const topLots = computed(() => {
  // active_lots가 없으면 빈 배열 반환
  if (!status.value.active_lots) return [];
  
  // 가공 중(Processing)인 것을 맨 위로
  const sorted = [...status.value.active_lots].sort((a, b) => (a.status === 'Processing' ? -1 : 1));
  return sorted.slice(0, 5);
});

onMounted(() => {
  // #region agent log
  axios.post(`${API_URL}/api/debug/ui-event`, {
    event: "ui_mounted",
    details: { uiRev: UI_REV, status_seq: status.value?.status_seq || 0 }
  }).catch(() => {});
  // #endregion
  fetchStatus();
  fetchLayout();
  // Fallback polling keeps UI in sync even after page refresh
  // while backend simulation is already running.
  statusPollTimer = setInterval(async () => {
    await fetchStatus();
    await fetchLayout();
  }, 1000);
});

onUnmounted(() => {
  isAutoRunning.value = false;
  if (statusPollTimer) {
    clearInterval(statusPollTimer);
    statusPollTimer = null;
  }
});
</script>

<template>
  <div class="container">
    
    <header class="header">
      <div class="title-area">
        <h1>🏭 Smart Fab Digital Twin </h1>
        <div class="status-bar">
          <span class="mini-kpi">🔁 Seq: <strong>{{ status.status_seq || 0 }}</strong></span>
          <span>⏱️ Sim Time: <strong>{{ status.time.toFixed(1) }}</strong> min</span>
          <span class="mini-kpi">⚙️ Processing: <strong>{{ status.kpi.processing_lots }}</strong></span>
          <span class="mini-kpi">🧩 Active: <strong>{{ status.active_lots?.length || 0 }}</strong></span>
          <span :class="{'badge-run': !status.is_paused, 'badge-stop': status.is_paused}">
            {{ status.is_paused ? "⏸️ PAUSED" : "▶️ RUNNING" }}
          </span>
        </div>
        <div class="live-lots">
          <span class="live-label">Live Lots:</span>
          <span v-if="liveLotBadges.length === 0" class="live-empty">-</span>
          <span v-for="(name, idx) in liveLotBadges" :key="`live-${idx}-${name}`" class="live-badge">
            {{ name }}
          </span>
        </div>
      </div>
    </header>

    <div class="kpi-board">
      <div class="card">
        <h3>📦 생산량 (Throughput)</h3>
        <p>{{ status.kpi.finished_lots }} <small>Lots</small></p>
      </div>
      <div class="card">
        <h3>⚡ 평균 TAT</h3>
        <p>{{ status.kpi.avg_tat.toFixed(0) }} <small>min</small></p>
      </div>
      <div class="card warning">
        <h3>⚠️ Q-Time 위반</h3>
        <p>{{ status.kpi.q_viol }} <small>회</small></p>
      </div>
      <div class="card">
        <h3>⚙️ 가공 중 Lot</h3>
        <p>{{ status.kpi.processing_lots }} <small>Lots</small></p>
      </div>
      <div class="card">
        <h3>🧩 활성 Lot 수</h3>
        <p>{{ status.active_lots?.length || 0 }} <small>Lots</small></p>
      </div>
    </div>

    <div class="controls">
      <button v-if="!isAutoRunning" @click="onStartClicked" class="btn start">▶️ START SIMULATION</button>
      <button v-else @click="stopAutoRun" class="btn stop">⏸️ PAUSE</button>
      <button @click="proceedStep" class="btn step">👣 NEXT STEP</button>
      <button @click="resetSim" class="btn reset">🔄 RESET</button>
    </div>

    <GanttChart :queue="status.active_lots" :currentTime="status.time" />

    <div class="panel active-panel">
      <div class="panel-header">
        <h2>🧾 Active Lots</h2>
      </div>
      <div class="active-content">
        <div v-if="status.active_lots && status.active_lots.length">
          <div class="lot-list">
            <div
              v-for="(lot, idx) in topLots"
              :key="`${lot.lot_name}-${idx}-${lot.rem_steps}`"
              class="lot-card passive"
            >
              <div class="lot-header">
                <span class="lot-name">{{ lot.lot_name }}</span>
                <span class="priority">{{ lot.status }}</span>
              </div>
              <div class="lot-info">
                <div>Rem: {{ lot.rem_steps }} / {{ lot.total_steps }}</div>
                <div>Due: {{ lot.due_date }}</div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="waiting">
          <p>No active lots at current time.</p>
        </div>
      </div>
    </div>

    <div class="dashboard-body">
      
      <div class="panel queue-panel">
        <div class="panel-header">
          <h2>🚨 Decision Queue </h2>
          <span v-if="status.target_machine" class="machine-tag">{{ status.target_machine }}</span>
        </div>
        
        <div class="queue-content">
          <div v-if="status.target_machine">
            <p class="desc">AI is waiting for a decision. Click a lot to override.</p>
            <div class="lot-list">
              <div 
                v-for="lot in status.queue" 
                :key="lot.index"
                class="lot-card"
                @click="manualDispatch(lot.index)"
              >
                <div class="lot-header">
                  <span class="lot-name">{{ lot.lot_name }}</span>
                  <span class="priority">P{{ lot.priority }}</span>
                </div>
                <div class="lot-info">
                  <div>Rem: {{ lot.rem_steps }}</div>
                  <div>Due: {{ lot.due_date }}</div>
                  <div v-if="lot.q_danger > 0" class="danger-text">🔥 Q-Risk!</div>
                </div>
              </div>
            </div>
          </div>
          <div class="waiting" v-else>
            <h3 v-if="status.kpi.processing_lots > 0">⚙️ Running...</h3>
            <h3 v-else>💤 Idle...</h3>
            <p v-if="status.kpi.processing_lots > 0">
              Lots are currently processing. Waiting for next dispatch decision.
            </p>
            <p v-else>Waiting for next event.</p>
          </div>
        </div>
      </div>

      <div class="panel map-panel">
        <div class="panel-header">
          <h2>🗺️ Fab Layout Map</h2>
        </div>
        <div class="map-content">
          <FabMap :layoutData="layoutData" />
        </div>
      </div>

    </div>

    <div class="build-rev">Build: {{ UI_REV }}</div>
    <div class="build-rev">Heartbeat: seq={{ heartbeat.seq }}, active={{ heartbeat.active }}, processing={{ heartbeat.processing }}, at={{ heartbeat.at }}, lots={{ heartbeat.firstLots || '-' }}</div>
    <div class="build-rev">StartClicks: {{ startClickCount }}</div>
    <div class="build-rev">DupLotNames: {{ duplicateLotNameCount }}</div>
    <div class="build-rev">ProgressSig: {{ status.progress_signature || '-' }}</div>

  </div>
</template>

<style scoped>
/* 레이아웃 스타일링 */
.container { max-width: 1200px; margin: 0 auto; padding: 20px; font-family: 'Segoe UI', sans-serif; color: #333; }

/* 헤더 */
.header { display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 2px solid #eee; padding-bottom: 20px; margin-bottom: 20px; }
.title-area h1 { margin: 0; font-size: 1.8rem; color: #2c3e50; }
.status-bar { display: flex; gap: 15px; align-items: center; font-size: 1.1rem; }
.live-lots { margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.live-label { font-size: 0.85rem; color: #6b7280; }
.live-empty { font-size: 0.85rem; color: #9ca3af; }
.live-badge { background: #f0f9ff; color: #0f172a; border: 1px solid #bae6fd; border-radius: 12px; padding: 2px 8px; font-size: 0.8rem; }
.mini-kpi { background: #eef3ff; color: #2c3e50; padding: 4px 10px; border-radius: 16px; font-size: 0.9rem; border: 1px solid #d6e0ff; }
.badge-run { background: #d4edda; color: #155724; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9rem; border: 1px solid #c3e6cb; }
.badge-stop { background: #f8d7da; color: #721c24; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9rem; border: 1px solid #f5c6cb; }

/* KPI */
.kpi-board { display: grid; grid-template-columns: repeat(5, 1fr); gap: 20px; margin-bottom: 20px; }
.card { background: white; padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eee; }
.card h3 { margin: 0 0 10px 0; color: #7f8c8d; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; }
.card p { margin: 0; font-size: 2rem; font-weight: bold; color: #2c3e50; }
.card.warning p { color: #e74c3c; }

/* 컨트롤 */
.controls { display: flex; gap: 10px; margin-bottom: 30px; }
.btn { flex: 1; padding: 15px; border: none; border-radius: 8px; cursor: pointer; font-size: 1rem; font-weight: bold; color: white; transition: all 0.2s; text-transform: uppercase; letter-spacing: 0.5px; }
.btn.start { background: linear-gradient(135deg, #2ecc71, #27ae60); box-shadow: 0 4px 10px rgba(46, 204, 113, 0.3); }
.btn.stop { background: linear-gradient(135deg, #f1c40f, #f39c12); box-shadow: 0 4px 10px rgba(241, 196, 15, 0.3); }
.btn.step { background: linear-gradient(135deg, #3498db, #2980b9); box-shadow: 0 4px 10px rgba(52, 152, 219, 0.3); }
.btn.reset { background: #95a5a6; }
.btn:hover { transform: translateY(-2px); opacity: 0.95; }
.btn:active { transform: translateY(0); }

/* 대시보드 바디 */
.dashboard-body {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 25px;
  height: 650px;
}
.active-panel { margin-bottom: 20px; }
.active-content { padding: 15px; }

/* 패널 공통 */
.panel { background: #f8f9fa; border-radius: 12px; border: 1px solid #e9ecef; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.03); }
.panel-header { background: white; padding: 15px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
.panel-header h2 { margin: 0; font-size: 1.1rem; color: #2c3e50; font-weight: 700; }
.machine-tag { background: #3498db; color: white; padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; font-weight: bold; }

/* 왼쪽 패널 */
.queue-panel { border-left: 5px solid #3498db; }
.queue-content { padding: 15px; overflow-y: auto; flex: 1; display: flex; flex-direction: column; }
.desc { font-size: 0.85rem; color: #7f8c8d; margin-bottom: 15px; text-align: center; }
.lot-list { display: flex; flex-direction: column; gap: 10px; }
.lot-card { background: white; padding: 12px; border-radius: 8px; cursor: pointer; border: 1px solid #eee; transition: all 0.2s; position: relative; overflow: hidden; }
.lot-card:hover { border-color: #3498db; transform: translateX(5px); box-shadow: 0 3px 8px rgba(0,0,0,0.05); }
.lot-card.passive { cursor: default; border-style: dashed; }
.lot-card.passive:hover { transform: none; border-color: #eee; box-shadow: none; }
.lot-header { display: flex; justify-content: space-between; margin-bottom: 8px; font-weight: bold; }
.priority { background: #ecf0f1; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; color: #7f8c8d; }
.lot-info { font-size: 0.85rem; color: #666; display: flex; justify-content: space-between; }
.danger-text { color: #e74c3c; font-weight: bold; }

.waiting { flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; color: #bdc3c7; }

/* 오른쪽 패널 */
.map-panel { background: white; }
.map-content { padding: 15px; overflow-y: auto; flex: 1; }
.build-rev { margin-top: 12px; text-align: right; color: #9aa3af; font-size: 0.75rem; }
</style>