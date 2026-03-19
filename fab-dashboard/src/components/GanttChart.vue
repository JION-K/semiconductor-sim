<script setup>
import { ref, computed } from 'vue';

const props = defineProps({
  queue: Array,     // 전체 대기열 데이터
  currentTime: Number // 현재 시뮬레이션 시간
});

const selectedLot = ref(null);

// 상위 3개 랏만 추출
const topLots = computed(() => {
  return props.queue ? props.queue.slice(0, 3) : [];
});

const selectLot = (lot) => {
  selectedLot.value = lot;
};

// 👇 [추가] 납기 바(Bar) 퍼센트 계산 함수
const getDueBarWidth = (due, current) => {
  const total = Number(due);
  if (!total || total === 0) return '0%';
  
  // (현재시간 / 납기일) * 100
  let pct = (current / total) * 100;
  
  // 100% 넘어가면(지각하면) 꽉 채움
  if (pct > 100) pct = 100;
  
  return pct + '%';
};

// 👇 [추가] 남은 시간 텍스트 포맷팅 함수
const formatTimeRem = (due, current) => {
  const diff = Number(due) - current;
  if (diff >= 0) {
    return `남은 시간: ${diff.toFixed(1)} min`;
  } else {
    // 음수면 절대값 씌우고 '지연' 표시
    return `🚨 지연 (Overdue): +${Math.abs(diff).toFixed(1)} min`;
  }
};
</script>

<template>
  <div class="gantt-section" v-if="topLots.length > 0">
    <h3>📊 실시간 Lot 추적 (Top 3)</h3>
    <div class="gantt-grid">
      
      <div class="gantt-list">
        <button 
          v-for="(lot, idx) in topLots" 
          :key="`${lot.lot_name}-${idx}-${lot.rem_steps}`"
          class="lot-btn"
          :class="{ active: selectedLot === lot }"
          @click="selectLot(lot)"
        >
          {{ lot.lot_name }}
        </button>
      </div>

      <div class="gantt-view" v-if="selectedLot">
        <div class="chart-header">
          <strong>{{ selectedLot.lot_name }}</strong> ({{ selectedLot.product }})
        </div>
        
        <div class="progress-container">
          <div class="progress-label">공정 진행률 (Step Progress)</div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" 
                 :style="{ width: (selectedLot.total_steps ? ((1 - selectedLot.rem_steps / selectedLot.total_steps) * 100) : (100 - (selectedLot.rem_steps * 5))) + '%' }">
            </div>
          </div>
          <div class="progress-info">
            진행: {{ selectedLot.total_steps - selectedLot.rem_steps }} / {{ selectedLot.total_steps }} steps
          </div>
        </div>

        <div class="progress-container">
          <div class="progress-label">납기 현황 (Due Date Status)</div>
           <div class="due-bar-bg">
             <div class="due-marker" :style="{ left: '100%' }">🚩 마감</div>
             <div class="due-bar-fill" 
                  :class="{ 'overdue-bar': (Number(selectedLot.due_date) - currentTime) < 0 }"
                  :style="{ width: getDueBarWidth(selectedLot.due_date, currentTime) }">
             </div> 
           </div>
           <div class="progress-info" :class="{ 'overdue-text': (Number(selectedLot.due_date) - currentTime) < 0 }">
             {{ formatTimeRem(selectedLot.due_date, currentTime) }}
           </div>
        </div>
      </div>
      
      <div class="gantt-view empty" v-else>
        👈 Lot을 클릭하여 상세 정보를 확인하세요.
      </div>
    </div>
  </div>
</template>

<style scoped>
.gantt-section { background: white; border: 1px solid #ddd; border-radius: 10px; padding: 15px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
.gantt-section h3 { margin: 0 0 10px 0; font-size: 1rem; color: #333; }
.gantt-grid { display: grid; grid-template-columns: 150px 1fr; gap: 15px; }
.gantt-list { display: flex; flex-direction: column; gap: 5px; }
.lot-btn { padding: 10px; border: 1px solid #eee; background: #f9f9f9; cursor: pointer; border-radius: 5px; text-align: left; font-weight: bold; transition: 0.2s; font-size: 0.9rem; }
.lot-btn:hover { background: #eef; }
.lot-btn.active { background: #3498db; color: white; border-color: #3498db; }

.gantt-view { background: #fafafa; padding: 15px; border-radius: 5px; border: 1px solid #eee; }
.gantt-view.empty { display: flex; align-items: center; justify-content: center; color: #999; }
.chart-header { font-size: 1.1rem; margin-bottom: 15px; border-bottom: 1px solid #ddd; padding-bottom: 5px; }

.progress-container { margin-bottom: 15px; }
.progress-label { font-size: 0.8rem; color: #666; margin-bottom: 5px; font-weight: bold; }

/* 공정 진행률 바 */
.progress-bar-bg { background: #e0e0e0; height: 20px; border-radius: 10px; overflow: hidden; }
.progress-bar-fill { background: linear-gradient(90deg, #3498db, #2ecc71); height: 100%; transition: width 0.5s; }

/* 납기 바 */
.due-bar-bg { background: #e0e0e0; height: 10px; border-radius: 5px; position: relative; margin-top: 15px; margin-bottom: 5px; }
.due-bar-fill { background: #f39c12; height: 100%; border-radius: 5px; transition: width 0.5s; } /* 기본: 주황색 */
.due-bar-fill.overdue-bar { background: #e74c3c; } /* 지연: 빨간색 */

.due-marker { position: absolute; top: -18px; font-size: 0.7rem; color: #666; font-weight: bold; transform: translateX(-100%); }

.progress-info { text-align: right; font-size: 0.85rem; color: #333; margin-top: 4px; }
.overdue-text { color: #e74c3c; font-weight: bold; animation: blink 2s infinite; }

@keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }
</style>