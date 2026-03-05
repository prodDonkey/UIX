<template>
  <el-row :gutter="12">
    <el-col :span="16">
      <el-card class="main-card">
        <template #header>
          <div class="header">
            <strong>执行详情 #{{ runId }}</strong>
            <div class="actions">
              <el-tag :type="statusTagType">{{ run?.status ?? 'unknown' }}</el-tag>
              <el-button @click="refresh(false)">刷新</el-button>
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
            <span v-if="activeLogKeyword" class="log-anchor">已定位：{{ activeLogKeyword }}</span>
          </div>
        </template>
        <div class="progress-summary">
          <div class="progress-title">Playground 执行流</div>
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
          <div v-if="playgroundSteps.length > 0" class="playground-stream">
            <div
              v-for="(step, index) in playgroundSteps"
              :key="`${index}-${step.action}-${step.status}`"
              :class="[
                'stream-card',
                { 'latest-step': index === playgroundSteps.length - 1, 'error-step': step.isError },
              ]"
            >
              <div class="stream-card-header">
                <span class="stream-action">{{ step.action }}</span>
                <span class="stream-status">{{ stepStatusText(step.status) }}</span>
              </div>
              <div v-if="step.description" class="stream-description">{{ step.description }}</div>
              <pre v-if="step.paramsJson" class="stream-params">{{ step.paramsJson }}</pre>
              <div v-if="step.errorMessage" class="stream-error">{{ step.errorMessage }}</div>
              <el-button link size="small" type="primary" class="locate-log-btn" @click="locateStepLog(step)">
                定位日志
              </el-button>
            </div>
          </div>
          <div v-else class="no-steps">暂无执行步骤</div>
          <div class="recent-steps">
            <div class="recent-title">步骤列表（简版）</div>
            <ul class="recent-list">
              <li v-for="(step, index) in recentSteps" :key="`${index}-${step.label}-${step.status}`">
                <div class="step-main">
                  <span class="step-text">{{ step.label }}</span>
                  <span class="step-status">{{ stepStatusText(step.status) }}</span>
                </div>
              </li>
            </ul>
          </div>
        </div>
        <el-input ref="logsInputRef" v-model="logs" type="textarea" :rows="18" readonly />
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { ElMessage, type InputInstance } from 'element-plus';
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
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
const logsInputRef = ref<InputInstance>();
const activeLogKeyword = ref('');

let timer: number | null = null;
let stopped = false;

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
const runnerBaseUrl = (import.meta.env.VITE_RUNNER_BASE_URL || 'http://127.0.0.1:8787').replace(/\/+$/, '');
let progressStream: EventSource | null = null;

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

type RecentStepItem = {
  label: string;
  status: string;
  keyword: string;
  isError: boolean;
  isRunning: boolean;
};

type PlaygroundStepItem = {
  action: string;
  description: string;
  status: string;
  paramsJson: string;
  errorMessage: string;
  keyword: string;
  isError: boolean;
};

function resolveStepLabel(task: {
  type?: string;
  subType?: string;
  thought?: string;
  param?: { name?: string; prompt?: string };
}) {
  return task.subType || task.param?.name || task.param?.prompt || task.thought || task.type || '';
}

const recentSteps = computed(() => {
  const tasks = parsedProgressPayload.value?.executionDump?.tasks || [];
  return tasks
    .slice(-8)
    .map((task): RecentStepItem | null => {
      const label = resolveStepLabel(task);
      if (!label) return null;
      const status = task.status || 'unknown';
      return {
        label,
        status,
        keyword: label,
        isError: status === 'failed' || status === 'cancelled',
        isRunning: status === 'running',
      };
    })
    .filter((item): item is RecentStepItem => !!item);
});

