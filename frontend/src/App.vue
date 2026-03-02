<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="title">YAML Script Platform</div>
      <el-menu mode="horizontal" :default-active="activeMenu" router>
        <el-menu-item index="/scripts">脚本列表</el-menu-item>
      </el-menu>
    </el-header>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const activeMenu = computed(() => (route.path.startsWith('/run') ? '/scripts' : route.path));
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
