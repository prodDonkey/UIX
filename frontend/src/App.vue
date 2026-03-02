<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="title">YAML Script Platform</div>
      <el-button type="primary" plain @click="goScripts">脚本列表</el-button>
    </el-header>
    <el-main class="main">
      <router-view :key="route.fullPath" />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router';

const router = useRouter();
const route = useRoute();

function goScripts() {
  router.push({ name: 'scripts-list' });
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e5e7eb;
}
.title {
  font-weight: 700;
  letter-spacing: 0.2px;
}
.main {
  background: #f7f8fa;
}
</style>