function stringifyPayload(value: unknown): string {
  if (value === undefined || value === null) return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

const playgroundSteps = computed(() => {
  const tasks = parsedProgressPayload.value?.executionDump?.tasks || [];
  return tasks
    .slice(-12)
    .map((task): PlaygroundStepItem | null => {
      const action = task.type || 'Action';
      const description = resolveStepLabel(task);
      const status = task.status || 'unknown';
      const errorMessage = stringifyPayload((task as any).error || '');
      const paramsJson = stringifyPayload((task as any).param || '');
      const keyword = description || action;
      if (!keyword) return null;
      return {
        action,
        description,
        status,
        paramsJson,
        errorMessage,
        keyword,
        isError: status === 'failed' || status === 'cancelled',
      };
    })
    .filter((item): item is PlaygroundStepItem => !!item);
});

function stepStatusText(status: string) {
  if (status === 'running') return '执行中';
  if (status === 'finished' || status === 'success') return '已完成';
  if (status === 'failed') return '失败';
  if (status === 'cancelled') return '已取消';
  return status;
}

function locateStepLog(step: { keyword: string }) {
  if (!step.keyword) {
    ElMessage.warning('该步骤缺少可定位关键字');
    return;
  }
  const content = logs.value || '';
  const matchedIndex = content.lastIndexOf(step.keyword);
  if (matchedIndex < 0) {
    ElMessage.warning(`日志中未找到：${step.keyword}`);
    return;
  }

  activeLogKeyword.value = step.keyword;
  nextTick(() => {
    const textarea = logsInputRef.value?.textarea;
    if (!textarea) return;
    textarea.focus();
    textarea.setSelectionRange(matchedIndex, matchedIndex + step.keyword.length);
    const linesBefore = content.slice(0, matchedIndex).split('\n').length - 1;
    textarea.scrollTop = Math.max(linesBefore * 20 - 40, 0);
  });
  ElMessage.success(`已定位日志关键字：${step.keyword}`);
}

/**
 * 将 runner-service SSE 事件映射为当前页面使用的 progress 结构。
 * 这样可以复用现有解析逻辑，不破坏后端接口兼容。
 */
function applyRunnerProgressEvent(payload: Record<string, any>) {
  const progressPayload = {
    status: payload.status,
    currentTask: payload.currentTask ?? null,
    currentAction: payload.currentAction ?? null,
    completed: Number(payload.completed ?? 0),
    total: Number(payload.total ?? 0),
    executionDump: payload.executionDump ?? null,
    updatedAt: payload.updatedAt ?? null,
  };
  runProgress.value = {
    run_id: Number(payload.runId ?? runId.value),
    status: progressPayload.status,
    current_task: progressPayload.currentTask,
    current_action: progressPayload.currentAction,
    progress_json: JSON.stringify(progressPayload),
    updated_at: progressPayload.updatedAt,
  };
}

function closeProgressStream() {
  if (!progressStream) return;
  progressStream.close();
  progressStream = null;
}

function setupProgressStream() {
  closeProgressStream();
  const currentRunId = runId.value;
  if (!Number.isFinite(currentRunId) || currentRunId <= 0) return;
  const streamUrl = `${runnerBaseUrl}/runs/${currentRunId}/stream`;
  const stream = new EventSource(streamUrl);
  progressStream = stream;

  const eventHandler = (event: MessageEvent) => {
    try {
      const payload = JSON.parse(event.data);
      applyRunnerProgressEvent(payload);
      if (payload?.status === 'success' || payload?.status === 'failed' || payload?.status === 'cancelled') {
        // 终态后主动刷新一次详情，确保报告/耗时等字段一致。
        refresh(true).catch(() => undefined);
      }
    } catch (error) {
      console.warn('[RunDetail] 解析runner进度事件失败', error);
    }
  };

  stream.addEventListener('snapshot', eventHandler);
  stream.addEventListener('progress', eventHandler);
  stream.addEventListener('done', eventHandler);
  stream.onerror = () => {
    // 流式通道断开时不打断主流程，轮询会继续兜底。
    console.warn(`[RunDetail] runner stream disconnected runId=${currentRunId}`);
    closeProgressStream();
  };
}

/**
 * 刷新运行详情数据。
 * - silent=true: 轮询场景，失败仅记录日志不弹窗，避免提示刷屏。
 * - silent=false: 手动刷新场景，失败会提示用户。
 */
async function refresh(silent = false) {
  const [detailResult, progressResult, logsResult, reportResult] = await Promise.allSettled([
    runApi.detail(runId.value),
    runApi.progress(runId.value),
    runApi.logs(runId.value),
    runApi.report(runId.value),
  ]);

  if (detailResult.status === 'fulfilled') {
    const detail = detailResult.value;
    run.value = detail;
    // 历史记录不阻断主数据渲染，失败仅告警。
    try {
      if (detail.script_id) {
        history.value = await runApi.list(detail.script_id);
      }
    } catch (error) {
      console.warn('[RunDetail] 获取历史执行失败', error);
    }
  } else {
    if (!silent) {
      ElMessage.error('获取执行详情失败，请稍后重试');
    }
  }

  if (progressResult.status === 'fulfilled') {
    runProgress.value = progressResult.value;
  } else {
    console.warn('[RunDetail] 获取进度失败', progressResult.reason);
  }

  if (logsResult.status === 'fulfilled') {
    logs.value = logsResult.value.content;
  } else {
    console.warn('[RunDetail] 获取日志失败', logsResult.reason);
  }

  if (reportResult.status === 'fulfilled') {
    reportInfo.value = reportResult.value;
  } else {
    console.warn('[RunDetail] 获取报告失败', reportResult.reason);
  }
}

function getPollIntervalMs(status: Run['status'] | undefined): number {
  if (status === 'queued' || status === 'running') return 2000;
  return 8000;
}

async function pollingLoop() {
  while (!stopped) {
    await refresh(true);
    const interval = getPollIntervalMs(run.value?.status);
    await new Promise<void>((resolve) => {
      timer = window.setTimeout(() => {
        timer = null;
        resolve();
      }, interval);
    });
  }
}

async function cancelRun() {
  await runApi.cancel(runId.value);
  ElMessage.success('已发送取消请求');
  await refresh(false);
}

async function rerun() {
  if (!run.value) return;
  const created = await runApi.create(run.value.script_id);
  ElMessage.success(`已创建重试任务 #${created.id}`);
  await router.push({ name: 'run-detail', params: { id: created.id } });
  await refresh(false);
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
  stopped = false;
  setupProgressStream();
  await refresh(true);
  await pollingLoop();
});

