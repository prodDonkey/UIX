<template>
  <div class="editor-wrapper">
    <div ref="editorRef" class="editor"></div>
  </div>
</template>

<script setup lang="ts">
import * as monaco from 'monaco-editor';
import { configureMonacoYaml } from 'monaco-yaml';
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = defineProps<{ modelValue: string }>();
const emit = defineEmits<{ 'update:modelValue': [value: string] }>();

const editorRef = ref<HTMLElement | null>(null);
let editor: monaco.editor.IStandaloneCodeEditor | undefined;
let disposeYaml: (() => void) | undefined;
let isUpdatingFromParent = false;

onMounted(() => {
  disposeYaml = configureMonacoYaml(monaco, {
    enableSchemaRequest: false,
    validate: true,
  });

  editor = monaco.editor.create(editorRef.value as HTMLElement, {
    value: props.modelValue,
    language: 'yaml',
    minimap: { enabled: false },
    automaticLayout: true,
    fontSize: 14,
  });

  editor.onDidChangeModelContent(() => {
    if (!editor || isUpdatingFromParent) return;
    emit('update:modelValue', editor.getValue());
  });
});

watch(
  () => props.modelValue,
  (val) => {
    if (!editor) return;
    if (editor.getValue() === val) return;
    isUpdatingFromParent = true;
    editor.setValue(val);
    isUpdatingFromParent = false;
  }
);

onBeforeUnmount(() => {
  editor?.dispose();
  disposeYaml?.();
});
</script>

<style scoped>
.editor-wrapper {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  overflow: hidden;
}
.editor {
  width: 100%;
  height: 560px;
}
</style>
