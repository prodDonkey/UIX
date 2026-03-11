<template>
  <el-card>
    <template #header>
      <div class="header">
        <span>脚本列表</span>
        <el-button type="primary" @click="createScript">新建脚本</el-button>
      </div>
    </template>

    <el-table :data="store.scripts" v-loading="store.loading" row-key="id">
      <el-table-column label="名称" min-width="180">
        <template #default="{ row }">
          <el-button link type="primary" class="name-link" @click="goEdit(row.id)">
            {{ row.name }}
          </el-button>
        </template>
      </el-table-column>
      <el-table-column label="所属场景数" width="110">
        <template #default="{ row }">
          {{ row.scene_count ?? 0 }}
        </template>
      </el-table-column>
      <el-table-column label="来源" width="120">
        <template #default="{ row }">
          {{ formatSourceType(row.source_type) }}
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="更新时间" min-width="180" :formatter="formatTime" />
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="goEdit(row.id)">编辑</el-button>
          <el-button size="small" @click="copyScript(row.id)">复制</el-button>
          <el-button size="small" type="danger" @click="deleteScript(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';

import { scriptApi } from '../api/scripts';
import { useScriptStore } from '../stores/script';
import { formatServerDateTime } from '../utils/datetime';

const store = useScriptStore();
const router = useRouter();

const defaultTemplate = `# 示例脚本：进入工作台并完成签到
android:
  deviceId: ""

tasks:
  - name: 打开工作台
    flow:
      - aiAction: 打开目标应用并进入“工作台”页面
      - aiAssert: 当前页面出现“工作台”标题

  - name: 进入签到页
    flow:
      - aiAction: 点击“签到”入口
      - aiAssert: 当前页面出现“立即签到”按钮

  - name: 完成签到
    flow:
      - aiAction: 点击“立即签到”按钮
      - aiAssert: 页面出现“签到成功”
`;

onMounted(async () => {
  await store.fetchScripts();
});

async function createScript() {
  const created = await scriptApi.create({
    name: `new-script-${Date.now()}`,
    content: defaultTemplate,
    source_type: 'manual',
  });
  ElMessage.success('脚本已创建');
  router.push(`/scripts/${created.id}`);
}

function goEdit(id: number) {
  router.push(`/scripts/${id}`);
}

function formatTime(_: unknown, __: unknown, value: string) {
  return formatServerDateTime(value);
}

function formatSourceType(sourceType: string) {
  if (sourceType === 'manual') return '手动';
  if (sourceType === 'ai') return 'AI生成';
  return sourceType || '-';
}

async function copyScript(id: number) {
  await scriptApi.copy(id);
  ElMessage.success('复制成功');
  await store.fetchScripts();
}

async function deleteScript(id: number) {
  const target = store.scripts.find((item) => item.id === id);
  const sceneCount = target?.scene_count ?? 0;
  const message =
    sceneCount > 0
      ? `该脚本已被 ${sceneCount} 个场景引用，删除后会同步移除关联关系。确认继续吗？`
      : '确认删除该脚本吗？';
  await ElMessageBox.confirm(message, '提示', { type: 'warning' });
  await scriptApi.remove(id);
  ElMessage.success('删除成功');
  await store.fetchScripts();
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
