<template>
  <el-row :gutter="12">
    <el-col :span="16">
      <el-card class="main-card">
        <template #header>
          <div class="header">
            <strong>执行详情 #{{ runId }}</strong>
            <div class="actions">
              <el-tag :type="statusTagType">{{ run?.status ?? 'unknown' }}</el-tag>
              <el-button @click="refresh">刷新</el-button>
              <el-button type="danger" plain :disabled="!canCancel" @click="cancelRun">取消执行</el-button>
            </div>
          </div>
        </template>

        <el-descriptions :column="2" border v-if="run">
          <el-descriptions-item label="脚本ID">{{ run.script_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ run.status }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ run.started_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ run.ended_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="耗时(ms)">{{ run.duration_ms ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="报告路径">{{ reportInfo?.report_path || run.report_path || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="run?.error_message"
          type="error"
          show-icon
          :title="`错误：${run.error_message}`"
          class="error"
        />

        <h4 class="title">实时日志</h4>
        <el-input v-model="logs" type="textarea" :rows="18" readonly />

        <h4 class="title">报告预览</h4>
        <div class="report-actions">
          <el-button :disabled="!reportInfo?.preview_url" @click="openPreview">新窗口预览</el-button>
          <el-button type="primary" :disabled="!reportInfo?.download_url" @click="downloadReport">下载报告</el-button>
        </div>
        <iframe v-if="reportInfo?.preview_url" :src="reportInfo.preview_url" class="report-frame" />
        <el-empty v-else description="暂无报告（任务完成后生成）" />
      </el-card>
    </el-col>

    <el-col :span="8">
      <el-card class="side-card">
        <template #header>
          <strong>同脚本历史执行</strong>
        </template>
        <el-table :data="history" size="small" height="420" row-key="id">
          <el-table-column prop="id" label="Run ID" width="85" />
          <el-table-column prop="status" label="状态" width="90" />
          <el-table-column prop="started_at" label="开始时间" min-width="150" />
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-button size="small" link @click="goRun(row.id)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { runApi, type Run, type RunReport } from '../api/runs';

const route = useRoute();
const router = useRouter();
const runId = computed(() => Number(route.params.id));

const run = ref<Run | null>(null);
const history = ref<Run[]>([]);
const logs = ref('');
const reportInfo = ref<RunReport | null>(null);

let timer: number | null = null;

const statusTagType = computed(() => {
  if (!run.value) return 'info';
  if (run.value.status === 'success') return 'success';
  if (run.value.status === 'failed' || run.value.status === 'cancelled') return 'danger';
  if (run.value.status === 'running') return 'warning';
  return 'info';
});

const canCancel = computed(() => run.value?.status === 'running' || run.value?.status === 'queued');

async function refresh() {
  const detail = await runApi.detail(runId.value);
  run.value = detail;
  const logData = await runApi.logs(runId.value);
  logs.value = logData.content;
  reportInfo.value = await runApi.report(runId.value);
  if (detail.script_id) {
    history.value = await runApi.list(detail.script_id);
  }
}

async function cancelRun() {
  await runApi.cancel(runId.value);
  ElMessage.success('已发送取消请求');
  await refresh();
}

function goRun(id: number) {
  router.push({ name: 'run-detail', params: { id } });
}

function openPreview() {
  if (!reportInfo.value?.preview_url) return;
  window.open(reportInfo.value.preview_url, '_blank');
}

function downloadReport() {
  if (!reportInfo.value?.download_url) return;
  window.open(reportInfo.value.download_url, '_blank');
}

onMounted(async () => {
  await refresh();
  timer = window.setInterval(async () => {
    await refresh();
  }, 2000);
});

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
});
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.actions {
  display: flex;
  gap: 8px;
}
.main-card,
.side-card {
  min-height: 600px;
}
.title {
  margin: 14px 0 8px;
}
.error {
  margin-top: 10px;
}
.report-actions {
  margin-bottom: 8px;
  display: flex;
  gap: 8px;
}
.report-frame {
  width: 100%;
  min-height: 500px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}
</style>
