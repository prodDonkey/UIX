<template>
  <el-card>
    <template #header>
      <div class="header">
        <span>场景列表</span>
        <el-button type="primary" @click="createScene">新建场景</el-button>
      </div>
    </template>

    <el-table :data="scenes" v-loading="loading" row-key="id">
      <el-table-column label="名称" min-width="220">
        <template #default="{ row }">
          <el-button link type="primary" class="name-link" @click="goDetail(row.id)">
            {{ row.name }}
          </el-button>
        </template>
      </el-table-column>
      <el-table-column label="脚本数" width="100">
        <template #default="{ row }">
          {{ row.script_count }}
        </template>
      </el-table-column>
      <el-table-column label="来源" width="120">
        <template #default="{ row }">
          {{ formatSourceType(row.source_type) }}
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="更新时间" min-width="180" :formatter="formatTime" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="goDetail(row.id)">编辑</el-button>
          <el-button size="small" @click="copyScene(row.id)">复制</el-button>
          <el-button size="small" type="danger" @click="deleteScene(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { sceneApi, type Scene } from '../api/scenes';
import { formatServerDateTime } from '../utils/datetime';

const router = useRouter();
const loading = ref(false);
const scenes = ref<Scene[]>([]);

onMounted(async () => {
  await refresh();
});

async function refresh() {
  loading.value = true;
  try {
    scenes.value = await sceneApi.list();
  } finally {
    loading.value = false;
  }
}

async function createScene() {
  const created = await sceneApi.create({
    name: `new-scene-${Date.now()}`,
    description: '',
    source_type: 'manual',
  });
  ElMessage.success('场景已创建');
  await router.push({ name: 'scene-detail', params: { id: created.id } });
}

async function deleteScene(id: number) {
  await ElMessageBox.confirm('确认删除该场景吗？删除后不会影响脚本资产。', '提示', { type: 'warning' });
  await sceneApi.remove(id);
  ElMessage.success('删除成功');
  await refresh();
}

async function copyScene(id: number) {
  const copied = await sceneApi.copy(id);
  ElMessage.success('复制成功');
  await router.push({ name: 'scene-detail', params: { id: copied.id } });
}

function goDetail(id: number) {
  router.push({ name: 'scene-detail', params: { id } });
}

function formatSourceType(sourceType: string) {
  if (sourceType === 'manual') return '手动';
  if (sourceType === 'ai') return 'AI生成';
  return sourceType || '-';
}

function formatTime(_: unknown, __: unknown, value: string) {
  return formatServerDateTime(value);
}
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.name-link {
  padding: 0;
  height: auto;
}
</style>
