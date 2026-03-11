<template>
  <el-card class="main-card">
    <template #header>
      <div class="header">
        <strong>执行详情 #{{ runId }}</strong>
        <div class="actions">
          <el-tag :type="statusTagType">{{ formatRunStatus(run?.status) }}</el-tag>
          <el-button :disabled="isCancelling || isRerunning" @click="refresh(false)">刷新</el-button>
          <el-button type="primary" plain :loading="isRerunning" :disabled="!canRerun" @click="rerun">
            重新执行
          </el-button>
          <el-button type="danger" plain :loading="isCancelling" :disabled="!canCancel" @click="cancelRun">
            取消执行
          </el-button>
        </div>
      </div>
    </template>

    <el-descriptions :column="2" border v-if="run">
      <el-descriptions-item label="脚本">
        <el-button link type="primary" class="script-link" @click="goScript(run.script_id)">
          {{ scriptDisplayName }}
        </el-button>
      </el-descriptions-item>
      <el-descriptions-item label="requestId">{{ run.request_id || '-' }}</el-descriptions-item>
      <el-descriptions-item label="状态">{{ formatRunStatus(run.status) }}</el-descriptions-item>
      <el-descriptions-item label="开始时间">{{ formatDateTime(run.started_at) }}</el-descriptions-item>
      <el-descriptions-item label="结束时间">{{ formatDateTime(run.ended_at) }}</el-descriptions-item>
      <el-descriptions-item label="耗时(ms)">{{ run.duration_ms ?? '-' }}</el-descriptions-item>
      <el-descriptions-item label="报告路径">
        <el-link v-if="displayReportUrl" :href="displayReportUrl" target="_blank" type="primary">
          {{ displayReportUrl }}
        </el-link>
        <span v-else>{{ reportInfo?.report_path || run.report_path || '-' }}</span>
      </el-descriptions-item>
      <el-descriptions-item label="备注">{{ run.remark || '-' }}</el-descriptions-item>
    </el-descriptions>

    <el-alert
      v-if="run?.error_message"
      type="error"
      show-icon
      :title="`错误：${run.error_message}`"
      class="error"
    />

    <div class="playground-panel">
      <div
        ref="taskLogLayoutRef"
        class="playground-main task-log-main"
        :style="{ gridTemplateColumns: `${taskLogPanelWidth}px 10px minmax(0, 1fr)` }"
      >
        <div class="task-log-panel">
          <h4 class="title">临时执行日志</h4>
          <el-empty v-if="!taskLogs.length" description="暂无实时日志" />
          <div v-else class="task-log-list">
            <div v-for="item in taskLogs" :key="item.key" class="task-log-item">
              <div class="task-log-header">
                <span class="task-log-type">{{ item.title }}</span>
                <span class="task-log-status">{{ item.status }}</span>
              </div>
              <div class="task-log-content">{{ item.content }}</div>
            </div>
          </div>
        </div>
        <div
          class="task-log-resizer"
          @mousedown="startResize"
        />
        <div class="device-preview-panel">
          <h4 class="title device-title-row">
            <span>设备实时画面</span>
            <div class="device-actions">
              <el-button class="history-trigger" plain @click="historyDrawerVisible = true">
                同脚本历史执行
              </el-button>
              <el-button link type="primary" @click="openAndroidPlayground">打开 Android Playground</el-button>
            </div>
          </h4>
          <div class="device-frame-shell">
            <iframe :src="androidPlaygroundEmbedUrl" class="device-frame main-device-frame" />
          </div>
        </div>
      </div>
    </div>

    <h4 class="title">报告预览</h4>
    <div class="report-actions">
      <el-button :disabled="!reportPreviewUrl" @click="openPreview">新窗口预览</el-button>
      <el-button type="primary" :disabled="!reportDownloadUrl" @click="downloadReport">下载报告</el-button>
    </div>
    <iframe v-if="reportPreviewUrl" :src="reportPreviewUrl" class="report-frame" />
    <el-empty v-else description="暂无报告（任务完成后生成）" />
  </el-card>

  <el-drawer
    v-model="historyDrawerVisible"
    title="同脚本历史执行"
    size="420px"
    append-to-body
    :destroy-on-close="false"
    class="history-drawer"
  >
    <div class="history-drawer-body">
      <div class="history-drawer-summary">
        <span>脚本 ID：{{ run?.script_id ?? '-' }}</span>
        <span>共 {{ sortedHistory.length }} 条</span>
      </div>
      <el-table
        :data="sortedHistory"
        size="small"
        row-key="id"
        height="100%"
        :row-class-name="historyRowClassName"
      >
        <el-table-column prop="id" label="Run ID" width="88" />
        <el-table-column label="⭐" width="56" align="center">
          <template #default="{ row }">
            <el-button size="small" link :type="row.is_starred ? 'warning' : 'info'" @click="toggleStar(row)">
              {{ row.is_starred ? '★' : '☆' }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="88">
          <template #default="{ row }">
            {{ formatRunStatus(row.status) }}
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" min-width="156" :formatter="formatHistoryTime" />
        <el-table-column label="备注" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.remark || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="118" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link @click="goRun(row.id)">查看</el-button>
            <el-button size="small" link type="primary" @click="editRemark(row)">备注</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import axios from 'axios';
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { runApi, type Run, type RunReport } from '../api/runs';
import { scriptApi, type Script } from '../api/scripts';
import { formatServerDateTime } from '../utils/datetime';

const route = useRoute();
const router = useRouter();
const runId = computed(() => Number(route.params.id));

const run = ref<Run | null>(null);
const script = ref<Script | null>(null);
const history = ref<Run[]>([]);
const reportInfo = ref<RunReport | null>(null);
const isCancelling = ref(false);
const isRerunning = ref(false);
const historyDrawerVisible = ref(false);
const taskLogs = ref<Array<{ key: string; title: string; status: string; content: string }>>([]);
const taskLogLayoutRef = ref<HTMLElement | null>(null);
const taskLogPanelWidth = ref(360);

let timer: number | null = null;
let stopped = false;
let lastDetailFetchAt = 0;
let lastScriptIdLoaded: number | null = null;
let stopResizeListeners: (() => void) | null = null;

const statusTagType = computed(() => {
  if (!run.value) return 'info';
  if (run.value.status === 'success') return 'success';
  if (run.value.status === 'failed' || run.value.status === 'cancelled') return 'danger';
  if (run.value.status === 'running') return 'warning';
  return 'info';
});

function isActiveRunStatus(status?: Run['status'] | null) {
  return status === 'queued' || status === 'running';
}

function formatRunStatus(status?: Run['status'] | null) {
  if (!status) return '未知';
  if (status === 'queued') return '排队中';
  if (status === 'running') return '执行中';
  if (status === 'success') return '成功';
  if (status === 'failed') return '失败';
  if (status === 'cancelled') return '已取消';
  return status;
}

function formatTaskStatus(status?: string | null) {
  if (!status) return '未知';
  if (status === 'finished' || status === 'completed') return '已完成';
  if (status === 'running') return '执行中';
  if (status === 'pending') return '等待中';
  if (status === 'failed') return '失败';
  if (status === 'cancelled') return '已取消';
  return status;
}

const canCancel = computed(
  () =>
    !isCancelling.value &&
    !isRerunning.value &&
    run.value?.status === 'running' &&
    !!run.value?.request_id,
);
const canRerun = computed(() => !isCancelling.value && !isRerunning.value && !!run.value && !canCancel.value);
const androidPlaygroundBaseUrl = (
  import.meta.env.VITE_ANDROID_PLAYGROUND_URL || 'http://localhost:5800'
).replace(/\/+$/, '');

function normalizeLoopbackUrl(rawUrl: string): string {
  if (!rawUrl) return rawUrl;
  try {
    const target = new URL(rawUrl);
    const current = new URL(window.location.href);
    const loopbackHosts = new Set(['localhost', '127.0.0.1', '0.0.0.0']);
    if (loopbackHosts.has(target.hostname) && loopbackHosts.has(current.hostname)) {
      target.hostname = current.hostname;
    }
    return target.toString();
  } catch {
    return rawUrl;
  }
}

const androidPlaygroundEmbedUrl = computed(() => {
  const query = new URLSearchParams({ embed: '1', deviceOnly: '1' });
  return normalizeLoopbackUrl(`${androidPlaygroundBaseUrl}/?${query.toString()}`);
});
const reportPreviewUrl = computed(() => {
  const previewUrl = reportInfo.value?.preview_url?.trim();
  if (!previewUrl) return '';
  return normalizeLoopbackUrl(previewUrl);
});
const reportDownloadUrl = computed(() => {
  const downloadUrl = reportInfo.value?.download_url?.trim();
  if (!downloadUrl) return '';
  return normalizeLoopbackUrl(downloadUrl);
});
const displayReportUrl = computed(() => {
  const previewUrl = reportPreviewUrl.value;
  if (previewUrl) return previewUrl;
  const reportPath = reportInfo.value?.report_path?.trim() || run.value?.report_path?.trim();
  if (reportPath && /^https?:\/\//i.test(reportPath)) return reportPath;
  return '';
});

const sortedHistory = computed(() =>
  [...history.value].sort((a, b) => {
    const aStar = a.is_starred ? 1 : 0;
    const bStar = b.is_starred ? 1 : 0;
    if (aStar !== bStar) return bStar - aStar;
    return b.id - a.id;
  }),
);
const scriptDisplayName = computed(() => {
  if (!run.value) return '-';
  return script.value?.name ? `${script.value.name} (#${run.value.script_id})` : `脚本 #${run.value.script_id}`;
});

async function loadScriptDetail(scriptId: number | null | undefined) {
  if (!scriptId || scriptId <= 0) {
    script.value = null;
    lastScriptIdLoaded = null;
    return;
  }
  if (lastScriptIdLoaded === scriptId && script.value?.id === scriptId) {
    return;
  }
  try {
    script.value = await scriptApi.detail(scriptId);
    lastScriptIdLoaded = scriptId;
  } catch (error) {
    console.warn('[RunDetail] 获取脚本信息失败', error);
    script.value = null;
    lastScriptIdLoaded = null;
  }
}

function stringifyTaskParam(value: unknown): string {
  if (!value) return '';
  if (typeof value === 'string') return value.trim();
  if (typeof value !== 'object') return String(value);

  const record = value as Record<string, unknown>;
  const candidates = [
    record.description,
    record.prompt,
    record.userInstruction,
    record.assertion,
    record.name,
    record.value,
    record.thought,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim();
    }
  }

  if (record.locate) {
    const locateText = stringifyTaskParam(record.locate);
    if (locateText) return locateText;
  }

  try {
    return JSON.stringify(record);
  } catch {
    return '';
  }
}

function extractTaskLogContent(task: Record<string, any>): string {
  const output = task?.output;
  const actionTexts = Array.isArray(output?.actions)
    ? output.actions
        .map((item: any) => stringifyTaskParam(item?.param) || item?.thought || item?.type || '')
        .filter(Boolean)
    : [];

  return (
    output?.log?.trim() ||
    output?.thought?.trim() ||
    task?.thought?.trim() ||
    stringifyTaskParam(task?.param) ||
    actionTexts.join('\n') ||
    ''
  );
}

async function refreshTaskLogs(silent = true) {
  const requestId = run.value?.request_id?.trim();
  if (!requestId) {
    taskLogs.value = [];
    return;
  }

  try {
    const data = await runApi.taskProgress(runId.value);
    const tasks = Array.isArray(data?.executionDump?.tasks) ? data.executionDump.tasks : [];
    const nextLogs = tasks
      .map((task: any, index: number) => {
        const content = extractTaskLogContent(task);
        if (!content) {
          return null;
        }
        const type = [task?.type, task?.subType].filter(Boolean).join(' / ') || 'Task';
        return {
          key: `${task?.taskId || index}-${task?.status || 'unknown'}-${content}`,
          title: type,
          status: formatTaskStatus(task?.status),
          content,
        };
      })
      .filter(Boolean);
    taskLogs.value = nextLogs;
  } catch (error) {
    if (!silent) {
      ElMessage.error('获取实时日志失败，请稍后重试');
    }
    console.warn('[RunDetail] 获取 task-progress 日志失败', error);
  }
}

/**
 * 刷新运行详情数据。
 * - silent=true: 轮询场景，失败仅记录日志不弹窗，避免提示刷屏。
 * - silent=false: 手动刷新场景，失败会提示用户。
 */
async function refresh(silent = false) {
  const now = Date.now();
  const isRunning = isActiveRunStatus(run.value?.status);
  const shouldFetchDetail =
    !isRunning || !silent || now - lastDetailFetchAt >= 8000 || (isRunning && !run.value?.request_id);

  const [detailResult, reportResult] = await Promise.allSettled([
    shouldFetchDetail ? runApi.detail(runId.value) : Promise.resolve(run.value as Run),
    runApi.report(runId.value),
  ]);

  if (detailResult.status === 'fulfilled') {
    const detail = detailResult.value;
    run.value = detail;
    await loadScriptDetail(detail.script_id);
    if (shouldFetchDetail) {
      lastDetailFetchAt = now;
      // 历史记录不阻断主数据渲染，失败仅告警。
      try {
        if (detail.script_id) {
          history.value = await runApi.list(detail.script_id);
        }
      } catch (error) {
        console.warn('[RunDetail] 获取历史执行失败', error);
      }
    }
  } else {
    if (!silent) {
      ElMessage.error('获取执行详情失败，请稍后重试');
    }
  }

  if (reportResult.status === 'fulfilled') {
    reportInfo.value = reportResult.value;
  } else {
    console.warn('[RunDetail] 获取报告失败', reportResult.reason);
  }

  await refreshTaskLogs(true);
}

function getPollIntervalMs(status: Run['status'] | undefined): number | null {
  if (isActiveRunStatus(status)) return 2000;
  return null;
}

function resolveErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail.trim();
    }
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }
  return fallback;
}

