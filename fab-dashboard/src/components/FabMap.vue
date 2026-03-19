<script setup>
import { computed } from 'vue';

// 부모(App.vue)로부터 layout 데이터를 받음
const props = defineProps({
  layoutData: Object
});

// 색상 매핑 (공정별 구분을 위해)
const getGroupColor = (groupName) => {
  if (groupName.includes('Litho')) return '#ffecb3'; // 노랑 (Photo)
  if (groupName.includes('Etch')) return '#ffcdd2';  // 빨강 (Etch)
  if (groupName.includes('Dep') || groupName.includes('TF')) return '#bbdefb'; // 파랑 (Thin Film)
  if (groupName.includes('Imp')) return '#d1c4e9';   // 보라 (Implant)
  if (groupName.includes('CMP') || groupName.includes('Planar')) return '#c8e6c9'; // 초록 (CMP)
  return '#e0e0e0'; // 기타
};
</script>

<template>
  <div class="fab-map-container">
    <h2>🏭 Fab Layout Map</h2>
    
    <div class="fab-grid">
      <div 
        v-for="(machines, groupName) in layoutData" 
        :key="groupName" 
        class="fab-zone"
        :style="{ borderColor: getGroupColor(groupName) }"
      >
        <h3 :style="{ backgroundColor: getGroupColor(groupName) }">{{ groupName }} Zone</h3>
        
        <div class="tool-list">
          <div v-for="m in machines" :key="m.name" class="tool-group">
            <div class="tool-header">
              <span>{{ m.name }}</span>
              <small>{{ m.utilization.toFixed(0) }}%</small>
            </div>
            
            <div class="slots">
              <div v-for="n in m.busy" :key="'busy'+n" class="slot busy" title="Running"></div>
              <div v-for="n in (m.total - m.busy)" :key="'idle'+n" class="slot idle" title="Idle"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fab-map-container { margin-top: 20px; padding: 20px; background: white; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
.fab-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }

.fab-zone { border: 2px solid #ccc; border-radius: 8px; overflow: hidden; }
.fab-zone h3 { margin: 0; padding: 10px; font-size: 1rem; color: #333; text-transform: uppercase; }

.tool-list { padding: 10px; display: flex; flex-direction: column; gap: 10px; }
.tool-group { display: flex; justify-content: space-between; align-items: center; background: #f9f9f9; padding: 8px; border-radius: 5px; }
.tool-header { display: flex; flex-direction: column; width: 100px; font-size: 0.85rem; font-weight: bold; }

.slots { display: flex; gap: 4px; flex-wrap: wrap; }
.slot { width: 15px; height: 15px; border-radius: 3px; border: 1px solid rgba(0,0,0,0.1); }
.slot.busy { background-color: #4caf50; box-shadow: 0 0 5px #4caf50; animation: pulse 1s infinite; }
.slot.idle { background-color: #e0e0e0; }

@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }
</style>