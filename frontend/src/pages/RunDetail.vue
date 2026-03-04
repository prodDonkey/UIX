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
              <el-button type="primary" plain :disabled="!canRerun" @click="rerun">重新执行</el-button>
              <el-button type="danger" plain :disabled="!canCancel" @click="cancelRun">取消执行</el-button>
            </div>
          </div>
        </template>

        <el-descriptions :column="2" border v-if="run">
          <el-descriptions-item label="脚本ID">{{ run.script_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ run.status }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatDateTime(run.started_at) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ formatDateTime(run.ended_at) }}</el-descriptions-item>
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

        <h4 class="title device-title-row">
          <span>设备实时画面</span>
          <el-button link type="primary" @click="openAndroidPlayground">打开 Android Playground</el-button>
        </h4>
        <iframe :src="androidPlaygroundEmbedUrl" class="device-frame main-device-frame" />

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
          <el-table-column prop="started_at" label="开始时间" min-width="150" :formatter="formatHistoryTime" />
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-button size="small" link @click="goRun(row.id)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="side-card device-card">
        <template #header>
          <div class="device-header logs-header">
            <strong>实时日志</strong>
          </div>
        </template>
        <div class="progress-summary">
          <div class="progress-title">当前步骤</div>
          <div class="progress-line">
            <span class="progress-label">任务</span>
            <span class="progress-value">{{ runProgress?.current_task || '-' }}</span>
          </div>
          <div class="progress-line">
            <span class="progress-label">动作</span>
            <span class="progress-value">{{ runProgress?.current_action || '-' }}</span>
          </div>
          <div class="progress-line">
            <span class="progress-label">进度</span>
            <span class="progress-value">{{ progressCounterText }}</span>
          </div>
          <div v-if="recentSteps.length > 0" class="recent-steps">
            <div class="recent-title">最近步骤</div>
            <ul class="recent-list">
              <li v-for="step in recentSteps" :key="step">{{ step }}</li>
            </ul>
          </div>
        </div>
        <el-input v-model="logs" type="textarea" :rows="18" readonly />
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { runApi, type Run, type RunProgress, type RunReport } from '../api/runs';
import { formatServerDateTime } from '../utils/datetime';

const route = useRoute();
const router = useRouter();
const runId = computed(() => Number(route.params.id));

const run = ref<Run | null>(null);
const history = ref<Run[]>([]);
const logs = ref('');
const reportInfo = ref<RunReport | null>(null);
const runProgress = ref<RunProgress | null>(null);

let timer: number | null = null;

const statusTagType = computed(() => {
  if (!run.value) return 'info';
  if (run.value.status === 'success') return 'success';
  if (run.value.status === 'failed' || run.value.status === 'cancelled') return 'danger';
  if (run.value.status === 'running') return 'warning';
  return 'info';
});

const canCancel = computed(() => run.value?.status === 'running' || run.value?.status === 'queued');
const canRerun = computed(() => !!run.value && !canCancel.value);
const androidPlaygroundEmbedUrl = (
  import.meta.env.VITE_ANDROID_PLAYGROUND_URL || 'http://127.0.0.1:5800'
).replace(/\/+$/, '');

const parsedProgressPayload = computed(() => {
  const raw = runProgress.value?.progress_json;
  if (!raw) return null;
  try {
    return JSON.parse(raw) as {
      completed?: number;
      total?: number;
      executionDump?: {
        tasks?: Array<{
          status?: string;
          type?: string;
          subType?: string;
          thought?: string;
          param?: { name?: string; prompt?: string };
        }>;
      };
    };
  } catch {
    return null;
  }
});

const progressCounterText = computed(() => {
  const payload = parsedProgressPayload.value;
  if (!payload) return '-';
  const completed = Number(payload.completed ?? 0);
  const total = Number(payload.total ?? 0);
  if (!total) return '-';
  return `${completed}/${total}`;
});

const recentSteps = computed(() => {
  const tasks = parsedProgressPayload.value?.executionDump?.tasks || [];
  return tasks
    .slice(-5)
    .map((task) => task.subType || task.param?.name || task.param?.prompt || task.thought || task.type || '')
    .filter((text) => !!text);
});

async function refresh() {
  const [detail, progress, logData, report] = await Promise.all([
    runApi.detail(runId.value),
    runApi.progress(runId.value),
    runApi.logs(runId.value),
    runApi.report(runId.value),
  ]);
  run.value = detail;
  runProgress.value = progress;
  logs.value = logData.content;
  reportInfo.value = report;
  if (detail.script_id) {
    history.value = await runApi.list(detail.script_id);
  }
}

async function cancelRun() {
  await runApi.cancel(runId.value);
  ElMessage.success('已发送取消请求');
  await refresh();
}

async function rerun() {
  if (!run.value) return;
  const created = await runApi.create(run.value.script_id);
  ElMessage.success(`已创建重试任务 #${created.id}`);
  await router.push({ name: 'run-detail', params: { id: created.id } });
  await refresh();
}

function goRun(id: number) {
  router.push({ name: 'run-detail', params: { id } });
}

function formatDateTime(value: string | null) {
  return formatServerDateTime(value);
}

function formatHistoryTime(_: unknown, __: unknown, value: string | null) {
  return formatServerDateTime(value);
}

function openPreview() {
  if (!reportInfo.value?.preview_url) return;
  window.open(reportInfo.value.preview_url, '_blank');
}

function downloadReport() {
  if (!reportInfo.value?.download_url) return;
  window.open(reportInfo.value.download_url, '_blank');
}

function openAndroidPlayground() {
  window.open(androidPlaygroundEmbedUrl, '_blank');
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
.device-card {
  margin-top: 12px;
}
.progress-summary {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fafafa;
}
.progress-title {
  font-weight: 600;
  margin-bottom: 6px;
}
.progress-line {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin: 4px 0;
}
.progress-label {
  min-width: 36px;
  color: #909399;
}
.progress-value {
  color: #303133;
  word-break: break-word;
}
.recent-steps {
  margin-top: 8px;
}
.recent-title {
  font-weight: 500;
  margin-bottom: 4px;
}
.recent-list {
  margin: 0;
  padding-left: 16px;
}
.recent-list li {
  line-height: 1.6;
}
.device-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.title {
  margin: 14px 0 8px;
}
.device-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
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
.device-frame {
  width: 100%;
  height: 480px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}
.main-device-frame {
  height: 620px;
}
</style>