onBeforeUnmount(() => {
  stopped = true;
  closeProgressStream();
  if (timer) window.clearTimeout(timer);
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
.playground-stream {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stream-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px 10px;
  background: #ffffff;
}
.stream-card.latest-step {
  border-color: #409eff;
}
.stream-card.error-step {
  border-color: #f56c6c;
  background: #fff6f6;
}
.stream-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.stream-action {
  font-weight: 600;
  color: #303133;
}
.stream-status {
  color: #909399;
  font-size: 12px;
}
.stream-description {
  margin-top: 6px;
  color: #303133;
  line-height: 1.5;
}
.stream-params {
  margin: 6px 0 0;
  padding: 8px;
  border-radius: 6px;
  border: 1px solid #edf2f7;
  background: #f8fafc;
  font-size: 12px;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-word;
}
.stream-error {
  margin-top: 6px;
  padding: 8px;
  border-radius: 6px;
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #b91c1c;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
}
.no-steps {
  margin-top: 8px;
  color: #909399;
  font-size: 13px;
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 2px 0;
}
.recent-list li.latest-step {
  color: #409eff;
  font-weight: 600;
}
.recent-list li.error-step {
  color: #f56c6c;
  font-weight: 600;
}
.recent-list li.running-step .step-status {
  color: #e6a23c;
}
.step-main {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.step-text {
  word-break: break-word;
}
.step-status {
  color: #909399;
  font-size: 12px;
  white-space: nowrap;
}
.locate-log-btn {
  flex-shrink: 0;
  padding: 0;
}
.device-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.log-anchor {
  color: #409eff;
  font-size: 12px;
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
