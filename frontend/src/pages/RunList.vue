<template>
  <el-card>
    <template #header>
      <div class="header">
        <span>运行列表</span>
        <el-button @click="refresh">刷新</el-button>
      </div>
    </template>

    <el-tabs v-model="activeTab" class="tabs">
      <el-tab-pane :label="`全部 (${runs.length})`" name="all" />
      <el-tab-pane :label="`排队 (${statusCounts.queued})`" name="queued" />
      <el-tab-pane :label="`运行中 (${statusCounts.running})`" name="running" />
      <el-tab-pane :label="`成功 (${statusCounts.success})`" name="success" />
      <el-tab-pane :label="`失败 (${statusCounts.failed})`" name="failed" />
      <el-tab-pane :label="`已取消 (${statusCounts.cancelled})`" name="cancelled" />
    </el-tabs>

    <el-table :data="filteredRuns" v-loading="loading" row-key="id">
      <el-table-column prop="id" label="Run ID" width="90" />
      <el-table-column label="脚本" min-width="220">
        <template #default="{ row }">
          <div class="script-cell">
            <el-button class="script-link" link @click="goScriptDetail(row.script_id)">
              {{ scriptNameMap[row.script_id] || `脚本 #${row.script_id}` }}
            </el-button>
            <span class="script-id">ID: {{ row.script_id }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)">{{ formatRunStatus(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="started_at" label="开始时间" min-width="180" :formatter="formatTime" />
      <el-table-column prop="ended_at" label="结束时间" min-width="180" :formatter="formatTime" />
      <el-table-column label="耗时(ms)" width="110">
        <template #default="{ row }">
          {{ row.duration_ms ?? '-' }}
        </template>
      </el-table-column>
      <el-table-column label="错误原因" min-width="280" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.error_message || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link @click="goRunDetail(row.id)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { runApi, type Run } from '../api/runs';
import { scriptApi, type Script } from '../api/scripts';
import { formatServerDateTime } from '../utils/datetime';

type RunStatusTab = 'all' | 'queued' | 'running' | 'success' | 'failed' | 'cancelled';

const router = useRouter();
const loading = ref(false);
const runs = ref<Run[]>([]);
const scripts = ref<Script[]>([]);
const activeTab = ref<RunStatusTab>('all');

const scriptNameMap = computed<Record<number, string>>(() => {
  const map: Record<number, string> = {};
  scripts.value.forEach((script) => {
    map[script.id] = script.name;
  });
  return map;
});

const statusCounts = computed(() => ({
  queued: runs.value.filter((run) => run.status === 'queued').length,
  running: runs.value.filter((run) => run.status === 'running').length,
  success: runs.value.filter((run) => run.status === 'success').length,
  failed: runs.value.filter((run) => run.status === 'failed').length,
  cancelled: runs.value.filter((run) => run.status === 'cancelled').length,
}));

const filteredRuns = computed(() => {
  if (activeTab.value === 'all') return runs.value;
  return runs.value.filter((run) => run.status === activeTab.value);
});

function statusTagType(status: Run['status']) {
  if (status === 'success') return 'success';
  if (status === 'failed' || status === 'cancelled') return 'danger';
  if (status === 'running') return 'warning';
  return 'info';
}

function formatRunStatus(status: Run['status']) {
  if (status === 'queued') return '排队中';
  if (status === 'running') return '执行中';
  if (status === 'success') return '成功';
  if (status === 'failed') return '失败';
  if (status === 'cancelled') return '已取消';
  return status;
}

function formatTime(_: unknown, __: unknown, value: string | null) {
  return formatServerDateTime(value);
}

function goRunDetail(runId: number) {
  router.push({ name: 'run-detail', params: { id: runId } });
}

function goScriptDetail(scriptId: number) {
  router.push({ name: 'script-editor', params: { id: scriptId } });
}

async function refresh() {
  loading.value = true;
  try {
    const [runList, scriptList] = await Promise.all([runApi.list(), scriptApi.list()]);
    runs.value = runList;
    scripts.value = scriptList;
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await refresh();
});
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tabs {
  margin-bottom: 10px;
}
.script-cell {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}
.script-name {
  font-weight: 500;
}
.script-link {
  font-size: 16px;
  font-weight: 500;
  justify-content: flex-start;
  padding: 0;
}
.script-id {
  color: #6b7280;
  font-size: 12px;
}
</style>
