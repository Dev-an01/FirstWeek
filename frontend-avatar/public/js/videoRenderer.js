/**
 * Video Renderer for Avatar Canvas
 * Renders base64 JPEG frames to canvas with high performance
 */

class VideoRenderer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) {
      throw new Error(`Canvas element with id "${canvasId}" not found`);
    }

    this.ctx = this.canvas.getContext('2d', {
      alpha: false, // Disable alpha for better performance
      desynchronized: true // Allow async rendering
    });

    this.frameCount = 0;
    this.lastFrameTime = 0;
    this.fps = 0;
    this.fpsCounter = { frames: 0, lastCheck: Date.now() };
    this.isRendering = false;
  }

  /**
   * Render a frame to canvas
   * Supports: Base64 string, Uint8Array (JPEG), or ImageBitmap
   * @param {string|Uint8Array|ImageBitmap} data - Frame data
   * @returns {Promise<void>}
   */
  async renderFrame(data) {
    if (!data) {
      return;
    }

    try {
      let imageSource = data;
      let shouldClose = false;

      // Handle Uint8Array (compressed JPEG from worker)
      if (data instanceof Uint8Array) {
        const blob = new Blob([data], { type: 'image/jpeg' });
        imageSource = await createImageBitmap(blob);
        shouldClose = true;
      }
      // Handle Base64 string (legacy/fallback)
      else if (typeof data === 'string') {
        const img = new Image();
        await new Promise((resolve, reject) => {
          img.onload = () => resolve(img);
          img.onerror = (error) => reject(error);
          img.src = 'data:image/jpeg;base64,' + data;
        });
        imageSource = img;
      }
      // Handle ImageBitmap (already decoded in worker)
      else if (data instanceof ImageBitmap) {
        imageSource = data;
        shouldClose = true;
      }

      // Clear canvas and draw image
      // Note: clearRect might not be needed if drawing full opaque image, but good for safety
      this.ctx.drawImage(imageSource, 0, 0, this.canvas.width, this.canvas.height);

      // Close bitmap to free memory immediately
      if (shouldClose && imageSource instanceof ImageBitmap) {
        imageSource.close();
      }

      // Update stats
      this.frameCount++;
      this.fpsCounter.frames++;
      this.lastFrameTime = Date.now();

      // Calculate FPS every second
      const now = Date.now();
      if (now - this.fpsCounter.lastCheck >= 1000) {
        this.fps = this.fpsCounter.frames;
        this.fpsCounter.frames = 0;
        this.fpsCounter.lastCheck = now;
      }

      // Mark as rendering
      if (!this.isRendering) {
        this.isRendering = true;
      }

    } catch (error) {
      console.error('[VideoRenderer] Failed to render frame:', error);
    }
  }

  /**
   * Clear the canvas
   */
  clear() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  /**
   * Show the canvas
   */
  show() {
    // Force display with inline styles AND class
    this.canvas.style.display = 'block';
    this.canvas.style.visibility = 'visible';
    this.canvas.style.opacity = '1';
    this.canvas.style.zIndex = '10';
    this.canvas.classList.add('active');

    // Hide the static avatar image
    const avatarImg = document.getElementById('avatar-img');
    if (avatarImg) {
      avatarImg.style.display = 'none';
      avatarImg.classList.add('hidden');
    }
  }

  /**
   * Hide the canvas
   */
  hide() {
    this.canvas.style.display = 'none';
    this.canvas.classList.remove('active');

    // Show the static avatar image
    const avatarImg = document.getElementById('avatar-img');
    if (avatarImg) {
      avatarImg.classList.remove('hidden');
    }
  }

  /**
   * Get rendering statistics
   */
  getStats() {
    return {
      frameCount: this.frameCount,
      fps: this.fps,
      lastFrameTime: this.lastFrameTime,
      isRendering: this.isRendering,
      timeSinceLastFrame: this.lastFrameTime ? Date.now() - this.lastFrameTime : null
    };
  }

  /**
   * Reset statistics
   */
  resetStats() {
    this.frameCount = 0;
    this.fps = 0;
    this.fpsCounter = { frames: 0, lastCheck: Date.now() };
  }
}

// Export for use in other scripts
window.VideoRenderer = VideoRenderer;
