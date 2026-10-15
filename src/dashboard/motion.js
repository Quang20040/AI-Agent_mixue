/* Continuous Mixue motion, scoped to branded elements. */
(() => {
  if (!window.gsap) return;
  if (window.mixueMotion?.version === 2) { window.mixueMotion.scan(); return; }
  window.mixueMotion?.destroy?.();
  const gsap = window.gsap;
  gsap.registerPlugin(window.ScrollTrigger);
  const active = new Map();
  const controls = new Map();
  const fine = window.matchMedia('(hover: hover) and (pointer: fine)');
  // Continuous motion is the user's explicit preference; pause remains available.
  let enabled = true;
  document.documentElement.dataset.mixueMotion = 'running';
  document.documentElement.classList.add('mixue-motion-active');
  function syncControls() {
    controls.forEach((fn, button) => {if (!button.isConnected) {button.removeEventListener('click', fn); controls.delete(button);}});
    document.querySelectorAll('.stage-motion-toggle').forEach(button => {
      const label = enabled ? 'Tạm dừng hiệu ứng' : 'Bật chuyển động';
      if (button.textContent !== label) button.textContent = label;
      button.setAttribute('aria-pressed', String(enabled));
      if (controls.has(button)) return;
      const toggle = () => {
        enabled = !enabled;
        document.documentElement.dataset.mixueMotion = enabled ? 'running' : 'paused';
        document.documentElement.classList.toggle('mixue-motion-paused', !enabled);
        document.documentElement.classList.toggle('mixue-motion-active', enabled);
        scan();
      };
      button.addEventListener('click', toggle);
      controls.set(button, toggle);
    });
  }
  function bind(node) {
    if (active.has(node) || !enabled) return;
    const cleanups = [];
    const loops = [];
    const context = gsap.context(() => {
      const loop = (target, vars) => {
        if (!target || (target.length !== undefined && !target.length)) return;
        loops.push(gsap.to(target, {repeat: -1, yoyo: true, ease: 'sine.inOut', ...vars}));
      };
      if (node.matches('.mixue-stage')) {
        gsap.timeline({defaults: {ease: 'power3.out'}})
          .from(node.querySelectorAll('.stage-copy > *'), {y: 24, opacity: 0, stagger: .08, duration: .75})
          .from(node.querySelectorAll('.photo-card'), {y: 60, rotationY: -18, opacity: 0, stagger: .16, duration: 1}, .15);
        node.querySelectorAll('.photo-card').forEach((photo, index) => {
          loop(photo, {y: index ? -17 : 15, rotationZ: index ? -3 : 3, duration: 2.5 + index * .6, delay: 1.2});
          loop(photo.querySelector('img'), {scale: 1.08, duration: 4.5, delay: index});
        });
        loop(node.querySelector('.stage-stamp'), {rotationY: 22, rotationZ: -14, y: -14, scale: 1.06, duration: 2.5, transformPerspective: 650});
        loop(node.querySelector('.stage-mascot img'), {y: -16, rotationZ: 9, rotationY: -15, scale: 1.09, duration: 1.6, transformPerspective: 600});
        loop(node.querySelector('.gallery-word'), {x: -18, opacity: .55, duration: 4});
        loop(node.querySelectorAll('.stage-orbit'), {scale: 1.17, x: 30, y: 16, duration: 6, stagger: 1});
        loop(node.querySelector('.stage-copy h1 em'), {textShadow: '0px 5px 0px rgba(110,0,25,.4)', duration: 2.1});
        node.querySelectorAll('.stage-sparkles i').forEach((spark, i) => {
          loop(spark, {y: -24 - i * 3, x: i % 2 ? 13 : -13, rotation: 90, scale: 1.5, opacity: .95, duration: 1.6 + i * .17, delay: i * .22});
        });
        const scroller = document.querySelector('[data-testid="stAppViewContainer"]');
        if (scroller && window.ScrollTrigger) {
          gsap.to(node.querySelector('.stage-gallery'), {y: 35, ease: 'none', scrollTrigger: {trigger: node, scroller, start: 'top top', end: 'bottom top', scrub: 1}});
        }
      } else if (node.matches('.menu-card')) {
        gsap.from(node.querySelector('.menu-copy'), {y: 12, opacity: 0, duration: .5});
        loop(node.querySelector('.menu-photo img'), {y: -6, rotationZ: 1.8, scale: 1.075, duration: 2.2 + Math.random() * .8});
        loop(node.querySelector('.product-halo'), {opacity: .7, scale: 1.3, duration: 1.8});
        loop(node.querySelector('.product-shine'), {xPercent: 480, duration: 3, repeatDelay: 1, yoyo: false, ease: 'power1.inOut'});
        loop(node.querySelector('.menu-arrow'), {rotationY: 25, y: -3, duration: 1.5, transformPerspective: 300});
      } else if (node.matches('.snowking-authentic, .brand-logo')) {
        const image = node.matches('img') ? node : node.querySelector('img');
        loop(image, {y: -5, rotationZ: 7, rotationY: 15, duration: 1.3, transformPerspective: 500});
      } else if (node.matches('.mixue-ribbon')) {
        loops.push(gsap.to(node.querySelector('div'), {xPercent: -50, duration: 24, repeat: -1, ease: 'none'}));
      }
      const targets = node.matches('[data-tilt]') ? [node] : node.querySelectorAll('[data-tilt]');
      targets.forEach(target => {
        const move = event => {
          if (!fine.matches || !enabled) return;
          const box = target.getBoundingClientRect();
          gsap.to(target, {rotationX: -(event.clientY - box.top - box.height / 2) / box.height * 14,
            rotationY: (event.clientX - box.left - box.width / 2) / box.width * 18,
            transformPerspective: 850, duration: .35, ease: 'power2.out', overwrite: 'auto'});
        };
        const reset = () => gsap.to(target, {rotationX: 0, rotationY: 0, duration: .65, overwrite: 'auto'});
        target.addEventListener('pointermove', move);
        target.addEventListener('pointerleave', reset);
        cleanups.push(() => {target.removeEventListener('pointermove', move); target.removeEventListener('pointerleave', reset); gsap.killTweensOf(target);});
      });
    }, node);
    const visibility = new IntersectionObserver(entries => entries.forEach(entry => {
      loops.forEach(animation => entry.isIntersecting ? animation.resume() : animation.pause());
    }), {rootMargin: '80px'});
    visibility.observe(node);
    active.set(node, () => {visibility.disconnect(); cleanups.forEach(fn => fn()); context.revert();});
  }
  function scan() {
    syncControls();
    active.forEach((cleanup, node) => {if (!node.isConnected || !enabled) {cleanup(); active.delete(node);}});
    document.querySelectorAll('.mixue-stage, .menu-card, .snowking-authentic, .brand-logo, .mixue-ribbon').forEach(bind);
  }
  let scheduled = false;
  const observer = new MutationObserver(() => {
    if (!scheduled) {scheduled = true; requestAnimationFrame(() => {scheduled = false; scan();});}
  });
  observer.observe(document.body, {childList: true, subtree: true});
  window.mixueMotion = {version: 2, scan, destroy() {
    observer.disconnect(); active.forEach(cleanup => cleanup()); active.clear();
    controls.forEach((fn, button) => button.removeEventListener('click', fn)); controls.clear();
  }};
  scan();
})();
