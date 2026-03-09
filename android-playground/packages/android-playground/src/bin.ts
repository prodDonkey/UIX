import { exec } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { promisify } from 'node:util';
import { select } from '@inquirer/prompts';
import {
  AndroidAgent,
  AndroidDevice,
  getConnectedDevices,
} from '@midscene/android';
import { PlaygroundServer } from '@midscene/playground';
import {
  PLAYGROUND_SERVER_PORT,
  SCRCPY_SERVER_PORT,
} from '@midscene/shared/constants';
import { findAvailablePort } from '@midscene/shared/node';
import cors from 'cors';
import ScrcpyServer from './scrcpy-server';

const promiseExec = promisify(exec);

// Function to get available devices
async function getAdbDevices() {
  try {
    const devices = await getConnectedDevices();
    return devices
      .filter((device) => device.state === 'device')
      .map((device) => ({
        id: device.udid,
        status: device.state,
        name: device.udid,
      }));
  } catch (error) {
    console.error('Error getting ADB devices:', error);
    return [];
  }
}

// Function to prompt user for device selection
async function selectDevice() {
  console.log('🔍 Scanning for Android devices...');

  const devices = await getAdbDevices();

  if (devices.length === 0) {
    console.error('❌ No Android devices found!');
    console.log('📱 Please ensure:');
    console.log('  • Your device is connected via USB');
    console.log('  • USB debugging is enabled');
    console.log('  • Device is authorized for debugging');
    process.exit(1);
  }

  if (devices.length === 1) {
    console.log(`📱 Found device: ${devices[0].name} (${devices[0].id})`);
    return devices[0].id;
  }

  // Multiple devices found, prompt user to choose
  const choices = devices.map((device) => ({
    name: `${device.name} (${device.id})`,
    value: device.id,
  }));

  const selectedDevice = await select({
    message: '📱 Multiple devices found. Please select one:',
    choices,
  });

  return selectedDevice;
}

function resolveStaticDir() {
  const packagedStaticDir = path.join(__dirname, '../../static');
  if (fs.existsSync(path.join(packagedStaticDir, 'index.html'))) {
    return packagedStaticDir;
  }

  const appDistDir = path.join(__dirname, '../../../apps/android-playground/dist');
  if (fs.existsSync(path.join(appDistDir, 'index.html'))) {
    console.log(`📦 Using app dist as static assets: ${appDistDir}`);
    return appDistDir;
  }

  return packagedStaticDir;
}

const staticDir = resolveStaticDir();
// 报告保存到上级目录的 midscene_run/report，可通过 /report 路径访问
const reportDir = path.join(__dirname, '../../midscene_run');
const shouldAutoOpenPlayground =
  process.env.MIDSCENE_NO_OPEN !== '1' &&
  process.env.MIDSCENE_NO_OPEN !== 'true';

const main = async () => {
  const { default: open } = await import('open');

  try {
    // First, let user select device
    const selectedDeviceId = await selectDevice();
    console.log(`✅ Selected device: ${selectedDeviceId}`);

    // Create PlaygroundServer with agent factory
    const playgroundServer = new PlaygroundServer(
      // Agent factory - creates new agent with device each time
      async () => {
        const device = new AndroidDevice(selectedDeviceId);
        await device.connect();
        return new AndroidAgent(device);
      },
      staticDir,
      reportDir,
    );

    const scrcpyServer = new ScrcpyServer();

    // Set the selected device in scrcpy server
    scrcpyServer.currentDeviceId = selectedDeviceId;

    // Add CORS middleware to playground server for remote access
    playgroundServer.app.use(
      cors({
        origin: true,
        credentials: true,
        methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
      }),
    );

    console.log('🚀 Starting servers...');

    // Find available ports
    const availablePlaygroundPort = await findAvailablePort(
      PLAYGROUND_SERVER_PORT,
    );
    const availableScrcpyPort = await findAvailablePort(SCRCPY_SERVER_PORT);

    if (availablePlaygroundPort !== PLAYGROUND_SERVER_PORT) {
      console.log(
        `⚠️  Port ${PLAYGROUND_SERVER_PORT} is busy, using port ${availablePlaygroundPort} instead`,
      );
    }
    if (availableScrcpyPort !== SCRCPY_SERVER_PORT) {
      console.log(
        `⚠️  Port ${SCRCPY_SERVER_PORT} is busy, using port ${availableScrcpyPort} instead`,
      );
    }

    await Promise.all([
      playgroundServer.launch(availablePlaygroundPort),
      scrcpyServer.launch(availableScrcpyPort),
    ]);

    // Store scrcpy server port in global for playground server to access
    (global as any).scrcpyServerPort = availableScrcpyPort;

    console.log('');
    console.log('✨ Midscene Android Playground is ready!');
    console.log(`🎮 Playground: http://localhost:${playgroundServer.port}`);
    console.log(`📱 Device: ${selectedDeviceId}`);
    console.log(`🔑 Generated Server ID: ${playgroundServer.id}`);
    console.log('');

    if (shouldAutoOpenPlayground) {
      open(`http://localhost:${playgroundServer.port}`);
    } else {
      console.log('🧩 Auto-open disabled (MIDSCENE_NO_OPEN=1).');
    }
  } catch (error) {
    console.error('Failed to start servers:', error);
    process.exit(1);
  }
};

main();
