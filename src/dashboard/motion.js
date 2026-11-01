/* Continuous Mixue motion, scoped to branded elements. */
(() => {
  if (!window.gsap) return;
  if (window.mixueMotion?.version === 5) { window.mixueMotion.scan(); return; }
  window.mixueMotion?.destroy?.();
  const gsap = window.gsap;
  gsap.registerPlugin(window.ScrollTrigger);
  const active = new Map();
  const controls = new Map();
  const fine = window.matchMedia('(hover: hover) and (pointer: fine)');
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  // Continuous motion is the user's explicit preference; pause remains available.
  let enabled = !reduce.matches;
  document.documentElement.dataset.mixueMotion = enabled ? 'running' : 'paused';
  document.documentElement.classList.toggle('mixue-motion-active', enabled);
  document.documentElement.classList.toggle('mixue-motion-paused', !enabled);
  function syncControls() {
    controls.forEach((fn, button) => {if (!button.isConnected) {button.removeEventListener('click', fn); controls.delete(button);}});
    document.querySelectorAll('.stage-motion-toggle').forEach(button => {
      const label = enabled ? 'Tạm dừng hiệu ứng' : 'Bật chuyển động';
      if (button.textContent !== label) button.textContent = label;
      button.setAttribute('aria-pressed', String(enabled));
      if (controls.has(button)) return;
      const toggle = () => {
        enabled = !enabled;
        document.documentElement.classList.toggle('mixue-motion-user-enabled', enabled);
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
      if (node.matches('.mx-hero')) {
        gsap.timeline({defaults: {ease: 'power3.out'}})
          .from(node.querySelectorAll('.mx-hero-copy > *'), {y: 18, opacity: 0, stagger: .07, duration: .7})
          .from(node.querySelector('.mx-hero-art'), {x: 35, rotationY: -20, opacity: 0, duration: .9}, .1);
        loop(node.querySelector('.mx-bubble'), {y: -5, rotationZ: -2, duration: 3.4});
        loop(node.querySelector('.mx-hero-drink'), {y: -9, rotationZ: -7, rotationY: 10, duration: 3, transformPerspective: 700});
        loop(node.querySelectorAll('.mx-orbit'), {scale: 1.12, x: -8, duration: 5, stagger: 1});
        node.querySelectorAll('.mx-spark').forEach((spark, index) => loop(spark, {y: -8, rotationZ: 20, scale: 1.2, duration: 2 + index * .5}));
      } else if (node.matches('.mx-card, .mx-kpi')) {
        // Reveal only when the panel enters view; leave content readable without JS.
        const reveal = new IntersectionObserver(entries => entries.forEach(entry => {
          if (!entry.isIntersecting) return;
          context.add(() => {
            gsap.from(node, {y: 18, rotationX: 5, transformPerspective: 1100, opacity: 0, duration: .65, ease: 'power3.out', clearProps: 'opacity,transform'});
            if (node.matches('.mx-revenue')) gsap.from(node.querySelectorAll('.mx-bar i'), {scaleY: .05, stagger: .045, duration: .8, ease: 'power2.out'});
          });
          reveal.disconnect();
        }), {threshold: .08});
        reveal.observe(node);
        cleanups.push(() => reveal.disconnect());
      } else if (node.matches('.mixue-stage')) {
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
      } else if (node.matches('.px-greet')) {
        // Greeting band: copy cascades in, Tuyết Vương pops up, then floats and snow drifts.
        gsap.timeline({defaults: {ease: 'power3.out'}})
          .from(node.querySelectorAll('.px-greet-copy > *, .px-greet-tasks .px-link'), {y: 16, opacity: 0, stagger: .06, duration: .6, clearProps: 'opacity,transform'})
          .from(node.querySelector('.px-mascot'), {y: 40, scale: .7, rotationZ: -8, opacity: 0, duration: .8, ease: 'back.out(1.8)'}, .15)
          .from(node.querySelector('.px-bubble'), {scale: .6, opacity: 0, transformOrigin: '90% 100%', duration: .5, ease: 'back.out(2)'}, .55);
        loop(node.querySelector('.px-mascot'), {y: -10, rotationZ: 4, duration: 2.2, delay: 1});
        loop(node.querySelector('.px-bubble'), {y: -4, duration: 2.8, delay: 1.2});
        node.querySelectorAll('.px-flake').forEach((flake, i) => loop(flake, {y: 14 + i * 3, x: i % 2 ? 8 : -8, rotation: 120, opacity: .9, duration: 2.4 + i * .35, delay: i * .2}));
      } else if (node.matches('.px-pillar')) {
        const reveal = new IntersectionObserver(entries => entries.forEach(entry => {
          if (!entry.isIntersecting) return;
          context.add(() => {
            gsap.from(node.querySelectorAll('.px-pillar-head, .px-stat, .px-chain, p'), {y: 14, opacity: 0, stagger: .06, duration: .55, ease: 'power3.out', clearProps: 'opacity,transform'});
            node.querySelectorAll('[data-count]').forEach(el => {
              const end = Number(el.dataset.count);
              if (!Number.isFinite(end) || end <= 0) return;
              const box = {v: 0};
              gsap.to(box, {v: end, duration: 1.1, ease: 'power2.out', onUpdate: () => {el.textContent = Math.round(box.v).toLocaleString('vi-VN');}});
            });
          });
          reveal.disconnect();
        }), {threshold: .1});
        reveal.observe(node);
        cleanups.push(() => reveal.disconnect());
        loop(node.querySelector('.px-pillar-icon'), {y: -4, rotationZ: -6, duration: 1.8});
        const nodes = node.querySelectorAll('.px-chain .px-node');
        if (nodes.length) {
          // A request "travels" through guard → model → authorize → tools → approval.
          const travel = gsap.timeline({repeat: -1, repeatDelay: .8});
          nodes.forEach(item => travel.to(item, {backgroundColor: '#e60012', color: '#fff', scale: 1.08, duration: .28, ease: 'power2.out'})
            .to(item, {backgroundColor: '', color: '', scale: 1, duration: .4, ease: 'power2.in', clearProps: 'backgroundColor,color,transform'}, '+=.15'));
          loops.push(travel);
        }
      } else if (node.matches('.vocr-steps')) {
        gsap.from(node.querySelectorAll('.vocr-step'), {x: -14, opacity: 0, stagger: .08, duration: .5, ease: 'power3.out', clearProps: 'opacity,transform'});
      } else if (node.matches('.px-rail')) {
        gsap.from(node.querySelectorAll('.px-rail-card'), {x: 18, opacity: 0, stagger: .1, duration: .55, ease: 'power3.out', clearProps: 'opacity,transform'});
        gsap.from(node.querySelectorAll('.px-trace li'), {x: 10, opacity: 0, stagger: .07, duration: .4, delay: .2, clearProps: 'opacity,transform'});
      } else if (node.matches('.mixue-ribbon')) {
        loops.push(gsap.to(node.querySelector('div'), {xPercent: -50, duration: 24, repeat: -1, ease: 'none'}));
      }
      const targets = node.matches('[data-tilt], .st-key-login_shell') ? [node] : node.querySelectorAll('[data-tilt]');
      targets.forEach(target => {
        const move = event => {
          if (!fine.matches || !enabled || target.matches(':focus-within')) return;
          const box = target.getBoundingClientRect();
          const subtle = node.matches('.st-key-login_shell, .mx-kpi');
          gsap.to(target, {rotationX: -(event.clientY - box.top - box.height / 2) / box.height * (subtle ? 4 : 14),
            rotationY: (event.clientX - box.left - box.width / 2) / box.width * (subtle ? 6 : 18),
            transformPerspective: 850, duration: .35, ease: 'power2.out', overwrite: 'auto'});
        };
        const reset = () => gsap.to(target, {rotationX: 0, rotationY: 0, duration: .65, overwrite: 'auto'});
        target.addEventListener('pointermove', move);
        target.addEventListener('pointerleave', reset);
        target.addEventListener('focusin', reset);
        cleanups.push(() => {target.removeEventListener('pointermove', move); target.removeEventListener('pointerleave', reset); target.removeEventListener('focusin', reset); gsap.killTweensOf(target);});
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
    document.querySelectorAll('.mx-hero, .mx-card, .mx-kpi, .mixue-stage, .menu-card, .snowking-authentic, .brand-logo, .mixue-ribbon, .st-key-login_shell, .px-greet, .px-pillar, .vocr-steps, .px-rail').forEach(bind);
  }
  // Native dialog provides focus trapping, Escape and an accessible search.
  const normalize = value => value.toLocaleLowerCase('vi').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd');
  const openSearch = () => {
    const dialog = document.querySelector('.mx-command');
    if (!dialog || dialog.open) return;
    dialog.showModal();
    dialog.querySelector('input')?.focus();
  };
  const click = event => {
    if (event.target.closest('[data-command-open]')) openSearch();
    if (event.target.closest('[data-command-close]')) event.target.closest('dialog')?.close();
    const action = event.target.closest('[data-command-page]');
    if (!action) return;
    const target = action.dataset.commandPage.trim();
    const option = [...document.querySelectorAll('.st-key-main_navigation label')].find(label => label.textContent.trim() === target);
    if (option) {
      document.querySelector('.mx-command[open]')?.close();
      option.click();
    }
  };
  const search = event => {
    if (!event.target.matches('.mx-command input')) return;
    const dialog = event.target.closest('dialog');
    const query = normalize(event.target.value);
    let visible = 0;
    dialog.querySelectorAll('[data-command-page]').forEach(button => {
      button.hidden = !normalize(button.dataset.commandPage).includes(query);
      if (!button.hidden) visible++;
    });
    dialog.querySelector('.mx-command-empty').hidden = Boolean(visible);
  };
  const keydown = event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k' && document.querySelector('.mx-command')) {event.preventDefault(); openSearch();}
    if (event.key === 'Enter' && event.target.matches('.mx-command input')) {event.preventDefault(); event.target.closest('dialog').querySelector('[data-command-page]:not([hidden])')?.click();}
  };
  const preference = event => {
    enabled = !event.matches;
    document.documentElement.dataset.mixueMotion = enabled ? 'running' : 'paused';
    document.documentElement.classList.toggle('mixue-motion-paused', !enabled);
    document.documentElement.classList.toggle('mixue-motion-active', enabled);
    document.documentElement.classList.remove('mixue-motion-user-enabled');
    scan();
  };
  document.addEventListener('click', click);
  document.addEventListener('input', search);
  document.addEventListener('keydown', keydown);
  reduce.addEventListener('change', preference);
  let scheduled = false;
  const observer = new MutationObserver(() => {
    if (!scheduled) {scheduled = true; requestAnimationFrame(() => {scheduled = false; scan();});}
  });
  observer.observe(document.body, {childList: true, subtree: true});
  window.mixueMotion = {version: 5, scan, destroy() {
    observer.disconnect(); active.forEach(cleanup => cleanup()); active.clear();
    controls.forEach((fn, button) => button.removeEventListener('click', fn)); controls.clear();
    document.removeEventListener('click', click); document.removeEventListener('input', search); document.removeEventListener('keydown', keydown);
    reduce.removeEventListener('change', preference);
  }};
  scan();
})();
