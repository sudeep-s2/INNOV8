import { test, expect } from '@playwright/test';

test.describe('Info2Impact End-to-End Workflow & Integration Suite', () => {
  test.beforeEach(async ({ page }) => {
    // Monitor console errors
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        console.error(`[Browser Error]: ${msg.text()}`);
      }
    });
  });

  test('1. Application Load & Header Verification', async ({ page }) => {
    await page.goto('/');

    // Check title and branding
    await expect(page).toHaveTitle(/Info2Impact/);
    await expect(page.getByText('Info2Impact', { exact: true })).toBeVisible();
    await expect(page.getByText('SIH26154 · NTRO')).toBeVisible();

    // Stepper navigation visible
    await expect(page.locator('nav.stepper-nav')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Source', exact: false })).toBeVisible();
  });

  test('2. Backend Connectivity & Health Check', async ({ page }) => {
    await page.goto('/');

    // Wait for the backend status pill to report connected
    const statusPill = page.locator('header span:has-text("Ollama Qwen3:8B")');
    await expect(statusPill).toBeVisible({ timeout: 15_000 });
    await expect(statusPill).toContainText('info2impact');
  });

  test('3. Source Ingestion Flow & Validation', async ({ page }) => {
    await page.goto('/');

    // Verify initial state
    const textarea = page.locator('textarea');
    await expect(textarea).toBeVisible();

    // Verify validation error on empty submit
    const analyzeBtn = page.getByRole('button', { name: /Analyze & Extract Canonical Model/i });
    await expect(analyzeBtn).toBeDisabled();

    // Type short text (< 10 chars)
    await textarea.fill('Short');
    await expect(analyzeBtn).toBeEnabled();
    await analyzeBtn.click();
    await expect(page.getByText(/Please provide at least 10 characters/i)).toBeVisible();

    // Click "Load Sample NTRO SCADA Incident"
    await page.getByRole('button', { name: /Load Sample NTRO SCADA Incident/i }).click();

    // Verify textarea populated with SCADA Incident text
    await expect(textarea).toContainText('NATIONAL CRITICAL INFRASTRUCTURE DEFENCE');
    await expect(textarea).toContainText('APT-44');
    await expect(textarea).toContainText('CVE-2026-38910');

    // Switch to Upload tab and verify dropzone
    await page.getByRole('button', { name: /Upload Document/i }).click();
    await expect(page.getByText(/Drag & drop document here/i)).toBeVisible();

    // Switch back to Paste tab
    await page.getByRole('button', { name: /Paste Raw Text/i }).click();
    await expect(textarea).toBeVisible();
  });

  test('4. End-to-End Canonical Analysis, Multi-Output Generation & Traceability', async ({ page }) => {
    test.setTimeout(360_000); // Allow sufficient time for CPU-bound Ollama Qwen3:8B inference

    await page.goto('/');

    // 1. Ingest Sample
    await page.getByRole('button', { name: /Load Sample NTRO SCADA Incident/i }).click();

    // 2. Submit for Canonical Analysis
    const analyzeBtn = page.getByRole('button', { name: /Analyze & Extract Canonical Model/i });
    await analyzeBtn.click();

    // Verify loading indicator
    await expect(page.getByText(/Deconstructing Factual Model/i)).toBeVisible();

    // 3. Stage 2: Verify Canonical Structured Model Output
    await expect(page.getByText('Canonical Structured Understanding')).toBeVisible({ timeout: 180_000 });
    await expect(page.getByText('Primary Subject & Synthesis')).toBeVisible();
    await expect(page.getByText(/Extracted Facts with Provenance/i)).toBeVisible();
    await expect(page.getByText(/Forensic Source Inspector/i)).toBeVisible();

    // Verify provenance citations and interactive inspector
    const citationPills = page.locator('button.citation-pill');
    const pillCount = await citationPills.count();
    expect(pillCount).toBeGreaterThan(0);

    // Click first citation pill and verify inspector updates
    await citationPills.first().click();
    const activeChunkBadge = page.locator('.citation-pill-verified');
    await expect(activeChunkBadge).toBeVisible();

    // 4. Stage 3: Proceed to Configuration
    await page.getByRole('button', { name: /Proceed to Configure/i }).click();
    await expect(page.getByText('Configure Output Deliverables')).toBeVisible();

    // Test parameter controls
    const audienceSelect = page.locator('select').nth(0);
    await audienceSelect.selectOption('technical');
    expect(await audienceSelect.inputValue()).toBe('technical');

    const toneSelect = page.locator('select').nth(1);
    await toneSelect.selectOption('formal');
    expect(await toneSelect.inputValue()).toBe('formal');

    // Select Executive Summary deliverable only for test 4 to verify complete pipeline without multi-minute CPU timeouts
    for (const label of ['Advisory Brief', 'Public Communication', 'Presentation Outline']) {
      const checkbox = page.locator(`label:has-text("${label}") input[type="checkbox"]`);
      if (await checkbox.isChecked()) {
        await checkbox.click();
      }
    }

    // 5. Stage 4 & 5: Trigger Transformation
    const generateBtn = page.getByRole('button', { name: /Generate Selected Outputs/i });
    await generateBtn.click();

    // Verify Stage 4 loading telemetry
    await expect(page.getByText('Synthesizing Verified Artefacts')).toBeVisible();

    // Verify Stage 5 Review results
    await expect(page.getByText('Generated Communication Artefacts')).toBeVisible({ timeout: 180_000 });

    // Verify generated deliverable renders correctly
    const execTab = page.getByRole('button', { name: /Executive Summary/i });
    await expect(execTab).toBeVisible();
    await expect(page.getByText('Executive Briefing')).toBeVisible();
    await expect(page.getByText('Key Strategic Findings')).toBeVisible();
  });

  test('5. Responsive Viewport & Multi-Device Verification', async ({ page }) => {
    const targetViewports = [
      { name: '1920x1080 Desktop', width: 1920, height: 1080, isMobile: false },
      { name: '1366x768 Laptop', width: 1366, height: 768, isMobile: false },
      { name: '1024x768 Tablet Landscape', width: 1024, height: 768, isMobile: false },
      { name: '768x1024 Tablet Portrait', width: 768, height: 1024, isMobile: false },
      { name: '390x844 Mobile (iPhone 14)', width: 390, height: 844, isMobile: true },
      { name: '375x667 Mobile (iPhone SE/8)', width: 375, height: 667, isMobile: true },
      { name: '320x568 Small Mobile (iPhone 5)', width: 320, height: 568, isMobile: true },
    ];

    for (const vp of targetViewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/');

      // Check header branding visible
      await expect(page.getByText('Info2Impact', { exact: true })).toBeVisible();

      // Check textarea visible
      const textarea = page.locator('textarea');
      await expect(textarea).toBeVisible();

      // Check stepper adaptations
      if (!vp.isMobile) {
        await expect(page.locator('nav.stepper-nav')).toBeVisible();
      }

      // Check that there is NO horizontal page overflow
      const isOverflowing = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      expect(isOverflowing, `Horizontal overflow detected at ${vp.name} (${vp.width}x${vp.height})`).toBe(false);

      // Verify controls are usable and not clipped
      const sampleBtn = page.getByRole('button', { name: /Load Sample NTRO SCADA Incident/i });
      await expect(sampleBtn).toBeVisible();
      await sampleBtn.click();
      await expect(textarea).toContainText('NATIONAL CRITICAL INFRASTRUCTURE DEFENCE');

      const analyzeBtn = page.getByRole('button', { name: /Analyze & Extract Canonical Model/i });
      await expect(analyzeBtn).toBeVisible();
      await expect(analyzeBtn).toBeEnabled();
    }
  });
});

