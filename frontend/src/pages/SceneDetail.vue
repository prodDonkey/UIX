<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="header">
          <div>
            <strong>场景编辑</strong>
            <span v-if="sceneId"> #{{ sceneId }}</span>
          </div>
          <div class="actions">
            <el-button @click="goBack">返回列表</el-button>
            <el-button @click="copyCurrentScene">复制场景</el-button>
            <el-button @click="showPicker = true">添加脚本</el-button>
            <el-button type="primary" @click="save">保存</el-button>
          </div>
        </div>
      </template>

      <el-form label-width="90px" class="meta-form">
        <el-form-item label="场景名称">
          <el-input v-model="name" />
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="sourceType" style="width: 220px">
            <el-option label="手动" value="manual" />
            <el-option label="AI生成" value="ai" />
          </el-select>
        </el-form-item>
        <el-form-item label="场景说明">
          <el-input v-model="description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <template #header>
        <div class="sub-header">
          <span>关联脚本</span>
          <span class="sub-header-desc">按顺序维护场景中的脚本</span>
        </div>
      </template>

      <el-table :data="relations" v-loading="loading" row-key="id" empty-text="暂无关联脚本">
        <el-table-column label="顺序" width="90">
          <template #default="{ row }">
            {{ row.sort_order }}
          </template>
        </el-table-column>
        <el-table-column label="脚本名称" min-width="220">
          <template #default="{ row }">
            <el-button link type="primary" @click="goScript(row.script_id)">
              {{ row.script.name }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="120">
          <template #default="{ row }">
            {{ formatSourceType(row.script.source_type) }}
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="180">
          <template #default="{ row }">
            {{ formatServerDateTime(row.script.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="220">
          <template #default="{ row }">
            <el-input
              :model-value="row.remark"
              placeholder="可填写该脚本在场景中的用途"
              @change="(value) => updateRemark(row.id, String(value ?? ''))"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row, $index }">
            <el-button size="small" :disabled="$index === 0" @click="moveRelation($index, -1)">上移</el-button>
            <el-button size="small" :disabled="$index === relations.length - 1" @click="moveRelation($index, 1)">下移</el-button>
            <el-button size="small" type="danger" @click="removeRelation(row.id)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card>
      <template #header>
        <div class="sub-header">
          <span>执行编排</span>
          <div class="sub-actions">
            <span class="sub-header-desc">从已关联脚本中选择 task，按顺序组合场景执行脚本</span>
            <el-button
              plain
              :disabled="syncableTaskCount === 0 || syncingAllTasks"
              @click="syncAllTaskItems"
            >
              {{ syncingAllTasks ? '同步中...' : `同步全部变更${syncableTaskCount > 0 ? ` (${syncableTaskCount})` : ''}` }}
            </el-button>
            <el-button
              type="success"
              :loading="executingScene"
              :disabled="taskItems.length === 0"
              @click="executeScene"
            >
              {{ executingScene ? '执行中...' : '执行场景' }}
            </el-button>
            <el-button type="primary" plain :disabled="taskItems.length === 0" @click="previewCompiledScript">
              预览场景脚本
            </el-button>
          </div>
        </div>
      </template>

      <div class="task-layout">
        <div class="task-source-panel">
          <div class="task-panel-title">可选任务</div>
          <el-empty v-if="relations.length === 0" description="请先关联脚本" />
          <div v-else class="task-source-list">
            <div v-for="relation in relations" :key="relation.id" class="task-source-group">
              <div class="task-source-group-title">
                <button
                  class="task-source-group-title-button"
                  type="button"
                  :disabled="batchAddingScriptId !== null"
                  :title="batchAddingScriptId === relation.script_id ? '正在添加该脚本任务' : '点击将该脚本下所有任务加入当前编排'"
                  @click="addScriptTaskItems(relation.script_id)"
                >
                  {{ relation.script.name }}
                  <span class="task-source-group-title-action">
                    {{ batchAddingScriptId === relation.script_id ? '添加中...' : '整组添加' }}
                  </span>
                </button>
              </div>
              <el-empty
                v-if="(scriptTasksMap[relation.script_id] || []).length === 0"
                description="该脚本暂无可编排任务"
                :image-size="56"
              />
              <div v-else class="task-chip-list">
                <el-button
                  v-for="task in scriptTasksMap[relation.script_id] || []"
                  :key="`${relation.script_id}-${task.task_index}`"
                  size="small"
                  plain
                  @click="addTaskItem(relation.script_id, task.task_index)"
                >
                  {{ task.task_name }}
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <div class="task-target-panel">
          <div class="task-panel-title">当前编排</div>
          <el-empty v-if="taskItems.length === 0" description="暂无编排任务" />
          <div v-else class="task-board">
            <div class="task-board-header">
              <div class="task-col-handle">拖拽</div>
              <div class="task-col-order">顺序</div>
              <div class="task-col-name">任务名称</div>
              <div class="task-col-script">来源脚本</div>
              <div class="task-col-status">状态</div>
              <div class="task-col-remark">备注</div>
              <div class="task-col-action">操作</div>
            </div>
            <div
              v-for="(row, index) in taskItems"
              :key="row.id"
              class="task-board-row"
              :class="{
                'task-board-row-dragging': draggingTaskItemId === row.id,
                'task-board-row-drop-target': dropTaskItemId === row.id && draggingTaskItemId !== row.id,
              }"
              draggable="true"
              @dragstart="onTaskDragStart(index, row.id, $event)"
              @dragover.prevent="onTaskDragOver(row.id)"
              @drop.prevent="onTaskDrop(index)"
              @dragend="onTaskDragEnd"
            >
              <div class="task-col-handle">
                <button class="drag-handle" type="button" title="拖拽排序">⋮⋮</button>
              </div>
              <div class="task-col-order">{{ row.sort_order }}</div>
              <div class="task-col-name">{{ row.task_name_snapshot }}</div>
              <div class="task-col-script">{{ row.script.name }}</div>
              <div class="task-col-status">
                <el-tag :type="syncStatusTagType(row.sync_status)" effect="light">
                  {{ syncStatusLabel(row.sync_status) }}
                </el-tag>
                <div v-if="row.sync_message" class="task-sync-message">
                  {{ row.sync_message }}
                </div>
              </div>
              <div class="task-col-remark">
                <el-input
                  :model-value="row.remark"
                  placeholder="可填写该任务在场景中的用途"
                  @change="(value) => updateTaskRemark(row.id, String(value ?? ''))"
                />
                <div class="task-variable-summary">
                  出参 {{ row.output_variables.length }} / 入参 {{ row.input_bindings.length }}
                </div>
              </div>
              <div class="task-col-action">
                <el-button
                  v-if="row.sync_status === 'stale'"
                  size="small"
                  plain
                  :loading="syncingTaskItemId === row.id"
                  @click="syncTaskItem(row.id)"
                >
                  同步
                </el-button>
                <el-button size="small" plain @click="openVariableDialog(row)">变量</el-button>
                <el-button size="small" type="danger" @click="removeTaskItem(row.id)">移除</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <SceneScriptPicker
      :visible="showPicker"
      :scripts="scripts"
      :excluded-script-ids="relations.map((item) => item.script_id)"
      @close="showPicker = false"
      @select="addScript"
    />

    <el-dialog
      v-model="compiledPreviewVisible"
      width="min(960px, 92vw)"
      destroy-on-close
    >
      <template #header>
        <div class="dialog-header">
          <strong>场景脚本预览</strong>
          <span class="dialog-desc">当前场景编排后生成的 YAML</span>
        </div>
      </template>
      <pre class="compiled-preview"><code>{{ compiledYaml }}</code></pre>
    </el-dialog>

    <el-dialog
      v-model="executeResultVisible"
      width="min(760px, 92vw)"
      destroy-on-close
    >
      <template #header>
        <div class="dialog-header">
          <strong>场景执行结果</strong>
          <span class="dialog-desc">{{ executeResult?.scene_name || '-' }}</span>
        </div>
      </template>
      <div v-if="executeResult" class="execute-result">
        <div class="execute-result-line"><strong>消息：</strong>{{ executeResult.message }}</div>
        <div class="execute-result-line"><strong>结果：</strong>{{ executeResult.success ? '成功' : '失败' }}</div>
        <div class="execute-result-line"><strong>任务数：</strong>{{ executeResult.task_count }}</div>
        <div class="execute-result-line" v-if="Object.keys(executeResult.outputs || {}).length > 0">
          <strong>输出变量：</strong>{{ JSON.stringify(executeResult.outputs) }}
        </div>
        <pre v-if="executeResult.detail" class="compiled-preview"><code>{{ formatExecuteDetail(executeResult.detail) }}</code></pre>
      </div>
    </el-dialog>

    <el-dialog
      v-model="variableDialogVisible"
      width="min(720px, 92vw)"
      destroy-on-close
    >
      <template #header>
        <div class="dialog-header">
          <strong>任务变量配置</strong>
          <span class="dialog-desc">{{ variableDialogTask?.task_name_snapshot || '-' }}</span>
        </div>
      </template>

      <el-form label-position="top">
        <el-form-item label="输出变量定义">
          <el-input
            v-model="variableOutputsText"
            type="textarea"
            :rows="8"
            placeholder='示例：[{"name":"recycleOrderId","source_path":"respMsg.data.fields.recycleOrderId","description":"下单返回单号"}]'
          />
        </el-form-item>
        <el-form-item label="输入变量映射">
          <el-input
            v-model="variableInputsText"
            type="textarea"
            :rows="8"
            placeholder='示例：[{"target_path":"interface.params.orderNo","expression":"${recycleOrderId}","description":"引用上一步生成单号"}]'
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="variableDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingVariableConfig" @click="saveVariableConfig">保存变量配置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import {
  sceneApi,
  type SceneExecuteResult,
  type SceneScriptRelation,
  type SceneTaskInputBinding,
  type SceneTaskItem,
  type SceneTaskOutputVariable,
  type ScriptTask,
} from '../api/scenes';
import { scriptApi, type Script } from '../api/scripts';
import SceneScriptPicker from '../components/SceneScriptPicker.vue';
import { formatServerDateTime } from '../utils/datetime';

const route = useRoute();
const router = useRouter();
const sceneId = computed(() => Number(route.params.id));

const loading = ref(false);
const showPicker = ref(false);
const name = ref('');
const description = ref('');
const sourceType = ref('manual');
const relations = ref<SceneScriptRelation[]>([]);
const taskItems = ref<SceneTaskItem[]>([]);
const scriptTasksMap = ref<Record<number, ScriptTask[]>>({});
const scripts = ref<Script[]>([]);
const compiledPreviewVisible = ref(false);
const compiledYaml = ref('');
const executeResultVisible = ref(false);
const executeResult = ref<SceneExecuteResult | null>(null);
const executingScene = ref(false);
const variableDialogVisible = ref(false);
const variableDialogTask = ref<SceneTaskItem | null>(null);
const variableOutputsText = ref('[]');
const variableInputsText = ref('[]');
const savingVariableConfig = ref(false);
const draggingTaskIndex = ref<number | null>(null);
const draggingTaskItemId = ref<number | null>(null);
const dropTaskItemId = ref<number | null>(null);
const taskReordering = ref(false);
const batchAddingScriptId = ref<number | null>(null);
const syncingTaskItemId = ref<number | null>(null);
const syncingAllTasks = ref(false);
const syncableTaskCount = computed(() => taskItems.value.filter((item) => item.sync_status === 'stale').length);

onMounted(async () => {
  if (Number.isNaN(sceneId.value) || sceneId.value <= 0) {
    await router.replace({ name: 'scenes-list' });
    return;
  }
  await Promise.all([loadScene(), loadScripts()]);
});

async function loadScene() {
  loading.value = true;
  try {
    const detail = await sceneApi.detail(sceneId.value);
    name.value = detail.name;
    description.value = detail.description;
    sourceType.value = detail.source_type;
    relations.value = [...detail.scripts].sort((a, b) => a.sort_order - b.sort_order);
    taskItems.value = [...detail.task_items].sort((a, b) => a.sort_order - b.sort_order);
    await loadAvailableTasks();
  } finally {
    loading.value = false;
  }
}

async function loadScripts() {
  scripts.value = await scriptApi.list();
}

async function loadAvailableTasks() {
  const entries = await Promise.all(
    relations.value.map(async (relation) => {
      try {
        const tasks = await sceneApi.listScriptTasks(relation.script_id);
        return [relation.script_id, tasks] as const;
      } catch (error) {
        console.warn('[SceneDetail] 获取脚本任务失败', relation.script_id, error);
        return [relation.script_id, []] as const;
      }
    }),
  );
  scriptTasksMap.value = Object.fromEntries(entries);
}

async function save() {
  await sceneApi.update(sceneId.value, {
    name: name.value,
    description: description.value,
    source_type: sourceType.value,
  });
  ElMessage.success('保存成功');
  await loadScene();
}

async function addScript(script: Script) {
  await sceneApi.addScript(sceneId.value, {
    script_id: script.id,
    sort_order: relations.value.length + 1,
    remark: '',
  });
  showPicker.value = false;
  ElMessage.success('脚本已添加');
  await Promise.all([loadScene(), loadScripts()]);
}

async function addTaskItem(scriptId: number, taskIndex: number) {
  await sceneApi.addTaskItem(sceneId.value, {
    script_id: scriptId,
    task_index: taskIndex,
    remark: '',
  });
  ElMessage.success('任务已加入编排');
  await loadScene();
}

async function addScriptTaskItems(scriptId: number) {
  const tasks = scriptTasksMap.value[scriptId] || [];
  if (tasks.length === 0) {
    ElMessage.warning('该脚本暂无可编排任务');
    return;
  }

  if (batchAddingScriptId.value !== null) {
    return;
  }

  batchAddingScriptId.value = scriptId;
  try {
    for (const task of tasks) {
      await sceneApi.addTaskItem(sceneId.value, {
        script_id: scriptId,
        task_index: task.task_index,
        remark: '',
      });
    }
    ElMessage.success(`已添加脚本中的 ${tasks.length} 个任务`);
    await loadScene();
  } finally {
    batchAddingScriptId.value = null;
  }
}

async function updateRemark(relationId: number, remark: string) {
  const current = relations.value.find((item) => item.id === relationId);
  if (!current || current.remark === remark) return;
  await sceneApi.updateScript(sceneId.value, relationId, { remark, sort_order: current.sort_order });
  const target = relations.value.find((item) => item.id === relationId);
  if (target) target.remark = remark;
  ElMessage.success('备注已更新');
}

async function moveRelation(index: number, delta: number) {
  const nextIndex = index + delta;
  if (nextIndex < 0 || nextIndex >= relations.value.length) return;

  const current = relations.value[index];
  const target = relations.value[nextIndex];
  await Promise.all([
    sceneApi.updateScript(sceneId.value, current.id, { sort_order: target.sort_order, remark: current.remark }),
    sceneApi.updateScript(sceneId.value, target.id, { sort_order: current.sort_order, remark: target.remark }),
  ]);
  ElMessage.success('顺序已更新');
  await loadScene();
}

async function updateTaskRemark(itemId: number, remark: string) {
  const current = taskItems.value.find((item) => item.id === itemId);
  if (!current || current.remark === remark) return;
  await sceneApi.updateTaskItem(sceneId.value, itemId, { remark, sort_order: current.sort_order });
  const target = taskItems.value.find((item) => item.id === itemId);
  if (target) target.remark = remark;
  ElMessage.success('任务备注已更新');
}

function openVariableDialog(row: SceneTaskItem) {
  variableDialogTask.value = row;
  variableOutputsText.value = JSON.stringify(row.output_variables || [], null, 2);
  variableInputsText.value = JSON.stringify(row.input_bindings || [], null, 2);
  variableDialogVisible.value = true;
}

async function saveVariableConfig() {
  if (!variableDialogTask.value) return;

  let outputVariables: SceneTaskOutputVariable[] = [];
  let inputBindings: SceneTaskInputBinding[] = [];
  try {
    outputVariables = JSON.parse(variableOutputsText.value || '[]');
    inputBindings = JSON.parse(variableInputsText.value || '[]');
  } catch (error) {
    ElMessage.error('变量配置 JSON 格式不正确');
    return;
  }

  savingVariableConfig.value = true;
  try {
    const updated = await sceneApi.updateTaskItem(sceneId.value, variableDialogTask.value.id, {
      output_variables: outputVariables,
      input_bindings: inputBindings,
      sort_order: variableDialogTask.value.sort_order,
      remark: variableDialogTask.value.remark,
    });
    const target = taskItems.value.find((item) => item.id === updated.id);
    if (target) {
      Object.assign(target, updated);
    }
    variableDialogVisible.value = false;
    ElMessage.success('变量配置已保存');
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存变量配置失败');
  } finally {
    savingVariableConfig.value = false;
  }
}

async function syncTaskItem(itemId: number) {
  syncingTaskItemId.value = itemId;
  try {
    const updated = await sceneApi.syncTaskItem(sceneId.value, itemId);
    const target = taskItems.value.find((item) => item.id === itemId);
    if (target) {
      Object.assign(target, updated);
    }
    ElMessage.success('任务快照已同步');
  } finally {
    syncingTaskItemId.value = null;
  }
}

async function syncAllTaskItems() {
  syncingAllTasks.value = true;
  try {
    const result = await sceneApi.syncTaskItems(sceneId.value);
    taskItems.value = [...result.task_items].sort((a, b) => a.sort_order - b.sort_order);
    const parts = [];
    parts.push(`已同步 ${result.updated_count} 项`);
    if (result.missing_count > 0) {
      parts.push(`${result.missing_count} 项已失效`);
    }
    ElMessage.success(parts.join('，'));
  } finally {
    syncingAllTasks.value = false;
  }
}

async function moveTaskItem(index: number, delta: number) {
  const nextIndex = index + delta;
  if (nextIndex < 0 || nextIndex >= taskItems.value.length) return;

  const current = taskItems.value[index];
  const target = taskItems.value[nextIndex];
  await Promise.all([
    sceneApi.updateTaskItem(sceneId.value, current.id, { sort_order: target.sort_order, remark: current.remark }),
    sceneApi.updateTaskItem(sceneId.value, target.id, { sort_order: current.sort_order, remark: target.remark }),
  ]);
  ElMessage.success('任务顺序已更新');
  await loadScene();
}

async function persistTaskOrder(nextItems: SceneTaskItem[]) {
  const updates = nextItems
    .map((item, index) => ({
      id: item.id,
      sort_order: index + 1,
      remark: item.remark,
      changed: item.sort_order !== index + 1,
    }))
    .filter((item) => item.changed);

  if (updates.length === 0) {
    taskItems.value = nextItems.map((item, index) => ({ ...item, sort_order: index + 1 }));
    return;
  }

  taskReordering.value = true;
  const optimisticItems = nextItems.map((item, index) => ({ ...item, sort_order: index + 1 }));
  taskItems.value = optimisticItems;
  try {
    await Promise.all(
      updates.map((item) =>
        sceneApi.updateTaskItem(sceneId.value, item.id, {
          sort_order: item.sort_order,
          remark: item.remark,
        }),
      ),
    );
    ElMessage.success('任务顺序已更新');
  } catch (error) {
    console.error('[SceneDetail] 拖拽更新任务顺序失败', error);
    ElMessage.error('拖拽排序失败，请稍后重试');
    await loadScene();
  } finally {
    taskReordering.value = false;
  }
}

function onTaskDragStart(index: number, itemId: number, event: DragEvent) {
  if (taskReordering.value) {
    event.preventDefault();
    return;
  }
  draggingTaskIndex.value = index;
  draggingTaskItemId.value = itemId;
  dropTaskItemId.value = itemId;
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', String(itemId));
  }
}

function onTaskDragOver(itemId: number) {
  if (draggingTaskItemId.value === null || draggingTaskItemId.value === itemId) return;
  dropTaskItemId.value = itemId;
}

async function onTaskDrop(dropIndex: number) {
  const fromIndex = draggingTaskIndex.value;
  if (fromIndex === null || fromIndex === dropIndex) {
    onTaskDragEnd();
    return;
  }

  const nextItems = [...taskItems.value];
  const [movedItem] = nextItems.splice(fromIndex, 1);
  if (!movedItem) {
    onTaskDragEnd();
    return;
  }
  nextItems.splice(dropIndex, 0, movedItem);
  onTaskDragEnd();
  await persistTaskOrder(nextItems);
}

function onTaskDragEnd() {
  draggingTaskIndex.value = null;
  draggingTaskItemId.value = null;
  dropTaskItemId.value = null;
}

async function removeTaskItem(itemId: number) {
  await ElMessageBox.confirm('确认移除该编排任务吗？', '提示', { type: 'warning' });
  await sceneApi.removeTaskItem(sceneId.value, itemId);
  ElMessage.success('编排任务已移除');
  await loadScene();
}

async function removeRelation(relationId: number) {
  await ElMessageBox.confirm('确认移除该脚本关联吗？', '提示', { type: 'warning' });
  await sceneApi.removeScript(sceneId.value, relationId);
  ElMessage.success('已移除');
  await Promise.all([loadScene(), loadScripts()]);
}

async function copyCurrentScene() {
  const copied = await sceneApi.copy(sceneId.value);
  ElMessage.success('场景已复制');
  await router.push({ name: 'scene-detail', params: { id: copied.id } });
}

async function previewCompiledScript() {
  const compiled = await sceneApi.getCompiledScript(sceneId.value);
  compiledYaml.value = compiled.yaml;
  compiledPreviewVisible.value = true;
}

async function executeScene() {
  executingScene.value = true;
  try {
    const result = await sceneApi.execute(sceneId.value);
    executeResult.value = result;
    executeResultVisible.value = true;
    ElMessage.success(result.message);
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '场景执行失败');
  } finally {
    executingScene.value = false;
  }
}

