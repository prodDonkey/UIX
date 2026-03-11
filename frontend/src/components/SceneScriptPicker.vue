<template>
  <el-dialog :model-value="visible" title="添加脚本" width="720px" @close="emit('close')">
    <el-input v-model="keyword" placeholder="按脚本名称搜索" clearable class="search-input" />

    <el-table :data="filteredScripts" max-height="360" empty-text="暂无可添加脚本">
      <el-table-column label="名称" min-width="220">
        <template #default="{ row }">
          {{ row.name }}
        </template>
      </el-table-column>
      <el-table-column label="来源" width="120">
        <template #default="{ row }">
          {{ formatSourceType(row.source_type) }}
        </template>
      </el-table-column>
      <el-table-column label="所属场景数" width="120">
        <template #default="{ row }">
          {{ row.scene_count ?? 0 }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click="emit('select', row)">添加</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

import type { Script } from '../api/scripts';

const props = defineProps<{
  visible: boolean;
  scripts: Script[];
  excludedScriptIds: number[];
}>();

const emit = defineEmits<{
  close: [];
  select: [script: Script];
}>();

const keyword = ref('');

const filteredScripts = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase();
  return props.scripts.filter((script) => {
    if (props.excludedScriptIds.includes(script.id)) return false;
    if (!normalizedKeyword) return true;
    return script.name.toLowerCase().includes(normalizedKeyword);
  });
});

function formatSourceType(sourceType: string) {
  if (sourceType === 'manual') return '手动';
  if (sourceType === 'ai') return 'AI生成';
  return sourceType || '-';
}
</script>

<style scoped>
.search-input {
  margin-bottom: 12px;
}
</style>
