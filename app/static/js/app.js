// Helper fetch + CSRF. TODO(Copilot): sesuaikan respons JSON {ok,data,error} dari backend.
const csrf = () => document.querySelector('meta[name=csrf-token]')?.content || '';
document.documentElement.classList.add('js-motion');

async function api(method, url, body) {
  const r = await fetch(url, {method, headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}, body: body ? JSON.stringify(body) : undefined});
  const j = await r.json().catch(() => ({ok: false, error: {message: 'Respons tidak valid'}}));
  if (!r.ok || j.ok === false) throw new Error(j.error?.message || 'Terjadi kesalahan');
  return j;
}

function toast(msg) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.setAttribute('role', 'status');
  t.setAttribute('aria-live', 'polite');
  t.textContent = msg;
  document.body.append(t);
  setTimeout(() => t.remove(), 2800);
}

const revealItems = document.querySelectorAll('.reveal');
if ('IntersectionObserver' in window) {
  const revealObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, {threshold: 0.12});
  revealItems.forEach(item => {
    revealObserver.observe(item);
    const bounds = item.getBoundingClientRect();
    if (bounds.bottom > 0 && bounds.top < window.innerHeight) {
      item.classList.add('is-visible');
    }
  });
} else {
  revealItems.forEach(item => item.classList.add('is-visible'));
}

const hero = document.querySelector('.home-hero');
const cursorGlow = hero?.querySelector('.hero-cursor-glow');
const supportsFinePointerMotion = window.matchMedia('(pointer: fine)').matches
  && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
if (hero && cursorGlow && supportsFinePointerMotion) {
  let pointerX = 0;
  let pointerY = 0;
  let animationFrame = 0;

  hero.addEventListener('pointermove', event => {
    const bounds = hero.getBoundingClientRect();
    pointerX = event.clientX - bounds.left;
    pointerY = event.clientY - bounds.top;

    if (!animationFrame) {
      animationFrame = window.requestAnimationFrame(() => {
        cursorGlow.style.left = `${pointerX}px`;
        cursorGlow.style.top = `${pointerY}px`;
        hero.classList.add('has-cursor-glow');
        animationFrame = 0;
      });
    }
  });
  hero.addEventListener('pointerleave', () => {
    if (animationFrame) window.cancelAnimationFrame(animationFrame);
    animationFrame = 0;
    hero.classList.remove('has-cursor-glow');
  });
}

if (supportsFinePointerMotion) {
  document.querySelectorAll('.storefront-body .pc').forEach(card => {
    let pointerX = 0;
    let pointerY = 0;
    let tiltX = 0;
    let tiltY = 0;
    let animationFrame = 0;

    card.addEventListener('pointermove', event => {
      const bounds = card.getBoundingClientRect();
      pointerX = ((event.clientX - bounds.left) / bounds.width) * 100;
      pointerY = ((event.clientY - bounds.top) / bounds.height) * 100;
      tiltX = (((event.clientX - bounds.left) / bounds.width) - 0.5) * 4;
      tiltY = (0.5 - ((event.clientY - bounds.top) / bounds.height)) * 4;

      if (!animationFrame) {
        animationFrame = window.requestAnimationFrame(() => {
          card.style.setProperty('--pointer-x', `${pointerX}%`);
          card.style.setProperty('--pointer-y', `${pointerY}%`);
          card.style.setProperty('--tilt-x', `${tiltX.toFixed(2)}deg`);
          card.style.setProperty('--tilt-y', `${tiltY.toFixed(2)}deg`);
          card.classList.add('is-pointer-active');
          animationFrame = 0;
        });
      }
    });

    card.addEventListener('pointerleave', () => {
      if (animationFrame) window.cancelAnimationFrame(animationFrame);
      animationFrame = 0;
      card.classList.remove('is-pointer-active');
      card.style.removeProperty('--pointer-x');
      card.style.removeProperty('--pointer-y');
      card.style.removeProperty('--tilt-x');
      card.style.removeProperty('--tilt-y');
    });
  });
}

