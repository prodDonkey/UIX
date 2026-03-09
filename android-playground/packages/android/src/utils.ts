import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { getDebug } from '@midscene/shared/logger';
import { ADB, type Device } from 'appium-adb';

const debugUtils = getDebug('android:utils');

function ensureAndroidSdkEnv() {
  if (process.env.ANDROID_HOME || process.env.ANDROID_SDK_ROOT) {
    return;
  }

  const candidateSdkRoots = [
    path.join(os.homedir(), 'Library/Android/sdk'),
    path.join(os.homedir(), 'Android/Sdk'),
    '/opt/android-sdk',
  ];

  const detectedSdkRoot = candidateSdkRoots.find((sdkRoot) =>
    fs.existsSync(path.join(sdkRoot, 'platform-tools/adb')),
  );

  if (!detectedSdkRoot) {
    return;
  }

  // 中文日志：帮助定位本机 SDK 已安装但环境变量未导出的场景
  process.env.ANDROID_HOME = detectedSdkRoot;
  process.env.ANDROID_SDK_ROOT = detectedSdkRoot;
  debugUtils(`Detected Android SDK automatically: ${detectedSdkRoot}`);
}

export async function getConnectedDevices(): Promise<Device[]> {
  try {
    ensureAndroidSdkEnv();
    const adb = await ADB.createADB({
      adbExecTimeout: 60000,
    });
    const devices = await adb.getConnectedDevices();

    debugUtils(`Found ${devices.length} connected devices: `, devices);

    return devices;
  } catch (error: any) {
    console.error('Failed to get device list:', error);
    throw new Error(
      `Unable to get connected Android device list, please check https://midscenejs.com/integrate-with-android.html#faq : ${error.message}`,
      {
        cause: error,
      },
    );
  }
}
