import { defineStore } from 'pinia';

import { scriptApi, type Script } from '../api/scripts';

export const useScriptStore = defineStore('script', {
  state: () => ({
    scripts: [] as Script[],
    loading: false,
  }),
  actions: {
    async fetchScripts() {
      this.loading = true;
      try {
        this.scripts = await scriptApi.list();
      } finally {
        this.loading = false;
      }
    },
  },
});
