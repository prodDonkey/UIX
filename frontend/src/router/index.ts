import { createRouter, createWebHistory } from 'vue-router';

import ScriptList from '../pages/ScriptList.vue';
import ScriptEditor from '../pages/ScriptEditor.vue';
import RunDetail from '../pages/RunDetail.vue';
import RunList from '../pages/RunList.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/scripts' },
    { path: '/scripts', name: 'scripts-list', component: ScriptList },
    { path: '/scripts/:id(\\d+)', name: 'script-editor', component: ScriptEditor },
    { path: '/runs', name: 'runs-list', component: RunList },
    { path: '/run/:id', name: 'run-detail', component: RunDetail },
  ],
});
