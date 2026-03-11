<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="title" role="button" tabindex="0" @click="goScenes" @keydown.enter="goScenes">UI自动化脚本</div>
      <div class="nav-actions">
        <el-button :type="isScenesPage ? 'primary' : 'default'" plain @click="goScenes">场景列表</el-button>
        <el-button :type="isScriptsPage ? 'primary' : 'default'" plain @click="goScripts">脚本列表</el-button>
        <el-button :type="isRunsPage ? 'primary' : 'default'" plain @click="goRuns">运行列表</el-button>
      </div>
    </el-header>
    <el-main class="main">
      <router-view :key="route.fullPath" />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const router = useRouter();
const route = useRoute();
const isScenesPage = computed(() => route.path.startsWith('/scenes'));
const isScriptsPage = computed(() => route.path.startsWith('/scripts'));
const isRunsPage = computed(() => route.path.startsWith('/runs') || route.path.startsWith('/run/'));

function goScenes() {
  router.push({ name: 'scenes-list' });
}

function goScripts() {
  router.push({ name: 'scripts-list' });
}

function goRuns() {
  router.push({ name: 'runs-list' });
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
  cursor: pointer;
  user-select: none;
}
.nav-actions {
  display: flex;
  gap: 8px;
}
.main {
  background: #f7f8fa;
}
</style>
