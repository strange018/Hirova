// Screenshot capture is entirely disabled.
// To re-enable, restore the original implementation from git history.

const InterviewScreenshotCapture = () => {
  // ── Screenshot capture disabled ──────────────────────────────────────────
  // Original flow:
  //   1. captureScreenshot()  – MediaDevices API → fallback html2canvas
  //   2. uploadToPinata()     – POST blob to Pinata IPFS
  //   3. sendToDatabase()     – POST imageUrl to /api/interview/interview-images/{sessionId}/
  //
  // Triggered once via useEffect on mount (hasStarted guard).
  // ─────────────────────────────────────────────────────────────────────────

  return null;
};

export default InterviewScreenshotCapture;