const homeDiscovery = document.querySelector('[data-home-discovery]');
if (homeDiscovery) {
  const filterControls = homeDiscovery.querySelector('[data-home-filter-controls]');
  const filterButtons = homeDiscovery.querySelectorAll('[data-home-filter]');
  const productCards = homeDiscovery.querySelectorAll('.pc[data-category]');
  const filterStatus = homeDiscovery.querySelector('[data-home-filter-status]');

  if (filterControls && filterButtons.length && productCards.length) {
    filterControls.hidden = false;
    productCards.forEach(card => {
      card.addEventListener('animationend', event => {
        if (event.animationName === 'home-filter-reveal') card.classList.remove('home-filter-enter');
      });
    });

    filterButtons.forEach(button => {
      button.addEventListener('click', () => {
        const filter = button.dataset.homeFilter;
        let visibleCount = 0;

        productCards.forEach(card => {
          const matches = filter === 'all' || card.dataset.category === filter;
          const wasHidden = card.hidden;
          card.hidden = !matches;
          if (matches) {
            card.style.setProperty('--filter-order', visibleCount);
            if (wasHidden && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
              card.classList.remove('home-filter-enter');
              window.requestAnimationFrame(() => {
                if (!card.hidden) card.classList.add('home-filter-enter');
              });
            }
            visibleCount += 1;
          } else {
            card.classList.remove('home-filter-enter');
          }
        });

        filterButtons.forEach(filterButton => {
          const isActive = filterButton === button;
          filterButton.classList.toggle('is-active', isActive);
          filterButton.setAttribute('aria-pressed', String(isActive));
        });

        if (filterStatus) {
          filterStatus.textContent = filter === 'all'
            ? `${visibleCount} produk ditampilkan`
            : `${visibleCount} produk dalam kategori ${button.dataset.homeFilterLabel}`;
        }
      });
    });
  }
}

document.querySelectorAll('[data-popular-close]').forEach(button => {
  button.addEventListener('click', () => {
    const recommendations = button.closest('[data-popular-float]');
    if (recommendations) recommendations.open = false;
  });
});

const scrollTopButton = document.querySelector('.scroll-top');
if (scrollTopButton) {
  const updateScrollButton = () => {
    scrollTopButton.hidden = window.scrollY < 450;
  };
  window.addEventListener('scroll', updateScrollButton, {passive: true});
  scrollTopButton.addEventListener('click', () => window.scrollTo({top: 0, behavior: 'smooth'}));
  updateScrollButton();
}

const orderFilterButtons = document.querySelectorAll('[data-order-filter]');
if (orderFilterButtons.length) {
  const orderCards = document.querySelectorAll('[data-order-status]');
  const emptyFilterState = document.querySelector('#orders-filter-empty');
  orderFilterButtons.forEach(button => {
    button.addEventListener('click', () => {
      const filter = button.dataset.orderFilter;
      let visibleCount = 0;
      orderCards.forEach(card => {
        const status = card.dataset.orderStatus;
        const matches = filter === 'all'
          || (filter === 'active' && !['completed', 'cancelled'].includes(status))
          || status === filter;
        card.hidden = !matches;
        if (matches) visibleCount += 1;
      });
      orderFilterButtons.forEach(filterButton => {
        const isActive = filterButton === button;
        filterButton.classList.toggle('is-active', isActive);
        filterButton.setAttribute('aria-pressed', String(isActive));
      });
      if (emptyFilterState) emptyFilterState.hidden = visibleCount > 0;
    });
  });
}

const checkoutForm = document.querySelector('[data-checkout]');
if (checkoutForm) {
  const deliveryFeeDisplay = checkoutForm.querySelector('#checkout-delivery-fee');
  const totalDisplay = checkoutForm.querySelector('#checkout-total');
  const subtotal = Number(checkoutForm.dataset.subtotal);
  const deliveryFee = Number(checkoutForm.dataset.deliveryFee);
  const formatPrice = amount => `Rp ${amount.toLocaleString('id-ID')}`;
  const updateCheckoutTotal = () => {
    const isDelivery = checkoutForm.querySelector('input[name="fulfillment_method"]:checked')?.value === 'delivery';
    const fee = isDelivery ? deliveryFee : 0;
    deliveryFeeDisplay.textContent = formatPrice(fee);
    totalDisplay.textContent = formatPrice(subtotal + fee);
  };

  checkoutForm.querySelectorAll('input[name="fulfillment_method"]').forEach(input => {
    input.addEventListener('change', updateCheckoutTotal);
  });
  updateCheckoutTotal();
}

document.addEventListener('click', async e => {
  const b = e.target.closest('[data-act]'); if (!b) return;
  if (b.disabled) return;
  b.disabled = true;
  try {
    if (b.dataset.act === 'add') { await api('POST', '/cart/items', {product_id: b.dataset.id, quantity: 1}); toast('Masuk keranjang'); }
    if (b.dataset.act === 'qty') { await api('PATCH', '/cart/items/' + b.dataset.id, {quantity: +b.dataset.q}); location.reload(); }
    if (b.dataset.act === 'del') { await api('DELETE', '/cart/items/' + b.dataset.id); location.reload(); }
    if (b.dataset.act === 'wish') { await api('POST', '/wishlist/items', {product_id: b.dataset.id}); toast('Disimpan ke wishlist'); }
  } catch (err) {
    toast(err.message);
  } finally {
    b.disabled = false;
  }
});