async function pollingLoop() {
  while (!stopped) {
    if (run.value && !isActiveRunStatus(run.value.status)) break;

    await refresh(true);

    const interval = getPollIntervalMs(run.value?.status);
    if (!interval) break;

    await new Promise<void>((resolve) => {
      timer = window.setTimeout(() => {
        timer = null;
        resolve();
      }, interval);
    });
  }
}

async function cancelRun() {
  if (isCancelling.value) return;
  isCancelling.value = true;
  try {
    await runApi.cancel(runId.value);
    ElMessage.success('已发送取消请求');
    await refresh(false);
  } catch (error) {
    console.error('[RunDetail] 取消执行失败', error);
    ElMessage.error(resolveErrorMessage(error, '取消执行失败，请稍后重试'));
  } finally {
    isCancelling.value = false;
  }
}

async function rerun() {
  if (!run.value || isRerunning.value) return;
  isRerunning.value = true;
  try {
    const created = await runApi.create(run.value.script_id);
    ElMessage.success(`已创建重试任务 #${created.id}`);
    await router.push({ name: 'run-detail', params: { id: created.id } });
    await refresh(false);
  } catch (error) {
    console.error('[RunDetail] 重新执行失败', error);
    ElMessage.error('重新执行失败，请稍后重试');
  } finally {
    isRerunning.value = false;
  }
}

