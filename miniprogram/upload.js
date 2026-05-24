const ci = require('miniprogram-ci');

async function uploadMiniProgram() {
  const projectPath = __dirname;
  const privateKeyPath = `${projectPath}/private.wxf1b550fac7e720d6.key`;

  try {
    const project = new ci.Project({
      appid: 'wxf1b550fac7e720d6',
      type: 'miniProgram',
      projectPath: projectPath,
      privateKeyPath: privateKeyPath,
      ignores: ['node_modules/**', '*.log']
    });

    const result = await ci.upload({
      project,
      version: '1.0.0',
      desc: 'Fix K-line display, score card sizing, button text wrapping, remove self-stocks section',
      setting: {
        es6: true,
        minify: false,
      }
    });

    console.log('Upload success:', result);
  } catch (err) {
    console.error('Upload failed:', err);
  }
}

uploadMiniProgram();