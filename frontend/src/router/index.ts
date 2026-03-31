import { createRouter, createWebHistory } from 'vue-router';

import SceneDetail from '../pages/SceneDetail.vue';
import SceneList from '../pages/SceneList.vue';
import ScriptList from '../pages/ScriptList.vue';
import ScriptEditor from '../pages/ScriptEditor.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/scenes' },
    { path: '/scenes', name: 'scenes-list', component: SceneList },
    { path: '/scenes/:id(\\d+)', name: 'scene-detail', component: SceneDetail },
    { path: '/scripts', name: 'scripts-list', component: ScriptList },
    { path: '/scripts/:id(\\d+)', name: 'script-editor', component: ScriptEditor },
  ],
});