async function editRemark(targetRun: Run) {
  try {
    const { value } = await ElMessageBox.prompt('请输入备注内容（最多500字）', `备注 Run #${targetRun.id}`, {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputValue: targetRun.remark || '',
      inputPlaceholder: '例如：本次执行用于回归验证，登录页网络波动',
      inputValidator: (inputValue) => {
        if (inputValue.length > 500) {
          return '备注不能超过500字';
        }
        return true;
      },
    });
    const saved = await runApi.updateRemark(targetRun.id, value);
    const row = history.value.find((item) => item.id === targetRun.id);
    if (row) row.remark = saved.remark ?? null;
    if (run.value?.id === targetRun.id) run.value.remark = saved.remark ?? null;
    ElMessage.success('备注已保存');
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return;
    console.error('[RunDetail] 更新备注失败', error);
    ElMessage.error('保存备注失败，请稍后重试');
  }
}

async function toggleStar(targetRun: Run) {
  const nextStarValue = !targetRun.is_starred;
  try {
    const saved = await runApi.updateStar(targetRun.id, nextStarValue);
    const row = history.value.find((item) => item.id === targetRun.id);
    if (row) row.is_starred = !!saved.is_starred;
    if (run.value?.id === targetRun.id) run.value.is_starred = !!saved.is_starred;
    ElMessage.success(saved.is_starred ? '已星标并置顶' : '已取消星标');
  } catch (error) {
    console.error('[RunDetail] 更新星标失败', error);
    ElMessage.error('更新星标失败，请稍后重试');
  }
}

