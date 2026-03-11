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
            <el-button type="success" plain :disabled="taskItems.length === 0" @click="runScene">
              执行整个场景
            </el-button>
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
            <el-button size="small" type="success" plain @click="runScript(row.script_id)">运行</el-button>
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
                {{ relation.script.name }}
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
          <el-table :data="taskItems" row-key="id" empty-text="暂无编排任务">
            <el-table-column label="顺序" width="80">
              <template #default="{ row }">{{ row.sort_order }}</template>
            </el-table-column>
            <el-table-column label="任务名称" min-width="180">
              <template #default="{ row }">{{ row.task_name_snapshot }}</template>
            </el-table-column>
            <el-table-column label="来源脚本" min-width="160">
              <template #default="{ row }">{{ row.script.name }}</template>
            </el-table-column>
            <el-table-column label="备注" min-width="200">
              <template #default="{ row }">
                <el-input
                  :model-value="row.remark"
                  placeholder="可填写该任务在场景中的用途"
                  @change="(value) => updateTaskRemark(row.id, String(value ?? ''))"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="210" fixed="right">
              <template #default="{ row, $index }">
                <el-button size="small" :disabled="$index === 0" @click="moveTaskItem($index, -1)">上移</el-button>
                <el-button
                  size="small"
                  :disabled="$index === taskItems.length - 1"
                  @click="moveTaskItem($index, 1)"
                >
                  下移
                </el-button>
                <el-button size="small" type="danger" @click="removeTaskItem(row.id)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
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
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { sceneApi, type SceneScriptRelation, type SceneTaskItem, type ScriptTask } from '../api/scenes';
import { runApi } from '../api/runs';
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

async function runScript(scriptId: number) {
  const run = await runApi.create(scriptId);
  ElMessage.success(`任务已创建 #${run.id}`);
  await router.push({ name: 'run-detail', params: { id: run.id } });
}

async function previewCompiledScript() {
  const compiled = await sceneApi.getCompiledScript(sceneId.value);
  compiledYaml.value = compiled.yaml;
  compiledPreviewVisible.value = true;
}

async function runScene() {
  const created = await sceneApi.runScene(sceneId.value);
  ElMessage.success(`场景任务已创建 #${created.run_id}`);
  await router.push({ name: 'run-detail', params: { id: created.run_id } });
}

function goBack() {
  router.push({ name: 'scenes-list' });
}

function goScript(scriptId: number) {
  router.push({ name: 'script-editor', params: { id: scriptId } });
}

function formatSourceType(sourceType: string) {
  if (sourceType === 'manual') return '手动';
  if (sourceType === 'ai') return 'AI生成';
  return sourceType || '-';
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
  font-weight: 600;
  color: #374151;
}

.task-chip-list {
  display: flex;
  flex-wrap: wrap;
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
}
</style>
