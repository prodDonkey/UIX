<template>
  <el-dialog :model-value="visible" title="AI 生成 YAML" width="700px" @close="close">
    <el-form label-width="90px">
      <el-form-item label="需求描述">
        <el-input
          v-model="prompt"
          type="textarea"
          :rows="8"
          placeholder="例如：打开上门超人，勾选同意协议，输入手机号和验证码并登录"
        />
      </el-form-item>
      <el-form-item label="设备ID">
        <el-input v-model="deviceId" placeholder="可选，不填则运行时注入" />
      </el-form-item>
      <el-form-item label="生成语言">
        <el-select v-model="language" style="width: 180px">
          <el-option label="中文" value="zh" />
          <el-option label="English" value="en" />
        </el-select>
      </el-form-item>
      <el-form-item label="模型名">
        <el-input v-model="model" placeholder="可选，不填使用后端默认模型" />
      </el-form-item>
    </el-form>

    <el-alert v-if="errorMsg" type="error" :title="errorMsg" show-icon class="msg" />
    <el-alert v-if="warningMsg" type="warning" :title="warningMsg" show-icon class="msg" />

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="loading" @click="generate">生成并回填</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { ref, watch } from 'vue';

import { scriptApi } from '../api/scripts';

const props = defineProps<{ visible: boolean }>();
const emit = defineEmits<{
  close: [];
  generated: [yaml: string];
}>();

const prompt = ref('');
const deviceId = ref('');
const language = ref<'zh' | 'en'>('zh');
const model = ref('');
const loading = ref(false);
const errorMsg = ref('');
const warningMsg = ref('');

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return;
    errorMsg.value = '';
    warningMsg.value = '';
  }
);

function close() {
  emit('close');
}

async function generate() {
  if (!prompt.value.trim()) {
    ElMessage.warning('请先输入需求描述');
    return;
  }

  loading.value = true;
  errorMsg.value = '';
  warningMsg.value = '';
  try {
    const result = await scriptApi.generate({
      prompt: prompt.value.trim(),
      device_id: deviceId.value.trim() || undefined,
      language: language.value,
      model: model.value.trim() || undefined,
    });
    if (result.warnings?.length) {
      warningMsg.value = result.warnings.join('; ');
    }
    emit('generated', result.yaml);
    emit('close');
    ElMessage.success('YAML 生成成功');
  } catch (error: any) {
    const detail = error?.response?.data?.detail;
    if (typeof detail === 'string') {
      errorMsg.value = detail;
      return;
    }
    if (detail?.message) {
      errorMsg.value = `生成结果校验失败：${detail.message}`;
      return;
    }
    errorMsg.value = '生成失败，请检查模型配置或稍后重试';
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.msg {
  margin-top: 10px;
}
</style>