function goRun(id: number) {
  historyDrawerVisible.value = false;
  router.push({ name: 'run-detail', params: { id } });
}

function goScript(scriptId: number) {
  router.push({ name: 'script-editor', params: { id: scriptId } });
}

function historyRowClassName({ row }: { row: Run }) {
  return row.id === run.value?.id ? 'history-row-current' : '';
}

function formatDateTime(value: string | null) {
  return formatServerDateTime(value);
}

function formatHistoryTime(_: unknown, __: unknown, value: string | null) {
  return formatServerDateTime(value);
}

function openPreview() {
  if (!reportPreviewUrl.value) return;
  window.open(reportPreviewUrl.value, '_blank');
}

function downloadReport() {
  if (!reportDownloadUrl.value) return;
  window.open(reportDownloadUrl.value, '_blank');
}

function openAndroidPlayground() {
  window.open(androidPlaygroundEmbedUrl.value, '_blank');
}

function stopResize() {
  stopResizeListeners?.();
  stopResizeListeners = null;
  document.body.classList.remove('task-log-resizing');
}

function startResize(event: MouseEvent) {
  const layout = taskLogLayoutRef.value;
  if (!layout) return;

  const rect = layout.getBoundingClientRect();
  const minWidth = 280;
  const maxWidth = Math.max(minWidth, rect.width - 360);

  const handleMouseMove = (moveEvent: MouseEvent) => {
    const nextWidth = moveEvent.clientX - rect.left;
    taskLogPanelWidth.value = Math.min(maxWidth, Math.max(minWidth, nextWidth));
  };

  const handleMouseUp = () => {
    stopResize();
  };

  stopResize();
  document.body.classList.add('task-log-resizing');
  window.addEventListener('mousemove', handleMouseMove);
  window.addEventListener('mouseup', handleMouseUp, { once: true });
  stopResizeListeners = () => {
    window.removeEventListener('mousemove', handleMouseMove);
    window.removeEventListener('mouseup', handleMouseUp);
  };
  event.preventDefault();
}

