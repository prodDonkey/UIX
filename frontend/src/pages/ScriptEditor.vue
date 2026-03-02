<template>
  <el-card>
    <template #header>
      <div class="header">
        <div>
          <strong>脚本编辑</strong>
          <span v-if="scriptId"> #{{ scriptId }}</span>
        </div>
        <div class="actions">
          <el-button @click="goBack">返回列表</el-button>
          <el-button @click="validate">校验</el-button>
          <el-button type="primary" @click="save">保存</el-button>
          <el-button type="success" disabled>执行（M2）</el-button>
        </div>
      </div>
    </template>

    <el-form label-width="90px" class="meta-form">
      <el-form-item label="脚本名称">
        <el-input v-model="name" />
      </el-form-item>
      <el-form-item label="来源">
        <el-select v-model="sourceType" style="width: 220px">
          <el-option label="manual" value="manual" />
          <el-option label="ai" value="ai" />
        </el-select>
      </el-form-item>
    </el-form>

    <YamlEditor v-model="content" />

    <el-alert
      v-if="validateMessage"
      :title="validateMessage"
      :type="validateOk ? 'success' : 'error'"
      show-icon
      class="alert"
    />
  </el-card>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { scriptApi } from '../api/scripts';
import YamlEditor from '../components/YamlEditor.vue';

const route = useRoute();
const router = useRouter();
const scriptId = computed(() => Number(route.params.id));

const name = ref('');
const sourceType = ref('manual');
const content = ref('');
const validateMessage = ref('');
const validateOk = ref(false);

onMounted(async () => {
  if (Number.isNaN(scriptId.value) || scriptId.value <= 0) {
    await router.replace({ name: 'scripts-list' });
    return;
  }

  const detail = await scriptApi.detail(scriptId.value);
  name.value = detail.name;
  sourceType.value = detail.source_type;
  content.value = detail.content;
});

async function save() {
  await scriptApi.update(scriptId.value, {
    name: name.value,
    source_type: sourceType.value,
    content: content.value,
  });
  ElMessage.success('保存成功');
}

async function validate() {
  const result = await scriptApi.validate(scriptId.value, content.value);
  validateOk.value = result.valid;
  validateMessage.value = result.valid
    ? 'YAML 校验通过'
    : `校验失败：${result.message ?? 'unknown error'}${result.line ? ` (line ${result.line})` : ''}`;
}

async function goBack() {
  await router.replace({ name: 'scripts-list' });
}
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
.meta-form {
  max-width: 680px;
  margin-bottom: 12px;
}
.alert {
  margin-top: 12px;
}
</style>
