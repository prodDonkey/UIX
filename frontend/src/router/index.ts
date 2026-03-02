import { createRouter, createWebHistory } from 'vue-router';

import ScriptList from '../pages/ScriptList.vue';
import ScriptEditor from '../pages/ScriptEditor.vue';
import RunDetail from '../pages/RunDetail.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/scripts' },
    { path: '/scripts', name: 'scripts-list', component: ScriptList },
    { path: '/scripts/:id(\\d+)', name: 'script-editor', component: ScriptEditor },
    { path: '/run/:id', name: 'run-detail', component: RunDetail },
  ],
});
