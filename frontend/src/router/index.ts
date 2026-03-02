import { createRouter, createWebHistory } from 'vue-router';

import ScriptList from '../pages/ScriptList.vue';
import ScriptEditor from '../pages/ScriptEditor.vue';
import RunDetail from '../pages/RunDetail.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/scripts' },
    { path: '/scripts', component: ScriptList },
    { path: '/scripts/:id', component: ScriptEditor },
    { path: '/run/:id', component: RunDetail },
  ],
});
