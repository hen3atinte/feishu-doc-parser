// 飞书自动扫码登录脚本
// 用途：保持二维码有效，自动刷新，检测登录成功
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const QR_FILE = path.join(process.env.HOME || process.env.USERPROFILE, '.workbuddy', 'feishu_qr_auto.png');
const PROFILE_DIR = path.join(process.env.HOME || process.env.USERPROFILE, '.workbuddy', 'playwright-feishu');

async function captureQR(page) {
  // Try to find and save QR code image directly
  const qrImg = await page.$('img[src*="qr"], img[src*="QR"], img[src*="qrcode"], canvas');
  if (qrImg) {
    await qrImg.screenshot({ path: QR_FILE });
    return true;
  }
  // Fallback: screenshot the whole login area
  await page.screenshot({ path: QR_FILE, fullPage: false });
  return false;
}

async function main() {
  console.log('启动飞书扫码登录助手...');

  const browser = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false,
    channel: 'chrome', // Use system Chrome for better cookie support
    viewport: { width: 1280, height: 800 }
  });

  const page = await browser.pages()[0] || await browser.newPage();

  // Navigate to login
  await page.goto('https://ta6hb0ysuge.feishu.cn/wiki/RyXHwqg0vitVFWkoIT1csrWgn9f');

  let lastQRTime = 0;
  const QR_REFRESH_INTERVAL = 120000; // Refresh QR every 2 minutes

  // Monitor for login success
  const checkInterval = setInterval(async () => {
    try {
      const url = page.url();
      
      // Check if logged in (no longer on login page)
      if (!url.includes('accounts.feishu.cn')) {
        console.log('✅ 登录成功！当前URL:', url);
        clearInterval(checkInterval);
        
        // Save cookies for later use
        const cookies = await page.context().cookies();
        fs.writeFileSync(
          path.join(PROFILE_DIR, 'cookies.json'),
          JSON.stringify(cookies, null, 2)
        );
        console.log('Cookies已保存');
        
        // Navigate back to the first doc
        await page.goto('https://ta6hb0ysuge.feishu.cn/wiki/RyXHwqg0vitVFWkoIT1csrWgn9f');
        console.log('已返回文档页面，浏览器保持开启');
        
        // Don't close browser - keep it open for extraction
        return;
      }
      
      // Refresh QR code periodically
      const now = Date.now();
      if (now - lastQRTime > QR_REFRESH_INTERVAL) {
        console.log('🔄 刷新二维码...');
        await page.reload();
        await page.waitForTimeout(2000);
        await captureQR(page);
        lastQRTime = now;
        console.log('📱 新二维码已保存:', QR_FILE);
      }
    } catch (e) {
      console.error('检查出错:', e.message);
    }
  }, 3000);

  // Initial capture
  await page.waitForTimeout(3000);
  await captureQR(page);
  lastQRTime = Date.now();
  console.log('📱 初始二维码已保存:', QR_FILE);
  console.log('🔍 等待扫码登录（每3秒检查一次，每2分钟自动刷新二维码）...');
}

main().catch(err => {
  console.error('启动失败:', err);
  process.exit(1);
});
