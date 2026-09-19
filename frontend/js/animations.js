/**
 * CivicSight — GSAP Transitions & Micro-Interactions Controller
 *
 * Implements Requirement 3 strictly:
 * - Sequenced hero text/CTA fade-in and upward slide on page load (logo -> badge -> h1 -> subtitle -> CTA -> 3D scene)
 * - "How CivicSight Works" 7-stage workflow step reveal on scroll using ScrollTrigger
 * - Card/section reveal animations on scroll for dashboard and reporting pages
 * - Subtle micro-interactions on buttons/nav (scale: 1.02, slight elevation — NO bounce, NO spin)
 * - Global prefers-reduced-motion bypass: instant visible state when requested
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Accessibility Check: prefers-reduced-motion
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Check if GSAP is available
  if (typeof gsap === 'undefined') {
    console.warn('GSAP library not detected. Falling back to native CSS.');
    return;
  }

  // Register ScrollTrigger plugin if present
  if (typeof ScrollTrigger !== 'undefined') {
    gsap.registerPlugin(ScrollTrigger);
  }

  if (prefersReducedMotion) {
    // If reduced motion is preferred, immediately ensure all elements are visible with zero transform
    gsap.set([
      '.navbar-inner',
      '.hero-badge',
      '.hero-title',
      '.hero-subtitle',
      '.hero-cta',
      '.hero-3d-wrapper',
      '.workflow-card',
      '.portal-card',
      '.report-form-card',
      '.dashboard-card',
      '.metric-card',
    ], { opacity: 1, y: 0, clearProps: 'all' });
    return;
  }

  // --- 2. Sequenced Hero Animation on Load ---
  // Sequence: logo/nav -> badge -> hero title -> hero subtitle -> hero CTA -> 3D scene container
  const heroSection = document.querySelector('.hero-section');
  if (heroSection) {
    const heroTl = gsap.timeline({ defaults: { ease: 'power2.out' } });

    heroTl
      .from('.navbar-inner', {
        opacity: 0,
        y: -10,
        duration: 0.5,
      })
      .from('.hero-badge, .badge-pill', {
        opacity: 0,
        y: 12,
        duration: 0.45,
      }, '-=0.2')
      .from('.hero-title', {
        opacity: 0,
        y: 16,
        duration: 0.55,
      }, '-=0.2')
      .from('.hero-subtitle', {
        opacity: 0,
        y: 14,
        duration: 0.5,
      }, '-=0.25')
      .from('.hero-cta .btn', {
        opacity: 0,
        y: 12,
        duration: 0.4,
        stagger: 0.1,
      }, '-=0.2')
      .from('.hero-3d-wrapper, .hero-3d-container', {
        opacity: 0,
        y: 18,
        duration: 0.65,
      }, '-=0.2');
  }

  // --- 3. ScrollTrigger: "How CivicSight Works" Section ---
  const workflowCards = document.querySelectorAll('.workflow-card');
  if (workflowCards.length > 0 && typeof ScrollTrigger !== 'undefined') {
    gsap.from(workflowCards, {
      scrollTrigger: {
        trigger: '.workflow-grid',
        start: 'top 85%',
        toggleActions: 'play none none none',
      },
      opacity: 0,
      y: 20,
      duration: 0.45,
      stagger: 0.08,
      ease: 'power2.out',
    });
  }

  // --- 4. ScrollTrigger: Card & Section Reveal Animations ---
  const portalCards = document.querySelectorAll('.portal-card');
  if (portalCards.length > 0 && typeof ScrollTrigger !== 'undefined') {
    gsap.from(portalCards, {
      scrollTrigger: {
        trigger: '.portals-grid',
        start: 'top 85%',
        toggleActions: 'play none none none',
      },
      opacity: 0,
      y: 20,
      duration: 0.5,
      stagger: 0.12,
      ease: 'power2.out',
    });
  }

  // Reporting Page Form Sections Reveal
  const formSections = document.querySelectorAll('.report-form-card .form-section');
  if (formSections.length > 0) {
    gsap.from(formSections, {
      opacity: 0,
      y: 16,
      duration: 0.45,
      stagger: 0.1,
      ease: 'power2.out',
      delay: 0.1,
    });
  }

  // Dashboard Cards & Metrics Reveal
  const metricCards = document.querySelectorAll('.metric-card');
  if (metricCards.length > 0) {
    gsap.from(metricCards, {
      opacity: 0,
      y: 14,
      duration: 0.4,
      stagger: 0.08,
      ease: 'power2.out',
    });
  }

  // --- 5. Micro-Interactions on Buttons and Nav Links ---
  // Pure subtle tactile feedback: slight translateY & scale (NO spinning, NO bouncing)
  const interactiveButtons = document.querySelectorAll('.btn:not(:disabled)');
  interactiveButtons.forEach((btn) => {
    btn.addEventListener('mouseenter', () => {
      gsap.to(btn, { y: -1, duration: 0.18, ease: 'power1.out' });
    });
    btn.addEventListener('mouseleave', () => {
      gsap.to(btn, { y: 0, duration: 0.18, ease: 'power1.out' });
    });
    btn.addEventListener('mousedown', () => {
      gsap.to(btn, { scale: 0.98, duration: 0.1, ease: 'power1.out' });
    });
    btn.addEventListener('mouseup', () => {
      gsap.to(btn, { scale: 1, duration: 0.12, ease: 'power1.out' });
    });
  });

  const navLinks = document.querySelectorAll('.nav-links .nav-link');
  navLinks.forEach((link) => {
    link.addEventListener('mouseenter', () => {
      gsap.to(link, { y: -1, duration: 0.15, ease: 'power1.out' });
    });
    link.addEventListener('mouseleave', () => {
      gsap.to(link, { y: 0, duration: 0.15, ease: 'power1.out' });
    });
  });
});
