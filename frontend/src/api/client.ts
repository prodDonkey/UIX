import axios from 'axios';
import { getApiBaseUrl } from '../config/runtime';

export const http = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 15000,
});