function goBack() {
  router.push({ name: 'scenes-list' });
}

function goScript(scriptId: number) {
  router.push({ name: 'script-editor', params: { id: scriptId } });
}

function formatSourceType(sourceType: string) {
  if (sourceType === 'manual') return '手动';
  return sourceType || '-';
}

function syncStatusLabel(status: string) {
  if (status === 'current') return '已同步';
  if (status === 'stale') return '已过期';
  if (status === 'missing') return '任务缺失';
  return status || '-';
}

function syncStatusTagType(status: string) {
  if (status === 'current') return 'success';
  if (status === 'stale') return 'warning';
  if (status === 'missing') return 'danger';
  return 'info';
}

function formatExecuteDetail(detail: SceneExecuteResult['detail']) {
  if (typeof detail === 'string') return detail;
  return JSON.stringify(detail, null, 2);
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header,
.sub-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sub-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.actions {
  display: flex;
  gap: 8px;
}

.meta-form {
  max-width: 760px;
}

.sub-header-desc {
  color: #6b7280;
  font-size: 13px;
}

.task-layout {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.task-source-panel,
.task-target-panel {
  min-width: 0;
}

.task-panel-title {
  margin-bottom: 12px;
  font-weight: 600;
  color: #111827;
}

.task-source-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-source-group {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  background: #fff;
}

.task-source-group-title {
  margin-bottom: 10px;
}

.task-source-group-title-button {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 0;
  padding: 0;
  background: transparent;
  font-weight: 600;
  color: #374151;
  text-align: left;
  cursor: pointer;
}

.task-source-group-title-button:disabled {
  cursor: wait;
  opacity: 0.7;
}

.task-source-group-title-action {
  color: #2563eb;
  font-size: 12px;
  font-weight: 500;
}

.task-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.task-board {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}

.task-board-header,
.task-board-row {
  display: grid;
  grid-template-columns: 72px 72px minmax(160px, 1.1fr) minmax(140px, 0.9fr) minmax(140px, 0.9fr) minmax(220px, 1.4fr) 132px;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
}

.task-board-header {
  background: #f8fafc;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  border-bottom: 1px solid #e5e7eb;
}

.task-board-row {
  border-bottom: 1px solid #e5e7eb;
  transition: background-color 0.2s ease, border-color 0.2s ease, opacity 0.2s ease;
}

.task-board-row:last-child {
  border-bottom: 0;
}

.task-board-row-dragging {
  opacity: 0.55;
  background: #eff6ff;
}

.task-board-row-drop-target {
  background: #f0f9ff;
  box-shadow: inset 0 2px 0 #60a5fa;
}

.drag-handle {
  border: 0;
  background: transparent;
  color: #9ca3af;
  font-size: 18px;
  line-height: 1;
  cursor: grab;
  padding: 4px 8px;
}

.drag-handle:active {
  cursor: grabbing;
}

.task-col-handle,
.task-col-order,
.task-col-action {
  display: flex;
  align-items: center;
}

.task-col-status {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.task-sync-message {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.4;
}

.task-variable-summary {
  margin-top: 6px;
  color: #6b7280;
  font-size: 12px;
}

.execute-result {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.execute-result-line {
  color: #374151;
  line-height: 1.5;
}

.task-col-action {
  justify-content: flex-end;
  gap: 8px;
}

.dialog-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dialog-desc {
  font-size: 12px;
  color: #6b7280;
}

.compiled-preview {
  margin: 0;
  max-height: 70vh;
  overflow: auto;
  padding: 16px;
  border-radius: 12px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 1024px) {
  .task-layout {
    grid-template-columns: 1fr;
  }

  .task-board-header,
  .task-board-row {
    grid-template-columns: 56px 56px minmax(140px, 1fr);
  }

  .task-col-script,
  .task-col-status,
  .task-col-remark,
  .task-col-action,
  .task-board-header .task-col-script,
  .task-board-header .task-col-status,
  .task-board-header .task-col-remark,
  .task-board-header .task-col-action {
    grid-column: 1 / -1;
  }

  .task-col-action {
    justify-content: flex-start;
  }
}
</style>
