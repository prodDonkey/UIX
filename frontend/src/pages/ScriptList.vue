<template>
  <el-card>
    <template #header>
      <div class="header">
        <span>脚本列表</span>
        <el-button type="primary" @click="createScript">新建脚本</el-button>
      </div>
    </template>

    <el-table :data="store.scripts" v-loading="store.loading" row-key="id">
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column prop="source_type" label="来源" width="120" />
      <el-table-column prop="updated_at" label="更新时间" min-width="180" />
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

const store = useScriptStore();
const router = useRouter();

const defaultTemplate = `android:\n  deviceId: ""\n\ntasks:\n  - name: demo\n    flow:\n      - aiAction: open Settings app\n`;

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

async function copyScript(id: number) {
  await scriptApi.copy(id);
  ElMessage.success('复制成功');
  await store.fetchScripts();
}

async function deleteScript(id: number) {
  await ElMessageBox.confirm('确认删除该脚本吗？', '提示', { type: 'warning' });
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
</style>