onMounted(async () => {
  stopped = false;
  await refresh(true);
  await pollingLoop();
});

watch(
  () => runId.value,
  async () => {
    lastDetailFetchAt = 0;
    historyDrawerVisible.value = false;
    reportInfo.value = null;
    script.value = null;
    lastScriptIdLoaded = null;
    await refresh(false);
  },
);

onBeforeUnmount(() => {
  stopped = true;
  stopResize();
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
.main-card {
  min-height: 600px;
}
.title {
  margin: 14px 0 8px;
}
.device-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.device-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.history-trigger {
  --el-button-hover-text-color: var(--el-color-primary);
  --el-button-hover-border-color: var(--el-color-primary-light-5);
  --el-button-hover-bg-color: var(--el-color-primary-light-9);
}
.error {
  margin-top: 10px;
}
.script-link {
  padding: 0;
  height: auto;
  font-weight: 500;
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
.playground-panel {
  display: block;
}
.task-log-main {
  display: grid;
  grid-template-columns: 360px 10px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.task-log-resizer {
  width: 10px;
  align-self: stretch;
  cursor: col-resize;
  position: relative;
}
.task-log-resizer::before {
  content: '';
  position: absolute;
  left: 50%;
  top: 0;
  transform: translateX(-50%);
  width: 2px;
  height: 100%;
  border-radius: 999px;
  background: #d1d5db;
}
.task-log-resizer:hover::before {
  background: #60a5fa;
}
.device-preview-panel {
  min-width: 0;
}
.device-frame {
  width: 100%;
  height: 100%;
  border: 0;
  background: #fff;
}
.device-frame-shell {
  width: 100%;
  height: clamp(640px, 70vh, 980px);
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.6);
}
.main-device-frame {
  min-height: 0;
}
.task-log-panel {
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.task-log-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: clamp(640px, 70vh, 980px);
  overflow: auto;
  padding-right: 6px;
}
.task-log-item {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px 14px;
  background: #fff;
}
.task-log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 6px;
}
.task-log-type {
  font-weight: 600;
  color: #111827;
}
.task-log-status {
  font-size: 12px;
  color: #6b7280;
}
.task-log-content {
  white-space: pre-wrap;
  color: #374151;
  line-height: 1.6;
}
.history-drawer :deep(.el-drawer__body) {
  padding-top: 0;
}
.history-drawer-body {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.history-drawer-summary {
  display: flex;
  justify-content: space-between;
  color: #6b7280;
  font-size: 12px;
}
.history-drawer-body :deep(.el-table .history-row-current) {
  --el-table-tr-bg-color: #eff6ff;
}
@media (max-width: 768px) {
  .header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .actions {
    flex-wrap: wrap;
  }
  .device-title-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .task-log-main {
    grid-template-columns: 1fr;
  }
  .task-log-resizer {
    display: none;
  }
  .task-log-list {
    max-height: none;
  }
  .device-actions {
    width: 100%;
    justify-content: space-between;
  }
  .device-frame-shell {
    height: 540px;
  }
}
</style>
